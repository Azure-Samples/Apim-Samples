# Samples: Inference Failover

<!-- markdownlint-disable MD013 -->
<!-- Long technical prose and wide telemetry tables are intentionally not hard-wrapped. -->

This sample uses Azure API Management as an AI Gateway for two Azure OpenAI models, combining priority and weighted backend failover with focused LLM telemetry in Log Analytics and an Azure Monitor Workbook.

⚙️ **Supported infrastructures**: All infrastructures

👟 **Expected *Run All* runtime (excl. infrastructure prerequisite): ~15 minutes**

## 🎯 Objectives

1. Route each model only to compatible Azure OpenAI deployments through model-specific APIM backend pools.
1. Observe priority failover and equal-weight terminal routing when regional `Standard` deployments return `429` or `503` responses.
1. Capture request, retry-trail, failure, latency, and token telemetry through `ApiManagementGatewayLogs`, `TraceRecords`, and `ApiManagementGatewayLlmLog`.
1. Use a controlled low-capacity model constellation to generate observable failover without treating simulated PTU tiers as real provisioned deployments.

## ✅ Prerequisites

Beyond the [general prerequisites](../../README.md#-getting-started) (Azure subscription, CLI, Python environment), this sample requires permissions and quota for Azure OpenAI deployments.

- **Cognitive Services Contributor** at resource group scope to create three Azure OpenAI resources and nine regional model deployments.
- **Role Based Access Control Administrator** or equivalent role-assignment permission at resource group scope to assign APIM's managed identity the **Cognitive Services OpenAI User** role.
- Regional model availability and quota in `eastus2`, `westus3`, and `southcentralus` for the requested `gpt-5.1` and `gpt-4.1-mini` `Standard` deployments.

## 📝 Scenario

An AI platform prefers provisioned capacity tiers across its available regions before using pay-as-you-go capacity: in-region PTU, out-of-region PTU, in-region PAYG, then out-of-region PAYG. This lab exercises that routing shape using only regional `Standard` pay-as-you-go Azure OpenAI deployments. Names containing `PTU` identify the simulated preference tier in the experiment and do not change the Azure OpenAI deployment SKU or billing model.

### Response Handling Rules

The inference policy uses the following response-handling matrix. "Failover" means returning the sample's generic caller-facing `503` after the eligible regional retry chain is exhausted; it is distinct from shifting an individual retry to another region.

| Code | Category | Retry     | Shift Region | Failover           | Severity |
| ---- | -------- | --------- | ------------ | ------------------ | -------- |
| 200  | Success  | N/A       | No           | No                 | None     |
| 400  | Client   | No        | No           | No                 | Low      |
| 401  | Auth     | No        | No           | No                 | Medium   |
| 403  | AuthZ    | No        | No           | No                 | Medium   |
| 404  | Config   | No        | No           | No                 | Medium   |
| 409  | Conflict | Sometimes | No           | No                 | Medium   |
| 429  | Capacity | Yes       | Yes (bias)   | No                 | Medium   |
| 500  | Infra    | Yes       | Yes          | Yes (if sustained) | High     |
| 502  | Infra    | Yes       | Yes          | Yes                | High     |
| 503  | Infra    | Yes       | Yes          | Yes                | High     |
| 504  | Infra    | Yes       | Yes          | Yes                | High     |

The policy interprets "Sometimes" as a `409` carrying `Retry-After`: APIM retries it immediately against the selected backend but does not open that backend's circuit or intentionally shift region. A `429` opens the capacity circuit, and `Retry-After` biases subsequent pool selection away from the constrained backend; if every eligible attempt still returns `429`, APIM preserves that response instead of converting it to failover. A `500` becomes a regional failover signal only after two occurrences within one minute, while `502`, `503`, and `504` open the infrastructure circuit immediately. After the regional chain is exhausted, those infrastructure responses become a generic caller-facing `503`.

### Failure Test Coverage

The notebook runs deterministic gateway contract probes before its capacity scenarios. These probes verify a valid `200`, an Azure OpenAI `400` from malformed JSON, an APIM `401` from a missing subscription key, and an APIM `404` from an unknown operation. The `400` also verifies `X-Backend-Retry: 0`, proving that client errors pass through without retry. The pressure scenarios exercise organic `429` handling against the intentionally small deployments. The remaining backend statuses require a controllable fault origin because Azure OpenAI does not provide a supported "return this status" test switch.

| Condition | Automated here | Recommended controlled test | Expected evidence |
| --- | --- | --- | --- |
| `200` | Yes | Send a valid small chat-completions request. | `200` and `X-Backend-Retry: 0`. |
| `400` | Yes | Send truncated JSON with `Content-Type: application/json`. | Backend `400`, caller `400`, and `X-Backend-Retry: 0`. |
| `401` | Yes | Omit the APIM subscription key. | Gateway `401`; the inference policy is not entered. |
| `403` | No | On an isolated deployment, remove **Cognitive Services OpenAI User** from APIM or add a temporary deny policy. Restore access immediately after the probe. | Backend/caller `403` and no retry. |
| `404` | Yes | Call an unknown APIM operation. For a backend-side variant, temporarily target a nonexistent model deployment in an isolated backend. | `404` and no retry. |
| `409` without `Retry-After` | No | Use a local fault server, Mockoon, WireMock, or a temporary Container App that returns `409` without the header. | One attempt; caller keeps `409`. |
| `409` with `Retry-After` | No | Return `409` plus `Retry-After: 1` from the controlled fault origin. | Retry count increases, but the backend circuit does not open. |
| `429` | Yes, workload-dependent | Run the pressure cells. For deterministic CI, return `429` plus `Retry-After` from a controlled fault origin. | Regional selection is biased; exhausted capacity remains `429`. |
| `500` | No | Return `500` twice within one minute, then recover. | First response is retryable; sustained failures open the circuit and can exhaust as generic `503`. |
| `502` | No | Return an explicit `502` from the controlled fault origin. | Immediate infrastructure circuit trip and regional retry. |
| `503` | Organic but not guaranteed | Return `503`, optionally with `Retry-After`, from the controlled fault origin. | Immediate regional retry; exhausted chain becomes generic `503`. |
| `504` | No | Return an explicit `504`; separately delay the origin beyond the APIM forwarding timeout to test transport timeout behavior. | HTTP `504` trips the circuit; timeout produces no backend HTTP response but is retried and normalized to `503`. |
| DNS/connection failure | No | Point one isolated backend at a reserved nonexistent host such as `https://unresolvable.invalid`. | `BackendConnectionFailure`, retries, then generic `503` if all destinations fail. |
| TLS failure | No | Point an isolated backend at a host with an expired certificate or a certificate-name mismatch while TLS validation remains enabled. | Backend connection failure, retries, and no certificate detail disclosed to the caller. |
| Caller disconnect | No | Start a streaming or deliberately slow request, then abort the client socket or use `curl --max-time 1`. | Native client-connection/cancellation telemetry; this is not backend failover. |

Use a separate APIM API/backend pool or a disposable deployment for controlled origin tests. Do not add public fault-injection headers to the production-shaped inference APIs, and do not remove role assignments from a shared environment. A nonexistent backend hostname is useful for DNS failure, but it does **not** simulate a client disconnect: DNS happens between APIM and the backend, while a client disconnect happens between the caller and APIM.

For the HTTP fault cases, a minimal local origin can return the requested status and optional `Retry-After` header. Expose it only to the test APIM network path, register one backend per region/priority under test, and apply the same inference policy and breaker configuration. Run each case twice: once with a later healthy pool member to prove recovery, and once with every member faulted to prove the terminal caller contract. Inspect `X-Backend-Retry`, `BackendResponseCode`, `LastErrorReason`, and the `InferenceBackendAttemptComplete`, `InferenceFallbackExhausted`, or `InferenceTransportFailure` trace event.

### Model Deployments

All deployments below use the regional `Standard` SKU with a capacity of `1` thousand tokens per minute (TPM). This deliberately small capacity makes concentrated `429`-driven failover practical to observe; it is not production sizing advice.

| Region           | Label | Deployment         | Model          | Version      | Simulates          |
| ---------------- | ----- | ------------------ | -------------- | ------------ | ------------------ |
| East US 2        | A     | `a-gpt-5-1`        | `gpt-5.1`      | `2025-11-13` | In-region PTU      |
| East US 2        | B     | `b-gpt-5-1`        | `gpt-5.1`      | `2025-11-13` | In-region PAYG     |
| East US 2        | C     | `c-gpt-4-1-mini`   | `gpt-4.1-mini` | `2025-04-14` | In-region PTU      |
| East US 2        | D     | `d-gpt-4-1-mini`   | `gpt-4.1-mini` | `2025-04-14` | In-region PAYG     |
| West US 3        | D     | `d-gpt-5-1`        | `gpt-5.1`      | `2025-11-13` | Out-of-region PTU  |
| West US 3        | E     | `e-gpt-5-1`        | `gpt-5.1`      | `2025-11-13` | Out-of-region PAYG |
| West US 3        | F     | `f-gpt-4-1-mini`   | `gpt-4.1-mini` | `2025-04-14` | Out-of-region PTU  |
| South Central US | G     | `g-gpt-5-1`        | `gpt-5.1`      | `2025-11-13` | Out-of-region PAYG |
| South Central US | H     | `h-gpt-4-1-mini`   | `gpt-4.1-mini` | `2025-04-14` | Out-of-region PAYG |

## 🛩️ Lab Components

This lab adds the following to an existing APIM infrastructure:

- Three regional Azure OpenAI resources containing nine `Standard` model deployments at `1` thousand TPM each.
- Nine concrete APIM backends named using `<model>-<PTU|PAYG>-<region>`, each with TLS validation and separate circuit breakers for capacity, sustained internal errors, and immediate gateway or availability failures.
- One APIM backend pool per model so a retry never crosses to an incompatible deployment.
- Two AI Gateway APIs with managed identity authentication to Azure OpenAI: `POST /inference/gpt-5-1/chat/completions` retries four times through A -> D -> B -> E/G (equal terminal weights), while `POST /inference/gpt-4-1-mini/chat/completions` retries three times through C -> F -> D -> H.

- Model-specific retry policies that buffer the POST body while immediately retrying conditional conflicts, throttling, and listed infrastructure failures; emit an information-level trace after every backend attempt; always return the caller-visible `X-Backend-Retry` count; preserve exhausted `409` and `429` responses; and return a generic `503` when infrastructure failover is exhausted.
- APIM AI Gateway diagnostics using the infrastructure-provided Log Analytics workspace and Application Insights component, plus an AOAI-only workbook for terminal outcomes, retry trails, backend distribution, APIM errors, token coverage, and latency.
- An optional Standard Event Hubs namespace, telemetry hub, and `external-observability` consumer group in the APIM region for downstream stream processors, SIEM platforms, or external analytics systems.

### Observability Signals

Every inference call produces one `ApiManagementGatewayLogs` row. The workbook and KQL files preserve the difference between the APIM caller response and the final backend response so an operator can determine whether APIM recovered, transformed the result, or exhausted fallback capacity.

| Signal | Source | What it explains |
| --- | --- | --- |
| Caller-visible response | `ApiManagementGatewayLogs.ResponseCode` | The HTTP status ultimately returned by APIM. |
| Caller-visible retries | `X-Backend-Retry` response header | The number of backend retries absorbed by APIM after the initial attempt. A healthy-path response normally returns `0`. |
| Final backend response | `ApiManagementGatewayLogs.BackendResponseCode` | The HTTP status from the last selected Azure OpenAI backend. |
| Final backend placement | `ApiManagementGatewayLogs.BackendId`, `BackendUrl` | The concrete backend used for the final attempt. |
| Retry trail | `ApiManagementGatewayLogs.TraceRecords` | Each `InferenceBackendAttemptComplete` event records its attempt number, backend response code, and whether retry remained eligible. |
| Exhausted fallback | `ApiManagementGatewayLogs.TraceRecords` | `InferenceFallbackExhausted` proves that APIM replaced the final `429` or `503` with the generic caller-facing `503`. |
| Native APIM failures | `Errors`, `LastErrorSource`, `LastErrorReason`, `LastErrorSection`, `LastErrorMessage` | Pipeline failures that are not ordinary Azure OpenAI HTTP responses. |
| LLM usage and message chunks | `ApiManagementGatewayLlmLog` joined by `CorrelationId` | Model deployment, token usage, and whether prompt/completion message telemetry arrived. |

The sample includes copy-paste KQL for aggregated outcomes, backend distribution, failure taxonomy, telemetry coverage, and a per-request investigation view. The workbook exposes the same operational views and adds a correlation-ID filter for targeted troubleshooting. See the [query catalog](queries/README.md) for parameters, signal sources, and investigation guidance.

- [failover-outcomes.kql](queries/failover-outcomes.kql) - Caller-visible outcomes, final backend outcomes, and retry statistics.
- [backend-distribution.kql](queries/backend-distribution.kql) - Final backend placement, status distribution, and latency.
- [failure-analysis.kql](queries/failure-analysis.kql) - Recovered failovers, exhausted chains, backend failures, and APIM pipeline errors.
- [llm-telemetry-coverage.kql](queries/llm-telemetry-coverage.kql) - Token and prompt/completion message-chunk coverage for successful calls.
- [request-details.kql](queries/request-details.kql) - Joined per-request gateway, retry, failure, and LLM telemetry for incident investigation.
- [token-throughput.kql](queries/token-throughput.kql) - Token volume by API, backend, and model.

### Managed Identity And Privacy

The inference API policy authenticates every selected backend request with APIM's system-assigned managed identity and the **Cognitive Services OpenAI User** role. It never stores or forwards an Azure OpenAI API key. For learning and testing, the infrastructure's global APIM policy returns the selected backend URL in the `X-Backend-URL` response header so the notebook can record routing decisions. Disable `revealBackendApiInfo` for production-like environments. The inference policy always returns `X-Backend-Retry`, including when fallback is exhausted, so callers can see how many backend failures APIM absorbed after the initial attempt. If fallback is exhausted, callers receive a generic `503` response without backend identity or placement information.

This learning sample enables LLM prompt and completion message logging. Treat the Log Analytics workspace as sensitive. Before production use, review retention and role-based access, then disable message capture or reduce logged message size when full prompt/completion bodies are not required. The workbook reports chunk counts for completeness but intentionally does not render prompt or completion bodies.

### Optional Event Hub Export

Set `enable_event_hub_export = True` under *SYSTEM CONFIGURATION* in [create.ipynb](create.ipynb) to stream the APIM diagnostic feed to a sample-scoped Event Hub while retaining Log Analytics ingestion and workbook views. The option defaults to `False` so the normal sample deployment does not add Event Hubs cost. When enabled, the sample deploys a Standard Event Hubs namespace in the selected infrastructure/APIM region, a non-compacted `apim-inference-failover` hub, and an `external-observability` consumer group for downstream processors.

The Event Hub receives the same broad APIM diagnostic stream configured for Log Analytics: `GatewayLogs`, `GatewayLlmLogs`, `WebSocketConnectionLogs`, and `AllMetrics`. This includes caller-visible responses, final backend responses, backend placement, policy `TraceRecords`, native APIM errors, model and token telemetry, and logged prompt/completion message chunks. Workbook calculations are derived views rather than emitted events, so external processors should reconstruct their preferred aggregations from the raw stream.

Treat the Event Hub stream as sensitive for the same reason as the Log Analytics workspace: prompt and completion content can be present. Apply appropriate retention, network controls, role-based access, and consumer-side data handling before using the option beyond the lab. The sample creates the namespace authorization rule required by Azure Monitor diagnostic streaming but does not expose its connection string.

Gateway ingress exposure follows the selected infrastructure: choose a Private Link or VNet architecture when private ingress is required, while the notebook keeps Simple API Management as its approachable default.

Routine probes intentionally do not perform inference: recurring multi-location model calls would consume request and token budgets while still providing an incomplete capacity signal. The notebook harness sends explicit inference traffic when a live readiness or failover observation is needed.

## ⚙️ Configuration

1. Deploy any [infrastructure architecture](../../README.md#list-of-infrastructures), with [Simple API Management](../../infrastructure/simple-apim/README.md) as the notebook default.
1. Open [create.ipynb](create.ipynb) and adjust only values under *USER CONFIGURATION* if necessary.
1. To externalize the APIM diagnostic feed, set `enable_event_hub_export = True` under *SYSTEM CONFIGURATION*. Leave the default `False` value in place when Event Hub streaming is not needed.
1. Run all notebook cells to deploy the model constellation, APIs, workbook, controlled inference requests, and telemetry charts.
1. Increase `max_completion_tokens` only when the initial traffic does not produce sufficient concentrated pressure for failover observation; requests consume real Azure OpenAI tokens.

## 🖼️ Expected Results

After the traffic cells run and telemetry ingestion completes, the notebook plots terminal outcomes and token usage while the workbook provides longer-lived views of:

- A self-contained local HTML report linked at the end of the run, with assertion totals, scenario outcomes, response-time graphs, available telemetry tables and graphs, and Azure exploration links.
- Per-run response-time charts for baseline, sustained-pressure, paced-recovery, and terminal-burst scenarios, colored by URL-derived backend index and annotated with captured `X-Backend-URL` values.
- Caller-visible `X-Backend-Retry` counts that expose how many backend failures APIM absorbed before returning each response.
- Caller-visible APIM response codes versus final backend response codes.
- Concrete final-backend distribution using gateway-recorded backend IDs and URLs.
- Per-request retry trails, recovered failovers, and terminal fallback exhaustion.
- Native APIM pipeline failures from `Errors` and `LastError*` fields.
- Prompt, completion, and total tokens by model route, plus successful-request token coverage and message-chunk statistics.
- Total and backend latency trends during controlled pressure.
- Joined request exploration by `CorrelationId` without rendering sensitive prompt or completion bodies.

## 🧹 Clean Up

The sample resources live in the selected infrastructure resource group. Remove the sample deployment or clean up the infrastructure resource group after experimenting to stop Azure OpenAI and APIM charges.

## 🔗 Additional Resources

- [Backends in API Management](https://learn.microsoft.com/azure/api-management/backends)
- [Authenticate and authorize access to LLM APIs by using API Management](https://learn.microsoft.com/azure/api-management/api-management-authenticate-authorize-ai-apis)
- [Diagnostic settings in Azure Monitor](https://learn.microsoft.com/azure/azure-monitor/platform/diagnostic-settings)
- [Azure Event Hubs documentation](https://learn.microsoft.com/azure/event-hubs/)
- [Azure OpenAI quotas and limits](https://learn.microsoft.com/azure/ai-services/openai/quotas-limits)
