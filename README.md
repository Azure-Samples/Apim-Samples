# Azure API Management Samples

[![Python Tests](https://github.com/Azure-Samples/Apim-Samples/actions/workflows/python-tests.yml/badge.svg?branch=main)](https://github.com/Azure-Samples/Apim-Samples/actions/workflows/python-tests.yml)

This repository provides a playground to safely experiment with and learn Azure API Management (APIM) policies in various architectures.  

_If you are interested in APIM & Azure OpenAI integrations, please check out the excellent [AI Gateway](https://github.com/Azure-Samples/AI-Gateway) GitHub repository._

## 🎯 Objectives

1. Educate you on common APIM architectures we see across industries and customers.
1. Empower you to safely experiment with APIM policies.
1. Provide you with high-fidelity building blocks to further your APIM integration efforts.

_Try it out, learn from it, apply it in your setups._

---

## 📁 List of Infrastructures

| Infrastructure Name                                                               | Description                                                                                                                                                           |
|:----------------------------------------------------------------------------------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [Simple API Management](./infrastructure/simple-apim)                             | Just the basics with a publicly accessible API Management instance fronting your APIs. This is the innermost way to experience and experiment with the APIM policies. |
| [API Management & Container Apps](./infrastructure/apim-aca)                      | APIs are often implemented in containers running in Azure Container Apps. This architecture accesses the container apps publicly. It's beneficial to test both APIM and container app URLs here to contrast and compare experiences of API calls through and bypassing APIM. It is not intended to be a security baseline. |
| [Secure Front Door & API Management & Container Apps](./infrastructure/afd-apim-pe)  | A higher-fidelity implementation of a secured setup in which Azure Front Door connects to APIM via the new private link integration. This traffic, once it traverses through Front Door, rides entirely on Microsoft-owned and operated networks. Similarly, the connection from APIM to Container Apps is secured but through a VNet configuration (it is also entirely possible to do this via private link). APIM Standard V2 is used here to accept a private link from Front Door. |

## 📁 List of Samples

| Sample Name                                                              | Description                                                                                                         | Supported Infrastructure(s)   |
|:-------------------------------------------------------------------------|:--------------------------------------------------------------------------------------------------------------------|:------------------------------|
| [AuthX](./samples/authX/README.md)                                       | Authentication and role-based authorization in a mock HR API.                                                       | All infrastructures           |
| [AuthX Pro](./samples/authX-pro/README.md)                               | Authentication and role-based authorization in a mock product with multiple APIs and policy fragments.              | All infrastructures           |
| [General](./samples/general/README.md)                                   | Basic demo of APIM sample setup and policy usage.                                                                   | All infrastructures           |
| [Load Balancing](./samples/load-balancing/README.md)                     | Priority and weighted load balancing across backends.                                                               | apim-aca, afd-apim (with ACA) |
| [Secure Blob Access](./samples/secure-blob-access/README.md)             | Secure blob access via the [valet key pattern](https://learn.microsoft.com/azure/architecture/patterns/valet-key).  | All infrastructures           |
| [Credential Manager (with Spotify)](./samples/oauth-3rd-party/README.md) | Authenticate with APIM which then uses its Credential Manager with Spotify's REST API.                              | All infrastructures           |
| [Azure Maps](./samples/azure-maps/README.md)                             | Proxying calls to Azure Maps with APIM policies.                                                                    | All infrastructures           |

---

## 🏗️ Infrastructure Setup

### Quick Start Options

#### Option 1: GitHub Codespaces / Dev Container (Recommended)

The fastest way to get started is using our pre-configured development environment:

- **GitHub Codespaces**: Click the green "Code" button → "Codespaces" → "Create codespace on main"
- **VS Code Dev Containers**: Install the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers), then "Reopen in Container"

All prerequisites are automatically installed and configured. 

📖 **For detailed setup information, troubleshooting, and optimization details, see [Dev Container Documentation](.devcontainer/README.md)**

#### Option 2: Local Setup

### 📋 Prerequisites

These prerequisites apply broadly across all infrastructure and samples. If there are specific deviations, expect them to be noted there.

- [Python 3.12](https://www.python.org/) installed
  - Python 3.13 may not have all dependencies ready yet. There have been issues during installs.
- [VS Code](https://code.visualstudio.com/) installed with the [Jupyter notebook extension](https://marketplace.visualstudio.com/items?itemName=ms-toolsai.jupyter) enabled
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) installed
- [An Azure Subscription](https://azure.microsoft.com/free/) with Owner or Contributor+UserAccessAdministrator permissions. Execute [shared/jupyter/verify-az-account.ipynb](shared/jupyter/verify-az-account.ipynb) to verify.
- **Azure Authentication**: Sign in to Azure with Azure CLI using the specific tenant and subscription you want to work with:
  - To log in to a specific tenant: `az login --tenant <your-tenant-id-or-domain>`
  - To set a specific subscription: `az account set --subscription <your-subscription-id-or-name>`
  - To verify your current context: `az account show`
  - See the [Azure CLI authentication guide](https://learn.microsoft.com/cli/azure/authenticate-azure-cli-interactively) for more options

### 🛠️ Initialization

#### Using Dev Container (Recommended)

If you're using the dev container (GitHub Codespaces or VS Code Dev Containers):

1. Open the repository in the dev container environment
2. Wait for the automatic setup to complete (includes interactive Azure CLI configuration)
3. If prompted during setup, choose your preferred Azure CLI authentication method:
   - **Mount local config**: Preserves authentication between container rebuilds
   - **Manual login**: Requires tenant-specific `az login` after each container startup
   - **Configure later**: Skip for now, configure manually later
4. **Sign in to Azure with correct tenant and subscription**:
   - If you chose manual login or skipped: `az login --tenant <your-tenant-id-or-domain>`
   - Set the correct subscription: `az account set --subscription <your-subscription-id-or-name>`
   - Verify your authentication context: `az account show`
5. Verify your Azure setup by executing [shared/jupyter/verify-az-account.ipynb](shared/jupyter/verify-az-account.ipynb)

#### Manual Local Setup

If you're setting up locally without the dev container:

##### Quick Setup (Recommended)

1. **Create Python Environment**: In VS Code, use Ctrl+Shift+P → "Python: Create Environment" → "Venv" → Select Python version → Check requirements.txt
2. **Complete Environment Setup**: Run the automated setup script:
   ```bash
   python setup/setup_python_path.py --complete-setup
   ```
   For help and available options, run without arguments:
   ```bash
   python setup/setup_python_path.py
   ```
3. **Restart VS Code** to apply all settings
4. **Sign in to Azure**: `az login --tenant <your-tenant-id>` and `az account set --subscription <your-subscription>`

That's it! Your local environment now matches the dev container experience with:
- ✅ Standardized "APIM Samples Python 3.12" Jupyter kernel
- ✅ Automatic notebook kernel selection  
- ✅ Python path configured for shared modules
- ✅ VS Code optimized for the project

When you open any `.ipynb` notebook, it will automatically use the correct kernel and all imports will work seamlessly.

**🔍 Verify Setup**: Run `python setup/verify_local_setup.py` to confirm everything is working correctly.

##### Manual Step-by-Step Setup

If you prefer manual setup or the automated script doesn't work:

1. Open VS Code.
1. Invoke the _Command Palette_ via the _View_ menu or a shortcut (on Windows: Ctrl + Shift + P, on Mac: CMD + Shift + P).
1. Select _Python: Create Environment_.
1. Select _Venv_ as we want a local virtual environment.
1. Select the desired, installed Python version.
1. Check _requirements.txt_ to install the Python dependencies we need for this repo, then press _OK_. The install may take a few minutes. You can check on progress in the _OUTPUT_ window (select `Python`).
1. Verify the virtual environment is set up. You should see a new _.venv_ directory with a _pyveng.cfg_ file and the Python version you selected earlier.
1. Set up the project environment:
   ```bash
   python setup/setup_python_path.py --generate-env
   python setup/setup_python_path.py --setup-kernel  
   python setup/setup_python_path.py --setup-vscode
   ```
1. **Restart VS Code** to ensure all environment settings are loaded properly.

The first time you run a Jupyter notebook, you may be asked to install the Jupyter kernel package (ipykernel) if not already available.

#### 🔧 Troubleshooting Setup Issues

If you encounter import errors (e.g., `ModuleNotFoundError: No module named 'requests'` or cannot import shared modules), try these steps:

1. **Fix Python path configuration**:
   ```bash
   python setup/setup_python_path.py --generate-env
   ```

2. **Verify setup**:
   ```bash
   python setup/verify_local_setup.py
   ```

3. **Restart VS Code** after running the above commands.

4. **Check Python interpreter**: Use `Ctrl+Shift+P` → "Python: Select Interpreter" and choose your `.venv` interpreter.

For detailed troubleshooting of setup issues, see [Import Troubleshooting Guide](.devcontainer/IMPORT-TROUBLESHOOTING.md).

📘 **For comprehensive troubleshooting including deployment errors, authentication issues, and more, see our main [Troubleshooting Guide](TROUBLESHOOTING.md).**

## 🚀 Running a Sample

1. Open the desired sample's `create.ipynb` file.
1. Optional: Adjust the parameters under the `User-defined Parameters` header, if desired.
1. Execute the `create.ipynb` Jupyter notebook via `Run All`.

> A supported infrastructure does not yet need to exist before the sample is executed. The notebook will determine the current state and present you with options to create or select a supported infrastructure, if necessary.

Now that infrastructure and sample have been stood up, you can experiment with the policies, make requests against APIM, etc.

---

## Troubleshooting

Encountering issues? Check our comprehensive **[Troubleshooting Guide](TROUBLESHOOTING.md)** which covers:

- **Deployment Errors** - Including the common "content already consumed" error and parameter mismatches
- **Authentication Issues** - Azure CLI login problems and permission errors  
- **Notebook & Development Environment Issues** - Module import errors and Python path problems
- **Azure CLI Issues** - Rate limiting and API version compatibility
- **Resource Management Issues** - Resource group and APIM service problems

For immediate help with common errors, diagnostic commands, and step-by-step solutions, see **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)**.

---

## 📂 Repo Structure

### 🦅 High-level

- All _samples_ can be found in the `samples` folder. Samples showcase functionality and provide a baseline for your experimentation.
- All _infrastructures_ can be found in the `infrastructure` folder. They provide the architectural underpinnings.
- All shared code, modules, functionality, policies, etc. can be found in the `shared` folder. 
  - Bicep _modules_ are versioned in the `bicep/modules` folder. Major changes require versioning.
  - Python _modules_ are found in the `python` folder. _They are not versioned yet but may be in the future._ 
  - Reusable _APIM policies_ are found in the `apim-policies` folder. 
  - Reusable Jupyter notebooks are found in the `jupyter` folder.

### ⚙️ Sample Setup

- Each sample uses an architecture infrastructure. This keeps the samples free of almost all setup.
- Each infrastructure and sample features a `create.ipynb` for creation (and running) of the sample setup and a `main.bicep` file for IaC configuration.
- Each infrastructure contains a `clean-up.ipynb` file to tear down everything in the infrastructure and its resource group. This reduces your Azure cost.
- Samples (and infrastructures) may contain additional files specific to their use cases.

### 🏛️ Infrastructure Architectures

We provide several common architectural approaches to integrating APIM into your Azure ecosystem. While these are high-fidelity setups, they are not production-ready. Please refer to the [Azure API Management landing zone accelerator](https://learn.microsoft.com/azure/cloud-adoption-framework/scenarios/app-platform/api-management/landing-zone-accelerator) for up-to-date production setups.

---

## 🛠️ Development

As you work with this repo, you will likely want to make your own customizations. There's little you need to know to be successful.

The repo uses the bicep linter and has rules defined in `bicepconfig.json`. See the [bicep linter documentation](https://learn.microsoft.com/azure/azure-resource-manager/bicep/bicep-config-linter) for details.

**We welcome contributions!** Please consider forking the repo and creating issues and pull requests to share your samples. Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details. Thank you! 

### ➕ Adding a Sample

Adding a new sample is relatively straight-forward.

1. Create a new feature branch for the new sample.
1. Copy the `/samples/_TEMPLATE` folder.
1. Rename the copied folder to a name representative of the sample (e.g. "load-balancing", "authX", etc.)
1. Change the `create.ipynb` and `main.bicep` files. Look for the brackets (`[ ]`) brackets for specific inputs.
1. Add any policy.xml files to the same folder if they are specific to this sample. If they are to be reused, place them into the `/shared/apim-policies` folder instead.
1. Test the sample with all supported infrastructures.
1. Create a pull request for merge.

### 🧪 Testing & Code Coverage

Python modules in `shared/python` are covered by comprehensive unit tests located in `tests/python`. All tests use [pytest](https://docs.pytest.org/) and leverage modern pytest features, including custom markers for unit and HTTP tests.

#### 🚀 Running Tests Locally

- **PowerShell (Windows):**
  - Run all tests with coverage: `./tests/python/run_tests.ps1`
- **Shell (Linux/macOS):**
  - Run all tests with coverage: `./tests/python/run_tests.sh`

Both scripts:
- Run all tests in `tests/python` using pytest
- Generate a code coverage report (HTML output in `tests/python/htmlcov`)
- Store the raw coverage data in `tests/python/.coverage`

You can also run tests manually and see details in the console:
```sh
pytest -v --cov=shared/python --cov-report=html:tests/python/htmlcov --cov-report=term tests/python
```

#### 📊 Viewing Coverage Reports

After running tests, open `tests/python/htmlcov/index.html` in your browser to view detailed coverage information.

#### 🏷️ Pytest Markers

- `@pytest.mark.unit` — marks a unit test
- `@pytest.mark.http` — marks a test involving HTTP/mocking

Markers are registered in `pytest.ini` to avoid warnings.

#### ⚡ Continuous Integration (CI)

On every push or pull request, GitHub Actions will:
- Install dependencies
- Run all Python tests in `tests/python` with coverage
- Store the `.coverage` file in `tests/python`
- Upload the HTML coverage report as a workflow artifact for download

#### 📝 Additional Notes

- The `.gitignore` is configured to exclude coverage output and artifacts.
- All test and coverage features work both locally and in CI.

For more details on pytest usage, see the [pytest documentation](https://docs.pytest.org/en/8.2.x/).

---

## 📚 Supporting Resources

The APIM team maintains an [APIM policy snippets repo](https://github.com/Azure/api-management-policy-snippets) with use cases we have seen. They are not immediately executable samples and require integrations such as in this repo.

---

## 🙏 Acknowledgements

This project has its roots in work done by [Alex Vieira](https://github.com/vieiraae) on the excellent Azure API Management [AI Gateway](https://github.com/Azure-Samples/AI-Gateway) GitHub repository. Much of the structure is similar and its reuse resulted in significant time savings. Thank you, Alex!

Furthermore, [Houssem Dellai](https://github.com/HoussemDellai) was instrumental in setting up a working Front Door to API Management [private connectivity lab](https://github.com/Azure-Samples/AI-Gateway/tree/main/labs/private-connectivity). This created a working baseline for one of this repository's infrastructures. Thank you, Houssem!

[Andrew Redman](https://github.com/anotherRedbeard) for contributing the _Azure Maps_ sample.

The original author of this project is [Simon Kurtz](https://github.com/simonkurtz-msft).
