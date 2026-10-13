# Azure OpenAI v1 Migration Runbook

## Run the Lab

1. Configure the top cell in [create.ipynb](create.ipynb). No existing Azure OpenAI accounts, PTU inventory, manual keys or approval records are needed.
1. Deploy stage one. It creates two PAYG model deployments and four APIM singleton pools (simple and advanced pairs) in one sample account, grants APIM managed identity access and installs only the simple legacy API.
1. Run both legacy baselines. Each model first makes a validated warm-up request that is excluded from measurements, then an identical second request through the same client. Only the second successful response is recorded as **Legacy Before**. Do not add v1 until HTTP 200, a completion, the model snapshot and the exact pool header are asserted for each model.
1. Deploy stage two with all four API definitions, then test both simple v1 model/pool pairs and the gateway's missing-pool rejection.
1. Run both final legacy regressions with the original request bodies, paths and key.
1. Run the advanced probe cell using the advanced APIs' own subscription keys. Both models must succeed on advanced legacy and v1 through `<deployment-name>-advanced-pool`, with the exact snapshot and `X-Backend-Retry` in `0..2`. The advanced v1 unknown-model probe must reject with HTTP 500. These are singleton-pool contract checks, not injected-failure or regional-recovery tests.
1. Run the final evidence cell to print the shared test summary and token/latency table, display the two model-specific charts, and save a local HTML report under the repository's ignored `tmp/` folder.

## Troubleshooting

- **Deployment authorization failure:** the deployment principal needs resource deployment permissions plus `Microsoft.Authorization/roleAssignments/write`. Contributor alone is insufficient.
- **RequestConflict on a model deployment:** Azure OpenAI can reject concurrent deployment changes on the same parent account. The template uses `@batchSize(1)` to deploy the two models sequentially. If another notebook or portal operation is still changing the account, wait for it to finish, then rerun the failed deployment cell. Incremental deployment retains resources already created; no deletion is required.
- **Model or quota deployment failure:** verify both enum snapshots, regional availability and quota for `GlobalStandard` or `Standard`. Capacity is allocated per model. Reduce capacity or choose two eligible models in USER CONFIGURATION, then rerun stage one. No PTU purchase is required.
- **HTTP 401/403:** check APIM system-assigned identity, the account-scoped Cognitive Services OpenAI User assignment and propagation. Keys must come from the matching API's deployment output, not Azure OpenAI. The bounded readiness retry may expire before RBAC propagation finishes; rerun the cell later.
- **HTTP 404:** check gateway ingress and model provisioning. For resolved pools, Azure OpenAI validates the caller-selected deployment and returns its own errors unchanged. v1 uses the sample-owned namespace, not gateway-wide `/openai/v1`.
- **HTTP 500 for an unknown pool:** the policy appends `-pool` to the caller's deployment/model selector. If that backend does not exist, `on-error` traces the failure and returns JSON with code `gateway_error`; it does not use another pool. This is the intentional negative probe's expected result. For a valid selector, confirm the matching pool exists and inspect the sanitized trace for the actual gateway error reason.
- **Native APIM error response:** gateway failures can return `{"statusCode": 500, "message": "Internal server error"}` instead of the API policy's OpenAI-style `error` object. The helper accepts either error format, but a native response must have an integer `statusCode` matching the HTTP error status and a non-empty string `message`. Empty, mismatched or malformed error bodies still fail. No response text is logged or retained by the helper.
- **HTTP 429:** wait for quota recovery or adjust available PAYG capacity. Smoke retries are bounded and do not certify throughput.
- **Advanced HTTP 503:** the inference-failover policy normalizes terminal infrastructure responses and handled transport failures to 503. Its singleton advanced pool may have no eligible destination after the circuit breaker trips. Wait for its one-minute trip duration or backend `Retry-After`, resolve the failure, and rerun. There is no alternate region or deployment in this lab.
- **Missing or malformed `X-Backend-Retry`:** rerun Cell 4 and stage two to deploy the advanced policies, then use the matching advanced API path and key. The smoke helper requires `0`, `1` or `2` on advanced successes; client readiness attempts are separate. A successful smoke run need not exercise a retry.
- **HTTP 400:** check the caller's API version or JSON payload. For resolved pools, Azure OpenAI performs validation; APIM does not enforce a single model/version. A v1 JSON parsing failure occurs at the gateway and returns a traced HTTP 500 JSON error instead.
- **Timeout or transport error:** verify infrastructure ingress, DNS and outbound access. Sessions are closed on failure. No remote deployment/test is performed by the offline unit tests.
- **HTTP 200 without completion content:** increase `max_completion_tokens` for reasoning models, check content filtering, and rerun. The helper refuses to report a successful completion for malformed/empty content.
- **Unexpected pool or model:** rerun Cell 4 and both deployment stages to replace stale routing data. The expected pool is `<sample>-<model>-pool`; the expected response model is the enum's exact `<model-name>-<version>` snapshot. A missing header or mismatched model fails even on HTTP 200. Check deployed API policies and deployment names rather than weakening the assertions.
- **Stale scalar model parameters:** older kernels may retain `modelName`, `modelVersion` and `modelCapacity`. Rerun Cell 4 to build the new `models` array before deploying; the notebook rejects these obsolete parameters before calling Azure.

