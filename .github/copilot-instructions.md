---
applyTo: "**"
---

# GitHub Copilot Instructions for this Repository

## Purpose

This instructions file is designed to guide GitHub Copilot's behavior specifically for this repository. It is intended to provide clear, general, and maintainable guidelines for code generation, style, and collaboration.

**In case of any conflict, instructions from other individualized or project-specific files (such as `my-copilot.instructions.md`) take precedence over this file.**

## Repository Context

- This repository provides a playground to safely experiment with and learn Azure API Management (APIM) policies in various architectures.
- The primary technologies are Python, Bicep, Jupyter notebooks, Azure CLI, APIM policy XML, and Markdown.
- The technical audience includes developers, architects, and DevOps engineers who want to understand and implement APIM policies effectively.
- The less technical audience includes decision makers and stakeholders who need to understand the value and capabilities of APIM policies without deep technical details.

## Instruction Hierarchy

- When the user asks about **Python** or a Python file is referenced in the chat context, prefer guidance and examples from [python instructions](./python.instructions.md).
- When the user asks about **Bicep** or a Bicep file is referenced in the chat context, prefer guidance and examples from [bicep instructions](./bicep.instructions.md).
- When the user asks about **JSON** or a JSON file is referenced in the chat context, prefer guidance and examples from [json instructions](./json.instructions.md).
- When other languages are used, look for a relevant instructions file to be included. The format is `./[language].instructions.md` where `[language]` acts as a placeholder. Also consider synonyms
  such as `JavaScript`, `JScript`, etc.

