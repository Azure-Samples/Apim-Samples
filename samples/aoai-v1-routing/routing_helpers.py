"""Configuration and sanitized live-probe mechanics for Azure OpenAI v1 Routing.

Autoreload: reload_conditional
Recompute configuration and recreate probe results after changing their schemas.
"""

import json
import re
import time
import warnings
from bisect import bisect_right
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from math import ceil, isfinite
from typing import Any, Literal, TypedDict
from urllib.parse import urlsplit

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from matplotlib.text import Annotation
from matplotlib.textpath import TextPath
from matplotlib.transforms import ScaledTranslation, blended_transform_factory

# APIM Samples imports
from ai_models import ApprovedModel
from aoai_models import to_deployment_config
from apimrequests import ApimRequests


class ModelConfiguration(TypedDict):
    """The same deployment identity is installed on every account."""

    name: str
    version: str
    capacity: int
    deploymentName: str


@dataclass(frozen = True)
class ProbeResult:
    """Evidence of generated text from either pathway, without retaining its content."""

    status: int
    error_code: str | None
    error_message: str | None
    completion: bool
    pool: str
    request_id: str
    backend_host: str = ''
    retry_after_seconds: int = 0


@dataclass(frozen = True, kw_only = True)
class TimedProbeResult(ProbeResult):
    """Include timing without changing the existing probe schema on notebook reload."""

    response_time_seconds: float


@dataclass(frozen = True)
class CapacityEvidence:
    """Keep ordered, sanitized evidence without treating an unobserved failure as a pass."""

    baseline: ProbeResult
    pressure: tuple[ProbeResult, ...]
    recovery: ProbeResult
    fallback_served: bool
    exhausted: bool
    recovery_wait_seconds: float
    stop_reason: Literal['request-limit', 'time-limit', 'exhausted'] = 'request-limit'
    elapsed_seconds: float = 0


@dataclass(frozen = True, kw_only = True)
class TimedCapacityEvidence(CapacityEvidence):
    """Retain response-observation times without changing older evidence on reload."""

    observation_times_seconds: tuple[float, ...]


def build_models(sample_name: str, models: Sequence[ApprovedModel], sku: str, capacity: int) -> list[ModelConfiguration]:
    """Validate PAYG configuration and keep model selectors equal to deployment names."""
    if not isinstance(sample_name, str) or not re.fullmatch(r'aoai-v1-routing-[a-z0-9-]{1,16}', sample_name):
        raise ValueError('Use aoai-v1-routing- plus 1-16 lowercase letters, digits or hyphens.')
    if sku not in ('Standard', 'GlobalStandard'):
        raise ValueError('Only Standard and GlobalStandard PAYG deployments are permitted.')
    if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
        raise ValueError('Capacity must be a positive integer.')
    if not models or any(not isinstance(model, ApprovedModel) or model.value.provider != 'openai' for model in models):
        raise ValueError('Select at least one approved OpenAI model.')
    names = [model.model_name for model in models]
    if len(set(names)) != len(names) or any(not re.fullmatch(r'[a-z0-9][a-z0-9.-]{0,47}', name) for name in names):
        raise ValueError('Deployment names must be distinct bounded lowercase aliases.')
    if any(len(f'{sample_name}-{name}-global-standard') > 80 for name in names):
        raise ValueError('The namespace and model name exceed the backend resource name budget.')

    return [{**to_deployment_config(model, capacity), 'deploymentName': model.model_name} for model in models]


def subscription_key(apis: Sequence[dict[str, Any]], api_name: str) -> str:
    """Select a shared API-module subscription without printing its key."""
    matches = [api for api in apis if api.get('name') == api_name]
    if len(matches) != 1 or not isinstance(matches[0].get('subscriptionPrimaryKey'), str) or not matches[0]['subscriptionPrimaryKey'].strip():
        raise ValueError('Expected exactly one API output with a subscription key.')

    return matches[0]['subscriptionPrimaryKey']


def probe(
    client_factory: Callable[[], ApimRequests],
    path: str,
    payload: dict[str, Any] | str,
    *,
    headers: dict[str, str] | None = None,
) -> TimedProbeResult:
    """Send exactly one request; close the shared client even on transport/parse errors.

    No readiness retries or delays hide upstream failures. The caller declares and
    asserts expected status, error identity and selected pool in the notebook.
    Responses success requires completed assistant output; Chat Completions uses choices.
    """
    if not isinstance(path, str) or not path.startswith('/') or not isinstance(payload, (dict, str)):
        raise ValueError('A rooted API path and JSON object or non-object JSON string are required.')
    with client_factory() as client:
        return _probe(client, path, payload, headers)


