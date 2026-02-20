# Samples: APIM Costing by Entra App ID

This sample demonstrates how to track API usage by Entra ID application (appid claim) using Azure API Management's `emit-metric` policy. It enables cost attribution and reporting for JWT/OAuth consumers.

⚙ **Supported infrastructures**: All infrastructures (or bring your own existing APIM deployment)

👟 **Expected *Run All* runtime (excl. infrastructure prerequisite): ~15 minutes**

## Objectives

1. **Extract caller identity from JWT** - Use the `appid` (or `azp`) claim to identify consuming applications
2. **Emit custom metrics** - Write caller identity to Azure Monitor via `emit-metric` policy
3. **Report usage by App ID** - Query `customMetrics` in Log Analytics for cost attribution
4. **Enable cost governance** - Provide KQL query templates for chargeback/showback reporting
5. **Visualize in a dashboard** - Deploy an Azure Workbook with cost attribution charts and tables

## How It Works

The sample deploys a lightweight observability stack and applies an APIM policy that extracts the Entra App ID from incoming JWT tokens.

### Data Flow

```
API Consumer        Azure API           Application        Log Analytics
(JWT Bearer) -----> Management -------> Insights --------> Workspace
                    |                                      |
                    | caller-id-policy.xml                  | customMetrics table
                    | 1. Parse JWT                         | - CallerId (appid)
                    | 2. Extract appid/azp                 | - API
                    | 3. emit-metric                       | - Operation
```

### The Policy

The `caller-id-policy.xml` does the following:

1. **Parses** the `Authorization: Bearer <token>` header using `AsJwt()`
2. **Extracts** the `appid` claim (falls back to `azp`)
3. **Falls back** to `context.Subscription.Id` if no JWT is present
4. **Emits** a `caller-requests` custom metric with `CallerId`, `API`, and `Operation` dimensions

```xml
<set-variable name="callerId" value="@{
    var authHeader = context.Request.Headers.GetValueOrDefault('Authorization', '');
    if (!string.IsNullOrEmpty(authHeader) && authHeader.StartsWith('Bearer '))
    {
        var jwt = authHeader.Substring(7).AsJwt();
        if (jwt != null)
        {
            var appId = jwt.Claims.GetValueOrDefault('appid', '');
            if (string.IsNullOrEmpty(appId))
                appId = jwt.Claims.GetValueOrDefault('azp', '');
            if (!string.IsNullOrEmpty(appId))
                return appId;
        }
    }
    return context.Subscription != null ? context.Subscription.Id : 'unknown';
}" />
<emit-metric name="caller-requests" value="1" namespace="apim-costing">
    <dimension name="CallerId" value="@((string)context.Variables['callerId'])" />
    <dimension name="API" value="@(context.Api.Id)" />
    <dimension name="Operation" value="@(context.Operation.Id)" />
</emit-metric>
```

> **Note**: `AsJwt()` parses the token structure but does **not** validate signatures. If you need signature validation, add a `<validate-jwt>` or `<validate-azure-ad-token>` policy before the extraction.

## Prerequisites

| Prerequisite | Description |
|---|---|
| **Azure subscription** | An active Azure subscription with Contributor access |
| **Azure CLI** | Logged in (`az login`) with the correct subscription selected |
| **APIM instance** | Deploy via this repo's [infrastructure][infrastructure-folder] or bring your own |
| **Python environment** | Python 3.12+ with dependencies installed (`uv sync`) |

## Configuration

### Option A: Use a repository infrastructure (recommended)

1. Navigate to the desired [infrastructure][infrastructure-folder] folder (e.g., [simple-apim](../../infrastructure/simple-apim/)) and follow its README.md.
2. Open `create.ipynb` and set `infrastructure` and `index` to match your deployment.
3. Run All Cells.

### Option B: Bring your own existing APIM

1. Open `create.ipynb` and uncomment `existing_rg_name` and `existing_apim_name`.
2. Set `az account set -s <subscription-id>`.
3. Run All Cells.

**What the sample deploys:**
- Application Insights instance
- Log Analytics Workspace
- Diagnostic Settings on APIM (gateway logs + App Insights logger)
- Azure Workbook with cost attribution dashboard (usage, cost allocation, and trend charts)
- A sample API (`appid-tracking-api`) without subscription requirement
- Entra ID test app registrations (for real token testing, cleaned up at the end)

**What it does NOT touch:**
- Your existing APIs, policies, or subscriptions
- Your APIM SKU or networking configuration

## Lab Components

| Component | Purpose |
|---|---|
| `caller-id-policy.xml` | APIM policy that extracts `appid` from JWT and emits custom metric |
| `main.bicep` | Deploys App Insights, Log Analytics, diagnostic settings, and cost attribution workbook |
| `create.ipynb` | Notebook that deploys resources, creates API, registers Entra test apps, generates traffic, and verifies |

### Cost Attribution Workbook

The Bicep deployment includes an Azure Workbook ("APIM Cost Attribution by Caller ID") with three collapsible sections:

1. **Usage by Caller ID** - Bar chart (60%) and summary table (40%) side-by-side showing total requests per caller
2. **Cost Allocation** - Proportional cost table with usage percentage bars and pie chart, based on a configurable monthly base cost
3. **Request Trend** - Hourly time chart showing request volume by caller over time

**Workbook parameters:**

| Parameter | Description |
|---|---|
| **Time Range** | Configurable time window (default: 24 hours) |
| **Monthly Base Cost (USD)** | Base cost for proportional allocation (default: $150.00) |
| **App ID Names (JSON)** | Optional JSON mapping to resolve GUIDs to friendly names |

