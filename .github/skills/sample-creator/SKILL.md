---
name: sample-creator
description: Guide for creating new Azure API Management (APIM) usage samples in this repository. Use when users want to create a new sample folder under `samples/` that demonstrates APIM policies, API configurations, or integration patterns. This skill provides the required folder structure, file templates, naming conventions, and step-by-step guidance based on the `samples/_TEMPLATE` structure.
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

1. **Sample name** - kebab-case folder name (e.g., `oauth-validation`, `rate-limiting`)
2. **Display name** - Human-readable title for README
3. **Description** - Brief explanation of what the sample demonstrates
4. **Supported infrastructures** - Which infrastructure architectures work with this sample:
   - `INFRASTRUCTURE.AFD_APIM_PE` - Azure Front Door + APIM with Private Endpoint
   - `INFRASTRUCTURE.APIM_ACA` - APIM with Azure Container Apps
   - `INFRASTRUCTURE.APPGW_APIM` - Application Gateway + APIM
   - `INFRASTRUCTURE.APPGW_APIM_PE` - Application Gateway + APIM with Private Endpoint
   - `INFRASTRUCTURE.SIMPLE_APIM` - Basic APIM setup
5. **Learning objectives** - What users will learn (3-5 bullet points)
6. **APIs to create** - List of APIs with operations, paths, and policies
7. **Policy requirements** - Any custom APIM policies needed

## Step 2: Create the Sample Folder

Create the folder structure:

```bash
mkdir samples/<sample-name>
```

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

## 📝 Scenario

<Optional: Describe the use case or scenario if applicable. Delete section if not needed.>

## 🛩️ Lab Components

<Describe what the lab sets up and how it benefits the learner.>

## 🔗 APIs

| API Name | What does it do? |
|:---------|:-----------------|
| <API 1>  | <Description>    |
| <API 2>  | <Description>    |

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
from apimtypes import *
from console import print_error, print_ok
from azure_resources import get_infra_rg_name

# ------------------------------
#    USER CONFIGURATION
# ------------------------------

rg_location = 'eastus2'
index       = 1
apim_sku    = APIM_SKU.BASICV2              # Options: 'BASICV2', 'STANDARDV2', 'PREMIUMV2'
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
# api1 = API('<api-path>', '<API Display Name>', '/<api-route>', '<API Description>', operations = [get_op], tags = tags)
# api2 = API('<api-path>', '<API Display Name>', '/<api-route>', '<API Description>', '<policy_xml>', [get_op, post_op], tags)

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
    print_error("Deployment failed!")
    raise SystemExit(1)
```

### Cell 5: Markdown - Verify Header

```markdown
### ✅ Verify API Request Success

Assert that the deployment was successful by making calls to the deployed APIs.
```

### Cell 6: Python - Verification

```python
from apimrequests import ApimRequests
from apimtesting import ApimTesting

# Initialize testing framework
tests = ApimTesting("<Sample Name> Tests", sample_folder, nb_helper.deployment)

# Determine endpoints
# endpoint_url, request_headers = utils.get_endpoint(deployment, rg_name, apim_gateway_url)

# ********** TEST EXECUTIONS **********

# Example: Test API response
# reqs = ApimRequests(endpoint_url)
# response = reqs.singleGet('/<api-route>', msg = 'Testing API. Expect 200.')
# tests.verify('API returns expected response', response.status_code == 200)

tests.print_summary()

print_ok('All done!')
```

## Step 5: Create main.bicep

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

// <Add additional parameters here>

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

// <Add additional resources here: backends, products, etc.>

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

// <Add additional modules here>

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

// <Add additional outputs here>
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

## API and Operation Types

### Creating Operations

```python
# Standard operations
get_op = GET_APIOperation('Description')
post_op = POST_APIOperation('Description')
put_op = PUT_APIOperation('Description')
delete_op = DELETE_APIOperation('Description')

# With custom policy
get_op = GET_APIOperation('Description', policy_xml = '<policy-xml-string>')
```

### Creating APIs

```python
# Basic API (no custom policy)
api = API(
    '<api-path>',           # URL path segment
    '<Display Name>',       # Human-readable name
    '/<route>',             # Service URL suffix
    '<Description>',        # API description
    operations = [get_op],
    tags = tags
)

# API with policy
api = API(
    '<api-path>',
    '<Display Name>',
    '/<route>',
    '<Description>',
    '<policy-xml>',         # Policy XML string
    [get_op, post_op],      # Operations list
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
- **Variable names**: camelCase in Python, snake_case for constants

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