Do not save notebook outputs containing keys, prompts, completions or deployment details. Clear outputs and execution counts before sharing. The local report excludes keys and request/response bodies, but does include model snapshots and sample pool names; review it before sharing outside your lab.

The simple policies preserve backend HTTP 400-599 through `outbound` because `forward-request` sets `fail-on-error-status-code="false"`. This avoids promoting an ordinary backend response to a gateway error and losing its status, such as an unknown-deployment 404 becoming 500. Inspect the sanitized `AoaiMigrationError` trace in the existing APIM diagnostics, subject to trace verbosity/sampling. It records contract, request ID, HTTP status and fixed error identifiers, not bodies, credentials or model selectors. Simple outbound tracing does not modify backend status, body or headers; inherited policies can still modify responses. Simple `on-error` maps `Timeout` and `BackendConnectionFailure` to 504 and 502 respectively; other failures map to 500. Advanced APIs instead use the [retry/error matrix](README.md#parallel-advanced-apis), including terminal infrastructure and handled transport normalization to 503. Already-started streaming responses cannot be replaced.

## Rerun Semantics

Deployments are incremental with deterministic account, deployment, backend, API and role-assignment names. Keep `sample_name` fixed to update the same sample instance. A changed namespace creates a separate sample instance and does not clean up the previous one.

Stage one supplies only simple legacy. On a fresh namespace this ensures legacy is installed and tested before v1 exists. On a previously completed namespace it does not delete simple v1 or advanced APIs. Stage two keeps legacy's API definition intact and adds the other three APIs; the notebook asserts the legacy subscription key remains stable.

There is no global policy merge or enterprise fault-gate workflow. Do not use complete-mode deployment on a shared resource group.

Simple contracts derive `<deployment-name>-pool` directly; advanced contracts derive `<deployment-name>-advanced-pool`. Neither uses dictionaries, per-model `choose` statements or fallback pools. Simple v1 reads JSON once solely for routing. Advanced policies also inspect `stream` to prevent replay; all preserve the original body. Missing or non-string selectors cannot select a configured sample pool; malformed JSON fails during parsing. Gateway failures are handled in `on-error`, not silently routed to another deployment. Incremental updates do not delete older model deployments or backends. Remove unused resources from earlier revisions explicitly, after confirming no other caller uses them.

## Optional Observability

Notebook evidence is available immediately from the completed probes. The local report uses the same shared `HtmlReport` and `charts.BarChart` components as Inference Failover, with console tables like Costing. HTTP 500 for the unknown model is labeled **Expected rejection**. Each model's first successful legacy request is a warm-up; the second successful request supplies **Legacy Before**. Latency and token counts exclude warm-ups, earlier readiness attempts and wait time. Attempt counts include only the measured phase. Warm-up and measured phases each have a separate bounded retry budget and reuse one client, which closes even if either phase fails. Missing measurements are empty; if an older in-memory result has no timing, the helper warns and skips that model's chart. Rerun its probes rather than treating missing timing as zero.

Run [migration-requests.kql](queries/migration-requests.kql) in the infrastructure's existing Log Analytics workspace after ingestion. Replace the namespace in the query if customized. It summarizes request counts, status and latency without reading bodies or keys. The lab does not create monitoring components, duplicate diagnostic settings or enable sensitive body logging.

KQL is optional and is not a prerequisite or approval gate for notebook execution.

## Clean Up

HTTP clients close deterministically on success and exceptions. Persistent Azure resources remain until explicitly removed; the notebook does not tear down a shared gateway.

For **sample-only cleanup**, use the Azure portal in the resource group selected by `nb_helper`:

1. In APIM, delete APIs `<sample>-legacy`, `<sample>-v1`, `<sample>-legacy-advanced` and `<sample>-v1-advanced`, and their sample subscriptions (`api-<api-name>`, as created by the shared API module).
1. Delete both simple `<sample>-<model>-pool` and both advanced `<sample>-<model>-advanced-pool` backends, then their singleton `<sample>-<model>-backend` and `<sample>-<model>-advanced-backend` members. The `modelDeployments` output lists exact names, including `advancedBackendName` and `advancedPoolName`. Earlier revisions created `<sample>-openai` and named values `<sample>-deployment`, `<sample>-legacy-version`, and `<sample>-model-alias`; if unused, remove those too. Incremental redeployment does not delete them.
1. At the sample Azure OpenAI account, remove its APIM OpenAI User role assignment, then delete the account (including both model deployments and any unused older `<sample>` deployment). Obtain the exact account name from deployment output `openAiAccountName`; do not delete other samples' accounts.
1. If abandoning the lab entirely, remove its resource-group deployment history records and locally generated parameters if they contain subscription outputs. Do not remove shared infrastructure resources.

If the entire resource group is disposable, use the selected infrastructure's cleanup notebook. Never delete a shared group merely to remove this sample.

## Validation Scope

Offline tests verify two-model defaults, isolated singleton pool IaC, ten successes and two expected rejections, stage ordering, XML contracts, peer retry-matrix alignment, streaming replay guards, retry-header validation and client cleanup. Bicep compilation and XML parsing cannot prove APIM policy runtime behavior, regional model availability, RBAC propagation or live inference. Validate those by running the notebook in your own Azure sample environment. Successful advanced smoke probes do not certify recovery, circuit-breaker timing or streaming behavior under backend failures.