**Name resolution:** To display friendly names instead of raw GUIDs, set the "App ID Names" parameter to a JSON mapping:

```json
{"a5846c0e-742f-422a-801a-788abde0d7ab": "HR Service", "9e6bfb3f-b201-4678-9d47-f8c22174a9cd": "Mobile Gateway"}
```

Callers with a mapping appear as `HR Service (a5846c0e-...)`, while unmapped callers show the raw ID.

**Accessibility features:**
- All sections are collapsible/expandable for screen reader navigation
- Visual borders (`showBorder`) separate sections for low-vision users
- Descriptive `noDataMessage` on all query items
- Human-readable column labels ("Caller", "Requests", "Usage %", "Allocated Cost")
- Proper number formatting (grouping separators, currency, percentages)

Access the workbook from the Azure Portal via the link printed by the notebook's portal links cell.

## Entra ID Verification

The notebook includes an end-to-end verification flow using real Entra ID app registrations:

1. **Create test app registrations** - Four apps are registered in Entra (e.g., "Cost Demo - Finance Portal"), each representing a different business unit
2. **Set Application ID URIs** - Each app gets `api://{appId}` to enable client credentials token requests
3. **Acquire real OAuth tokens** - Client credentials flow (`grant_type=client_credentials`) obtains tokens with real `appid` GUIDs
4. **Generate API traffic** - Calls the APIM API with real Bearer tokens so the `emit-metric` policy captures actual Entra App IDs
5. **Verify in dashboard** - The `customMetrics` table will show real Entra App ID GUIDs as `CallerId` dimensions, suitable for screenshots
6. **Clean up** - A final cell deletes the test app registrations from the tenant

### Why Real Tokens?

The simulated JWT approach (using self-signed tokens with `pyjwt`) is useful for quick testing, but real Entra tokens demonstrate:

- Production-realistic `appid` GUIDs in the dashboard
- End-to-end OAuth flow verification
- Accurate cost attribution reporting with real identities

## Key Concepts

### Why `emit-metric` instead of `set-header`?

- `set-header` only forwards data to the backend; it does **not** appear in `ApiManagementGatewayLogs`
- `emit-metric` writes directly to Azure Monitor Metrics and `customMetrics` (Application Insights), making the data queryable in Log Analytics

### Why `AsJwt()` instead of `validate-jwt`?

- `AsJwt()` is lightweight - it parses the token without validating signatures
- This is sufficient for extracting the `appid` claim for cost tracking purposes
- If your API also needs authorization, add `<validate-jwt>` or `<validate-azure-ad-token>` **before** the extraction

### Mapping App IDs to Business Units

The `appid` claim contains an Entra App Registration ID (a GUID in production). To map these to meaningful business unit names:

| Approach | Description |
|---|---|
| **Workbook parameter** | Use the built-in "App ID Names (JSON)" parameter in the cost attribution workbook |
| **Naming convention** | Name app registrations with a prefix (e.g., `bu-finance-app`) |
| **Mapping table** | Maintain a lookup table in Log Analytics or a Storage Account |
| **KQL join** | Join `customMetrics` with a reference table at query time |

## Sample KQL Queries

### Usage by App ID

```kql
customMetrics
| where TimeGenerated > ago(30d) and name == "caller-requests"
| extend CallerId = tostring(customDimensions.CallerId)
| where isnotempty(CallerId)
| summarize RequestCount = sum(value) by CallerId
| order by RequestCount desc
```

### Cost Allocation by App ID

```kql
let baseCost = 150.00;   // Adjust to your APIM SKU monthly cost
let perKRate = 0.003;    // Adjust to your overage rate per 1K requests
let metrics = customMetrics
| where TimeGenerated > ago(30d) and name == "caller-requests"
| extend CallerId = tostring(customDimensions.CallerId)
| where isnotempty(CallerId);
let totalRequests = toscalar(metrics | summarize sum(value));
metrics
| summarize RequestCount = sum(value) by CallerId
| extend UsageShare = round(RequestCount * 100.0 / totalRequests, 2)
| extend BaseCostShare = round(baseCost * RequestCount / totalRequests, 2)
| extend VariableCost = round(RequestCount * perKRate / 1000.0, 2)
| extend TotalAllocatedCost = round(BaseCostShare + VariableCost, 2)
| order by TotalAllocatedCost desc
```

## Known Constraints

| Constraint | Impact | Mitigation |
|---|---|---|
| `ApiManagementGatewayLogs` has no custom dimensions | App ID cannot appear in gateway logs | Use `customMetrics` from `emit-metric` instead |
| `AsJwt()` does not validate signatures | Token could be forged | Add `<validate-jwt>` if authorization is also needed |
| emit-metric data latency | 5-10 minutes before data appears | Build dashboards with appropriate time windows |
| App registrations are external to APIM | Cannot assign to APIM Products directly | Maintain an external App ID to BU mapping |

## References

- [emit-metric policy](https://learn.microsoft.com/azure/api-management/emit-metric-policy)
- [validate-jwt policy](https://learn.microsoft.com/azure/api-management/validate-jwt-policy)
- [validate-azure-ad-token policy](https://learn.microsoft.com/azure/api-management/validate-azure-ad-token-policy)
- [APIM Diagnostic Settings](https://learn.microsoft.com/azure/api-management/api-management-howto-use-azure-monitor)
- [Entra ID Authentication with APIM](https://learn.microsoft.com/azure/api-management/api-management-howto-protect-backend-with-aad)

[infrastructure-folder]: ../../infrastructure/
