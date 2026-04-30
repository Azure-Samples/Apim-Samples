---
name: sample-creator
description: Guide for creating new Azure API Management (APIM) usage samples in this repository. Use when users want to create a new sample folder under `samples/`, scaffold from `samples/_TEMPLATE`, or update README, website, slide deck, and compatibility listings for a new sample. This skill provides the required folder structure, file templates, naming conventions, and step-by-step guidance based on the `samples/_TEMPLATE` structure.
---

# Sample Creator

This skill guides creating new APIM samples that follow the repository's established patterns.

## Sample Structure

Every sample under `samples/` must contain these files:

```
samples/<sample-name>/
├── README.md         (documentation)
├── create.ipynb      (Jupyter notebook for deployment)
├── main.bicep        (infrastructure as code)
└── *.xml             (optional: APIM policy files)
```

## Step 1: Gather Requirements

Before creating the sample, collect:

1. **Sample name** - kebab-case folder name (e.g., `oauth-validation`, `rate-limiting`). If the user has not provided it, ask before creating files.
2. **Display name** - Human-readable title for README
3. **Description** - Brief explanation of what the sample demonstrates
4. **Supported infrastructures** - Which infrastructure architectures work with this sample:
   - `INFRASTRUCTURE.AFD_APIM_PE` - Azure Front Door + APIM with Private Endpoint
   - `INFRASTRUCTURE.APIM_ACA` - APIM with Azure Container Apps
   - `INFRASTRUCTURE.APPGW_APIM` - Application Gateway + APIM
   - `INFRASTRUCTURE.APPGW_APIM_PE` - Application Gateway + APIM with Private Endpoint
   - `INFRASTRUCTURE.SIMPLE_APIM` - Basic APIM setup
    - If the user has not provided supported infrastructures, ask before scaffolding the sample.
5. **Learning objectives** - What users will learn (3-5 bullet points)
6. **APIs to create** - List of APIs with operations, paths, and policies
7. **Policy requirements** - Any custom APIM policies needed
8. **Downstream updates** - Whether the sample requires updates to the website, slide deck, or compatibility artifacts. Default to yes for new samples.

## Step 2: Create the Sample Folder

Create the folder structure under `samples/` unless the user explicitly requests another location:

```bash
mkdir samples/<sample-name>
```

Start from `samples/_TEMPLATE/` and compare the result against at least one similar existing sample before finalizing.

## Step 3: Create README.md

Use this template:

```markdown
# Samples: <Display Name>

<Brief description of what this sample demonstrates>

⚙️ **Supported infrastructures**: <Comma-separated list or "All infrastructures">

👟 **Expected *Run All* runtime (excl. infrastructure prerequisite): ~<N> minute(s)**

## 🎯 Objectives

1. <Learning objective 1>
1. <Learning objective 2>
1. <Learning objective 3>

<!-- ## ✅ Prerequisites -->

<!-- ONLY ADD THIS SECTION IF THE SAMPLE HAS REQUIREMENTS BEYOND THE ROOT README'S GENERAL PREREQUISITES (Azure subscription, CLI, Python, APIM instance). Examples: additional RBAC roles, external service accounts, special tooling. Open with a one-line reference to the root README, then list only sample-specific requirements. DELETE THIS COMMENT BLOCK IF NOT NEEDED. -->

## 📝 Scenario

<Optional: Describe the use case or scenario if applicable. Delete section if not needed.>

## 🛩️ Lab Components

<Describe what the lab sets up and how it benefits the learner.>

## ⚙️ Configuration

1. Decide which of the [Infrastructure Architectures](../../README.md#infrastructure-architectures) you wish to use.
    1. If the infrastructure _does not_ yet exist, navigate to the desired [infrastructure](../../infrastructure/) folder and follow its README.md.
    1. If the infrastructure _does_ exist, adjust the `user-defined parameters` in the _Initialize notebook variables_ below.
```

## Step 4: Create create.ipynb