def _retry_after_seconds(value: str | None) -> int:
    """Normalize delta-seconds and HTTP dates without retaining arbitrary header text."""
    if value is None:
        return 0
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Malformed Retry-After header.')
    if value.strip().isascii() and value.strip().isdecimal():
        return int(value)
    try:
        instant = parsedate_to_datetime(value)
    except (ValueError, TypeError) as exc:
        raise ValueError('Malformed Retry-After header.') from exc
    if instant.tzinfo is None:
        raise ValueError('Retry-After dates must include a timezone.')

    return max(0, ceil((instant - datetime.now(timezone.utc)).total_seconds()))


def _probe(client: ApimRequests, path: str, payload: dict[str, Any] | str, headers: dict[str, str] | None) -> TimedProbeResult:
    """Read one response on an already-owned client, sharing the smoke-probe contract."""
    rows = client.multiPost(path, 1, data = payload, headers = headers, printResponse = False)
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise ValueError('Expected exactly one APIM response.')
    row = rows[0]
    status = row.get('status_code')
    if isinstance(status, bool) or not isinstance(status, int) or not 100 <= status <= 599:
        raise ValueError('Invalid response status.')
    if not isinstance(row.get('response'), str):
        raise ValueError('Expected a serialized response body.')
    body = json.loads(row['response'])
    response_headers = row.get('headers')
    if not isinstance(body, dict) or not isinstance(response_headers, dict):
        raise ValueError('Expected a JSON object and response headers.')
    response_time = row.get('response_time')
    if isinstance(response_time, bool) or not isinstance(response_time, (int, float)) or not isfinite(response_time) or response_time < 0:
        raise ValueError('Missing or invalid response time.')
    normalized = {str(key).lower(): value for key, value in response_headers.items()}
    request_id = normalized.get('x-routing-request-id', '')
    pool = normalized.get('x-routing-pool', '')
    backend_host = normalized.get('x-routing-backend-host', '')
    if not isinstance(request_id, str) or not re.fullmatch(r'[0-9a-fA-F-]{36}', request_id):
        raise ValueError('Missing or malformed request correlation ID.')
    if not isinstance(pool, str) or (pool and not re.fullmatch(r'[a-z0-9.-]{1,100}', pool)):
        raise ValueError('Malformed pool evidence.')
    if not isinstance(backend_host, str) or (backend_host and not re.fullmatch(r'[a-z0-9][a-z0-9.-]{0,252}', backend_host)):
        raise ValueError('Malformed backend host evidence.')
    retry_after = _retry_after_seconds(normalized.get('retry-after'))
    if status >= 400:
        error = body.get('error')
        if not isinstance(error, dict):
            raise ValueError('Expected a sanitized error object, not just a failure status.')
        code, message = error.get('code'), error.get('message')
        safe_codes = {
            'ModelNotAvailable', 'model_not_available', 'InvalidRequest', 'SubscriptionNotAllowed',
            'DeploymentNotFound', 'model_not_found', 'InvalidRequestError', 'BadRequest', 'RateLimitReached',
            'UpstreamError', 'UpstreamUnavailable', 'UpstreamTimeout', 'GatewayError',
        }
        safe_messages = {
            'The specified model is not available for use',
            'The request payload is invalid.',
            'The subscription is not permitted for this scenario.',
            'The upstream service rejected the request.',
            'The upstream service is unavailable.',
            'The upstream request timed out.',
            'The gateway could not complete the request.',
        }
        if not isinstance(code, str) or not isinstance(message, str) or code not in safe_codes or message not in safe_messages:
            raise ValueError('Response error is not the sample sanitized error contract.')

        return TimedProbeResult(status, code, message, False, pool, request_id, backend_host, retry_after, response_time_seconds = float(response_time))
    if urlsplit(path).path.endswith('/responses'):
        operation = 'Responses'
        output = body.get('output')
        completion = (
            body.get('object') == 'response' and body.get('status') == 'completed'
            and body.get('error') is None and isinstance(output, list)
            and any(
                isinstance(item, dict) and item.get('type') == 'message'
                and item.get('role') == 'assistant' and item.get('status') == 'completed'
                and isinstance(item.get('content'), list)
                and any(
                    isinstance(content, dict) and content.get('type') == 'output_text'
                    and isinstance(content.get('text'), str) and bool(content['text'].strip())
                    for content in item['content']
                )
                for item in output
            )
        )
    else:
        operation = 'Chat Completions'
        choices = body.get('choices')
        completion = (
            isinstance(choices, list) and bool(choices) and isinstance(choices[0], dict)
            and isinstance(choices[0].get('message'), dict)
            and isinstance(choices[0]['message'].get('content'), str)
            and bool(choices[0]['message']['content'].strip())
        )
    if status != 200 or not completion:
        raise ValueError(f'Expected a real non-streaming {operation} result.')

    return TimedProbeResult(status, None, None, True, pool, request_id, backend_host, retry_after, response_time_seconds = float(response_time))


