# Samples: APIM Costing & Showback

This sample demonstrates how to track and allocate API costs using Azure API Management with Azure Monitor, Application Insights, Log Analytics, and Cost Management. It supports three complementary approaches: **subscription-based** tracking (using APIM subscription keys), **Entra ID application** tracking (using the `emit-metric` policy with JWT `appid` claims), and **AI Gateway token/PTU** tracking (using the `ApiManagementGatewayLlmLog` diagnostic to capture per-request token consumption when APIM acts as an AI Gateway, joined with `ApiManagementGatewayLogs` on `CorrelationId` for business unit attribution). All approaches share a single Azure Monitor Workbook with tabbed views.

⚙️ **Supported infrastructures**: All infrastructures (or bring your own existing APIM deployment)

👟 **Expected *Run All* runtime (excl. infrastructure prerequisite): ~15 minutes**

## 🎯 Objectives

1. **Track API usage by caller** - Use APIM subscription keys to identify business units, departments, or applications
2. **Track API usage by Entra ID application** - Use the `emit-metric` policy to extract `appid`/`azp` JWT claims and emit per-caller custom metrics
3. **Capture request metrics** - Log subscriptionId, apiName, operationName, and status codes
4. **Aggregate cost data** - Combine API usage metrics with Azure Cost Management data
5. **Visualize showback data** - Create Azure Monitor Workbooks with tabbed views for both approaches
6. **Enable cost governance** - Establish patterns for consistent tagging and naming conventions
7. **Enable budget alerts** - Create scheduled query alerts when callers exceed configurable thresholds
8. **Track AI token consumption per client** - When APIM is used as an AI Gateway, capture prompt, completion, and total token usage per calling application, enabling per-client cost attribution for PTU or pay-as-you-go OpenAI deployments
9. **Real AOAI interactions via Foundry** (optional) - Deploy a full Microsoft Foundry environment (Hub + Project + Azure AI Services) and route real Azure OpenAI chat completions through APIM, demonstrating accurate token tracking for both non-streaming and streaming (SSE) responses

> **Note on non-OpenAI models**: This sample deploys an Azure OpenAI model only (default: `gpt-5-mini`). Other model families on Azure AI Services - such as Anthropic Claude via the Azure Marketplace - are gated by separate quota that is granted through a manual approval process, which puts them beyond the scope of a self-service sample. If you have approved quota for another provider, you can extend the sample by adding a second deployment in `main.bicep`; the token-tracking policy and workbook queries are model-agnostic.

## ✅ Prerequisites

