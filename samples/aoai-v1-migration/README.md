# Samples: Azure OpenAI v1 Migration

Create PAYG Azure OpenAI resources, establish a dated legacy API and smoke-test it, then add a simple v1 API and parallel advanced legacy/v1 APIs using the Inference Failover retry/error logic. Verify the original legacy request unchanged and exercise both advanced contracts. No pre-existing Azure OpenAI resource, provisioned throughput (PTU), approved inventory or manually supplied keys is required.

⚙️ **Supported infrastructures**: SIMPLE_APIM, APPGW_APIM, APPGW_APIM_PE, AFD_APIM_PE. APIM_ACA is unsupported.

👟 **Expected *Run All* runtime (excl. infrastructure prerequisite): ~10-20 minutes**, depending on Azure provisioning and RBAC propagation.

## 🎯 Objectives

1. Deploy a sample-owned PAYG account with two different models and isolated simple/advanced model-specific singleton backend pools.
1. Establish the deployment-in-path, dated `api-version` legacy contract before adding v1.
1. Demonstrate the v1 model-in-body contract with unchanged request bodies and managed identity authentication.
1. Exercise both pools through legacy and v1, then repeat both unchanged legacy requests after adding v1.
1. Compare sanitized routing, latency and token evidence with the same test-summary and chart/report helpers used by the AOAI peer samples.
1. Compare simple pass-through policies with advanced bounded retries, circuit breakers, attempt telemetry and terminal-error normalization without adding Azure OpenAI capacity.

## ✅ Prerequisites

