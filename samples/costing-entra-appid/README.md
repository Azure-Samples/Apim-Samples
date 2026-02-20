# Samples: APIM Cost Attribution by Entra ID Application

This sample demonstrates how to track and allocate API costs by **Entra ID application** using the APIM `emit-metric` policy. Instead of relying on APIM subscription keys, it extracts the `appid` (or `azp`) claim from JWT tokens to identify each calling application and emit custom metrics to Application Insights.

⚙️ **Supported infrastructures**: All infrastructures (or bring your own existing APIM deployment)

👟 **Expected *Run All* runtime (excl. infrastructure prerequisite): ~15 minutes**

## 🎯 Objectives

1. **Track API usage by Entra ID application** - Use the `emit-metric` policy to extract `appid`/`azp` JWT claims and emit per-caller custom metrics
2. **Capture caller-level request counts** - Log each API request as a `caller-requests` custom metric with a `CallerId` dimension in Application Insights
3. **Visualise cost allocation** - Deploy an Azure Monitor Workbook that shows proportional cost breakdown by calling application
4. **Compare to subscription-based tracking** - Understand when caller-level `emit-metric` attribution is more suitable than APIM subscription-based tracking (see the sibling `costing` sample)
5. **Enable budget alerts per caller** - Create scheduled query alerts when a caller exceeds a configurable request threshold

## ✅ Prerequisites

Before running this sample, ensure you have the following:

### Required

| Prerequisite | Description |
|---|---|
| **Azure subscription** | An active Azure subscription with Owner or Contributor access |
| **Azure CLI** | Logged in (`az login`) with the correct subscription selected (`az account set -s <id>`) |
| **APIM instance** | Either deploy one via this repo's infrastructure, or bring your own |
| **Python environment** | Python 3.12+ with dependencies installed (`uv sync` or `pip install -r requirements.txt`) |

### Azure RBAC Permissions

The signed-in user needs the following role assignments:

| Role | Scope | Purpose |
|---|---|---|
| **Contributor** | Resource Group | Deploy Bicep resources (App Insights, Log Analytics, Workbook, Diagnostic Settings) |

### For Workbook Consumers

Users who only need to **view** the deployed Azure Monitor Workbook (not deploy the sample) need:

| Role | Scope | Purpose |
|---|---|---|
| **Monitoring Reader** | Resource Group | Open and view the workbook |
| **Log Analytics Reader** | Application Insights | Execute the KQL queries that power the workbook |

## ⚙️ Configuration

### Option A: Use a repository infrastructure (recommended)

1. Navigate to the desired [infrastructure](../../infrastructure/) folder (e.g. [simple-apim](../../infrastructure/simple-apim/)) and follow its README.md to deploy
2. Open `create.ipynb` and set:

   ```python
   deployment = INFRASTRUCTURE.SIMPLE_APIM    # Match your deployed infra
   index      = 1                              # Match your infra index
   ```

3. Run All Cells

### Option B: Bring your own existing APIM

You can use any existing Azure API Management instance. The sample only adds diagnostic settings, a sample API, and monitoring resources.

1. Set the correct Azure subscription: `az account set -s <subscription-id>`
2. Open `create.ipynb` and configure the user variables
3. Run All Cells

## 📝 Scenario

Some organisations identify API callers by their **Entra ID application registration** rather than by APIM subscription key. This is common when:

- Multiple services share a single APIM subscription but need individual cost tracking
- OAuth 2.0 client-credentials flow is the primary authentication mechanism
- The organisation wants to correlate API costs with its Entra ID app catalogue
- Fine-grained, claim-based caller identification is preferred over subscription-level grouping

### How It Works

1. Each API call includes a JWT Bearer token containing an `appid` (v1) or `azp` (v2) claim
2. The `emit-metric` APIM policy extracts this claim and emits a `caller-requests` custom metric to Application Insights
3. The metric carries a `CallerId` dimension set to the extracted app ID
4. An Azure Monitor Workbook queries `customMetrics` to display usage and cost allocation per caller
5. Optional budget alerts fire when a caller exceeds a threshold

### Key Difference from the `costing` Sample

| Aspect | `costing` sample | `costing-entra-appid` sample |
|---|---|---|
| **Caller identification** | APIM subscription key (`ApimSubscriptionId`) | JWT `appid`/`azp` claim |
| **Data source** | `ApiManagementGatewayLogs` in Log Analytics | `customMetrics` in Application Insights |
| **Tracking mechanism** | Built-in APIM logging | `emit-metric` policy |
| **Cost Management export** | Yes (storage account) | No (metrics-based) |

## 🛩️ Lab Components

This lab deploys and configures:

- **Application Insights** - Receives `caller-requests` custom metrics from the `emit-metric` policy
- **Log Analytics Workspace** - Stores APIM diagnostic logs
- **Diagnostic Settings** - Links APIM to both Log Analytics and Application Insights
- **Sample API** - A demo API with the `emit-metric` policy applied
- **Azure Monitor Workbook** - Pre-built dashboard with:
  - Usage by Caller ID (bar chart and table)
  - Cost Allocation (proportional breakdown with pie chart)
  - Request Trend (hourly time chart per caller)

## 🔗 Additional Resources

- [APIM emit-metric policy](https://learn.microsoft.com/azure/api-management/emit-metric-policy)
- [Application Insights custom metrics](https://learn.microsoft.com/azure/azure-monitor/essentials/metrics-custom-overview)
- [Azure Monitor Workbooks](https://learn.microsoft.com/azure/azure-monitor/visualize/workbooks-overview)
- [Azure API Management Pricing](https://azure.microsoft.com/pricing/details/api-management/)
- [Microsoft Entra ID application model](https://learn.microsoft.com/entra/identity-platform/application-model)
