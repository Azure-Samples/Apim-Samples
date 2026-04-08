# Agent Instructions for APIM Samples

This document provides AI agents with structured guidance for working with the Azure API Management (APIM) Samples repository.

## Repository Purpose

This repository provides resources to deploy Azure API Management infrastructures and experiment with APIM policies. It offers:

- **Infrastructures**: Pre-built Azure architectures featuring APIM in various configurations
- **Samples**: Real-world policy examples that can be deployed to any supported infrastructure
- **Shared Resources**: Reusable Bicep modules, Python helpers, and policy templates

## Repository Structure

```text
/
├── infrastructure/          # Azure infrastructure deployments
│   ├── afd-apim-pe/         # Azure Front Door + APIM with Private Endpoint
│   ├── apim-aca/            # APIM with Azure Container Apps
│   ├── appgw-apim/          # Application Gateway + APIM (VNet)
│   ├── appgw-apim-pe/       # Application Gateway + APIM with Private Endpoint
│   └── simple-apim/         # Basic APIM setup (fastest, lowest cost)
│
├── samples/                 # APIM policy samples
│   ├── _TEMPLATE/           # Template for creating new samples
│   ├── authX/               # Authentication and authorization
│   ├── authX-pro/           # Advanced auth with policy fragments
│   ├── azure-maps/          # Azure Maps integration
│   ├── costing/             # APIM costing and showback
│   ├── egress-control/      # Egress control via NVA routing
│   ├── general/             # Basic policy demonstrations
│   ├── load-balancing/      # Backend pool load balancing
│   ├── oauth-3rd-party/     # OAuth 3rd-party (Spotify example)
│   └── secure-blob-access/  # Valet key pattern for blob storage
│
├── shared/                  # Reusable components
│   ├── apim-policies/       # Common APIM policy XML files
│   ├── bicep/modules/       # Versioned Bicep modules
│   ├── jupyter/             # Reusable Jupyter notebooks
│   └── python/              # Python helper modules
│
├── tests/                   # Unit tests for Python code
│   └── python/              # pytest-based tests
│
├── setup/                   # Environment setup scripts
├── assets/                  # Images and diagrams
└── .github/                 # CI/CD and Copilot instructions
    ├── agents/              # Custom agents for focused repository workflows
    ├── copilot-instructions.md
    └── skills/              # Agent skills for specialized tasks
```

## Key Files in Each Sample/Infrastructure

| File              | Purpose                                                        |
| ----------------- | -------------------------------------------------------------- |
| `README.md`       | Documentation, objectives, and configuration instructions      |
| `create.ipynb`    | Jupyter notebook for deploying the sample                      |
| `main.bicep`      | Bicep template defining Azure resources                        |
| `clean-up.ipynb`  | (Infrastructure only) Teardown notebook                        |
| `*.xml`           | APIM policy files                                              |

## Available Skills

Use these skills for specialized tasks. Skills are located in `.github/skills/`.

| Skill               | When to Use                                                                                      |
| ------------------- | ------------------------------------------------------------------------------------------------ |
| **sample-creator**  | Creating new samples under `samples/` following the `_TEMPLATE` structure                        |
| **apim-bicep**      | Writing Bicep templates for APIM resources (APIs, backends, policies, products)                  |
| **apim-policies**   | Creating or modifying APIM XML policies (inbound/outbound, authentication, rate limiting)        |

## Available Agents

Use these custom agents for focused repository workflows. Agents are located in `.github/agents/`.

| Agent                   | When to Use                                                                                                                                                 |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **APIM Sample Creator** | Adding a new sample, gathering missing sample metadata, scaffolding from `_TEMPLATE`, and updating README, website, slide deck, and compatibility artifacts |

### How to Use Skills

When a task matches a skill's domain, read the skill file first:

```text
.github/skills/<skill-name>/SKILL.md
```

Skills provide templates, patterns, and step-by-step workflows.

## Creating New Samples

### Quick Process

1. **Prefer the custom agent**: Use `.github/agents/apim-sample-creator.agent.md` for end-to-end sample creation.
2. **Read the skill**: Load `.github/skills/sample-creator/SKILL.md`
3. **Gather requirements**: Sample name, description, supported infrastructures, learning objectives
4. **Create folder**: `samples/<sample-name>/` unless the user explicitly requests another location
5. **Create required files**:
   - `README.md` - Follow the template structure
   - `create.ipynb` - Jupyter notebook with initialization, deployment, and verification cells
   - `main.bicep` - Reference shared modules from `shared/bicep/modules/`
   - `*.xml` - Policy files (if needed)
6. **Update repo surfaces**:
    - Root `README.md` sample table
    - `docs/index.html` sample cards and JSON-LD list
    - `assets/APIM-Samples-Slide-Deck.html` when sample inventory or descriptions are shown
    - `tests/Test-Matrix.md`
    - Compatibility diagrams when supported infrastructures change visually

### Sample Addition Requirements

- Ask the user for the sample name if it is not provided.
- Ask the user for supported infrastructures if they are not provided.
- Keep sample display names consistent across README tables, the website, the slide deck, and compatibility artifacts.
- If a broadly useful improvement is discovered while creating a sample, suggest updating `samples/_TEMPLATE` so future samples inherit it.