def capacity_backend_labels(accounts: Sequence[dict[str, Any]]) -> dict[str, str]:
    """Map exact deployed inference hostnames to the three public semantic tier labels."""
    labels: dict[str, str] = {}
    for account in accounts:
        endpoint = account.get('endpoint')
        if not isinstance(endpoint, str):
            raise ValueError('Redeploy the sample to obtain account inference endpoints.')
        parsed = urlsplit(endpoint)
        if (
            parsed.scheme != 'https' or not parsed.hostname or parsed.port not in (None, 443)
            or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment
            or parsed.path not in ('', '/') or parsed.hostname in labels
        ):
            raise ValueError('Expected distinct HTTPS inference origins.')
        label = account.get('label')
        if not isinstance(label, str):
            raise ValueError('Expected all three distinct simulated tier labels.')
        labels[parsed.hostname] = label
    if len(labels) != 3 or set(labels.values()) != {'global-standard', 'ptu', 'consumption'}:
        raise ValueError('Expected all three distinct simulated tier labels.')

    return labels


def capacity_figure(
    label: str,
    evidence: CapacityEvidence,
    backend_labels: Mapping[str, str],
    *,
    preferred_labels: tuple[str, str],
    fallback_label: str,
) -> Figure:
    """Render measured latency and sanitized routing observations for one capacity case."""
    tiers = [*preferred_labels, fallback_label]
    if len(set(tiers)) != 3 or set(backend_labels.values()) != set(tiers):
        raise ValueError('The chart requires the three distinct deployed tier labels.')

    # Mirror the fixed pool configurations in main.bicep; rendering does not query Azure.
    pool_settings = {
        'standard': {'global-standard': (1, 3), 'consumption': (1, 1), 'ptu': (2, 1)},
        'priority': {'ptu': (1, 3), 'consumption': (1, 1), 'global-standard': (2, 1)},
    }
    family = next((name for name in pool_settings if evidence.baseline.pool.endswith(f'-{name}-pool')), None)
    if family is None:
        raise ValueError('The chart requires a recognized sample pool configuration.')
    member_settings = pool_settings[family]
    if set(preferred_labels) != {tier for tier, (priority, _) in member_settings.items() if priority == 1}:
        raise ValueError('The chart roles do not match the sample pool configuration.')
    tier_labels = [
        f'{tier} ({role}, priority {member_settings[tier][0]}, weight {member_settings[tier][1]})'
        for tier, role in zip(tiers, ('preferred', 'preferred', 'fallback'), strict = True)
    ]

    observations = [evidence.baseline, *evidence.pressure, evidence.recovery]
    durations = [getattr(result, 'response_time_seconds', None) for result in observations]
    if any(value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value < 0) for value in durations):
        raise ValueError('The chart received an invalid response time.')

    unattributed = 'No backend identified'
    observed_tiers = [
        backend_labels.get(result.backend_host, unattributed) if result.status in (200, 429) else unattributed
        for result in observations
    ]
    tier_positions = {tier: index for index, tier in enumerate([*tiers, unattributed])}
    tier_colors = {'global-standard': '#005a9e', 'ptu': '#6b3f8d', 'consumption': '#107c10'}
    role_colors = ['#107c10', '#107c10', '#9a4a00', '#4d4d4d']
    title_color = '#005a9e' if family == 'standard' else '#6b3f8d'
    styles = {
        200: ('o', '#005a9e', '', 'completed'),
        429: ('X', '#9a4a00', '///', 'throttled'),
        503: ('D', '#a4262c', 'xxx', 'unavailable'),
    }
    missing_count = sum(duration is None for duration in durations)
    all_times_missing = missing_count == len(observations)
    recorded_times = getattr(evidence, 'observation_times_seconds', None)
    if recorded_times is not None and (
        len(recorded_times) != len(observations)
        or any(isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value < 0 for value in recorded_times)
        or any(left > right for left, right in zip(recorded_times, recorded_times[1:]))
    ):
        raise ValueError('The chart received invalid observation times.')
    last_index = len(observations) - 1
    recovery_gap = (
        recorded_times[-1] - recorded_times[-2]
        if recorded_times is not None and evidence.pressure else None
    )
    time_origin = recorded_times[1] if recorded_times is not None and evidence.pressure else None
    windows: dict[str, list[tuple[int, float, float, int]]] = {tier: [] for tier in tiers}
    for index, (result, tier) in enumerate(zip(observations, observed_tiers, strict = True)):
        retry_after = getattr(result, 'retry_after_seconds', 0)
        if isinstance(retry_after, bool) or not isinstance(retry_after, int) or retry_after < 0:
            raise ValueError('The chart received an invalid Retry-After duration.')
        if recorded_times is not None and result.status == 429 and tier in windows and retry_after > 0:
            start = recorded_times[index]
            windows[tier].append((index, start, start + retry_after, retry_after))

    figure, (latency, routing) = plt.subplots(
        2, 1, figsize = (17, 8 if all_times_missing else 10), sharex = True,
        gridspec_kw = {'height_ratios': [0.2, 1] if all_times_missing else [1.1, 1]},
    )
    with ExitStack() as cleanup:
        cleanup.callback(plt.close, figure)
        figure.subplots_adjust(left = 0.23, right = 0.98, top = 0.87, bottom = 0.34 if all_times_missing else 0.31, hspace = 0.2)
        routing.set_xlim(-0.65, last_index + 0.65)

        def label_width(text: str, size: float) -> float:
            """Measure text in display pixels, including a small spacing margin."""
            return max(TextPath((0, 0), line, size = size).get_extents().width for line in text.splitlines()) * figure.dpi / 72 + 6

        required_ticks = {0, last_index}
        if evidence.pressure:
            required_ticks.update((1, last_index - 1))
        candidates = sorted(required_ticks.union(range(5, last_index, 5)))
        candidate_labels = [
            'Warm-up' if tick == 0 else 'Recovery' if tick == last_index else str(tick)
            for tick in candidates
        ]
        time_labels = [
            f'{recorded_times[tick] - time_origin:.1f}s'
            if tick and recorded_times is not None and time_origin is not None else ''
            for tick in candidates
        ]
        tick_size = routing.xaxis.get_major_ticks(1)[0].label1.get_fontsize()
        tick_widths = [
            max(label_width(request, tick_size), label_width(elapsed, tick_size) if elapsed else 0)
            for request, elapsed in zip(candidate_labels, time_labels, strict = True)
        ]
        tick_centers = [routing.transData.transform((tick, 0))[0] for tick in candidates]
        if evidence.pressure:
            last_request = candidates.index(last_index - 1)
            if tick_centers[last_request] + tick_widths[last_request] / 2 > tick_centers[-1] - tick_widths[-1] / 2:
                right = min(0.98, 1 - (tick_widths[-1] + 4) / figure.bbox.width)
                if right <= figure.subplotpars.left:
                    warnings.warn('The recovery label is too wide to fit in the chart.', UserWarning, stacklevel = 2)
                else:
                    figure.subplots_adjust(right = right)
                    tick_centers = [routing.transData.transform((tick, 0))[0] for tick in candidates]
        tick_alignments = ['center'] * len(candidates)
        if evidence.pressure:
            first_request = candidates.index(1)
            last_request = candidates.index(last_index - 1)
            if tick_centers[0] + tick_widths[0] / 2 > tick_centers[first_request] - tick_widths[first_request] / 2:
                tick_alignments[0], tick_alignments[first_request] = 'right', 'left'
            if tick_centers[last_request] + tick_widths[last_request] / 2 > tick_centers[-1] - tick_widths[-1] / 2:
                tick_alignments[last_request], tick_alignments[-1] = 'right', 'left'
        tick_lefts = [
            center - width * (1 if alignment == 'right' else 0.5 if alignment == 'center' else 0)
            for center, width, alignment in zip(tick_centers, tick_widths, tick_alignments, strict = True)
        ]
        selected: list[int] = []
        previous_end = float('-inf')
        for index, tick in enumerate(candidates):
            end = tick_lefts[index] + tick_widths[index]
            if tick in required_ticks:
                selected.append(index)
                previous_end = end
                continue
            next_required = next(
                tick_lefts[next_index] for next_index in range(index + 1, len(candidates))
                if candidates[next_index] in required_ticks
            )
            if tick_lefts[index] >= previous_end and end <= next_required:
                selected.append(index)
                previous_end = end

        for index, (result, tier, duration) in enumerate(zip(observations, observed_tiers, durations, strict = True)):
            if duration is not None:
                _, color, hatch, _ = styles.get(result.status, ('s', '#5c2d91', '...', 'other'))
                if result.status == 200:
                    color = tier_colors.get(tier, '#4d4d4d')
                latency.bar(index, duration * 1000, color = color, edgecolor = '#1a1a1a', hatch = hatch, width = 0.8)
        if missing_count:
            latency.text(
                0.5, 0.5 if all_times_missing else 0.95,
                f'Response time not recorded for {missing_count} of {len(observations)} observations.',
                transform = latency.transAxes, ha = 'center', va = 'center' if all_times_missing else 'top',
            )
            if all_times_missing:
                latency.set_yticks([])
        latency.set_ylabel('Response time\n(ms)')
        latency.grid(axis = 'y', linestyle = ':', color = '#767676', alpha = 0.6)
        latency.set_axisbelow(True)

        if recorded_times is not None:
            for tier, intervals in windows.items():
                merged: list[tuple[int, float, float, list[int]]] = []
                for index, start, end, duration in intervals:
                    if merged and start <= merged[-1][2]:
                        first_index, first_start, previous_end, durations_in_window = merged[-1]
                        durations_in_window.append(duration)
                        merged[-1] = (first_index, first_start, max(end, previous_end), durations_in_window)
                    else:
                        merged.append((index, start, end, [duration]))
                labels: list[tuple[Annotation, float, float]] = []
                for window_index, (index, start, end, durations_in_window) in enumerate(merged):
                    continues = end > recorded_times[-1]
                    following = bisect_right(recorded_times, end)
                    if following == len(recorded_times):
                        end_position = last_index + 0.55 if continues else last_index
                    else:
                        before = following - 1
                        end_position = before + (end - recorded_times[before]) / (recorded_times[following] - recorded_times[before])
                    routing.broken_barh(
                        [(index, end_position - index)], (tier_positions[tier] - 0.35, 0.7),
                        facecolors = '#a4262c', edgecolors = '#a4262c', alpha = 0.12, hatch = '///', zorder = 1,
                    )
                    shortest, longest = min(durations_in_window), max(durations_in_window)
                    duration_label = f'{shortest}s' if shortest == longest else f'{shortest}-{longest}s'
                    merged_label = len(durations_in_window) > 1
                    duration_label += f' {"durations" if merged_label else "duration"}'
                    if time_origin is not None:
                        duration_label += f' ({start - time_origin:.1f}s - {end - time_origin:.1f}s{", merged" if merged_label else ""})'
                    elif merged_label:
                        duration_label += ' (merged)'
                    if continues:
                        duration_label += ' (continues)'
                    text_width = label_width(duration_label, 8)
                    anchor_x = routing.transData.transform((index, 0))[0]
                    if anchor_x - text_width / 2 < routing.bbox.x0:
                        alignment, offset = 'left', 3
                    elif anchor_x + text_width / 2 > routing.bbox.x1:
                        alignment, offset = 'right', -3
                    else:
                        alignment, offset = 'center', 0
                    above = window_index % 2 == 0
                    annotation = routing.annotate(
                        duration_label, (index, tier_positions[tier]), xytext = (offset, 9 if above else -9),
                        textcoords = 'offset points', ha = alignment,
                        va = 'bottom' if above else 'top', fontsize = 8, color = '#a4262c', zorder = 4,
                    )
                    label_anchor = anchor_x + offset * figure.dpi / 72
                    label_left = label_anchor - (text_width if alignment == 'right' else text_width / 2 if alignment == 'center' else 0)
                    labels.append((annotation, label_left, text_width))

                for lane_count in (2, 3, 4):
                    label_lanes = [labels[index::lane_count] for index in range(lane_count)]
                    if all(sum(width for _, _, width in lane) <= routing.bbox.width for lane in label_lanes):
                        break
                else:
                    warnings.warn(f'Too many Retry-After window labels on {tier}; labels may overlap.', UserWarning, stacklevel = 2)
                    continue
                offsets = {
                    2: ((9, 'bottom'), (-9, 'top')),
                    3: ((13, 'bottom'), (-9, 'top'), (4, 'bottom')),
                    4: ((13, 'bottom'), (-13, 'top'), (4, 'bottom'), (-4, 'top')),
                }[lane_count]
                for lane, (vertical_offset, alignment) in zip(label_lanes, offsets, strict = True):
                    if not lane:
                        continue
                    lefts = [max(routing.bbox.x0, left) for _, left, _ in lane]
                    for lane_index in range(1, len(lane)):
                        lefts[lane_index] = max(lefts[lane_index], lefts[lane_index - 1] + lane[lane_index - 1][2])
                    lefts[-1] = min(lefts[-1], routing.bbox.x1 - lane[-1][2])
                    for lane_index in range(len(lane) - 2, -1, -1):
                        lefts[lane_index] = min(lefts[lane_index], lefts[lane_index + 1] - lane[lane_index][2])
                    for (annotation, original_left, _), left in zip(lane, lefts, strict = True):
                        x, _ = annotation.get_position()
                        annotation.set_verticalalignment(alignment)
                        annotation.set_position((x + (left - original_left) * 72 / figure.dpi, vertical_offset))

        for status in sorted({result.status for result in observations}):
            marker, color, _, description = styles.get(status, ('s', '#5c2d91', '...', 'other'))
            positions = [
                (index, tier_positions[tier])
                for index, (result, tier) in enumerate(zip(observations, observed_tiers, strict = True))
                if result.status == status
            ]
            routing.scatter(
                [position[0] for position in positions], [position[1] for position in positions],
                marker = marker, color = color, edgecolors = '#1a1a1a', s = 65,
                label = f'HTTP {status} - {description}', zorder = 3,
            )
        routing.set_yticks(range(4), [*tier_labels, unattributed])
        for tick, color in zip(routing.get_yticklabels(), role_colors, strict = True):
            tick.set_color(color)
        routing.set_ylim(3.5, -0.5)
        routing.grid(axis = 'both', linestyle = ':', color = '#767676', alpha = 0.5)
        routing.set_axisbelow(True)
        handles, legend_labels = routing.get_legend_handles_labels()
        if any(windows.values()):
            handles.append(Patch(facecolor = '#a4262c', alpha = 0.12, hatch = '///'))
            legend_labels.append('Reported Retry-After (not breaker state)')
        routing.legend(
            handles, legend_labels, loc = 'upper center', bbox_to_anchor = (0.5, 0),
            bbox_transform = routing.transAxes + ScaledTranslation(0, -0.75, figure.dpi_scale_trans),
            borderaxespad = 0, ncols = 4, frameon = False,
        )

        ticks = [candidates[index] for index in selected]
        request_axis = latency.secondary_xaxis('top')
        request_axis.set_xticks(ticks, [candidate_labels[index] for index in selected])
        request_axis.set_xlabel('Response order (load request number) - equally spaced, not to scale', labelpad = 8)
        routing.set_xticks(ticks, [f'{candidate_labels[index]}\n{time_labels[index]}' for index in selected])
        for axis in (request_axis, routing):
            for tick, index in zip(axis.get_xticklabels(), selected, strict = True):
                tick.set_horizontalalignment(tick_alignments[index])
        routing.set_xlabel(
            'Request\nTime (not recorded)' if recorded_times is None
            else 'Request\nTime' if time_origin is not None else 'Request\nTime (no load)',
            fontsize = tick_size, ha = 'right', va = 'top',
        )
        tick_transform = routing.xaxis.get_major_ticks(1)[0].label1.get_transform()
        label_offset = min(-0.3, (tick_lefts[0] - routing.bbox.x0) / figure.dpi - 0.08)
        routing.xaxis.set_label_coords(
            0, 0,
            transform = blended_transform_factory(routing.transAxes, tick_transform) + ScaledTranslation(label_offset, 0, figure.dpi_scale_trans),
        )
        for axis in (latency, routing):
            axis.axvspan(-0.65, 0.5, facecolor = '#f2f2f2', edgecolor = 'none', zorder = 0, label = '_warmup_phase')
            if evidence.pressure:
                axis.axvline(0.5, color = '#4d4d4d', linestyle = '--', linewidth = 1)
                axis.axvline(last_index - 0.5, color = '#4d4d4d', linestyle = '--', linewidth = 1)
            if recovery_gap is not None and recovery_gap >= 20:
                axis.plot(
                    last_index - 0.5, 0, transform = axis.get_xaxis_transform(), marker = r'$//$',
                    color = '#1a1a1a', markersize = 14, linestyle = 'none', clip_on = False,
                    label = '_recovery_gap_break',
                )

        recovery = evidence.recovery
        preferred_recovery = (
            recovery.status == 200 and recovery.completion and recovery.pool == evidence.baseline.pool
            and backend_labels.get(recovery.backend_host) in preferred_labels
        )
        fallback_text = 'demonstrated' if evidence.fallback_served else 'not demonstrated'
        exhaustion_text = 'demonstrated' if evidence.exhausted else 'not demonstrated'
        recovery_text = 'demonstrated' if preferred_recovery else 'not demonstrated'
        caption_y = 0.04 if all_times_missing else 0.06
        gap_text = (
            f' | // {recovery_gap:.1f}s between final load and recovery responses (compressed)'
            if recovery_gap is not None and recovery_gap >= 20 else ''
        )
        figure.suptitle(f'{label} - load testing and recovery', fontsize = 15, fontweight = 'bold', color = title_color)
        figure.text(
            0.05, 0.16,
            f'{len(evidence.pressure)} load-test responses in {evidence.elapsed_seconds:.1f}s | '
            f'Recovery wait: {evidence.recovery_wait_seconds:.1f}s{gap_text}',
            fontsize = 10,
        )
        figure.text(0.05, 0.125, f'Fallback: {fallback_text} | Exhaustion: {exhaustion_text} | Preferred recovery: {recovery_text}', fontsize = 11)
        figure.text(
            0.05, caption_y,
            f'Experiment: {label} via the recommended API: healthy warm-up -> bounded load testing -> cooldown -> recovery.\n'
            f'Routing: preferred members {preferred_labels[0]} + {preferred_labels[1]}; fallback member {fallback_label}.\n'
            'Goal: demonstrate successful fallback, full-pool exhaustion and recovery on a preferred member.',
            fontsize = 10, va = 'bottom',
        )
        cleanup.pop_all()

    return figure


