# Azure OpenAI v1 Migration Runbook

## Run the Lab

1. Configure the top cell in [create.ipynb](create.ipynb). No existing Azure OpenAI accounts, PTU inventory, manual keys or approval records are needed.
1. Deploy stage one. It creates two PAYG model deployments and two singleton pools in one sample account, grants APIM managed identity access and installs the legacy API.
1. Run both legacy baselines. Do not add v1 until HTTP 200, a completion, the model snapshot and the exact pool header are asserted for each model.
1. Deploy stage two with both API definitions, then test both v1 model/pool pairs and the gateway's missing-pool rejection.
1. Run both final legacy regressions with the original request bodies, paths and key.

## Troubleshooting

- **Deployment authorization failure:** the deployment principal needs resource deployment permissions plus `Microsoft.Authorization/roleAssignments/write`. Contributor alone is insufficient.
- **RequestConflict on a model deployment:** Azure OpenAI can reject concurrent deployment changes on the same parent account. The template uses `@batchSize(1)` to deploy the two models sequentially. If another notebook or portal operation is still changing the account, wait for it to finish, then rerun the failed deployment cell. Incremental deployment retains resources already created; no deletion is required.
- **Model or quota deployment failure:** verify both enum snapshots, regional availability and quota for `GlobalStandard` or `Standard`. Capacity is allocated per model. Reduce capacity or choose two eligible models in USER CONFIGURATION, then rerun stage one. No PTU purchase is required.
- **HTTP 401/403:** check APIM system-assigned identity, the account-scoped Cognitive Services OpenAI User assignment and propagation. Keys must come from the matching API's deployment output, not Azure OpenAI. The bounded readiness retry may expire before RBAC propagation finishes; rerun the cell later.
- **HTTP 404:** check gateway ingress and model provisioning. For resolved pools, Azure OpenAI validates the caller-selected deployment and returns its own errors unchanged. v1 uses the sample-owned namespace, not gateway-wide `/openai/v1`.
- **HTTP 500 for an unknown pool:** the policy appends `-pool` to the caller's deployment/model selector. If that backend does not exist, `on-error` traces the failure and returns JSON with code `gateway_error`; it does not use another pool. This is the intentional negative probe's expected result. For a valid selector, confirm the matching pool exists and inspect the sanitized trace for the actual gateway error reason.
- **Native APIM error response:** gateway failures can return `{"statusCode": 500, "message": "Internal server error"}` instead of the API policy's OpenAI-style `error` object. The helper accepts either error format, but a native response must have an integer `statusCode` matching the HTTP error status and a non-empty string `message`. Empty, mismatched or malformed error bodies still fail. No response text is logged or retained by the helper.
- **HTTP 429:** wait for quota recovery or adjust available PAYG capacity. Smoke retries are bounded and do not certify throughput.
- **HTTP 400:** check the caller's API version or JSON payload. For resolved pools, Azure OpenAI performs validation; APIM does not enforce a single model/version. A v1 JSON parsing failure occurs at the gateway and returns a traced HTTP 500 JSON error instead.
- **Timeout or transport error:** verify infrastructure ingress, DNS and outbound access. Sessions are closed on failure. No remote deployment/test is performed by the offline unit tests.
- **HTTP 200 without completion content:** increase `max_completion_tokens` for reasoning models, check content filtering, and rerun. The helper refuses to report a successful completion for malformed/empty content.
- **Unexpected pool or model:** rerun Cell 2 and both deployment stages to replace stale routing data. The expected pool is `<sample>-<model>-pool`; the expected response model is the enum's exact `<model-name>-<version>` snapshot. A missing header or mismatched model fails even on HTTP 200. Check deployed API policies and deployment names rather than weakening the assertions.
- **Stale scalar model parameters:** older kernels may retain `modelName`, `modelVersion` and `modelCapacity`. Rerun Cell 2 to build the new `models` array before deploying; the notebook rejects these obsolete parameters before calling Azure.