### Sample Naming Conventions

- **Folder**: kebab-case (e.g., `oauth-validation`, `rate-limiting`)
- **API prefix**: Short, unique, with trailing hyphen (e.g., `oauth-`, `rl-`)
- **Policy files**: Descriptive, kebab-case (e.g., `token-validation.xml`)
- **Admin APIs**: Samples needing admin/operational endpoints use path `{api_prefix}admin` with `subscriptionRequired=True` and kebab-case operation paths (e.g., `/load-cache`)

### Infrastructure Constants

Available in Python via `from apimtypes import INFRASTRUCTURE`:

| Constant                            | Description                                           |
| ----------------------------------- | ----------------------------------------------------- |
| `INFRASTRUCTURE.AFD_APIM_PE`        | Azure Front Door + APIM with Private Endpoint         |
| `INFRASTRUCTURE.APIM_ACA`           | APIM with Azure Container Apps                        |
| `INFRASTRUCTURE.APPGW_APIM`         | Application Gateway + APIM (VNet injection)           |
| `INFRASTRUCTURE.APPGW_APIM_PE`      | Application Gateway + APIM with Private Endpoint      |
| `INFRASTRUCTURE.SIMPLE_APIM`        | Basic APIM setup                                      |

## Working with Existing Samples

### Running a Sample

1. Ensure an infrastructure is deployed (or will be created on first run)
2. Open `samples/<sample-name>/create.ipynb`
3. Adjust `USER CONFIGURATION` section if needed
4. Execute all cells

### Modifying Policies

1. Edit the `*.xml` policy file in the sample folder
2. Re-run the deployment cell in `create.ipynb`
3. Test via the verification cells

### Adding APIs to a Sample

In `create.ipynb`, define APIs using:

```python
from apimtypes import API, GET_APIOperation, POST_APIOperation

# Create operations
get_op = GET_APIOperation('Description of the operation')
post_op = POST_APIOperation('Description', policyXml = '<policy-xml>')

# Create API
api = API(
    '<name>',               # API name (resource identifier)
    '<Display Name>',       # Human-readable display name
    '<path>',               # URL path segment (often same value as name)
    '<Description>',        # API description
    operations = [get_op, post_op],
    tags = ['tag1', 'tag2']
)

# Add to apis array
apis = [api]
```

## Python Modules

Key modules in `shared/python/`:

| Module               | Purpose                                                     |
| -------------------- | ----------------------------------------------------------- |
| `utils.py`           | NotebookHelper, policy loading, endpoint helpers            |
| `apimtypes.py`       | Type definitions (API, INFRASTRUCTURE, APIM_SKU)            |
| `azure_resources.py` | Azure CLI wrappers for resource management                  |
| `console.py`         | Formatted console output (print_ok, print_error)            |
| `apimrequests.py`    | HTTP request helpers for testing APIs                       |
| `apimtesting.py`     | Test framework for sample verification                      |

## Bicep Modules

Shared modules in `shared/bicep/modules/`:

- Use versioned modules (e.g., `v1/api.bicep`) for stability
- Reference with relative paths: `../../shared/bicep/modules/apim/v1/api.bicep`
- See `apim-bicep` skill for APIM-specific patterns

## Code Quality Requirements

### Python

- Follow Ruff configuration in `pyproject.toml`
- Use type hints and docstrings
- Run `ruff check` before committing
- Tests in `tests/python/` with pytest

### Bicep

- Follow `bicepconfig.json` linter rules
- Use `@description` for all parameters
- Include Microsoft Learn template reference links above resources
- Follow section structure: Parameters → Constants → Variables → Resources → Outputs

### Jupyter Notebooks

- Clear all cell outputs before committing
- Set `index = 1` in the first code cell
- Follow the standard cell structure from `_TEMPLATE`

## Testing

### Running Tests

```bash
# Via Developer CLI
./start.ps1  # Windows
./start.sh   # macOS/Linux
# Select "Tests" menu

# Or directly
pytest tests/python/
ruff check shared/python/
```

### Writing Tests

- Place tests in `tests/python/`
- Mock Azure CLI interactions (no live Azure access in tests)
- Target 95%+ code coverage
- Use `test_helpers.py` for common test utilities

## Common Tasks Reference

| Task                   | Skill to Use   | Key Files                    |
| ---------------------- | -------------- | ---------------------------- |
| Create a new sample    | sample-creator | `samples/_TEMPLATE/*`        |
| Write APIM policies    | apim-policies  | `shared/apim-policies/*.xml` |
| Create Bicep templates | apim-bicep     | `shared/bicep/modules/`      |

## Additional Resources

- **Troubleshooting**: See `TROUBLESHOOTING.md` for common issues
- **Contributing**: See `CONTRIBUTING.md` for contribution guidelines
- **Language-specific instructions**:
  - Python: `.github/python.instructions.md`
  - Bicep: `.github/bicep.instructions.md`
  - JSON: `.github/json.instructions.md`