The notebook must contain these cells in order:

### Cell 1: Markdown - Initialize Header

```markdown
### 🛠️ Initialize Notebook Variables

**Only modify entries under _USER CONFIGURATION_.**
```

### Cell 2: Python - Initialization

```python
import utils
from typing import List
from apimtypes import API, APIM_SKU, GET_APIOperation, INFRASTRUCTURE, POST_APIOperation, Region
from console import print_error, print_ok
from azure_resources import get_infra_rg_name

# ------------------------------
#    USER CONFIGURATION
# ------------------------------

rg_location = Region.EAST_US_2
index       = 1
apim_sku    = APIM_SKU.BASICV2              # Options: 'DEVELOPER', 'BASIC', 'STANDARD', 'PREMIUM', 'BASICV2', 'STANDARDV2', 'PREMIUMV2'
deployment  = INFRASTRUCTURE.<DEFAULT>      # Options: see supported_infras below
api_prefix  = '<prefix>-'                   # ENTER A PREFIX FOR THE APIS TO REDUCE COLLISION POTENTIAL
tags        = ['<tag1>', '<tag2>']          # ENTER DESCRIPTIVE TAGS



# ------------------------------
#    SYSTEM CONFIGURATION
# ------------------------------

sample_folder    = '<sample-name>'
rg_name          = get_infra_rg_name(deployment, index)
supported_infras = [<LIST_OF_SUPPORTED_INFRASTRUCTURES>]
nb_helper        = utils.NotebookHelper(sample_folder, rg_name, rg_location, deployment, supported_infras, index = index, apim_sku = apim_sku)

# Define the APIs and their operations and policies
# <Add policy loading if needed>
# pol_example = utils.read_policy_xml('<policy-file>.xml', sample_name = sample_folder)

# API Operations
# get_op = GET_APIOperation('Description of GET operation')
# post_op = POST_APIOperation('Description of POST operation')

# APIs
# api1_path = f'{api_prefix}<name>'
# api1 = API(api1_path, '<API Display Name>', api1_path, '<API Description>', operations = [get_op], tags = tags)
# api2 = API(api2_path, '<API Display Name>', api2_path, '<API Description>', '<policy_xml>', [get_op, post_op], tags)

# APIs Array
apis: List[API] = []  # Add your APIs here

print_ok('Notebook initialized')
```

### Cell 3: Markdown - Deploy Header

```markdown
### 🚀 Deploy Infrastructure and APIs

Creates the bicep deployment into the previously-specified resource group. A bicep parameters, `params.json`, file will be created prior to execution.
```

### Cell 4: Python - Deployment

```python
# Build the bicep parameters
bicep_parameters = {
    'apis': {'value': [api.to_dict() for api in apis]}
}

# Deploy the sample
output = nb_helper.deploy_sample(bicep_parameters)

if output.success:
    # Extract deployment outputs for testing
    apim_name        = output.get('apimServiceName', 'APIM Service Name')
    apim_gateway_url = output.get('apimResourceGatewayURL', 'APIM API Gateway URL')
    apim_apis        = output.getJson('apiOutputs', 'APIs')

    print_ok('Deployment completed successfully')
else:
    print_error('Deployment failed!')
    raise SystemExit(1)
```

### Cell 5: Markdown - Verify Header

```markdown
### ✅ Verify API Request Success

Assert that the deployment was successful by making calls to the deployed APIs.
```

### Cell 6: Python - Verification

Use `ApimRequests` and `ApimTesting` for structured test verification with verbose logging. If the sample also needs **traffic generation loops** (multi-caller simulation, load generation, etc.), add separate cells that use `requests.Session()` instead — see the "Testing and Traffic Generation" section in `copilot-instructions.md` for the session pattern.

