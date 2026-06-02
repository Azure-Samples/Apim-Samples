# Samples: Inference Failover

This sample uses Azure API Management as an AI Gateway for two Azure OpenAI models, combining priority and weighted backend failover with focused LLM telemetry in Log Analytics and an Azure Monitor Workbook.

⚙️ **Supported infrastructures**: All infrastructures

👟 **Expected *Run All* runtime (excl. infrastructure prerequisite): ~15 minutes**

## 🎯 Objectives

1. Route each model only to compatible Azure OpenAI deployments through model-specific APIM backend pools.
1. Observe priority failover and equal-weight terminal routing when regional `Standard` deployments return `429` or `503` responses.
1. Capture request, latency, and token telemetry through `ApiManagementGatewayLogs` and `ApiManagementGatewayLlmLog`.
1. Use a controlled low-capacity model constellation to generate observable failover without treating simulated PTU tiers as real provisioned deployments.

## ✅ Prerequisites

Beyond the [general prerequisites](../../README.md#-getting-started) (Azure subscription, CLI, Python environment), this sample requires permissions and quota for Azure OpenAI deployments.

- **Cognitive Services Contributor** at resource group scope to create three Azure OpenAI resources and nine regional model deployments.
- **Role Based Access Control Administrator** or equivalent role-assignment permission at resource group scope to assign APIM's managed identity the **Cognitive Services OpenAI User** role.
- Regional model availability and quota in `eastus2`, `westus3`, and `southcentralus` for the requested `gpt-5.1` and `gpt-4.1-mini` `Standard` deployments.

## 📝 Scenario

An AI platform prefers provisioned capacity tiers across its available regions before using pay-as-you-go capacity: in-region PTU, out-of-region PTU, in-region PAYG, then out-of-region PAYG. This lab exercises that routing shape using only regional `Standard` pay-as-you-go Azure OpenAI deployments. Names containing `PTU` identify the simulated preference tier in the experiment and do not change the Azure OpenAI deployment SKU or billing model.

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
- Nine concrete APIM backends named using `<model>-<PTU|PAYGO>-<region>`, each with TLS validation and a one-minute circuit breaker for `429` and `503` responses that accepts `Retry-After`.
- One APIM backend pool per model so a retry never crosses to an incompatible deployment.
- Two AI Gateway APIs with managed identity authentication to Azure OpenAI: `POST /inference/gpt-5-1/chat/completions` retries four times through A -> D -> B -> E/G (equal terminal weights), while `POST /inference/gpt-4-1-mini/chat/completions` retries three times through C -> F -> D -> H.

- Model-specific retry policies that buffer the POST body while retrying throttled or unavailable backends and return a generic `503` when fallback is exhausted.
- APIM AI Gateway diagnostics using the infrastructure-provided Log Analytics workspace and Application Insights component, plus an AOAI-only workbook for terminal outcomes, backend distribution, token usage, and latency.

### Managed Identity And Privacy

The inference API policy authenticates every selected backend request with APIM's system-assigned managed identity and the **Cognitive Services OpenAI User** role. It never stores or forwards an Azure OpenAI API key. For learning and testing, the infrastructure's global APIM policy returns the selected backend URL in the `X-Backend-URL` response header so the notebook can record routing decisions. Disable `revealBackendApiInfo` for production-like environments. If fallback is exhausted, callers receive a generic `503` response without backend identity or placement information.

Gateway ingress exposure follows the selected infrastructure: choose a Private Link or VNet architecture when private ingress is required, while the notebook keeps Simple API Management as its approachable default.

Routine probes intentionally do not perform inference: recurring multi-location model calls would consume request and token budgets while still providing an incomplete capacity signal. The notebook harness sends explicit inference traffic when a live readiness or failover observation is needed.

## ⚙️ Configuration

1. Deploy any [infrastructure architecture](../../README.md#list-of-infrastructures), with [Simple API Management](../../infrastructure/simple-apim/README.md) as the notebook default.
1. Open [create.ipynb](create.ipynb) and adjust only values under *USER CONFIGURATION* if necessary.
1. Run all notebook cells to deploy the model constellation, APIs, workbook, controlled inference requests, and telemetry charts.
1. Increase `pressure_requests_per_model` only when the initial traffic does not produce sufficient concentrated pressure for failover observation; requests consume real Azure OpenAI tokens.

## 🖼️ Expected Results

After the traffic cells run and telemetry ingestion completes, the notebook plots terminal outcomes and token usage while the workbook provides longer-lived views of:

- Requests and terminal `503` results by inference API.
- Concrete backend distribution when the APIM gateway log records the resolved backend identity.
- Prompt, completion, and total tokens by model route.
- Backend latency trends during controlled pressure.

## 🧹 Clean Up

The sample resources live in the selected infrastructure resource group. Remove the sample deployment or clean up the infrastructure resource group after experimenting to stop Azure OpenAI and APIM charges.

## 🔗 Additional Resources

- [Backends in API Management](https://learn.microsoft.com/azure/api-management/backends)
- [Authenticate and authorize access to LLM APIs by using API Management](https://learn.microsoft.com/azure/api-management/api-management-authenticate-authorize-ai-apis)
- [Azure OpenAI quotas and limits](https://learn.microsoft.com/azure/ai-services/openai/quotas-limits)
