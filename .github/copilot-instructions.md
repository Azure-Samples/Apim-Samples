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

- When the user asks about **Python** or a Python file is referenced in the chat context, prefer guidance and examples from `./python.instructions.md`.
- When the user asks about **Bicep** or a Bicep file is referenced in the chat context, prefer guidance and examples from `./bicep.instructions.md`.
- When the user asks about **JSON** or a JSON file is referenced in the chat context, prefer guidance and examples from `./json.instructions.md`.
- When the user asks about **GitHub Workflows** or workflow files (`.github/workflows/*.yml`) are referenced in the chat context, prefer guidance and examples from `./github-workflows.instructions.md`.
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
- Treat accessibility as a default quality requirement across the entire repository, not only for presentations.
- New or updated user-facing experiences (docs, webpages, notebooks, dashboards/workbooks, and slide content) must target WCAG 2.0 AA contrast and non-color-only communication as the baseline.

## Consistency & Uniformity

Uniformity, clarity, and ease of use are paramount across all infrastructures and samples. Every infrastructure and every sample should look and feel as alike as possible so that users maintain familiarity as they move between them. A user who has completed one sample should never feel like they are viewing something entirely new when they open the next.

- **Follow the established templates.** New infrastructures must follow the structure of existing infrastructures. New samples must follow `samples/_TEMPLATE`. Deviations are permitted only when a sample has genuinely unique requirements, and those deviations should be minimal.
- **Use consistent naming, headings, and cell order.** Markdown headings, variable names, section labels (e.g. `USER CONFIGURATION`, `SYSTEM CONFIGURATION`), emoji usage, and code cell ordering must match the patterns established by the template and existing artefacts.
- **Keep README structure uniform.** Infrastructure READMEs and sample READMEs each follow their own standard layout (see the guidelines below). Readers should be able to predict where to find objectives, configuration steps, and execution instructions.
- **Reuse shared utilities.** Use `NotebookHelper`, `InfrastructureNotebookHelper`, `ApimRequests`, `ApimTesting`, and shared Bicep modules rather than inventing ad-hoc alternatives. Shared code is the single best tool for enforcing uniformity.
- **Mirror tone and depth.** Similar sections across artefacts should use similar levels of detail. If one sample's README explains configuration in three sentences, another sample of comparable complexity should do the same.
- **Sort samples alphabetically.** Wherever samples are listed (README tables, landing page cards, JSON-LD structured data, diagrams, AGENTS.md), they must appear in alphabetical order by their display name. Infrastructures keep their current deliberate ordering.
- **Use consistent sample display names.** The display name used for a sample in README tables, landing page cards, JSON-LD, and compatibility diagrams must be identical. The canonical name is the one shown in the compatibility-matrix SVG diagram (e.g. "Costing", not "Costing & Showback"; "OAuth 3rd-Party", not "Credential Manager (with Spotify)"). Longer descriptions belong in the Description column or card body text, not in the name.
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

## Linting and Style

- Ruff is the Python linter; follow `pyproject.toml` for line length and rule selection.
- Prefer explicit imports over `from module import *` to avoid `F403/F405`.
- Wrap long strings or function calls to stay within the configured line length.

## Repository Structure

- `/`: Root directory containing the main files and folders. Bicep configuration is stored in `bicepconfig.json`.
- The following folders are all at the root level:
    - `assets/`: Draw.io diagrams, SVG exports, and images. Static assets such as these should be placed here. Architecture diagrams should be placed in the /diagrams subfolder.
    - `docs/`: Source for the public GitHub Pages landing page. See the *GitHub Pages Site* section below for upkeep rules.
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
- Standard text: "When you're finished experimenting, it's advisable to remove all associated resources from Azure to avoid unnecessary cost. Use the clean-up notebook for that."

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
- `apim-policies/*.xml` - Sample-owned APIM policy files (if applicable to the sample)
- `queries/*.kql` - KQL (Kusto Query Language) files (if applicable to the sample)

New sample-owned APIM policy XML and KQL files must not be placed at the sample root. Existing root-level files may remain until their sample is migrated.

### New Sample Sync Checklist