```python
from apimrequests import ApimRequests
from apimtesting import ApimTesting

# Initialize testing framework
tests = ApimTesting('<Sample Name> Tests', sample_folder, nb_helper.deployment)

# Determine endpoints
# endpoint_url, request_headers, allow_insecure_tls = utils.get_endpoint(deployment, rg_name, apim_gateway_url)

# ********** TEST EXECUTIONS **********

# Example: Test API response
# reqs = ApimRequests(endpoint_url, subscription_key, request_headers, allowInsecureTls = allow_insecure_tls)
# output = reqs.singleGet('/<api-route>', msg = 'Testing API. Expect 200.')
# tests.verify('Expected String' in output, True)

tests.print_summary()

print_ok('All done!')
```

## Step 5: Create main.bicep

> **Always reuse infrastructure-provided resources.** The infrastructure deployment already creates an APIM service, a Log Analytics workspace, and an Application Insights component (the latter wired to APIM as the `apim-logger`). Sample `main.bicep` files must consume these via `existing` resource references — **do not** redeploy them. Only deploy a sample-local copy of one of these resources when the sample has a documented reason that satisfies one of the exceptions in `.github/copilot-instructions.md` ("Always reuse infrastructure-provided resources"). When wiring API-level diagnostics, omit the `apimLoggerName` parameter so APIs inherit the infrastructure logger automatically.

Use this template:

```bicep
// ------------------
//    PARAMETERS
// ------------------

@description('Location to be used for resources. Defaults to the resource group location')
param location string = resourceGroup().location

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)

param apimName string = 'apim-${resourceSuffix}'
param appInsightsName string = 'appi-${resourceSuffix}'
param apis array = []

// [ADD RELEVANT PARAMETERS HERE]

// ------------------
//    RESOURCES
// ------------------

// https://learn.microsoft.com/azure/templates/microsoft.insights/components
resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: appInsightsName
}

var appInsightsId = appInsights.id
var appInsightsInstrumentationKey = appInsights.properties.InstrumentationKey

// https://learn.microsoft.com/azure/templates/microsoft.apimanagement/service
resource apimService 'Microsoft.ApiManagement/service@2024-06-01-preview' existing = {
  name: apimName
}

// [ADD RELEVANT BICEP MODULES HERE]

// APIM APIs
module apisModule '../../shared/bicep/modules/apim/v1/api.bicep' = [for api in apis: if(!empty(apis)) {
  name: '${api.name}-${resourceSuffix}'
  params: {
    apimName: apimName
    appInsightsInstrumentationKey: appInsightsInstrumentationKey
    appInsightsId: appInsightsId
    api: api
  }
}]

// [ADD RELEVANT BICEP MODULES HERE]

// ------------------
//    MARK: OUTPUTS
// ------------------

output apimServiceId string = apimService.id
output apimServiceName string = apimService.name
output apimResourceGatewayURL string = apimService.properties.gatewayUrl

// API outputs
output apiOutputs array = [for i in range(0, length(apis)): {
  name: apis[i].name
  resourceId: apisModule[i].?outputs.?apiResourceId ?? ''
  displayName: apisModule[i].?outputs.?apiDisplayName ?? ''
  productAssociationCount: apisModule[i].?outputs.?productAssociationCount ?? 0
  subscriptionResourceId: apisModule[i].?outputs.?subscriptionResourceId ?? ''
  subscriptionName: apisModule[i].?outputs.?subscriptionName ?? ''
  subscriptionPrimaryKey: apisModule[i].?outputs.?subscriptionPrimaryKey ?? ''
  subscriptionSecondaryKey: apisModule[i].?outputs.?subscriptionSecondaryKey ?? ''
}]

// [ADD RELEVANT OUTPUTS HERE]
```

## Step 6: Create Policy XML Files (If Needed)

For samples with custom policies, create XML files following the APIM policy structure:

```xml
<policies>
    <inbound>
        <base />
        <!-- Add inbound policies -->
    </inbound>
    <backend>
        <base />
    </backend>
    <outbound>
        <base />
        <!-- Add outbound policies -->
    </outbound>
    <on-error>
        <base />
    </on-error>
</policies>
```