Beyond the [general prerequisites](../../README.md#-getting-started) (Azure subscription, CLI, Python environment), this sample requires additional Azure RBAC role assignments.

### Azure RBAC Permissions

The signed-in user needs the following role assignments:

| Role                               | Scope           | Purpose                                                                                      |
| ---------------------------------- | --------------- | -------------------------------------------------------------------------------------------- |
| **Contributor**                    | Resource Group  | Deploy Bicep resources (App Insights, Log Analytics, Storage, Workbook, Diagnostic Settings) |
| **Cost Management Contributor**    | Subscription    | Create Cost Management export                                                                |
| **Storage Blob Data Contributor**  | Storage Account | Write cost export data (auto-assigned by the notebook)                                       |
| **Cognitive Services Contributor** | Resource Group  | Deploy Azure AI Services when `enable_foundry = True` (not needed for mock path)             |

### For Workbook Consumers

Users who only need to **view** the deployed Azure Monitor Workbook (not deploy the sample) need:

| Role                     | Scope                   | Purpose                                           |
| ------------------------ | ----------------------- | ------------------------------------------------- |
| **Monitoring Reader**    | Resource Group          | Open and view the workbook                        |
| **Log Analytics Reader** | Log Analytics Workspace | Execute the Kusto queries that power the workbook |

> 💡 If a user can open the workbook but sees empty visualizations, they are likely missing **Log Analytics Reader** on the workspace.

## 📝 Scenario

Organizations often need to allocate the cost of shared API Management infrastructure to different consumers (business units, departments, applications, or customers). This sample addresses:

- **Cost Transparency**: Understanding which teams or applications drive API consumption
- **Chargeback/Showback**: Producing data that can inform internal billing or cost awareness
- **Resource Optimization**: Identifying high-cost consumers and opportunities for optimization
- **Budget Planning**: Historical usage patterns to forecast future costs

### Key Principle: Cost Determination, Not Billing

This sample focuses on **producing cost data**, not implementing billing processes. You determine costs; how you use that information (showback reports, chargeback, budgeting) is a separate business decision.

### Three Tracking Approaches

| Aspect                     | Subscription-Based                           | Entra ID Application                                 | AI Gateway Token/PTU                                       |
| -------------------------- | -------------------------------------------- | ---------------------------------------------------- | ---------------------------------------------------------- |
| **Caller identification**  | APIM subscription key (`ApimSubscriptionId`) | JWT `appid`/`azp` claim                              | JWT `appid`/`azp` claim                                    |
| **Data source**            | `ApiManagementGatewayLogs` in Log Analytics  | `customMetrics` in Application Insights              | `ApiManagementGatewayLlmLog` in Log Analytics              |
| **Tracking mechanism**     | Built-in APIM logging                        | `emit-metric` policy                                 | APIM diagnostic setting (zero-buffering)                   |
| **Metric name**            | N/A (built-in logs)                          | `caller-requests`                                    | N/A (per-request diagnostic log)                           |
| **Cost Management export** | Yes (storage account)                        | No (metrics-based)                                   | No (metrics-based)                                         |
| **Best for**               | Dedicated subscriptions per BU               | OAuth client-credentials flows, shared subscriptions | AI Gateway scenarios (Azure OpenAI, PTU capacity planning) |

All three approaches are deployed together. Toggle `enable_entraid_tracking` and `enable_token_tracking` in the notebook to include or exclude each flow. Setting `enable_foundry = True` adds a real Azure OpenAI backend so token tracking uses actual model responses instead of mock data.

### Streaming Support

When `enable_foundry = True`, the notebook demonstrates both non-streaming and streaming (SSE) chat completions. For streaming, half the requests explicitly send `stream_options.include_usage = true` and half intentionally omit it so the `pf-ensure-stream-include-usage.xml` policy fragment can prove when APIM had to inject the flag (when `force_stream_include_usage` is enabled). Token counts are captured by the APIM `ApiManagementGatewayLlmLog` diagnostic setting with **zero response buffering**, and proof of the policy mutation is recorded in `ApiManagementGatewayLogs.TraceRecords`.

- **Non-streaming**: The gateway logs exact token counts from the JSON response
- **Streaming (SSE)**: The gateway reads token counts from the final SSE chunk (requires `stream_options.include_usage = true`; the sample proves when APIM had to add it)

The workbook surfaces **both** streaming variants side-by-side so you can see exactly how each request acquired the usage object:

- **Streaming (client-supplied usage)** — the client already set `stream_options.include_usage = true`; APIM forwards the request unchanged.
- **Streaming (policy-injected usage)** — the client omitted the flag; the APIM policy fragment injected it and emitted a trace into `ApiManagementGatewayLogs.TraceRecords` (look for `IncludeUsageInjected`).

The **AI Gateway** tab's *Streaming vs Non-Streaming Breakdown* and the **Per-Request Detail** tab's `AI Delivery Mode` + `Usage Provenance` columns both render this distinction, so you can confirm token capture works regardless of whether the client or APIM supplied the usage option.

> **Business unit attribution**: Join `ApiManagementGatewayLlmLog` with `ApiManagementGatewayLogs` on `CorrelationId` to map token counts to `ApimSubscriptionId` (business unit). See `bu-token-usage.kql` for a ready-to-use query.

### Context Propagation

The token tracking policy forwards two headers to the backend:

| Header                     | Value                                 | Purpose                                                |
| -------------------------- | ------------------------------------- | ------------------------------------------------------ |
| `x-business-unit`          | Extracted `callerId` from JWT `appid` | Correlate backend logs with APIM caller metrics        |
| `x-ms-client-request-id`   | `context.RequestId`                   | End-to-end correlation ID across APIM and backend logs |

## 🛩️ Lab Components

This lab deploys and configures:

- **Application Insights** - Receives APIM diagnostic logs for request tracking
- **Log Analytics Workspace** - Stores `ApiManagementGatewayLogs` with detailed request metadata (resource-specific mode)
- **Storage Account** - Receives Azure Cost Management exports
- **Cost Management Export** - Automated export of cost data (configurable frequency)
- **Diagnostic Settings** - Links APIM to Log Analytics with `logAnalyticsDestinationType: Dedicated` for resource-specific tables
- **Sample API & Subscriptions** - 4 subscriptions representing different business units
- **Entra ID Tracking API** (optional) - A second API with the `emit-metric` policy that extracts `appid` from JWT tokens and emits `caller-requests` custom metrics
- **AI Gateway Token Tracking API** (optional) - A third API with inbound caller identity propagation and `stream_options.include_usage` enforcement; token counts are captured by the `ApiManagementGatewayLlmLog` diagnostic setting and correlated to business units via `CorrelationId` join with `ApiManagementGatewayLogs`
- **AOAI Gateway API** (optional, requires `enable_foundry`) - A fourth API that routes real Azure OpenAI chat completions through APIM using a managed-identity-authenticated backend, enabling accurate token tracking against a live model deployment
- **Microsoft Foundry** (optional) - When `enable_foundry = True`, deploys an Azure AI Foundry Hub, Project, Azure AI Services account with a `gpt-5-mini` model deployment, and an APIM backend with managed identity authentication (`Cognitive Services OpenAI User` role)
- **Azure Monitor Workbook** - Pre-built tabbed dashboard with:
  - **Subscription-Based Costing tab**: Cost allocation table (base + variable cost per BU), base vs variable cost stacked bar chart, cost breakdown by API, request count and distribution charts, success/error rate analysis, response code distribution, business unit drill-down
  - **Entra ID Application Costing tab**: Usage by caller ID (bar chart + table), cost allocation by caller (table + pie chart), hourly request trend by caller
  - **AI Gateway Token/PTU tab**: Three rows of summary tiles grouped under **APIM Inbound** (total APIM requests, AI APIM requests, inbound), **AI Backend** (backend requests, successful, throttled, failed), and **Tokens** (total tokens), followed by a request-funnel table, scope-reconciliation explainer + table, token cost allocation table with configurable per-1K-token rates, model and streaming pie charts, streaming vs non-streaming breakdown table, token-share pie, and hourly token-type trend chart
- **SKU-Based Pricing** - Automatically derives base monthly cost, overage rate, and included request allowance from the deployed APIM SKU using built-in pricing data (sourced from the [Azure API Management pricing page](https://azure.microsoft.com/pricing/details/api-management/), March 2026)
- **Budget Alerts** (optional) - Per-BU scheduled query alerts when request thresholds are exceeded

### Workbook Query Optimization

Azure Monitor Workbook query items execute independently — there is no native mechanism to share a materialized table across query items. The workbook applies two patterns to minimise data scanned:

| Pattern | Where applied | Effect |
| ------- | ------------- | ------ |
| **`materialize()` for multi-reference `let` bindings** | Subscription-Based and Entra ID tabs (any query that derives both a `toscalar(count)` total and a per-BU `summarize` from the same base set) | Log Analytics computes the base set once per query execution instead of scanning the underlying table twice |
| **Column-project before joins** | AI Gateway tab (all `ApiManagementGatewayLlmLog ⟕ ApiManagementGatewayLogs` joins) | Each query projects only the columns it needs from both sides of the join, reducing the join's memory and network footprint |

> **Why not a single base query for the AI Gateway tab?** Workbooks cannot share a materialized table across query items. Merge items can combine two already-computed result sets but cannot perform arbitrary re-aggregation. Each AI Gateway visual therefore runs its own join, but column-projecting both sides keeps each join as lean as possible.

### Cost Allocation Model

| Component           | Formula                                              |
| ------------------- | ---------------------------------------------------- |
| **Base Cost Share** | `Base Monthly Cost x (BU Requests / Total Requests)` |
| **Variable Cost**   | `BU Requests x (Rate per 1K / 1000)`                 |
| **Total Allocated** | `Base Cost Share + Variable Cost`                    |

### What Gets Logged

| Field                | Description                                   |
| -------------------- | --------------------------------------------- |
| `ApimSubscriptionId` | Identifies the caller (BU / department / app) |
| `ApiId`              | Which API was called                          |
| `OperationId`        | Specific operation within the API             |
| `ResponseCode`       | Success / failure indication                  |
| Request count        | Number of requests (primary cost metric)      |

> **Important**: The API must have `subscriptionRequired: true` for `ApimSubscriptionId` to be populated in logs. This sample configures it automatically.

## ⚙️ Configuration

### Quick Setup Checklist

Follow these steps to prepare and run the costing sample:

1. **Choose an infrastructure**
   - Select one from the [Infrastructure Architectures][infrastructure-architectures] (or use an existing APIM deployment)
   - If your chosen infrastructure does not yet exist, navigate to its folder under [infrastructure][infrastructure-folder] and follow its README to deploy it first

2. **Configure user parameters** (in the notebook's first code cell, under `USER CONFIGURATION`)
   - **Deployment**: Match `deployment`, `rg_location`, and `index` to your chosen infrastructure
   - **Features to deploy**: Toggle `enable_entraid_tracking`, `enable_token_tracking`, and `enable_foundry` to control which cost-tracking approaches are set up
   - **Traffic to run**: Use `run_regular_requests` and `run_ai_requests` to skip phases if iterating on workbook logic
   - **Optional**: For real Entra ID token testing, set `use_real_jwt = True` and populate JWT credentials (see [Getting Started](../../README.md#-getting-started))
   - **Alerts**: Customize `alert_threshold`, `alert_email`, and `cost_export_frequency` if desired

3. **Run all cells** (`Run All` in Jupyter)
   - Deployment takes ~3–5 minutes (longer if `enable_foundry = True`)
   - Traffic generation takes ~2–3 minutes
   - At the end, the notebook prints Azure portal links — click the workbook link to view your cost dashboard

### What Each Configuration Toggle Does

| Toggle                    | Purpose                                        | Impact if disabled                                               |
| ------------------------- | ---------------------------------------------- | ---------------------------------------------------------------- |
| `enable_entraid_tracking` | Deploy Entra ID JWT tracking API               | No `caller-requests` metrics in Entra ID workbook tab            |
| `enable_token_tracking`   | Deploy AI Gateway token tracking API           | No per-caller token/PTU data in AI Gateway workbook tab          |
| `enable_foundry`          | Deploy real Azure OpenAI via Foundry           | D1 skipped; D2 uses mock instead (adds ~5 min if enabled)        |
| `run_regular_requests`    | Generate BU + Entra ID traffic                 | Workbook Subscription and Entra ID tabs show no data             |
| `run_ai_requests`         | Generate AI traffic (real or mock)             | Workbook AI Gateway tab shows no data                            |
| `create_budget_alerts`    | Deploy per-BU request thresholds               | No budget alerts (Cell B4 creates zero alerts)                   |

## 🖼️ Expected Results

After running the notebook, you will have:

1. **Application Insights** showing real-time API requests and `caller-requests` custom metrics (Entra ID)
2. **Log Analytics** with queryable `ApiManagementGatewayLogs` (resource-specific table)
3. **Storage Account** receiving cost export data
4. **Azure Monitor Workbook** with tabbed views for both subscription-based and Entra ID cost allocation
5. **Portal links** printed in the notebook's final cell for quick access

### Cost Management Export

The cost export is configured automatically using a system-assigned managed identity with **Storage Blob Data Contributor** access.

![Cost Report - Export Overview](screenshots/costreport-01.png)

![Cost Report - Export Details](screenshots/costreport-02.png)

### Azure Monitor Workbook Dashboard

The deployed workbook provides a comprehensive view of API cost allocation and usage analytics across business units.

![Dashboard - Cost Allocation Overview](screenshots/Dashboard-01.png)

![Dashboard - Cost Breakdown by Business Unit](screenshots/Dashboard-02.png)

![Dashboard - Request Distribution](screenshots/Dashboard-03.png)

![Dashboard - Usage Analytics](screenshots/Dashboard-04.png)

![Dashboard - Response Code Analysis](screenshots/Dashboard-05.png)

![Dashboard - Drill-Down Details](screenshots/Dashboard-06.png)

### Entra ID Application Costing Tab

The Entra ID tab shows cost attribution by calling application, using the `emit-metric` policy's `caller-requests` custom metric.

![Entra ID - Usage by Caller ID](screenshots/EntraID-01.png)

![Entra ID - Cost Allocation](screenshots/EntraID-02.png)

![Entra ID - Request Trend](screenshots/EntraID-03.png)

### AI Gateway Token/PTU Tab

The AI Gateway tab shows per-client token consumption and estimated costs when APIM is used as an AI Gateway in front of Azure OpenAI or other LLM backends. It uses the `ApiManagementGatewayLlmLog` diagnostic data (PromptTokens, CompletionTokens, TotalTokens, ModelName) joined with `ApiManagementGatewayLogs` via `CorrelationId` for `ApimSubscriptionId`-based business unit attribution.

![AI Gateway - Token Consumption by Client](screenshots/AIGateway-01.png)

![AI Gateway - Token Cost Allocation](screenshots/AIGateway-02.png)

![AI Gateway - Token Trends & PTU Utilization](screenshots/AIGateway-03.png)

![AI Gateway - Model & Caller Breakdown](screenshots/AIGateway-04.png)

### Streaming vs Non-Streaming Verification

When `enable_foundry = True`, the multi-caller traffic phase alternates between non-streaming and streaming chat completions for every business unit. The **AI Gateway** tab includes a *Streaming vs Non-Streaming Breakdown* group with:

- A **pie chart** showing overall request distribution across delivery modes
- A **color-coded table** showing per-BU request counts and prompt, completion, and total token counts split by delivery mode

This makes it easy to confirm that token tracking works identically for both modes. The streaming visuals also distinguish between **client-supplied usage** (the caller already set `stream_options.include_usage = true`) and **APIM-injected usage** (the policy fragment added the flag and logged proof into `TraceRecords`), so you can verify policy behavior end to end. The same split is available per-request on the **Per-Request Detail** tab via the `AI Delivery Mode` and `Usage Provenance` columns.

## 🧹 Clean Up

To remove all resources created by this sample, open and run `clean-up.ipynb`. This deletes:

- Sample API and subscriptions from APIM
- Application Insights, Log Analytics, Storage Account
- Azure Monitor Workbook
- Cost Management export
- Microsoft Foundry Hub, Project, Azure AI Services (when `enable_foundry = True`)

> The clean-up notebook does **not** delete your APIM instance or resource group.

## 🔗 Additional Resources

- [Azure API Management Pricing](https://azure.microsoft.com/pricing/details/api-management/)
- [Azure Retail Prices API](https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices)
- [Azure Cost Management Documentation](https://learn.microsoft.com/azure/cost-management-billing/)
- [Log Analytics Kusto Query Language](https://learn.microsoft.com/azure/data-explorer/kusto/query/)
- [Azure Monitor Workbooks](https://learn.microsoft.com/azure/azure-monitor/visualize/workbooks-overview)
- [APIM Diagnostic Settings](https://learn.microsoft.com/azure/api-management/api-management-howto-use-azure-monitor)
- [APIM emit-metric policy](https://learn.microsoft.com/azure/api-management/emit-metric-policy)
- [Application Insights custom metrics](https://learn.microsoft.com/azure/azure-monitor/essentials/metrics-custom-overview)
- [Microsoft Entra ID application model](https://learn.microsoft.com/entra/identity-platform/application-model)
- [Azure OpenAI usage and token metrics](https://learn.microsoft.com/azure/ai-services/openai/how-to/monitoring)
- [PTU provisioned throughput concepts](https://learn.microsoft.com/azure/ai-services/openai/concepts/provisioned-throughput)
- [Azure OpenAI streaming with usage](https://learn.microsoft.com/azure/ai-services/openai/how-to/streaming)
- [APIM azure-openai-emit-token-metric policy](https://learn.microsoft.com/azure/api-management/azure-openai-emit-token-metric-policy)
- [Azure AI Foundry documentation](https://learn.microsoft.com/azure/ai-studio/)
- [Tracking every token (Tech Community blog)](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/tracking-every-token-granular-cost-and-usage-metrics-for-microsoft-foundry-agent/4503143)

[infrastructure-architectures]: ../../README.md#infrastructure-architectures
[infrastructure-folder]: ../../infrastructure/