In case of any conflicting instructions, the following hierarchy shall apply. If a conflict cannot be resolved by this hierarchy, please prompt the user and ask for their situational preference.

  1. Individualized instructions (e.g. a developer's or an organization's instruction file(s)), if present
  2. This repository's `.github/.copilot-instructions.md`
  3. General best practices and guidelines from sources such as [Microsoft Learn](https://learn.microsoft.com/docs/)
    This includes the [Microsoft Cloud Adoption Framework](https://learn.microsoft.com/azure/cloud-adoption-framework/).
  4. Official [GitHub Copilot best practices documentation](https://docs.github.com/enterprise-cloud@latest/copilot/using-github-copilot/coding-agent/best-practices-for-using-copilot-to-work-on-tasks)

## Copilot Personality Behavior

- Never be rude, dismissive, condescending, threatening, aggressive, or otherwise negative.
- Emphasise friendly, supportive, and collaborative interactions.
- Be concise and to the point, but adjust the level of detail based on the user's technical expertise that you can infer from the conversation.

## General Principles

- Write concise, efficient, and well-documented code for a global audience.
- Consider non-native English speakers in code comments and documentation, using clear and simple language.

## Consistency & Uniformity

Uniformity, clarity, and ease of use are paramount across all infrastructures and samples. Every infrastructure and every sample should look and feel as alike as possible so that users maintain familiarity as they move between them. A user who has completed one sample should never feel like they are viewing something entirely new when they open the next.

- **Follow the established templates.** New infrastructures must follow the structure of existing infrastructures. New samples must follow `samples/_TEMPLATE`. Deviations are permitted only when a sample has genuinely unique requirements, and those deviations should be minimal.
- **Use consistent naming, headings, and cell order.** Markdown headings, variable names, section labels (e.g. `USER CONFIGURATION`, `SYSTEM CONFIGURATION`), emoji usage, and code cell ordering must match the patterns established by the template and existing artefacts.
- **Keep README structure uniform.** Infrastructure READMEs and sample READMEs each follow their own standard layout (see the guidelines below). Readers should be able to predict where to find objectives, configuration steps, and execution instructions.
- **Reuse shared utilities.** Use `NotebookHelper`, `InfrastructureNotebookHelper`, `ApimRequests`, `ApimTesting`, and shared Bicep modules rather than inventing ad-hoc alternatives. Shared code is the single best tool for enforcing uniformity.
- **Mirror tone and depth.** Similar sections across artefacts should use similar levels of detail. If one sample's README explains configuration in three sentences, another sample of comparable complexity should do the same.
- **Validate against peers.** Before finalising a new infrastructure or sample, compare it side-by-side with at least one existing peer to identify structural or stylistic drift.

## General Coding Guidelines

- All code, scripts, and configuration must be cross-platform compatible, supporting Windows, Linux, and macOS. If any special adjustments are to be made, please clearly indicate so in comments.
- Prioritize clarity, maintainability, and readability in all generated code.
- Focus on achieving a Minimal Viable Product (MVP) first, then iterate.
- Follow language-specific conventions and style guides (e.g., PEP 8 for Python).
- Use idiomatic code and language-specific best practices.
- Write clear and concise comments for each function and class.
- Use descriptive names for variables, functions, and classes.
- Handle edge cases and errors gracefully.
- Break down complex logic into smaller, manageable functions or classes.
- Use type annotations and docstrings where appropriate.
- Prefer standard libraries and well-maintained dependencies.
- Use `samples/_TEMPLATE` as the baseline for every new sample. The template provides the canonical structure, cell order, and format. New samples must not deviate from this structure unless the sample has genuinely unique requirements.

## Repository Structure

- `/`: Root directory containing the main files and folders. Bicep configuration is stored in `bicepconfig.json`.
- The following folders are all at the root level:
    - `assets/`: PlantUML diagrams and images. Static assets such as these should be placed here. Any diagrams should be placed in the /diagrams/src subfolder.
    - `infrastructure/`: Contains Jupyter notebooks for setting up various API Management infrastructures. When modifying samples, these notebooks should not need to be modified.
    - `samples/`: Various policy and scenario samples that can be applied to the infrastructures.
    - `setup/`: General setup scripts and configurations for the repository and dev environment setup.
    - `shared/`: Shared resources, such as Bicep modules, Python libraries, and other reusable components.
    - `tests/`: Contains unit tests for Python code and Bicep modules. This folder should contain all tests for all code in the repository.

## Infrastructure Development Guidelines

Infrastructures live in `infrastructure/[infra-name]/` and provide the foundational Azure environment that samples deploy onto. All infrastructures must follow the same structure and patterns so that users experience a consistent workflow regardless of which architecture they choose.

### Infrastructure File Structure

Each infrastructure in `infrastructure/[infra-name]/` must contain:
- `create.ipynb` - Jupyter notebook that deploys the infrastructure
- `create_infrastructure.py` - Python helper script for infrastructure creation logic
- `main.bicep` - Bicep template for deploying the infrastructure resources
- `params.json` - Bicep parameter file
- `clean-up.ipynb` - Jupyter notebook for tearing down the infrastructure
- `README.md` - Documentation explaining the architecture, objectives, and execution steps

### Infrastructure Jupyter Notebook (`create.ipynb`) Structure

All infrastructure notebooks must follow this exact cell pattern:

#### Cell 1: Configure & Create (Markdown)
- Heading: `### 🛠️ Configure Infrastructure Parameters & Create the Infrastructure`
- One-sentence description naming the specific infrastructure
- Bold reminder: `❗️ **Modify entries under _User-defined parameters_**.`
- Optional: a short note if the infrastructure has unique deployment phases (e.g. private link approval)

#### Cell 2: Configure & Create (Python Code)
- Import only `APIM_SKU`, `INFRASTRUCTURE` from `apimtypes`, `InfrastructureNotebookHelper` from `utils`, and `print_ok` from `console`
- `USER CONFIGURATION` section with `rg_location`, `index`, and `apim_sku` (comment each with inline description)
- `SYSTEM CONFIGURATION` section: instantiate `InfrastructureNotebookHelper` and call `create_infrastructure()`
- Final line: `print_ok('All done!')`

#### Cell 3: Clean Up (Markdown)
- Heading: `### 🗑️ Clean up resources`
- Standard text: "When you're finished experimenting, it's advisable to remove all associated resources from Azure to avoid unnecessary cost. Use the [clean-up notebook](clean-up.ipynb) for that."

### Infrastructure README.md

Use this consistent layout:
- **Title** - Name of the architecture (e.g. "Simple API Management Infrastructure")
- **Description** - One to two sentences summarising the architecture and its value
- **Architecture diagram** - `<img>` tag referencing the SVG in the infrastructure folder
- **🎯 Objectives** - Numbered list of what the infrastructure provides
- **⚙️ Configuration** - One-sentence reference to the notebook's initialise-variables section
- **▶️ Execution** - Expected runtime badge and numbered steps to run the notebook
- **Reference links** - Markdown reference-style links at the bottom

---

## Sample Development Guidelines

### Sample File Structure

Each sample in `samples/[sample-name]/` must contain:
- `create.ipynb` - Jupyter notebook that deploys and demonstrates the sample
- `main.bicep` - Bicep template for deploying sample resources
- `README.md` - Documentation explaining the sample, use cases, and concepts
- `*.xml` - APIM policy files (if applicable to the sample)
- `*.kql` - KQL (Kusto Query Language) files (if applicable to the sample)

### Jupyter Notebook (`create.ipynb`) Structure

Follow this pattern for **all** sample `create.ipynb` files. Consistency here is critical - users should recognise the layout immediately from having used any other sample:

#### Cell 1: Title & Overview (Markdown)
- Notebook title and brief description
- Reference to README.md for detailed information

#### Cell 2: What This Sample Does (Markdown)
- Bullet list of key actions/demonstrations
- Keep focused on user-facing outcomes

#### Cell 3: Initialize Notebook Variables (Markdown)
- Heading with note that only USER CONFIGURATION should be modified

#### Cell 4: Initialize Notebook Variables (Python Code)
**This cell should be straightforward configuration only. No Azure SDK calls here.**

Structure:
1. Import statements at the top:
   - Standard library imports (time, json, tempfile, requests, pathlib, datetime)
   - `utils`, `apimtypes`, `console`, `azure_resources` (including `az`, `get_infra_rg_name`, `get_account_info`)
2. USER CONFIGURATION section:
   - `rg_location`: Azure region (default: 'eastus2')
   - `index`: Deployment index for resource naming (default: 1)
   - `deployment`: Selected infrastructure type (reference INFRASTRUCTURE enum options)
   - `api_prefix`: Prefix for APIs to avoid naming collisions
   - `tags`: List of descriptive tags
   - Sample-specific configuration (e.g., SKU, feature flags, thresholds)
3. SYSTEM CONFIGURATION section:
   - `sample_folder`: Folder name matching the sample directory
   - `rg_name`: Computed using `get_infra_rg_name(deployment, index)`
   - `supported_infras`: List of compatible infrastructure types
   - `nb_helper`: Instance of `utils.NotebookHelper(...)` - **Do NOT check if resource group exists here**
4. Get account info:
   - Call `get_account_info()` to retrieve subscription ID and user info
5. Final line: `print_ok('Notebook initialized')`

**Important:** Do NOT call `az` commands in this cell. Do NOT create a config dictionary. Do NOT initialize deployment outputs. All Azure operations and variable definitions should happen in subsequent operation cells.

#### Cell 5+: Functional Cells (Markdown + Code pairs)
- Each logical operation gets a markdown heading cell followed by one or more code cells

**First operation cell (typically deployment):**

⚠️ **CRITICAL**: Use `nb_helper.deploy_sample()` for all sample deployments. This method:
  - Automatically validates the infrastructure exists (checks resource group)
  - Prompts user to select or create infrastructure if needed
  - Handles all Azure availability checks internally
  - Returns deployment outputs including the APIM service name

**Process:**
1. Print configuration summary using variables from init cell
2. Build `bicep_parameters` dict with sample-specific parameters (e.g., `location`, `costExportFrequency`)
   - **DO NOT** manually query for APIM services
   - **DO NOT** pass `apimServiceName` to `bicep_parameters` if the infrastructure already provides it
3. Call `nb_helper.deploy_sample(bicep_parameters)` to deploy Bicep template
4. Extract deployment outputs and store as **individual variables** (not in a dictionary)
   - Example: `apim_name = output.get('apimServiceName')`, `app_insights_name = output.get('applicationInsightsName')`

**Invalid approach** (do NOT do this):
```python
# ❌ WRONG - Manual APIM service queries
apim_list_result = az.run(f'az apim list --resource-group {rg_name}...')
apim_name = apim_list_result.json_data[0]['name']  # WRONG!

# ❌ WRONG - Passing APIM name in bicep parameters when it should come from output
bicep_parameters = {'apimServiceName': {'value': apim_name}}
```

**Valid approach** (do this):
```python
# ✅ CORRECT - Let deploy_sample() handle infrastructure validation
bicep_parameters = {
    'location': {'value': rg_location},
    'costExportFrequency': {'value': cost_export_frequency}
}
output = nb_helper.deploy_sample(bicep_parameters)
apim_name = output.get('apimServiceName')  # Get from output
```

**Subsequent cells:**
- Check prerequisites with `if 'variable_name' not in locals(): raise SystemExit(1)`
- Use variables directly in code (e.g., `rg_name`, `subscription_id`, `apim_name`)
- Do NOT recreate or duplicate variables from previous cells
- Follow pattern: Markdown description → Code implementation → Output validation

### Variable Management

**Do NOT use a config dictionary.** Use individual variables that flow naturally through cells:
- Init cell defines user and system configuration variables
- Deployment cell creates new variables for deployment outputs (e.g., `apim_name`, `app_insights_name`)
- Subsequent cells reference these variables directly
- Check prerequisites using `if 'variable_name' not in locals():` pattern
- Variables created in one cell are automatically available in all subsequent cells

Example:
```python
# Init cell
apim_sku = APIM_SKU.BASICV2
deployment = INFRASTRUCTURE.SIMPLE_APIM
subscription_id = get_account_info()[2]

# Deployment cell
apim_name = apim_services[0]['name']
app_insights_name = output.get('applicationInsightsName')

# Cost export cell
if 'app_insights_name' not in locals():
    raise SystemExit(1)
storage_account_id = f'/subscriptions/{subscription_id}/...'
```

### NotebookHelper Usage

**What NotebookHelper does:**
- `__init__()`: Initializes with sample folder, resource group name, location, infrastructure type, and supported infrastructure list
- `deploy_sample(bicep_parameters)`: Orchestrates the complete deployment process:
  1. Checks if the desired resource group/infrastructure exists
  2. If not found, queries all available infrastructures and prompts user to select or create new
  3. Executes the Bicep deployment with provided parameters
  4. Returns `Output` object containing deployment results (resource names, IDs, connection strings, endpoints)

**How to use:**
1. Initialize in the configuration cell (Cell 4):
   ```python
   nb_helper = utils.NotebookHelper(
       sample_folder,
       rg_name,
       rg_location,
       deployment,
       supported_infras,
       index=index,
       apim_sku=APIM_SKU.BASICV2  # Optional: default is BASICV2
   )
   ```

2. Call in the deployment cell (Cell 5+):
   ```python
   bicep_parameters = {
       'location': {'value': rg_location},
       # ... other sample-specific parameters
   }
   output = nb_helper.deploy_sample(bicep_parameters)
   ```

3. Extract outputs:
   ```python
   apim_name = output.get('apimServiceName')
   app_insights_name = output.get('applicationInsightsName')
   # ... extract all needed resources
   ```

**CRITICAL: Do not bypass NotebookHelper!**
- ❌ Do NOT manually check `az group exists`
- ❌ Do NOT manually query `az apim list` to find APIM services
- ❌ Do NOT check if resources exist before deployment
- ✅ Let `deploy_sample()` handle all infrastructure validation, selection, and existence checking

### Bicep Template (`main.bicep`)

- Deploy only resources specific to the sample (don't re-deploy APIM infrastructure)
- Accept parameters for APIM service name, location, sample-specific config
- Use `shared/bicep/` modules where available for reusable components
- Return outputs for all created resources (names, IDs, connection strings, etc.)

### Sample README.md

Every sample README must follow this standard layout to maintain uniformity across the repository. Users should be able to predict where to find each piece of information:

- **Title** - `# Samples: [Sample Name]`
- **Description** - One to two sentences summarising the sample
- **Supported infrastructures badge** - `⚙️ **Supported infrastructures**: ...`
- **Expected runtime badge** - `👟 **Expected *Run All* runtime (excl. infrastructure prerequisite): ~N minutes**`
- **🎯 Objectives** - Numbered list of learning or experimentation goals
- **📝 Scenario** (if applicable) - Use case or scenario context; omit if not relevant
- **🛩️ Lab Components** - What the lab deploys and how it benefits the user
- **⚙️ Configuration** - How to choose an infrastructure and run the notebook
- **🧹 Clean Up** (if applicable) - Reference to a clean-up notebook or manual steps
- **🔗 Additional Resources** (if applicable) - Links to relevant documentation

Match the heading emojis, heading levels, and section ordering exactly. If a section is not applicable, omit it entirely rather than leaving it empty.

### Testing and Traffic Generation

- Use the `ApimRequests` and `ApimTesting` classes from `apimrequests.py` and `apimtesting.py` for all API testing and traffic generation in notebooks.
- Do not use the `requests` library directly for calling APIM endpoints.
- Use `utils.get_endpoint(deployment, rg_name, apim_gateway_url)` to determine the correct endpoint URL and headers based on the infrastructure type.
- Example:
  ```python
  from apimrequests import ApimRequests
  from apimtesting import ApimTesting

  tests = ApimTesting("Sample Tests", sample_folder, nb_helper.deployment)
  endpoint_url, request_headers = utils.get_endpoint(deployment, rg_name, apim_gateway_url)
  reqs = ApimRequests(endpoint_url, subscription_key, request_headers)

  output = reqs.singleGet('/api-path', msg='Calling API')
  tests.verify('Expected String' in output, True)
  ```

  ## Language-specific Instructions

  - Python: see `.github/copilot-instructions.python.md`
  - Bicep: see `.github/copilot-instructions.bicep.md`

## Formatting and Style

- Maintain consistent indentation and whitespace but consider Editor Config settings, etc, for the repository.
- Use only LF, never CRLF for line endings.
- Use blank lines to separate logical sections of code. Whitespace is encouraged for readability.
- Organize code into logical sections (constants, variables, private/public methods, etc.).
- Prefer single over double quotes, avoiding typographic quotes.
- Only use apostrophe (U+0027) and quotes (U+0022), not left or right single or double quotation marks.
- Do not localize URLs (e.g. no "en-us" in links).
- Never use emoji variation selectors in Markdown. They are sneaky little things that can cause rendering and Markdown anchor link issues.

## Testing and Edge Cases

- Include test cases for critical paths and edge cases.
- Include negative tests to ensure robustness.
- Document expected behavior for edge cases and error handling.
- Write unit tests for functions and classes, following language-specific testing frameworks.

## Required before each commit
- Ensure all code is well-documented and follows the guidelines in this file.
- Ensure that Jupyter notebooks do not contain any cell output.
- Ensure that Jupyter notebooks have `index` assigned to `1` in the first cell.

## Jupyter Notebook Instructions

- Use these [configuration settings](https://github.com/microsoft/vscode-jupyter/blob/dd568fde/package.nls.json) as a reference for the VS Code Jupyter extension configuration.

### PlantUML Instructions

- Ensure you verify that all include links are correct and up to date. This link provides a starting point: https://github.com/plantuml-stdlib/Azure-PlantUML/blob/master/AzureSymbols.md
- Keep diagrams simple. For Azure, include major components, not individual aspects of components. For example, there is no need for individual policies in WAFs or APIs in API Management, Smart Detector Alert Rules, etc.
- Less is more. Don't be too verbose in the diagrams.
- Never include subscription IDs, resource group names, or any other sensitive information in the diagrams. That data is not relevant.
- Don't use the "legend" command if the information is relatively obvious.

### KQL (Kusto Query Language) Instructions

- Store KQL queries in dedicated `.kql` files within the sample folder rather than embedding them inline in Python code. This keeps notebooks readable and lets users copy-paste the query directly into a Log Analytics or Azure Data Explorer query editor.
- Load `.kql` files at runtime using `utils.determine_policy_path()` and `Path.read_text()`:
  ```python
  from pathlib import Path
  kql_path = utils.determine_policy_path('my-query.kql', sample_folder)
  kql_query = Path(kql_path).read_text(encoding='utf-8')
  ```
- Parameterise KQL queries using native `let` bindings. Define parameters as `let` statements prepended to the query body at runtime, keeping the `.kql` file free of Python string interpolation:
  ```python
  kusto_query = f"let buName = '{bu_name}';\nlet threshold = {alert_threshold};\n{kql_template}"
  ```
- In the `.kql` file, document available parameters in a comment header so users know which `let` bindings to supply:
  ```kql
  // Parameters (prepend as KQL 'let' bindings before running):
  //   let buName    = 'bu-hr';     // Business unit subscription ID
  //   let threshold = 1000;        // Request count threshold
  ApiManagementGatewayLogs
  | where ApimSubscriptionId == buName
  | summarize RequestCount = count()
  | where RequestCount > threshold
  ```
- When executing KQL via `az rest` or `az monitor log-analytics query`, write the query body to a temporary JSON file and pass it with `--body @tempfile.json` to avoid shell pipe-character interpretation issues on Windows.

### API Management Policy XML Instructions

- Policies should use camelCase for all variable names.