Load policies in the notebook:

```python
pol_example = utils.read_policy_xml('example-policy.xml', sample_name = sample_folder)
```

## Step 7: Update Repository Surfaces

Adding a sample is not complete until the repository listings stay in sync.

Update these files when a new sample is added:

1. `README.md` - Add the sample to the root sample table in alphabetical order.
2. `docs/index.html` - Add the sample card and the matching JSON-LD `ItemList` entry.
3. `assets/APIM-Samples-Slide-Deck.html` - Update sample inventory, counts, and sample descriptions where the deck surfaces them.
4. `tests/Test-Matrix.md` - Add the sample row and mark unsupported infrastructures as `N/A` where appropriate.
5. `assets/diagrams/Infrastructure-Sample-Compatibility.svg` - Add a new row for the sample in alphabetical order. Every new sample needs a row here, regardless of whether the compatibility pattern is unique. Mark each infrastructure cell as compatible (green check) or not compatible (red cross).

Keep the canonical display name identical across README tables, the website, the slide deck, and compatibility diagrams.

If the sample work exposes a reusable structural improvement, suggest updating `samples/_TEMPLATE/` as part of the same task or as a follow-up.

## API and Operation Types

### Creating Operations

```python
# Standard operations (available in apimtypes)
get_op = GET_APIOperation('Description')
post_op = POST_APIOperation('Description')

# With custom policy
get_op = GET_APIOperation('Description', policyXml = '<policy-xml-string>')

# For other HTTP methods, use the base APIOperation class directly
# from apimtypes import APIOperation, HTTP_VERB
# put_op = APIOperation('put-op', 'PUT operation', '/', HTTP_VERB.PUT, 'Description')
```

### Creating APIs

The `API` constructor signature is `API(name, displayName, path, description, policyXml=None, operations=None, tags=None, ...)`. The `_TEMPLATE` uses the same value for `name` and `path`.

```python
# Basic API (no custom policy)
api1_path = f'{api_prefix}example'
api = API(
    api1_path,              # name (resource identifier)
    '<Display Name>',       # displayName (human-readable)
    api1_path,              # path (URL path segment)
    '<Description>',        # description
    operations = [get_op],
    tags = tags
)

# API with policy (positional policyXml, operations, tags)
api = API(
    api1_path,
    '<Display Name>',
    api1_path,
    '<Description>',
    '<policy-xml>',         # policyXml string
    [get_op, post_op],      # operations list
    tags
)
```

## Infrastructure Constants

Available infrastructure types:

| Constant | Description |
|----------|-------------|
| `INFRASTRUCTURE.AFD_APIM_PE` | Azure Front Door + APIM with Private Endpoint |
| `INFRASTRUCTURE.APIM_ACA` | APIM with Azure Container Apps |
| `INFRASTRUCTURE.APPGW_APIM` | Application Gateway + APIM |
| `INFRASTRUCTURE.APPGW_APIM_PE` | Application Gateway + APIM with Private Endpoint |
| `INFRASTRUCTURE.SIMPLE_APIM` | Basic APIM setup |

## Naming Conventions

- **Folder name**: kebab-case (e.g., `oauth-validation`)
- **API prefix**: short, unique, ending with hyphen (e.g., `oauth-`)
- **Policy files**: descriptive, kebab-case with `.xml` extension
- **Python variable names**: snake_case per PEP 8 (note: `apimtypes` constructor parameters use camelCase for JSON mapping)

## Validation Checklist

Before committing, verify:

- [ ] README.md follows the template structure
- [ ] create.ipynb has all required cells with correct order
- [ ] main.bicep references shared modules correctly
- [ ] Policy XML files are well-formed
- [ ] `sample_folder` matches the actual folder name
- [ ] `supported_infras` list is accurate
- [ ] All API paths use the defined `api_prefix`
- [ ] Tags are descriptive and relevant
- [ ] No cell outputs in notebook (clear before commit)