Do not save notebook outputs containing keys, prompts, completions or deployment details. Clear outputs and execution counts before sharing.

Backend HTTP 400-599 pass through `outbound` because `forward-request` sets `fail-on-error-status-code="false"`. This avoids promoting an ordinary backend response to a gateway error and losing its status, such as an unknown-deployment 404 becoming 500. Inspect the sanitized `AoaiMigrationError` trace in the existing APIM diagnostics, subject to trace verbosity/sampling. It records contract, request ID, HTTP status and fixed error identifiers, not bodies, credentials or model selectors. The outbound trace does not modify backend status, body or headers; inherited policies can still modify responses. `on-error` traces gateway failures: `Timeout` and `BackendConnectionFailure` without a backend error response map to 504 and 502 respectively; other failures map to 500. Already-started streaming responses cannot be replaced.

## Rerun Semantics

Deployments are incremental with deterministic account, deployment, backend, API and role-assignment names. Keep `sample_name` fixed to update the same sample instance. A changed namespace creates a separate sample instance and does not clean up the previous one.

Stage one supplies only legacy. On a fresh namespace this ensures legacy is installed and tested before v1 exists. On a previously completed namespace it does not delete v1. Stage two keeps legacy's API definition intact and adds v1; the notebook asserts the legacy subscription key remains stable.

There is no global policy merge or enterprise fault-gate workflow. Do not use complete-mode deployment on a shared resource group.

Each contract derives `<deployment-name>-pool` directly, without dictionaries, per-model `choose` statements or fallback pools. v1 reads JSON once solely for routing and preserves the original body. Missing or non-string selectors cannot select a configured sample pool; malformed JSON fails during parsing. Gateway failures are handled in `on-error`, not silently routed to another deployment. Incremental updates do not delete older model deployments or backends. Remove unused resources from earlier revisions explicitly, after confirming no other caller uses them.

## Optional Observability

Run [migration-requests.kql](queries/migration-requests.kql) in the infrastructure's existing Log Analytics workspace after ingestion. Replace the namespace in the query if customized. It summarizes request counts, status and latency without reading bodies or keys. The lab does not create monitoring components, duplicate diagnostic settings or enable sensitive body logging.

KQL is optional and is not a prerequisite or approval gate for notebook execution.

## Clean Up

HTTP clients close deterministically on success and exceptions. Persistent Azure resources remain until explicitly removed; the notebook does not tear down a shared gateway.

For **sample-only cleanup**, use the Azure portal in the resource group selected by `nb_helper`:

1. In APIM, delete APIs `<sample>-legacy` and `<sample>-v1` and their sample subscriptions (`api-<api-name>`, as created by the shared API module).
1. Delete both `<sample>-<model>-pool` backends, then their singleton `<sample>-<model>-backend` members. The `modelDeployments` output lists exact names. Earlier revisions created `<sample>-openai` and named values `<sample>-deployment`, `<sample>-legacy-version`, and `<sample>-model-alias`; if unused, remove those too. Incremental redeployment does not delete them.
1. At the sample Azure OpenAI account, remove its APIM OpenAI User role assignment, then delete the account (including both model deployments and any unused older `<sample>` deployment). Obtain the exact account name from deployment output `openAiAccountName`; do not delete other samples' accounts.
1. If abandoning the lab entirely, remove its resource-group deployment history records and locally generated parameters if they contain subscription outputs. Do not remove shared infrastructure resources.

If the entire resource group is disposable, use the selected infrastructure's cleanup notebook. Never delete a shared group merely to remove this sample.

## Validation Scope

Offline tests verify two-model defaults, singleton pool IaC, the six-success routing matrix, unknown-deployment handling, stage ordering, XML contracts and client cleanup. Bicep compilation and XML parsing cannot prove APIM policy runtime behavior, regional model availability, RBAC propagation or live inference. Validate those by running the notebook in your own Azure sample environment.
