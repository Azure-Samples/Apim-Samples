"""
Costing-sample-private helpers.

These functions are intentionally scoped to the costing sample because they
encode costing-specific contracts (the local `bu-request-counts.local.json`
schema, the fake-JWT shape used by the emit-metric policy, the retry profile
appropriate for the traffic-generation cells). They are NOT part of the
shared helpers in `shared/python/` to avoid leaking sample-specific concerns
into other samples.

Imported by `samples/costing/create.ipynb` after the sample folder is added
to `sys.path` in cell 1.
"""

import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests as http_requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def make_fake_jwt(appid: str) -> str:
    """Create a minimal unsigned JWT carrying an `appid` claim.

    The emit-metric policy reads the `appid` (or `azp`) claim from the
    bearer token to extract caller identity. Signing is irrelevant for the
    sample because the policy does not validate the token.

    Args:
        appid: The Entra ID application ID to embed in the JWT payload.

    Returns:
        A three-segment JWT string (header.payload.signature) with an
        empty signature segment.
    """
    header = base64.urlsafe_b64encode(json.dumps({'alg': 'none', 'typ': 'JWT'}).encode()).rstrip(b'=').decode()
    payload = base64.urlsafe_b64encode(json.dumps({'appid': appid}).encode()).rstrip(b'=').decode()

    return f'{header}.{payload}.'


def build_session(
    request_headers: dict | None,
    allow_insecure_tls: bool,
    *,
    extra_headers: dict | None = None,
    with_retries: bool = False,
) -> http_requests.Session:
    """Create a `requests.Session` with TLS verification and headers preconfigured.

    Args:
        request_headers: Headers returned by `utils.get_endpoint(...)` (may be None).
        allow_insecure_tls: True when the endpoint uses a self-signed certificate
            (e.g. Application Gateway infrastructures). Disables TLS verification.
        extra_headers: Optional additional headers to set on the session
            (e.g. `Content-Type`, `api-key`, `Authorization`).
        with_retries: When True, mounts an HTTPAdapter that retries on 502/503/504
            and on transient connection / read errors. Useful for the heavy
            BU traffic loop in cell 7 where a single TLS blip should not abort
            the whole run.

    Returns:
        A configured `requests.Session`. Caller is responsible for closing it.
    """
    session = http_requests.Session()
    session.verify = not allow_insecure_tls
    if request_headers:
        session.headers.update(request_headers)
    if extra_headers:
        session.headers.update(extra_headers)

    if with_retries:
        retry_strategy = Retry(
            total=4,
            connect=4,
            read=4,
            backoff_factor=0.5,
            status_forcelist=[502, 503, 504],
            allowed_methods=['GET', 'POST'],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount('https://', adapter)
        session.mount('http://', adapter)

    return session


def purge_traffic_source(local_data_path: Path, source_name: str) -> bool:
    """Remove a single named entry from `bu-request-counts.local.json` if present.

    Each traffic-generation cell calls this *before* checking whether it should
    actually run. That keeps the persisted JSON honest when the corresponding
    `run_*` toggle is flipped off between runs — otherwise the file would
    still show last run's request counts and mislead the workbook cross-check.

    Args:
        local_data_path: Path to the local JSON file (typically returned by
            `utils.determine_policy_path('bu-request-counts.local.json', ...)`).
        source_name: The `name` field of the traffic-source entry to remove
            (e.g. `'subscription-based-costing'`, `'ai-gateway-aoai'`).

    Returns:
        True if an entry was removed (and the file was rewritten),
        False if the file is missing or contained no matching entry.
    """
    if not local_data_path.exists():
        return False

    existing = json.loads(local_data_path.read_text(encoding='utf-8'))
    sources = existing.get('trafficSources', [])
    filtered = [s for s in sources if s.get('name') != source_name]

    if len(filtered) == len(sources):
        return False

    existing['trafficSources'] = filtered
    existing['generatedUtc'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    local_data_path.write_text(json.dumps(existing, indent=2), encoding='utf-8')

    return True


def persist_traffic_source(
    local_data_path: Path,
    *,
    sample_folder: str,
    rg_name: str,
    apim_name: str,
    source_entry: dict[str, Any],
) -> None:
    """Append-or-replace a single traffic-source entry in the local JSON file.

    Replacement is keyed by `source_entry['name']` so each cell can call this
    idempotently on re-runs. The top-level `generatedUtc` is always refreshed.

    Args:
        local_data_path: Path to `bu-request-counts.local.json`.
        sample_folder: Sample folder name, persisted as `sampleFolder`.
        rg_name: Resource group name, persisted as `resourceGroup`.
        apim_name: APIM service name, persisted as `apimService`.
        source_entry: The traffic-source dict to insert. Must contain a
            `name` key; existing entries with the same name are replaced.
    """
    existing = json.loads(local_data_path.read_text(encoding='utf-8')) if local_data_path.exists() else {}
    sources = [s for s in existing.get('trafficSources', []) if s.get('name') != source_entry['name']]
    sources.append(source_entry)

    persisted = {
        'sampleFolder': sample_folder,
        'resourceGroup': rg_name,
        'apimService': apim_name,
        'generatedUtc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'trafficSources': sources,
    }
    local_data_path.write_text(json.dumps(persisted, indent=2), encoding='utf-8')
