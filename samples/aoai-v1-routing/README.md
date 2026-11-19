# Samples: Azure OpenAI v1 Routing

Route OpenAI v1 Chat Completions and Responses to models hosted in Microsoft Foundry through native APIM backend pools. Compare focused body, header and subscription policies with a recommended endpoint combining header-first selection and validated subscription priority, using shared circuit breakers and sanitized error telemetry. The AI Scenarios category describes sample content, not an APIM SKU; this sample does not require the AI Gateway SKU.

⚙️ **Supported infrastructures**: All infrastructures (`simple-apim`, `apim-aca`, `appgw-apim`, `appgw-apim-pe`, `afd-apim-pe`).

**Category**: AI Scenarios

👟 **Expected _Run All_ runtime (excl. infrastructure prerequisite): ~15-25 minutes**, subject to quota and managed identity propagation.

## 🎯 Objectives

1. Construct model-specific pool identifiers by convention without a model-to-pool lookup table.
1. Route both v1 Chat Completions and Responses without translating their request or success-response formats.
1. Route a header-first request without inspecting or changing its body, including its streaming flag.
1. Compare standard and priority pool families using validated APIM subscription IDs, then combine priority with header-first selection.
1. Reuse concrete backend entities so circuit breaker state is shared across families.
1. Verify actual upstream error identities and correlate sanitized failures in Application Insights.

## ✅ Prerequisites