Follow the [repository prerequisites](../../README.md#prerequisites), then ensure:

- The subscription has Azure OpenAI access and sufficient quota for both selected models, the region and PAYG deployment type. Availability is subscription- and region-specific; defaults are not a quota guarantee.
- The deployment identity has resource deployment permissions and **Microsoft.Authorization/roleAssignments/write**, for example Owner or Contributor plus Role Based Access Control Administrator at the lab resource group scope. Contributor alone cannot grant APIM the Cognitive Services OpenAI User role.
- The selected APIM infrastructure has a system-assigned managed identity and can reach the Azure OpenAI public endpoint. Infrastructure ingress selection is handled by `NotebookHelper.create_apim_requests()`.

There are no enterprise approval gates. Use a non-production lab subscription and understand its billing and data handling requirements.

## 📝 Scenario

A client already uses a dated Azure OpenAI Chat Completions contract for multiple models. Rather than modifying that client in place, expose v1 alongside legacy and verify both contracts reach each model's dedicated pool.

- **Established API:** `POST /<sample>/openai/deployments/<deployment-name>/chat/completions?api-version=2024-10-21`, with `messages` in JSON and no body `model` selector.
- **v1:** `POST /<sample>/openai/v1/chat/completions`, with `messages` and `"model": "<deployment-name>"` in JSON, without a dated query parameter.
- Both policies forward bodies unchanged. Legacy retains the caller's deployment path and query parameters; v1 uses the caller's JSON `model` field and drops unmatched query parameters.

Both simple policies derive the backend pool name by appending `-pool` to the caller's deployment name. There is no dictionary, gateway allowlist, per-model `choose` branch or default-pool fallback. New deployments must have a matching `<deployment-name>-pool` backend; adding one does not require changing these policies. This sample deliberately provisions two distinct enum models. Legacy reads the deployment from the URL without body parsing. v1 parses JSON once with `preserveContent: true` to obtain its `model` selector, but never serializes or rewrites the body.

If the derived pool does not exist, APIM fails the request and `on-error` traces the gateway failure and returns a fixed JSON error. It does not send the request to another pool. Once a pool resolves, Azure OpenAI validates the unchanged deployment selector, API version and payload. This is not per-model authorization: APIM subscriptions and inherited authentication remain the caller gate. Naming alone does not restrict callers to this sample's pools; use a separate authorization design if consumers must be restricted to particular deployments or pools on a shared gateway.

The sample treats `/<sample>/openai` as the established API and adds `/<sample>/openai/v1` alongside it. The existing public path and display name do not label it as "legacy"; that term only distinguishes the dated contract in the sample narrative and internal resource IDs. The sample prefix isolates the sample from gateway-wide routes. It does not modify existing production APIs or global policies.

## 🛩️ Lab Components

- One deterministic Azure OpenAI `S0` account with local key authentication disabled.
- Two PAYG `GlobalStandard` deployments by default, or `Standard` when explicitly configured. No PTU resources or simulated PTU tiers.
- Defaults are `AzureOpenAIModel.GPT_5_MINI` and `AzureOpenAIModel.GPT_5_NANO`, snapshot `2025-08-07`, each with capacity `10`. Capacity uses model-specific quota conversion; ensure both allocations are available.
- Deployment names are `<sample>-<model>` and pools are `<sample>-<model>-pool`, for example `aoai-v1-migration-1-gpt-5-mini-pool` and `aoai-v1-migration-1-gpt-5-nano-pool`. Dots in model names become hyphens in resource identifiers.
- Each pool contains one dedicated `<sample>-<model>-backend` targeting the shared sample Azure OpenAI account. This demonstrates model routing, not load balancing.
- Two additional advanced singleton pools and backends target the same model deployments. Their circuit-breaker state is separate from the original pools, so failures on an advanced API do not trip the simple API's breaker. They do not isolate the shared deployment's quota or capacity.
- Four API-scoped subscriptions and an OpenAI User role assignment for APIM managed identity.
- Existing APIM, Application Insights and Log Analytics infrastructure remains shared; no duplicate monitoring resources or diagnostic settings are deployed.
- Sample-local [migration_helpers.py](migration_helpers.py) handles configuration validation, key selection, response normalization and bounded readiness retries. Notebook cells retain the visible deployment sequence, requests and assertions.

Simple policies do not replay requests automatically. Advanced policies can replay non-streaming requests as described below. Streaming is passed through without replay on all four APIs, but the lab smoke tests cover **non-streaming Chat Completions only**, not Responses, SDK integration, resilience or production migration readiness. The sample does not enable request/response body logging; inherited infrastructure policy/logging settings still apply.

The simple policies explicitly set `fail-on-error-status-code="false"` so backend HTTP 400-599 remain ordinary responses. `outbound` traces them without changing their status, body or headers, including `Retry-After`. Forcing them into `on-error` can replace a backend 404 with a gateway 500. Both error paths produce sanitized `AoaiMigrationError` traces containing contract, request ID, status and error source/reason only. `on-error` handles gateway failures: a `Timeout` without a backend error response maps to 504, `BackendConnectionFailure` to 502, and other failures, including missing pools and JSON parsing failures, to 500. The API policy returns an `error` object with code `gateway_error` and a fixed message. Native APIM gateway errors can instead have integer `statusCode` and string `message` fields; the helper validates either format without logging response text. A native error's code must match the HTTP status and its message must be non-empty. A missing pool is a gateway configuration error, distinct from Azure OpenAI's deployment-not-found HTTP 404. Inherited policies can still modify responses. An error after streaming response headers have been sent cannot replace the caller's already-started response.

### Parallel Advanced APIs

Stage two also installs [legacy-advanced.xml](apim-policies/legacy-advanced.xml) and [v1-advanced.xml](apim-policies/v1-advanced.xml) on separate APIs:

- **Advanced dated contract:** `POST /<sample>/advanced/openai/deployments/<deployment-name>/chat/completions?api-version=2024-10-21`.
- **Advanced v1 contract:** `POST /<sample>/advanced/openai/v1/chat/completions`, with `"model": "<deployment-name>"` in the unchanged JSON body.
- Each uses its own API subscription key. Routing derives `<deployment-name>-advanced-pool`, with no default-pool fallback. Legacy preserves the caller's dated query parameters; v1 drops them.

These policies adapt the default [Inference Failover policy](../inference-failover/apim-policies/inference-api-policy.xml), not its optional cached Retry-After tracking variant:

- Two immediate retries after the initial call, independent of pool size. Each backend attempt has a 60-second timeout, for at most 180 seconds of backend waits per non-streaming request, plus gateway overhead.
- Retry a missing response, 408, 429, 499, 500, 502, 503 and 504. Retry 409 only when `Retry-After` is present. Other backend errors, including 400, 401, 403 and 404, are not retried.
- Return final 408, 409, 429 and 499 unchanged, including the backend's `Retry-After`. Normalize final 500, 502, 503 and 504 to JSON 503. Handled transport timeouts/connection failures also become 503. Other gateway errors, including missing pools, remain JSON 500.
- Broader isolated circuit breakers trip on the first 408, 429, 499-500 or 502-504 in a one-minute window, avoid the backend for one minute, and honor `Retry-After`. A singleton pool may have no eligible backend after its only member trips; retrying does not guarantee recovery.
- `InferenceBackendAttempt` traces record contract, correlation ID, attempt number and HTTP status, never caller URLs, selectors, credentials or bodies. `X-Backend-Retry` reports retries for the final APIM request, separately from client readiness attempts. The smoke helper requires a numeric value in `0..2` on advanced successes.
- A JSON `stream: true` disables replay through the retry condition and keeps response buffering disabled. Advanced legacy additionally parses the body for this safety check; advanced v1 reads the preserved JSON body for both streaming safety and model selection. Neither rewrites the request body.

There are still only two Azure OpenAI deployments. The advanced APIs demonstrate the retry/error matrix on singleton pools, **not actual alternate-destination or cross-region failover**. They do not introduce simulated PTU tiers, pressure tests, fault injection, telemetry workbooks or sensitive LLM body logging. Replays can add latency and billable work; do not treat Chat Completions as idempotent.

The notebook uses the shared `ApimRequests` client, whose per-request read timeout is 30 seconds. It validates successful routing and headers, not the entire worst-case retry duration. Slow or failed requests can therefore time out at the client before the gateway finishes its retry chain; transport exceptions propagate and close the client. Use a suitably longer caller timeout when independently testing the full gateway retry budget.

## ⚙️ Configuration

1. Open [create.ipynb](create.ipynb) using the repository notebook environment.
1. Adjust the top **USER CONFIGURATION** if necessary. Defaults select `SIMPLE_APIM`, `BASICV2`, East US 2, `index = 1`, and namespace `aoai-v1-migration-1`.
1. Use `NotebookHelper`'s standard selection/creation workflow if the desired APIM infrastructure is absent. No Azure OpenAI inventory must be prepared beforehand.
1. Check regional availability/quota before changing `primary_model`, `secondary_model`, `model_sku` or the per-model `model_capacity`. Select two different enum models; use the enum's `.version`, not a guessed snapshot.
1. Run cells in order: deploy legacy → legacy baseline → add simple v1 and advanced legacy/v1 → simple v1 success/rejection → unchanged legacy regression → advanced success/rejection → combined report.

Subscription keys come from the shared API module's deployment outputs and are selected without logging. Never paste them into notebook configuration or commit executed notebook outputs.

## 🖼️ Expected Results

The notebook records six successful probes: both models through legacy before v1 exists, both through v1, and both through the original legacy requests after v1 is added. Before each model's **Legacy Before** measurement, it validates one successful warm-up request, discards its evidence, and sends an identical second request through the same client. Only that second successful request appears in the evidence table and chart. Each warm-up and measured request asserts HTTP 200, a non-empty completion, the exact `x-migration-backend-pool` response header, and the backend's actual `model` snapshot (`<model-name>-<version>`). HTTP 200 alone is not sufficient routing evidence. The policy overwrites the sample-owned header after inherited outbound processing.

A seventh probe supplies an unknown v1 deployment name, which derives a nonexistent pool and expects a JSON HTTP 500 gateway error, not a completion from a fallback pool. Four additional successes exercise both models through advanced legacy and advanced v1, asserting the advanced pool, model snapshot and bounded retry header. A twelfth probe checks the advanced v1 missing-pool rejection. Both negative probes make one client attempt without readiness retries. Generated completion wording is not expected to be identical.

The final verification cell produces:

- An `ApimTesting` summary with 48 checks covering HTTP status, completion shape, exact pool/model identity, bounded advanced retry headers and expected rejections.
- A `TableLogger` evidence table with status, readiness attempts, APIM backend retries, response time in milliseconds and prompt/completion/total tokens.
- Two shared `charts.BarChart` latency charts, one per model, showing **Legacy Before**, **v1**, **Legacy After**, **Advanced Legacy** and **Advanced v1**. Expected HTTP 500 rejections are labeled in the table rather than plotted as operational failures.
- A self-contained `HtmlReport` saved under the repository's ignored `tmp/` folder as `<sample_name>-report.html`, with the same table, verified routing and embedded charts.

Measurements describe the **final response** of each measured probe. Warm-up requests, earlier readiness attempts and waits are excluded from recorded latency and token counts. Attempt counts include only the measured phase, never the warm-up phase. Advanced final-response latency includes any APIM backend retries; token usage reflects the final response, not total billable work across retries. Missing latency/token fields remain empty rather than becoming zero. No keys, prompts or completion content are saved. Five successful probes per model do not establish a performance baseline or compare model quality.

This deliberately reuses the peer samples' test, table, chart and local-report building blocks, not their scope. Unlike [Costing](../costing/README.md), it does not generate showback traffic, exercise Responses/streaming modes or allocate costs. It adapts the retry/error matrix from [Inference Failover](../inference-failover/README.md) only for the parallel advanced APIs, without that sample's regional topology, capacity pressure or telemetry workbook. The legacy baseline must precede adding v1, so that verification remains between the two deployment stages; all charts and reporting run together at the end without telemetry polling.

### Results and Reruns

Stage two reuses the legacy API definition and verifies that its subscription key is unchanged. Deterministic names make deployments incremental and rerunnable. Stage one resets old smoke evidence; stage two requires successful new baselines for both pools. Rerunning stage one after stage two **does not remove** v1, because incremental deployments do not delete omitted resources. Use a new namespace for a fresh legacy-only sample.

Each warm-up or measured request has a separate readiness budget of six attempts and 180 seconds of scheduled waits. A **Legacy Before** probe can therefore make up to 12 requests with 360 seconds of scheduled waits across both phases; normally it makes two successful requests. Other successful probes normally make one client request, and negative probes never retry at the client. These readiness retries are distinct from the advanced APIs' APIM retry policy: each advanced client attempt can cause up to three backend attempts, increasing latency and billable work. If propagation takes longer, resolve the issue and rerun the affected smoke cell.

See [RUNBOOK.md](RUNBOOK.md) for failures, cleanup and optional existing-workspace queries.

## 🧹 Clean Up

Follow [sample-only cleanup](RUNBOOK.md#clean-up) when sharing an infrastructure. If the entire infrastructure resource group is disposable, use that infrastructure's cleanup notebook instead. PAYG inference is billed per usage; APIM and other infrastructure resources can continue accruing charges independently.

## 🔗 Additional Resources

- [Azure OpenAI v1 API](https://learn.microsoft.com/azure/ai-foundry/openai/api-version-lifecycle)
- [Azure OpenAI deployment types](https://learn.microsoft.com/azure/ai-foundry/openai/how-to/deployment-types)
- [Azure OpenAI role-based access](https://learn.microsoft.com/azure/ai-foundry/openai/how-to/role-based-access-control)
- [Python helper architecture](../../shared/python/README.md)