def wait_for_capacity_isolation(
    evidence: TimedCapacityEvidence,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> float:
    """Wait for remaining pressure cooldown before another case shares the same backends."""
    times = evidence.observation_times_seconds
    if len(times) != len(evidence.pressure) + 2 or not evidence.pressure:
        raise ValueError('The previous capacity case needs complete pressure and recovery timestamps.')
    deadline = max(
        observed + max(60, result.retry_after_seconds) + 5
        for observed, result in zip(times[1:-1], evidence.pressure, strict = True)
    )
    remaining = max(0.0, deadline - times[-1])
    if remaining > 180:
        raise RuntimeError('The previous case needs more than 180 seconds of additional cooldown; stop traffic and rerun after quota recovery.')
    if remaining:
        sleep(remaining)

    return remaining


def exercise_capacity(
    client_factory: Callable[[], ApimRequests],
    path: str,
    baseline_payload: dict[str, Any],
    pressure_payload: dict[str, Any],
    *,
    pool: str,
    backend_labels: Mapping[str, str],
    preferred_labels: tuple[str, str],
    fallback_label: str,
    max_requests: int = 20,
    max_seconds: int = 90,
    concurrency: int = 1,
    recovery_limit_seconds: int = 180,
    wait_for_initial_cooldown: bool = True,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> CapacityEvidence:
    """Bound real-model pressure, then make one recovery request after breaker/quota cooldown.

    Each loop iteration is a new caller request, not a replay of a failed POST.
    Pressure is sequential by default: the next request waits for the previous response.
    Each client owns a separate session and is used by only one in-flight request.
    Evidence must precede a batch's submission; completions already in flight
    cannot prove that a new selection avoided a subsequently throttled member.
    """
    tiers = {'global-standard', 'ptu', 'consumption'}
    if (
        not isinstance(path, str) or not path.startswith('/') or not isinstance(baseline_payload, dict) or not isinstance(pressure_payload, dict)
        or baseline_payload.get('stream') is not False or pressure_payload.get('stream') is not False
        or baseline_payload.get('model') != pressure_payload.get('model') or not baseline_payload.get('model')
        or len(backend_labels) != 3 or set(backend_labels.values()) != tiers
        or len(set(preferred_labels)) != 2 or set(preferred_labels) | {fallback_label} != tiers
        or fallback_label in preferred_labels
    ):
        raise ValueError('Capacity tests require one non-streaming model, three distinct tiers and a valid family.')
    if (
        type(max_requests) is not int or not 1 <= max_requests <= 200
        or type(max_seconds) is not int or not 1 <= max_seconds <= 300
        or type(concurrency) is not int or not 1 <= concurrency <= 8
        or type(recovery_limit_seconds) is not int or not 65 <= recovery_limit_seconds <= 600
        or type(wait_for_initial_cooldown) is not bool
    ):
        raise ValueError('Use bounded request/time budgets, concurrency from 1 through 8, a recovery limit from 65 through 600 seconds and a boolean initial cooldown.')

    if wait_for_initial_cooldown:
        sleep(65)
    with ExitStack() as stack:
        client = stack.enter_context(client_factory())
        baseline = _probe(client, path, baseline_payload, None)
        baseline_observed_at = clock()
        if baseline.status != 200 or baseline.pool != pool or backend_labels.get(baseline.backend_host) not in preferred_labels:
            raise RuntimeError(f'Capacity baseline is not a healthy preferred backend: {baseline}')
        clients = [client]
        for _ in range(min(concurrency, max_requests) - 1):
            worker_client = client_factory()
            if any(worker_client is existing for existing in clients):
                raise ValueError('The capacity client factory must create distinct clients for independent sessions.')
            clients.append(stack.enter_context(worker_client))
        pressure: list[ProbeResult] = []
        observation_times = [0.0]
        throttled_until: dict[str, float] = {}
        fallback_served = False
        exhausted = False
        started_at = clock()
        deadline = started_at + max_seconds
        preferred_retry_until: dict[str, float] = {}
        with ThreadPoolExecutor(max_workers = len(clients)) as executor:
            while len(pressure) < max_requests and clock() < deadline and not exhausted:
                before_batch = throttled_until.copy()
                batch: list[tuple[ProbeResult, str | None, float]] = []
                futures = [
                    executor.submit(_probe, worker_client, path, pressure_payload, None)
                    for worker_client in clients[:max_requests - len(pressure)]
                ]
                for future in as_completed(futures):
                    result = future.result()
                    observed_at = clock()
                    label = backend_labels.get(result.backend_host)
                    if (
                        result.status not in (200, 429, 503) or result.pool not in ('', pool)
                        or (result.status != 503 and (result.pool != pool or label is None))
                    ):
                        raise RuntimeError(f'Unexpected capacity-test response: {result}')
                    pressure.append(result)
                    observation_times.append(observed_at - baseline_observed_at)
                    batch.append((result, label, observed_at))
                    if result.status == 429 and label in preferred_labels:
                        retry_until = observed_at + (result.retry_after_seconds or 60)
                        preferred_retry_until[label] = max(preferred_retry_until.get(label, retry_until), retry_until)

                # Gateway-local selection may reach a recovered member before a prior
                # observation expires. A real success overrides that stale assumption.
                healthy = {label for result, label, _ in batch if result.status == 200}
                for label in healthy:
                    if label is not None:
                        throttled_until.pop(label, None)
                # This batch's selections predate its new 429s; retain those new
                # observations only for decisions made by the next batch.
                for result, label, observed_at in batch:
                    if result.status == 429 and label is not None:
                        throttled_until[label] = observed_at + (result.retry_after_seconds or 60)
                fallback_served |= any(
                    result.status == 200 and label == fallback_label
                    and all(before_batch.get(tier, 0) > observed_at and tier not in healthy for tier in preferred_labels)
                    for result, label, observed_at in batch
                )
                exhausted = any(
                    result.status == 503
                    and all(before_batch.get(tier, 0) > observed_at and tier not in healthy for tier in tiers)
                    for result, _, observed_at in batch
                )

        elapsed_seconds = clock() - started_at
        stop_reason = 'exhausted' if exhausted else 'time-limit' if clock() >= deadline else 'request-limit'
        # Leave a small margin for approximate quota reset timing, without retrying the recovery POST.
        recovery_wait = 65.0 if not preferred_retry_until else max(0.0, min(preferred_retry_until.values()) - clock() + 5)
        if recovery_wait > recovery_limit_seconds:
            raise RuntimeError('Retry-After exceeds the bounded recovery wait; stop traffic and rerun after quota recovery.')
        if recovery_wait:
            sleep(recovery_wait)
        recovery = _probe(client, path, baseline_payload, None)
        observation_times.append(clock() - baseline_observed_at)

    return TimedCapacityEvidence(
        baseline, tuple(pressure), recovery, fallback_served, exhausted, recovery_wait, stop_reason, elapsed_seconds,
        observation_times_seconds = tuple(observation_times),
    )