Whenever a new sample is added:
- Ask for the sample name if it has not been provided. Do not invent it.
- Ask for supported infrastructures if they have not been provided. Do not assume "All infrastructures".
- Create the sample under `samples/[sample-name]/` unless the user explicitly requests another location.
- Use `samples/_TEMPLATE` as the baseline and suggest updating the template if the improvement should apply to future samples.
- Update the root `README.md` sample table in alphabetical order.
- Update `docs/index.html`, including the matching sample card and JSON-LD `ItemList` entry.
- Update `assets/APIM-Samples-Slide-Deck.html` when the sample catalog, counts, or descriptions are surfaced in the deck.
- Update `tests/Test-Matrix.md` and `assets/diagrams/Infrastructure-Sample-Compatibility.svg` (add a new row for the sample in alphabetical order, marking each infrastructure as compatible or not).
- Keep the canonical sample display name identical across README tables, website cards, slide deck content, and compatibility diagrams.

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
   - `rg_location`: Azure region (default: `Region.EAST_US_2`)
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

#### Always reuse infrastructure-provided resources

Samples must default to **reusing the resources already created by the infrastructure deployment**. Do not redeploy resources the infrastructure already provides — this creates duplicate Azure resources, costs extra money, can misconfigure APIM logger wiring, and confuses users about which resource is "the real one".

The simple-apim infrastructure (and equivalents) already provides:

- An **APIM service** (with `apim-logger` already attached)
- A **Log Analytics workspace** (already wired to APIM diagnostics)
- An **Application Insights** component (already wired as the APIM logger)

Sample `main.bicep` files must consume these via `existing` resource references rather than `module ... = { ... }` deployments. The sample's `create.ipynb` should read the infrastructure's resource names from `nb_helper.deployment_outputs` (populated by `deploy_sample()`) — these include `applicationInsightsName`, `logAnalyticsWorkspaceName`, `apimServiceName`, etc.

A sample may deploy **its own** Application Insights, Log Analytics, or other shared monitoring infrastructure **only** when one of these conditions holds:

1. The sample needs **isolation** from other samples (e.g. a dedicated workspace for cost data that must not mix with other samples' telemetry).
2. The sample's resource has **sample-specific configuration** that cannot be applied to the shared infrastructure resource without affecting other samples (e.g. a custom retention policy, a different region for compliance).
3. The sample exercises a **scenario** where having a separate resource is the point of the sample (e.g. a sample demonstrating multi-workspace federation).

When a sample does deploy its own version of an infrastructure-provided resource, the sample README must include a short section explaining **why** the duplicate is necessary and how it differs from the infrastructure-provided one.

When wiring APIM API-level diagnostics (`apimLoggerName` parameter on `shared/bicep/modules/apim/v1/api.bicep`), **omit the parameter** so the API inherits the infrastructure's `apim-logger`. Only set `apimLoggerName` when the sample has a justified reason (per the rules above) to point a specific API at a different logger.

### Sample README.md

Every sample README must follow this standard layout to maintain uniformity across the repository. Users should be able to predict where to find each piece of information:

- **Title** - `# Samples: [Sample Name]`
- **Description** - One to two sentences summarising the sample
- **Supported infrastructures badge** - `⚙️ **Supported infrastructures**: ...`
- **Expected runtime badge** - `👟 **Expected *Run All* runtime (excl. infrastructure prerequisite): ~N minutes**`
- **🎯 Objectives** - Numbered list of learning or experimentation goals
- **✅ Prerequisites** (if applicable) - Sample-specific prerequisites only; see rules below
- **📝 Scenario** (if applicable) - Use case or scenario context; omit if not relevant
- **🛩️ Lab Components** - What the lab deploys and how it benefits the user
- **⚙️ Configuration** - How to choose an infrastructure and run the notebook
- **🖼️ Expected Results** (if applicable) - Screenshots and descriptions of what the user should see after running the sample
- **🧹 Clean Up** (if applicable) - Reference to a clean-up notebook or manual steps
- **🔗 Additional Resources** (if applicable) - Links to relevant documentation

Match the heading emojis, heading levels, and section ordering exactly. If a section is not applicable, omit it entirely rather than leaving it empty.

#### Prerequisites rules

- **Do NOT repeat general prerequisites** (Azure subscription, Azure CLI, Python environment, APIM instance). These are documented once in the root README's [Getting Started](../../README.md#-getting-started) section and apply to all samples. The APIM Samples Developer CLI (`start.ps1` / `start.sh`) handles environment setup.
- **Only add `## ✅ Prerequisites`** when a sample has genuinely unique requirements that go beyond the root README, such as:
  - Additional Azure RBAC role assignments beyond Contributor
  - External service accounts (e.g., a Spotify developer account)
  - Special tooling or configuration not covered by the Developer CLI
- When a Prerequisites section is needed, **open with a one-line reference** to the root README for general prerequisites, then list only the sample-specific requirements. Example:
  ```markdown
  ## ✅ Prerequisites

  Beyond the [general prerequisites](../../README.md#-getting-started) (Azure subscription, CLI, Python environment), this sample requires ...
  ```
- The `oauth-3rd-party` sample is the canonical example of sample-specific prerequisites (external service accounts). The `costing` sample is the canonical example of additional RBAC requirements.

### Testing and Traffic Generation

- Use the `ApimRequests` and `ApimTesting` classes from `apimrequests.py` and `apimtesting.py` for structured API testing with verbose logging and response formatting.
- **Favour `requests.Session()` for loops, multi-caller traffic, and any code that sends more than one HTTP request.** Creating a new `ApimRequests` instance (or a bare `requests.get/post`) inside a loop opens a fresh TCP+TLS connection on every iteration, adding 200-500 ms per request. Instead, create a single `requests.Session()` at the top of the section, configure `session.verify` and `session.headers` once from `utils.get_endpoint()`, and route all calls through it. Close the session in a `finally` block. Import as `import requests as http_requests` for clarity when the `requests` name would shadow other uses.
- `ApimRequests` already uses a session internally for its `multiGet`/`multiPost` methods, so a single `ApimRequests` instance per loop iteration is acceptable when you need its verbose logging. However, if you only need to send requests without per-request logging, prefer a raw `requests.Session()` loop — it is simpler and avoids creating throw-away objects.
- **One session per cell is fine.** Each notebook cell should be independently runnable, so create and close a session within the same cell rather than sharing one across cells.
- Use `utils.get_endpoint(deployment, rg_name, apim_gateway_url)` to determine the correct endpoint URL, headers, and TLS verification flag based on the infrastructure type. `allow_insecure_tls` is returned as `True` only for Application Gateway infrastructures because they use a self-signed certificate; it defaults to `False` everywhere else.
- Session pattern example (preferred for loops):
  ```python
  import requests as http_requests

  endpoint_url, request_headers, allow_insecure_tls = utils.get_endpoint(deployment, rg_name, apim_gateway_url)

  session = http_requests.Session()
  session.verify = not allow_insecure_tls
  if request_headers:
      session.headers.update(request_headers)
  session.headers['Ocp-Apim-Subscription-Key'] = subscription_key

  url = f'{endpoint_url}/api-path'

  try:
      for item in items:
          session.get(url, headers={'Authorization': f'Bearer {item["token"]}'}, timeout=30)
  finally:
      session.close()
  ```
- ApimRequests example (for structured test verification with logging):
  ```python
  from apimrequests import ApimRequests
  from apimtesting import ApimTesting

  tests = ApimTesting("Sample Tests", sample_folder, nb_helper.deployment)
  endpoint_url, request_headers, allow_insecure_tls = utils.get_endpoint(deployment, rg_name, apim_gateway_url)
  reqs = ApimRequests(endpoint_url, subscription_key, request_headers, allowInsecureTls=allow_insecure_tls)

  output = reqs.singleGet('/api-path', msg='Calling API')
  tests.verify('Expected String' in output, True)
  ```

### Notebook Cell Ordering: Batch Traffic, Then Verify

Telemetry pipelines (Log Analytics ingestion, Application Insights custom metrics, `ApiManagementGatewayLlmLog`, Cost Management exports) all have ingestion latency measured in **minutes, not seconds**. A naive notebook structure that alternates *generate traffic → wait/verify → generate more traffic → wait/verify* pays this latency tax repeatedly and stretches a sample's *Run All* time well beyond what it needs to be.

When designing or restructuring a sample notebook:

- **Batch all traffic generation first, then verify once at the end.** Group every traffic-generating cell into a contiguous block, followed by a contiguous block of verification cells. By the time the verification cells run, ingestion pipelines have already had several minutes of warm-up across the preceding traffic cells, so polling typically returns on the first attempt instead of on a cold-start retry schedule.
- **Avoid inline verification inside traffic cells.** A cell that sends traffic *and* polls for that traffic's metrics in the same cell forces every subsequent step to wait for that poll. If verification is genuinely useful, factor it out into a dedicated verification cell at the end of the notebook.
- **Group related cells with a shared prefix in the markdown heading.** When the notebook has multiple traffic cells and multiple verification cells, prefix each heading with a short tag so users immediately see which cells belong together. The `costing` sample uses `[Traffic]` and `[Verify]` prefixes (e.g. `### 7/14: [Traffic] Generate Sample API Traffic`, `### 12/14: [Verify] Verify Log Ingestion`). Keep prefixes short, bracketed, and consistent within a notebook.
- **Place setup-time work (alerts, exports, dashboards) before traffic cells**, so the demo traffic exercises them end-to-end. For example, budget alerts should be created *before* traffic is generated, not after.
- **Place context cells (pricing tables, cost models, reference data) before action cells.** A pricing-and-cost-analysis cell that does no Azure calls should run early so users see the cost framing before they generate billable traffic, not as a postscript.
- **Reuse polling output across verifications when possible.** If two verification cells query the same workspace or component, consolidate them into a single cell or schedule their polls so the second one benefits from the warm pipeline established by the first.

## Language-specific Instructions

  - Python: see `.github/python.instructions.md`
  - Bicep: see `.github/bicep.instructions.md`
  - JSON: see `.github/json.instructions.md`
  - Markdown: see `.github/markdown.instructions.md`

## Formatting and Style

- Maintain consistent indentation and whitespace but consider Editor Config settings, etc, for the repository.
- Use only LF, never CRLF for line endings.
- Use blank lines to separate logical sections of code. Whitespace is encouraged for readability.
- Organize code into logical sections (constants, variables, private/public methods, etc.).
- Prefer single over double quotes, avoiding typographic quotes.
- Only use apostrophe (U+0027) and quotes (U+0022), not left or right single or double quotation marks.
- Use only ASCII punctuation in text content. Replace em-dashes (U+2014) and en-dashes (U+2013) with a plain hyphen-minus (`-`), the minus sign (U+2212) with `-`, the horizontal ellipsis (U+2026) with `...`, and math comparison glyphs (U+2264, U+2265, U+2260) with `<=`, `>=`, `!=`. These typographic characters do not always render correctly in downstream surfaces such as Azure Monitor Workbook markdown tiles, slide-deck HTML, and some terminal fonts. This rule applies to every text-bearing file in the repository, including Markdown, Python docstrings/comments, Bicep `@description` strings, XML policy comments, and **JSON string values that contain user-facing text (notably Azure Monitor Workbook `*.workbook.json` files where markdown is embedded in `content.json` strings).**
- Do not localize URLs (e.g. no "en-us" in links).

For Markdown-specific formatting guidelines (including critical rules about emoji variation selectors and table alignment), see `.github/markdown.instructions.md`.

## Testing and Edge Cases

- Include test cases for critical paths and edge cases.
- Include negative tests to ensure robustness.
- Document expected behavior for edge cases and error handling.
- Write unit tests for functions and classes, following language-specific testing frameworks.

## GitHub Pages Site

The public landing page at <https://azure-samples.github.io/Apim-Samples/> is built from `docs/index.html` by `.github/workflows/github-pages.yml` on every push to `main`. The page intentionally mirrors a subset of the root `README.md` (infrastructure cards, sample cards, quick-start steps) so that visitors get a polished overview without cloning the repo.

**Treat `docs/index.html` as a downstream consumer of the README.** When you change any of the following, update the landing page in the same PR:

| Change | Update required in `docs/index.html` | Also update |
|---|---|---|
| Add / remove / rename an **infrastructure** | Add / remove / rename the matching `.infra-card` **and** the matching `ListItem` in the JSON-LD `ItemList` (in `<head>`). Update the infrastructure count in the first `.value-card` if it still says "Five". | Add / remove the SVG copy line in `.github/workflows/github-pages.yml`. |
| Add / remove / rename a **sample** | Add / remove / rename the matching `.sample-card` **and** the matching `ListItem` in the JSON-LD `ItemList`. | — |
| Change a sample's **supported infrastructures** | Update the `.infra-tag` text on that sample's card. | — |
| Change the **quick-start flow** in the root README | Update the four `.step` items. | — |
| Rename or replace an **architecture SVG** in `assets/diagrams/` | — | Update the matching `cp` line in `.github/workflows/github-pages.yml`. |

Check `docs/README.md` for local preview instructions and styling notes. The page is deliberately plain static HTML + an external stylesheet (`docs/styles.css`), with no executable JavaScript and no build tooling, so that it cannot rot due to a transitive npm dependency. The only `<script>` tag is the JSON-LD structured-data block, which must stay inline because search-engine crawlers do not reliably follow external JSON-LD references. Keep it that way unless there is a compelling reason to add a build step.

## Required before each commit
- Ensure all code is well-documented and follows the guidelines in this file.
- Ensure that Jupyter notebooks do not contain any cell output.
- Ensure that Jupyter notebooks have `index` assigned to `1` in the first cell.
- If the change touches the infrastructure list, sample list, quick-start steps, or architecture SVGs, ensure `docs/index.html` (and the asset copy step in `.github/workflows/github-pages.yml` where relevant) has been updated to match.

## Jupyter Notebook Instructions

- Use these [configuration settings](https://github.com/microsoft/vscode-jupyter/blob/dd568fde/package.nls.json) as a reference for the VS Code Jupyter extension configuration.
- When generating or editing notebook files as JSON, structure the document with a top-level `cells` array.
- Each cell must be a valid JSON object with:
  - `cell_type`
  - `metadata.language`
  - `source`
- Existing cells must keep a unique `metadata.id` value.
- New cells do not need a `metadata.id` value unless an editor or tool assigns one.
- Keep notebook JSON logically structured and valid. Do not emit partial notebook fragments when a full notebook document is required.
- Place **all** `import` statements at the top of every code cell, before any other code. Never nest imports inside `if` / `else` / `try` blocks within a cell. Ruff's `PLC0415` does not flag imports inside module-level conditionals, so this must be enforced manually.
- When describing notebook changes to users, refer to cells by visible cell number (Cell 1, Cell 2, etc.), not by internal cell IDs.

### Presentation Instructions

- Presentation source files should remain accessible to a broad audience and should target WCAG 2.0 AA color contrast as the default baseline.
- Do not rely on color alone to communicate meaning. If a color distinguishes state, priority, or emphasis, pair it with text, icons, labels, or structure.
- Body text and other normal-sized text on slides should meet at least `4.5:1` contrast against their background. Large text (roughly `24px` regular or `18.66px` bold and above) and essential UI indicators should meet at least `3:1`.
- Pay special attention to helper text, footer text, captions, badge text, and text placed on gradients or translucent overlays. These are the most common places where contrast regressions appear.
- When using muted text on light backgrounds, prefer dark neutral tones over mid-gray decorative values. When using text on dark or gradient backgrounds, prefer near-white text unless the accent color has been checked for sufficient contrast.
- Preserve meaningful `alt` text for presentation images and diagrams, and avoid conveying critical information only inside images when the same message can be stated in text on the slide.
- If you introduce a new presentation theme or palette, validate the shared color tokens first so accessibility is enforced consistently across all slides.

### Diagram Instructions

- Architecture diagrams are maintained as Draw.io (`.drawio`) files in `assets/diagrams/`. SVG exports are co-located alongside the `.drawio` source files.
- The Draw.io diagrams were created with the [Azure Draw.io MCP Server](https://github.com/simonkurtz-MSFT/drawio-mcp-server).
- Keep diagrams simple. For Azure, include major components, not individual aspects of components. For example, there is no need for individual policies in WAFs or APIs in API Management, Smart Detector Alert Rules, etc.
- Less is more. Don't be too verbose in the diagrams.
- Sample names in compatibility-matrix diagrams are the canonical display names. README tables, landing page cards, and JSON-LD entries must use the same names. When adding or renaming a sample, update the diagram and all listings together.
- Samples in compatibility-matrix diagrams must be listed in alphabetical order by display name.
- Never include subscription IDs, resource group names, or any other sensitive information in the diagrams. That data is not relevant.

### KQL (Kusto Query Language) Instructions

- Store every sample-owned KQL query in a dedicated `.kql` file under `samples/<sample-name>/queries/` rather than at the sample root or embedded inline in Python code. This keeps notebooks readable and lets users copy-paste the query directly into a Log Analytics or Azure Data Explorer query editor.
- Resolve `.kql` files from the sample's `queries/` directory and load them with `Path.read_text()`:
  ```python
  from pathlib import Path

  kql_path = Path(utils.get_project_root()) / 'samples' / sample_folder / 'queries' / 'my-query.kql'
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

### Azure Monitor Workbook File Convention

Azure Monitor Workbook definitions stored in this repository must follow the **`<name>.workbook.json`** suffix convention. The double extension makes the file's purpose obvious at a glance, prevents collisions with other JSON artefacts in the same folder (Bicep parameter files, schemas, configuration), and groups all workbook source files under a single, greppable pattern.

- **Naming**: Use kebab-case for `<name>` and match the sample folder where reasonable (e.g. `costing.workbook.json` in `samples/costing/`, `latency.workbook.json` if a future sample adds one). One file per workbook.
- **Location**: Place the file in the sample folder that owns the workbook (e.g. `samples/<sample-name>/<sample-name>.workbook.json`). Workbooks shared across samples belong under `shared/` with a descriptive `<name>` prefix.
- **Schema**: The first property must be `"$schema": "https://raw.githubusercontent.com/Microsoft/Application-Insights-Workbooks/refs/heads/master/schema/workbook.json"`. Follow `.github/json.instructions.md` for `$schema` URL formatting.
- **Bicep loading**: When embedding the workbook in a Bicep template, load it via `loadJsonContent('<name>.workbook.json')` and serialise it to a string for `properties.serializedData`. Match the filename exactly — do not rename to `workbook.json` inside Bicep.
- **Push script**: A sample that ships a workbook should provide an `update-workbook.ps1` (or equivalent) helper that reads `<name>.workbook.json` and updates the deployed workbook resource via `az rest`. The script should accept a mandatory `-rg` parameter and preserve any user-edited workbook parameter values (e.g. cost rates) from the live resource so that re-pushing source-controlled changes does not clobber portal edits.
- **Tests**: Workbook JSON files should be parsed and structurally validated by a unit test (see `tests/python/test_costing_workbook.py` for the canonical pattern: schema check, parameter presence, KQL query well-formedness).

### Azure Monitor Workbook Query Optimization

Azure Monitor Workbook query items execute independently — there is no native mechanism to share a materialized table across query items. Apply the following patterns to minimise data scanned and improve workbook responsiveness:

- **`materialize()` for multi-reference `let` bindings.** When a `let` binding is referenced more than once in the same query (e.g. once for a `toscalar(count)` and once for the main `summarize`), wrap it in `materialize()` so Log Analytics computes the base set once per query execution rather than scanning the underlying table twice.
  ```kql
  let logs = materialize(ApiManagementGatewayLogs
  | where TimeGenerated {TimeRange} and ApimSubscriptionId startswith 'bu-');
  let totalRequests = toscalar(logs | summarize count());
  logs
  | summarize RequestCount = count() by ApimSubscriptionId
  | extend UsageShare = round(RequestCount * 100.0 / totalRequests, 2)
  ```
- **Column-project before joins.** When joining two tables, add an explicit `| project` on both sides to carry only the columns that the downstream `summarize`/`extend`/`project` actually needs. Wide diagnostic tables like `ApiManagementGatewayLlmLog` contain many columns; projecting only the needed ones before the join reduces memory and network cost.
  ```kql
  ApiManagementGatewayLlmLog
  | where TimeGenerated {TimeRange} and TotalTokens > 0
  | project CorrelationId, TotalTokens             // only what this query needs
  | join kind=inner (
      ApiManagementGatewayLogs
      | where TimeGenerated {TimeRange} and ApimSubscriptionId startswith 'bu-'
      | project CorrelationId, BusinessUnit = ApimSubscriptionId
  ) on CorrelationId
  | summarize TotalTokens = sum(TotalTokens) by BusinessUnit
  ```
- **Avoid duplicate queries across items.** If two workbook visualisations require identical data, consider whether they can share a single query item with different chart/table renderings, or whether the layout can be restructured to avoid scanning the same data twice. Workbook Merge items can combine two previously-computed result sets but cannot perform arbitrary re-aggregation.
- **Keep the Workbook `timeContext` on each query item** rather than relying solely on the global parameter. This ensures Log Analytics can push down the time filter to the storage layer even when the parameter is complex.
- **Prefer `summarize` close to the source.** Push `summarize` as early as possible in the pipeline to reduce the volume of rows flowing through subsequent operators.

### Admin APIs (`/admin/`) Convention

Samples that require administrative or operational endpoints (cache loading, configuration reloads, health checks, etc.) must place them under an **`/admin/`** API path. This establishes a consistent, recognisable pattern across all APIM Samples.

- **API path**: `{api_prefix}admin` (e.g. `cors-admin`, `lb-admin`). The sample's `api_prefix` keeps admin APIs namespaced per sample.
- **Subscription required**: Always `True`. Admin APIs must never be publicly accessible without a subscription key.
- **Production security**: Subscription keys are a baseline gate but are shared secrets, not identity-based auth. Production deployments should layer JWT validation (`validate-azure-ad-token` or `validate-jwt`) on top of subscription keys. See the `authX` and `authX-pro` samples for implementation patterns.
- **Naming**: Use kebab-case operation paths that describe the action (e.g. `/load-cache`, `/clear-cache`, `/refresh-config`).
- **Tags**: Include the sample's tags so the admin API is grouped with its sibling APIs in the APIM portal.
- **Documentation**: The admin API's display name should start with the option or sample context (e.g. `Option 3 Admin`) so its purpose is clear in the APIM portal.

### API Management Policy XML Instructions

- Store every sample-owned APIM policy XML file under `samples/<sample-name>/apim-policies/`. Keep reusable, cross-sample policy assets under `shared/apim-policies/`.
- When migrating existing samples, update policy path helpers to check `samples/<sample-name>/apim-policies/` first and the sample root second as a temporary backwards-compatible fallback. New files must use `apim-policies/`; do not rely on the fallback for newly created policies.
- After moving KQL or policy XML files, check and update every notebook, Python helper, Bicep `loadTextContent()` call, test, script, and documentation reference that consumes them. Add or update tests for canonical-directory resolution, root-level fallback, explicit paths, auto-detected sample names, and missing files before considering the migration complete.
- Policies should use camelCase for all variable names.
- In policy expressions inside double-quoted XML attributes, escape embedded double quotes as `&quot;` (for example, `value="@((string)context.Variables[&quot;callerId&quot;])"`). Unescaped quotes make the XML malformed. Expressions in element text, such as `<value>@("text")</value>`, do not require this escaping.
- Policy expressions (`@(...)` and `@{...}`) may **only** reference .NET types and members on APIM's [allow-list](https://learn.microsoft.com/azure/api-management/api-management-policy-expressions#CLRTypes). Using anything outside the list (e.g. `System.Globalization.*`, `DateTime.TryParse`, `DateTime.ToUniversalTime`, `System.Text.Json`) causes a deploy-time `ValidationError: One or more fields contain incorrect values` with no further detail. Verify each type/member against the allow-list before writing the expression. See `.github/skills/apim-policies/SKILL.md` for common pitfalls and allowed replacements.
