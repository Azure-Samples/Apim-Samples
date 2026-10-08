# Samples: Azure OpenAI v1 Migration

Create PAYG Azure OpenAI resources, establish a dated legacy API and smoke-test it, then add and test a v1 API alongside it. Finish by rerunning the original legacy request unchanged. No pre-existing Azure OpenAI resource, provisioned throughput (PTU), approved inventory or manually supplied keys is required.

⚙️ **Supported infrastructures**: SIMPLE_APIM, APPGW_APIM, APPGW_APIM_PE, AFD_APIM_PE. APIM_ACA is unsupported.

👟 **Expected *Run All* runtime (excl. infrastructure prerequisite): ~10-20 minutes**, depending on Azure provisioning and RBAC propagation.

## 🎯 Objectives

1. Deploy a sample-owned PAYG account with two different models and two model-specific singleton backend pools.
1. Establish the deployment-in-path, dated `api-version` legacy contract before adding v1.
1. Demonstrate the v1 model-in-body contract with unchanged request bodies and managed identity authentication.
1. Exercise both pools through legacy and v1, then repeat both unchanged legacy requests after adding v1.
1. Compare sanitized routing, latency and token evidence with the same test-summary and chart/report helpers used by the AOAI peer samples.

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

Both policies derive the backend pool name by appending `-pool` to the caller's deployment name. There is no dictionary, gateway allowlist, per-model `choose` branch or default-pool fallback. New deployments must have a matching `<deployment-name>-pool` backend; adding one does not require changing these policies. This sample deliberately provisions two distinct enum models. Legacy reads the deployment from the URL without body parsing. v1 parses JSON once with `preserveContent: true` to obtain its `model` selector, but never serializes or rewrites the body.

If the derived pool does not exist, APIM fails the request and `on-error` traces the gateway failure and returns a fixed JSON error. It does not send the request to another pool. Once a pool resolves, Azure OpenAI validates the unchanged deployment selector, API version and payload. This is not per-model authorization: APIM subscriptions and inherited authentication remain the caller gate. Naming alone does not restrict callers to this sample's pools; use a separate authorization design if consumers must be restricted to particular deployments or pools on a shared gateway.

The sample treats `/<sample>/openai` as the established API and adds `/<sample>/openai/v1` alongside it. The existing public path and display name do not label it as "legacy"; that term only distinguishes the dated contract in the sample narrative and internal resource IDs. The sample prefix isolates the sample from gateway-wide routes. It does not modify existing production APIs or global policies.

## 🛩️ Lab Components

- One deterministic Azure OpenAI `S0` account with local key authentication disabled.
- Two PAYG `GlobalStandard` deployments by default, or `Standard` when explicitly configured. No PTU resources or simulated PTU tiers.
- Defaults are `AzureOpenAIModel.GPT_5_MINI` and `AzureOpenAIModel.GPT_5_NANO`, snapshot `2025-08-07`, each with capacity `10`. Capacity uses model-specific quota conversion; ensure both allocations are available.
- Deployment names are `<sample>-<model>` and pools are `<sample>-<model>-pool`, for example `aoai-v1-migration-1-gpt-5-mini-pool` and `aoai-v1-migration-1-gpt-5-nano-pool`. Dots in model names become hyphens in resource identifiers.
- Each pool contains one dedicated `<sample>-<model>-backend` targeting the shared sample Azure OpenAI account. This demonstrates model routing, not load balancing.
- Two API-scoped subscriptions and an OpenAI User role assignment for APIM managed identity.
- Existing APIM, Application Insights and Log Analytics infrastructure remains shared; no duplicate monitoring resources or diagnostic settings are deployed.
- Sample-local [migration_helpers.py](migration_helpers.py) handles configuration validation, key selection, response normalization and bounded readiness retries. Notebook cells retain the visible deployment sequence, requests and assertions.

Policies do not replay requests automatically. Streaming is passed through, but the lab smoke tests cover **non-streaming Chat Completions only**, not Responses, SDK integration, resilience or production migration readiness. The sample does not enable request/response body logging; inherited infrastructure policy/logging settings still apply.

`forward-request` explicitly sets `fail-on-error-status-code="false"` so backend HTTP 400-599 remain ordinary responses. `outbound` traces them without changing their status, body or headers, including `Retry-After`. Forcing them into `on-error` can replace a backend 404 with a gateway 500. Both error paths produce sanitized `AoaiMigrationError` traces containing contract, request ID, status and error source/reason only. `on-error` handles gateway failures: a `Timeout` without a backend error response maps to 504, `BackendConnectionFailure` to 502, and other failures, including missing pools and JSON parsing failures, to 500. The API policy returns an `error` object with code `gateway_error` and a fixed message. Native APIM gateway errors can instead have integer `statusCode` and string `message` fields; the helper validates either format without logging response text. A native error's code must match the HTTP status and its message must be non-empty. A missing pool is a gateway configuration error, distinct from Azure OpenAI's deployment-not-found HTTP 404. Inherited policies can still modify responses. An error after streaming response headers have been sent cannot replace the caller's already-started response.