Start with the [repository prerequisites](../../README.md#prerequisites), plus:

- A supported infrastructure with system-assigned APIM identity and its normal `apim-logger` Application Insights logger. If the configured infrastructure is missing, `NotebookHelper.deploy_sample()` creates it or offers infrastructure creation/selection through the shared workflow.
- Permission to create Microsoft Foundry resources/model deployments and assign the Cognitive Services OpenAI User role to APIM on each account.
- Azure OpenAI access, model availability and PAYG quota in your chosen region for **three accounts**, each containing every selected model. Defaults are `gpt-5-mini` and `gpt-5-nano`, each at capacity 10. Capacity-to-TPM conversion depends on the model.
- Gateway egress to the Foundry resources' OpenAI-compatible endpoints and Microsoft Entra ID. Private gateway ingress does not imply private Foundry egress.
- A gateway/tier supporting native backend pools and circuit breakers. All five repository architectures are supported; this is not a claim that the **APIM Consumption SKU** supports these features.

No provisioned throughput is purchased. Account SKU is `S0`; model deployment SKUs are restricted to `GlobalStandard` or `Standard` PAYG. Names `global-standard`, `ptu` and `consumption` are **simulated semantic tier labels only**. All three destinations are real, distinct Microsoft Foundry resources (`Microsoft.CognitiveServices/accounts`, `kind: 'AIServices'`).

## 📝 Scenario

Four subscription-protected APIs each expose both operations under `/aoai-v1-routing-1/<scenario>/openai/v1`, with one focused API policy per scenario:

- `POST /chat/completions`, using the Chat Completions request and response contract.
- `POST /responses`, using the Responses request and response contract.

Both operations share the same scenario's subscriptions, backend pools and policy fragments:

- **body** ([body.xml](apim-policies/body.xml)) reads the JSON model deployment name and constructs `aoai-v1-routing-1-<model>-standard-pool`. It does not evaluate routing headers or priority entitlements.
- **header** ([header.xml](apim-policies/header.xml)) chooses the first nonempty `x-ai-model` header value and always uses the standard family. When present, the header bypasses **all body reads**, even validation or stream detection. Empty/whitespace header values fall back to body selection. An invalid nonempty header does not fall back.
- **subscription** ([subscription.xml](apim-policies/subscription.xml)) reads the body model and chooses the standard or priority family using only `context.Subscription.Id`. It does not evaluate routing headers.
- **recommended** ([recommended.xml](apim-policies/recommended.xml)) combines the same header-first selection/body fallback with the same validated subscription-based family selection. It has its own API-scoped standard and priority subscriptions; the subscription route's keys do not authorize this API.

The subscription-aware APIs each allow only their configured standard and priority subscription IDs. Other valid subscriptions, including all-APIs/admin subscriptions, do not gain access by display name or caller headers. The two header-first APIs never rewrite the body model: it must name a deployment available on the selected upstream, and mismatches remain the caller's responsibility. The recommended endpoint combines the sample's routing techniques; it does not add per-model authorization or replace production identity-based access controls.

Every model has the **same deployment name on every account**, equal to its model selector. Pool names are constructed by convention, with syntax/length validation but **no model membership set or model-to-pool lookup**. Adding/removing model records changes resources through data, without Python/XML model-specific branches or routing lookups. A syntactically valid unknown selector reaches native route resolution just like a configured selector.

Routing uses the matched APIM operation's `UrlTemplate`, so `/responses` is forwarded to `/openai/v1/responses`, not `/chat/completions`. Unmatched query parameters are dropped on both pathways, preserving the existing v1 forwarding behavior. Request bodies are preserved: Chat Completions uses `messages`; Responses can use string or array `input`. The backend owns operation-specific schema validation.

This sample exposes the two **POST creation operations**, not the full Responses resource lifecycle. Native pool selection provides no account affinity for `previous_response_id` or stored-response retrieval. Responses probes therefore send `store: false` and provide their input directly. For multi-turn usage, send client-held conversation context in `input`; account-affine server-side state requires a separate routing design.

The standard family uses priorities `[1, 2, 1]` and weights `[3, 1, 1]` for global-standard/ptu/consumption labels. The priority family uses priorities `[2, 1, 1]` and weights `[1, 3, 1]`. Lower numeric priority is preferred; weights matter **within the eligible priority group**. Thus standard favors global-standard over consumption, with ptu as fallback; priority favors ptu over consumption, with global-standard as fallback. No tiny probe set proves the statistical distribution.

### Policy Composition

Endpoint policies show only applicable choices. There are no runtime scenario switches: `scenario` is a fixed telemetry label, set after inherited inbound policies and reset in each endpoint's error section so inherited failures retain the correct label. Deployment selects the policy file; a request never selects a scenario branch inside a shared policy.

The sample-local [fragments](apim-policies/fragments/) share these mechanics:

| Fragment                                                                   | Responsibility                                                               |
| -------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| [body-model.xml](apim-policies/fragments/body-model.xml)                   | Validate common v1 fields in a preserved body; select its model.             |
| [header-model.xml](apim-policies/fragments/header-model.xml)               | Read the first nonempty header without touching the body.                    |
| [subscription-family.xml](apim-policies/fragments/subscription-family.xml) | Select the family using the endpoint's configured subscription IDs.          |
| [route-request.xml](apim-policies/fragments/route-request.xml)             | Resolve the model pool, preserve the matched operation and authenticate.     |
| [safe-response.xml](apim-policies/fragments/safe-response.xml)             | Add correlation/pool evidence and sanitize upstream errors.                  |
| [safe-error.xml](apim-policies/fragments/safe-error.xml)                   | Classify scoped resolver/connectivity failures and trace bounded reasons.    |

Endpoints initialize `errorCode`, `errorStatus` and `family`; subscription-aware endpoints also supply fixed standard/priority IDs. Model selection sets `model`; shared routing validates it before resolving a pool. Fragments, pools and subscriptions use the fixed `aoai-v1-routing-1` prefix, with literal resource references in the XML. Bicep deploys the XML unchanged and creates fragments through the existing shared module before their API references. No fragment includes another fragment, which APIM does not support. Header/body fallback remains visible in the two endpoint policies where it applies.

The shared modules deploy policies and fragments with APIM's `rawxml` format, so expressions use readable C# such as `As<JObject>()`, `&&` and `>=` rather than XML entities. These are native APIM policy documents, not strict XML for a general-purpose XML validator. Structural tests encode expression attributes only in memory; deployment loads the source files unchanged. See Microsoft's [policy output-format guidance](https://github.com/Azure/azure-api-management-policy-toolkit/blob/main/docs/OutputFormat.md).

## 🛩️ Lab Components

![Routing topology showing separate body, header and subscription routes plus a recommended header-first, subscription-aware route selecting pools for gpt-5-mini and gpt-5-nano across three Microsoft Foundry resources.](../../assets/diagrams/Azure-OpenAI-v1-Routing.svg)

The visual shows the default two-model configuration: **four APIs, four pools, six concrete backends and six model deployments across three accounts**. The recommended API reuses the same pools, backends and deployments; no additional model capacity is purchased. Each model lane repeats the same three accounts for readability; it does not represent additional accounts. Solid and dashed pool connections distinguish standard and priority membership, not separate request attempts.

Read each path from **route -> selected model and family -> pool -> concrete backend -> model deployment**. Pool member labels use `P` for priority and `W` for weight: lower `P` wins, and `W` applies only within the eligible priority group. Both families share each concrete backend's circuit breaker. The header route selects the pool but does not rewrite the body's model; the caller must keep it compatible with the selected account.

The editable [Draw.io source](../../assets/diagrams/Azure-OpenAI-v1-Routing.drawio) accompanies the SVG. Names omit the common `aoai-v1-routing-1-` prefix for space; deployment names are the model selectors without that prefix.

Each notebook section opens with a one-sentence recap of the current state and next step, followed by its purpose and expected outcome. This written walkthrough covers configuration, deployment, successful routing, local rejections, upstream rejections and telemetry without inline section diagrams; the full topology above remains an optional reference.

- Three Microsoft Foundry resources with system-assigned identities, project management enabled, identical PAYG model deployment lists, and APIM managed-identity RBAC. Local API-key authentication is disabled.
- One concrete backend per account/model, shared by both pool families and all four APIs. Breakers trip on 429/500-504; deployment mismatch 404 does not trip them.
- Two native, three-member pools per model, with distinct real account endpoints.
- Four APIs with two POST operations each, created with the shared API module and six sample-local policy fragments, preserving subscription authentication and inherited inbound policies.
- Sample-owned API diagnostics referencing the existing logger at **verbose** level, 100% sampling and `allErrors`, with header/body capture disabled. No LLM content logging is enabled.

The backend policy sends **one attempt, with no retries**, for every scenario. This avoids replaying header-first streaming requests whose stream state is intentionally unknown and avoids duplicate generation/billing for POSTs. Breakers affect subsequent native pool selections; this sample does not promise immediate retry/failover. `forward-request` has a 60-second timeout and unbuffered responses.

If a selected backend does not respond within that limit, the policy returns 504 `UpstreamTimeout`, not a generic 500 or a missing-model 404. Cell 7 includes the sanitized `ProbeResult` in a failed assertion, including its error code and request ID. Use that ID to inspect `LastErrorReason`, `LastErrorSource`, `LastErrorSection`, `BackendId` and `BackendTime` in gateway diagnostics; no prompts or keys are needed. A provisioned model does not guarantee every inference completes within the timeout. The sample deliberately fails instead of silently retrying or increasing the timeout.

Body-read paths parse, validate and select the model in one C# block with one preserved request-body deserialization. Only a compact `bodySelection` result containing the model, error code and error status is retained in context; the full parsed payload stays local to the block. Short policy assignments expose the result without reading or casting the payload again. Header-present paths do not parse the body. Common validation requires a JSON object, a string model selector and a boolean stream if present. Missing/null models return local 404 `ModelNotAvailable`; non-string models return local 400 `InvalidRequest`. Unlike the earlier Chat Completions-only version, the fragment does not require `messages` or validate `input`: operation-specific payload errors now reach authoritative upstream validation and retain the upstream HTTP status with a sanitized error body.

Both pathways retain unbuffered forwarding and leave successful response bodies unchanged, including streaming responses. The notebook probes validate non-streaming text results; they do not prove live SSE behavior.

### Foundry Hosting and Existing Deployments

[foundry-account.bicep](foundry-account.bicep) creates Foundry resources with `kind: 'AIServices'` and `allowProjectManagement: true`. This inference-only sample does not create projects, hubs, agents or evaluation resources. Model deployments remain account-scoped, use the `OpenAI` model format, and retain their existing selectors and PAYG SKUs.

APIM uses each resource's published OpenAI inference endpoint and appends `/openai/v1`; it does not send requests to a project endpoint or assume that the generic multi-service endpoint supports the same route. The endpoint metadata key contains the word `Legacy`, but the sample calls the current OpenAI v1 API. APIM's managed identity retains the account-scoped **Cognitive Services OpenAI User** role, which permits OpenAI inference without granting broader Foundry capabilities.

For an existing deployment of this sample, the deterministic `oai-r-...` account names, custom subdomains, nested deployment names and role-assignment IDs are preserved. Re-running deployment targets the same accounts for an [in-place upgrade to Foundry](https://learn.microsoft.com/azure/foundry/how-to/upgrade-azure-openai), rather than creating duplicate model capacity. Review organizational policies and regional Foundry support first. If you added private endpoints yourself, follow the upgrade guide's DNS/private-endpoint requirements before redeploying. This change does not perform a live upgrade automatically.

## ⚙️ Configuration

1. Open [create.ipynb](create.ipynb) and select the desired infrastructure, index and APIM SKU.
1. Set the region, model list, capacity and PAYG deployment SKU in **USER CONFIGURATION**. The sample prefix is fixed at `aoai-v1-routing-1`, so each APIM instance hosts one instance of this sample; choose a different infrastructure index for a separate deployment.
1. Run initialization, deployment, success probes, rejection probes and reporting in order. The deployment cell reuses the configured infrastructure when available. Otherwise, the helper creates it when no supported instances exist, or offers to create it or select another supported instance.
1. Do not print deployment outputs or commit generated parameter/output files: shared deployment conventions retain subscription keys locally.

The notebook keeps scenarios, expected outcomes and assertions visible. [routing_helpers.py](routing_helpers.py) owns validated model projection, secret selection and single-request result normalization, composing the existing `ApimRequests` client. Its injected client factory owns cleanup on success and failures. Deployment uses `NotebookHelper`; no parallel Azure command/deployment framework is added.

## 🔍 Results and Telemetry

Successful probes require the requested operation's actual result shape, the convention-selected pool and a request correlation ID. Chat Completions must contain assistant text in `choices`; Responses must be `completed` with assistant `output_text` content in its `output` array, allowing preceding reasoning items. Incomplete Responses and a Chat Completions result returned to a Responses request fail the gate. Generated text is not retained in `ProbeResult`.

Both configured models are exercised across both pathways on all four APIs. The subscription and recommended APIs use identical path/body pairs for their standard/priority comparisons; recommended also covers header-present, empty-header and absent-header paths. Rejection, fallback and upstream mismatch probes run against both operations.

The negative probes check error identities, safe messages and pool evidence, not just status:

- Unknown selectors/missing pools return 404, `model_not_available`, and **The specified model is not available for use** when the scoped resolver fails. Missing/invalid selectors are rejected locally with the same message (`ModelNotAvailable`).
- Malformed/non-object body-read requests, non-string models and non-boolean stream flags return 400, `InvalidRequest`.
- On both header-first APIs, a known header pool with a body naming a deployment absent on **all three accounts** must produce an actual upstream deployment-not-found error (404, `DeploymentNotFound` or `model_not_found`). The body is not rewritten. If Azure changes its error identity, the assertion fails rather than treating any 404 as success.
- A known header with a non-object JSON body reaches upstream validation rather than local `InvalidRequest` on both header-first APIs; this proves the bypass separately from successful requests.

The header fallback probes use an empty string, because the `requests` client rejects whitespace-only header values before sending them. The policy treats both forms as empty; no live claim is made for a whitespace-only header sent through that client.

Upstream failure statuses are preserved. Error bodies retain only allow-listed upstream codes and a fixed safe message; arbitrary upstream text is not forwarded. Every local early return traces **before** `return-response`; outbound HTTP errors and policy failures trace independently. Trace dimensions contain request ID, a fixed scenario, a fixed error category and status. Policy failures additionally retain the original machine-readable `LastError.Reason` only when it matches `^[A-Za-z][A-Za-z0-9]{0,63}$`, otherwise `Other`: no prompts, responses, keys, selectors or `LastError.Message` content.

Use [queries/routing-errors.kql](queries/routing-errors.kql) in Application Insights Logs, replacing `requestId` with `x-routing-request-id` from a probe. The query also joins request telemetry by `operation_Id` without projecting URLs or content. Workspace-native equivalents use `AppTraces`/`AppRequests` and their PascalCase columns. Allow time for ingestion before checking error trace coverage.

### Scoped Unavailable Route Classification and Runtime Gates

The official [error handling reference](https://learn.microsoft.com/azure/api-management/api-management-error-handling-policies) documents `BackendConnectionFailure` for upstream connection failures. Neither it nor the [set-backend-service reference](https://learn.microsoft.com/azure/api-management/set-backend-service-policy) documents an exact missing-backend/pool `LastError.Reason`. **Do not invent `BackendNotFound`, match localized message strings, or translate all gateway errors to missing model.**

The policy precomputes `backendPool` from the syntax-validated selector, fixed `aoai-v1-routing-1` prefix and validated subscription family, then validates the complete identifier's syntax and 80-character bound. Before the resolver, parsing and validation are already finished. The `set-backend-service` expression is only a typed read of that variable, not arbitrary evaluation.

The exact classifier is:

1. Documented `BackendConnectionFailure` takes precedence and returns 503 `UpstreamUnavailable`.
1. `LastError.Reason == "Timeout"` with `LastError.Section == "backend"` returns 504 `UpstreamTimeout` with a fixed safe message. Timeouts in other policy sections do not match this backend-only guard.
1. Otherwise, **all three** must match: `LastError.PolicyId == "resolve-model-pool"`, `LastError.Section == "inbound"`, and `routePhase == "resolve"`. That scoped route-resolution failure returns 404 `model_not_available` with **The specified model is not available for use**.
1. Other policy failures return 500 `GatewayError`. The phase changes to `resolved` immediately after the resolver and before rewriting, managed-identity authentication or forwarding. Those later failures cannot match the unavailable-route guard. No source-name or undocumented reason string is assumed.

This means **the convention-derived route is unavailable**, not proof of an absent Azure model deployment. Actual upstream deployment-not-found responses are handled separately in outbound, preserving their status and safe upstream error identity. Neither a generic gateway failure nor an upstream/MI/auth error is converted to a model 404.

**Precise remaining runtime uncertainty:** the references document `PolicyId` attribution and dynamic backend identifiers, but not whether each gateway build reports a nonexistent native pool synchronously at `set-backend-service` with that ID/section, or defers rejection until forwarding. The former follows the implemented graceful 404 contract; a deferred failure or absent/mismatched attribution deliberately stays a non-404 gateway/connectivity error. The unknown-alias notebook probes assert the expected resolver behavior without deleting resources. A deleted configured pool uses the same resolution path, but its actual attribution still requires a disposable live-Azure acceptance check; never remove shared or existing-sample backends. No destructive probe runs in the notebook.

APIM rejects missing/invalid subscription keys and unmatched operations **before** API policies run. Those requests cannot execute a sample `trace` statement; use the existing logger's request/gateway diagnostics for that coverage. Similarly, inherited policies can short-circuit before sample instrumentation. A claim of sample-policy traces for literally every gateway error is therefore gated by the platform pipeline. Existing/global telemetry settings may capture additional data independently; audit them before sending sensitive traffic.

No live Azure deployment or runtime policy compilation was performed when authoring this sample. Offline XML checks and Bicep builds do not execute APIM expressions, prove quota/RBAC readiness, prove trace ingestion, or verify Azure's current v1 error shape. Notebook assertions are intentional live acceptance gates.

## 🧹 Clean Up

Model removal from an incremental Bicep deployment stops advertising the model but **does not delete** old deployments, backends or pools. Plan and remove those sample-owned resources explicitly to release quota. Do not use complete-mode deployment on the shared infrastructure resource group.

For full cleanup, use the `aoai-v1-routing-1` prefix to identify its APIs, subscriptions, fragments, pools and concrete backends; standard API subscriptions use the shared module's `api-aoai-v1-routing-1-` prefix. Remove APIs before their referenced fragments, and pools before their members. Delete the three account resource IDs in `accountOutputs` to release their model deployments and account-scoped role assignments. Delete only sample-owned resources, never the existing logger, monitoring workspace or APIM service. No automatic notebook cleanup is run against shared infrastructure.

## 🔗 Links

- [APIM backend pools and circuit breakers](https://learn.microsoft.com/azure/api-management/backends)
- [Reusable policy fragments and their limitations](https://learn.microsoft.com/azure/api-management/policy-fragments)
- [Trace policy and Application Insights integration](https://learn.microsoft.com/azure/api-management/trace-policy)
- [Azure OpenAI v1 API lifecycle](https://learn.microsoft.com/azure/ai-foundry/openai/api-version-lifecycle)
- [Azure OpenAI Responses API](https://learn.microsoft.com/azure/foundry/openai/how-to/responses)
- [Microsoft Foundry architecture and resource types](https://learn.microsoft.com/azure/foundry/concepts/architecture)
- [Foundry model deployment and inference endpoints](https://learn.microsoft.com/azure/foundry/foundry-models/how-to/create-model-deployments)
- [Comparable Azure OpenAI v1 Migration sample](../aoai-v1-migration/README.md)