## ⚙️ Configuration

1. Open [create.ipynb](create.ipynb) using the repository notebook environment.
1. Adjust the top **USER CONFIGURATION** if necessary. Defaults select `SIMPLE_APIM`, `BASICV2`, East US 2, `index = 1`, and namespace `aoai-v1-migration-1`.
1. Use `NotebookHelper`'s standard selection/creation workflow if the desired APIM infrastructure is absent. No Azure OpenAI inventory must be prepared beforehand.
1. Check regional availability/quota before changing `primary_model`, `secondary_model`, `model_sku` or the per-model `model_capacity`. Select two different enum models; use the enum's `.version`, not a guessed snapshot.
1. Run cells in order: deploy legacy → legacy baseline → add v1 → v1 success/rejection → unchanged legacy regression.

Subscription keys come from the shared API module's deployment outputs and are selected without logging. Never paste them into notebook configuration or commit executed notebook outputs.

## 🖼️ Expected Results

The notebook records six successful probes: both models through legacy before v1 exists, both through v1, and both through the original legacy requests after v1 is added. Before each model's **Legacy Before** measurement, it validates one successful warm-up request, discards its evidence, and sends an identical second request through the same client. Only that second successful request appears in the evidence table and chart. Each warm-up and measured request asserts HTTP 200, a non-empty completion, the exact `x-migration-backend-pool` response header, and the backend's actual `model` snapshot (`<model-name>-<version>`). HTTP 200 alone is not sufficient routing evidence. The policy overwrites the sample-owned header after inherited outbound processing.

A seventh probe supplies an unknown v1 deployment name, which derives a nonexistent pool and expects a JSON HTTP 500 gateway error, not a completion from a fallback pool. This intentional negative probe makes one attempt without readiness retries. Generated completion wording is not expected to be identical.

The final verification cell produces:

- An `ApimTesting` summary with 26 checks covering HTTP status, completion shape, exact pool/model identity and expected rejection.
- A `TableLogger` evidence table with status, readiness attempts, response time in milliseconds and prompt/completion/total tokens.
- Two shared `charts.BarChart` latency charts, one per model, showing **Legacy Before**, **v1** and **Legacy After**. The expected HTTP 500 rejection is labeled in the table rather than plotted as an operational failure.
- A self-contained `HtmlReport` saved under the repository's ignored `tmp/` folder as `<sample_name>-report.html`, with the same table, verified routing and embedded charts.

Measurements describe the **final response** of each measured probe. Warm-up requests, earlier readiness attempts and waits are excluded from recorded latency and token counts. Attempt counts include only the measured phase, never the warm-up phase. Missing latency/token fields remain empty rather than becoming zero. No keys, prompts or completion content are saved. Three successful probes per model do not establish a performance baseline or compare model quality.

This deliberately reuses the peer samples' test, table, chart and local-report building blocks, not their scope. Unlike [Costing](../costing/README.md), it does not generate showback traffic, exercise Responses/streaming modes or allocate costs. Unlike [Inference Failover](../inference-failover/README.md), it does not pressure capacity, introduce retry policies or deploy a telemetry workbook. The legacy baseline must precede adding v1, so that verification remains between the two deployment stages; all charts and reporting run together at the end without telemetry polling.

### Results and Reruns

Stage two reuses the legacy API definition and verifies that its subscription key is unchanged. Deterministic names make deployments incremental and rerunnable. Stage one resets old smoke evidence; stage two requires successful new baselines for both pools. Rerunning stage one after stage two **does not remove** v1, because incremental deployments do not delete omitted resources. Use a new namespace for a fresh legacy-only sample.

Each warm-up or measured request has a separate readiness budget of six attempts and 180 seconds of scheduled waits. A **Legacy Before** probe can therefore make up to 12 requests with 360 seconds of scheduled waits across both phases; normally it makes two successful requests. Other successful probes normally make one request, and the negative probe never retries. Warm-ups and retries are still billable; they are not an APIM retry/failover policy. If propagation takes longer, resolve the issue and rerun the affected smoke cell.

See [RUNBOOK.md](RUNBOOK.md) for failures, cleanup and optional existing-workspace queries.

## 🧹 Clean Up

Follow [sample-only cleanup](RUNBOOK.md#clean-up) when sharing an infrastructure. If the entire infrastructure resource group is disposable, use that infrastructure's cleanup notebook instead. PAYG inference is billed per usage; APIM and other infrastructure resources can continue accruing charges independently.

## 🔗 Additional Resources

- [Azure OpenAI v1 API](https://learn.microsoft.com/azure/ai-foundry/openai/api-version-lifecycle)
- [Azure OpenAI deployment types](https://learn.microsoft.com/azure/ai-foundry/openai/how-to/deployment-types)
- [Azure OpenAI role-based access](https://learn.microsoft.com/azure/ai-foundry/openai/how-to/role-based-access-control)
- [Python helper architecture](../../shared/python/README.md)
