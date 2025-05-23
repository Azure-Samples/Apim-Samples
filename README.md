# Azure API Management Samples

This repository provides a playground to safely experiment with and learn Azure API Management (APIM) policies in various architectures. 

## Objectives

1. Educate you on common APIM architectures we see across industries and customers.
1. Empower you to safely experiment with APIM policies.
1. Provide you with high-fidelity building blocks to further your APIM integration efforts.

_Try it out, learn from it, apply it in your setups._

## Repo Structure

### High-level 

- All _samples_ can be found in the `samples` folder. Samples showcase functionality and provide a baseline for your experimentation.
- All _infrastructures_ can be found in the `infrastructure` folder. They provide the architectural underpinnings.
- All shared code, modules, functionality, policies, etc. can be found in the `shared` folder. 
  - Bicep _modules_ are versioned in the `bicep/modules` folder. Major changes require versioning.
  - Python _modules_ are found in the `python` folder. _They are not versioned yet but may be in the future._ 
  - Reusable _APIM policies_ are found in the `apim-policies` folder. 
  - Reusable Jupyter notebooks are found in the `jupyter` folder.

### Sample Setup

- Each sample uses an architecture infrastructure. This keeps the samples free of almost all setup.
- Each infrastructure and sample features a `create.ipynb` for creation (and running) of the sample setup and a `main.bicep` file for IaC configuration.
- Each infrastructure contains a `clean-up.ipynb` file to tear down everything in the infrastructure and its resource group. This reduces your Azure cost.
- Samples (and infrastructures) may contain additional files specific to their use cases.

### Infrastructure Architectures

We provide several common architectural approaches to integrating APIM into your Azure ecosystem. While these are high-fidelity setups, they are not production-ready. Please refer to the [Azure API Management landing zone accelerator](https://learn.microsoft.com/azure/cloud-adoption-framework/scenarios/app-platform/api-management/landing-zone-accelerator) for up-to-date production setups.

- [Simple API Management](./infrastructure/simple-apim)
  - Just the basics with a publicly accessible API Management intance fronting your APIs. This is the innermost way to experience and experiment with the APIM policies. 
- [API Management & Container Apps](./infrastructure/apim-aca)
  - APIs are often times implemented in containers that are running in Azure Container Apps. This architecture accesses the container apps publicly. It's beneficial to test both APIM and container app URLs here to contrast and compare experiences of API calls through and bypassing APIM. It is not intended to be a security baseline.
- [Secure Front Door & API Management & Container Apps](./infrastructure/afd-apim)
  - A higher-fidelity implementation of a secured setup in which Azure Front Door connects to APIM via the new private link integration. This traffic, once it traverses through Front Door, rides entirely on Microsoft-owned and operated networks. Similarly, the connection from APIM to Container Apps is secured but through a VNet configuration (it is also entirely possible to do this via private link). It's noteworthy that we are using APIM Standard V2 here as we need the ability to accept a private link from Front Door.

---

## Getting Started

### Prerequisites

These prerequisites apply broadly across all infrastructure and samples. If there are specific deviations, expect them to be noted there.

- [Python 3.12](https://www.python.org/) installed
  - Python 3.13 may not have all dependencies ready yet. There have been issues during installs.
- [VS Code](https://code.visualstudio.com/) installed with the [Jupyter notebook extension](https://marketplace.visualstudio.com/items?itemName=ms-toolsai.jupyter) enabled
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) installed
- [An Azure Subscription](https://azure.microsoft.com/free/) with Owner or Contributor+UserAccessAdministrator permissions. Execute [shared/jupyter/verify-az-account.ipynb](shared/jupyter/verify-az-account.ipynb) to verify.
- [Sign in to Azure with Azure CLI](https://learn.microsoft.com/cli/azure/authenticate-azure-cli-interactively)

### Initialization

Run through the following steps to create a Python virtual environment before doing anything else:

1. Open VS Code.
1. Invoke the _Command Palette_ via the _View_ menu or a shortcut (on Windows: Ctrl + Shift + P).
1. Select _Python: Create Environment_.
1. Select _Venv_ as we want a local virtual environment.
1. Select the desired, installed Python version.
1. Check _requirements.txt_ to install the Python dependencies we need for this repo, then press _OK_. The install may take a few minutes. You can check on progress in the _OUTPUT_ window.
1. Verify the virtual environment is set up. You should see a new _.venv_ directory with a _pyveng.cfg_ file and the Python version you selected earlier.

The first time you run a Jupyter notebook, you'll be asked to install the Jupyter kernel package (ipykernel).

### Running a Sample

1. Locate the specific sample's `create.ipynb` file and adjust the parameters under the `User-defined Parameters` header as you see fit.
1. Ensure that the specified infrastructure already exists in your subscription. If not, proceed to the desired infrastructure folder and execute its `create.ipynb` file. Wait until this completes before continuing.
1. Execute the sample's `create.ipynb` file.

Now that infrastructure and sample have been stood up, you can experiment with the policies, make requests against APIM, etc.

---

## Development

As you work with this repo, you will likely want to make your own customizations. There's little you need to know to be successful.

The repo uses the bicep linter and has rules defined in `bicepconfig.json`. See the [bicep linter documentation](https://learn.microsoft.com/azure/azure-resource-manager/bicep/bicep-config-linter) for details.

We welcome contributions! Please consider forking the repo and creating issues and pull requests to share your samples. Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details. Thank you! 


### Testing & Code Coverage

Python modules in `shared/python` are covered by comprehensive unit tests located in `tests/python`. All tests use [pytest](https://docs.pytest.org/) and leverage modern pytest features, including custom markers for unit and HTTP tests.


#### Running Tests Locally

- **PowerShell (Windows):**
  - Run all tests with coverage: `./tests/python/run_coverage.ps1`
- **Shell (Linux/macOS):**
  - Run all tests with coverage: `./tests/python/run_coverage.sh`

Both scripts:
- Run all tests in `tests/python` using pytest
- Generate a code coverage report (HTML output in `tests/python/htmlcov`)
- Store the raw coverage data in `tests/python/.coverage`

You can also run tests manually:
```powershell
pytest -v --cov=shared/python --cov-report=html:tests/python/htmlcov --cov-report=term tests/python
```

#### Viewing Coverage Reports

After running tests, open `tests/python/htmlcov/index.html` in your browser to view detailed coverage information.

#### Pytest Markers

- `@pytest.mark.unit` — marks a unit test
- `@pytest.mark.http` — marks a test involving HTTP/mocking

Markers are registered in `pytest.ini` to avoid warnings.

#### Continuous Integration (CI)

On every push or pull request, GitHub Actions will:
- Install dependencies
- Run all Python tests in `tests/python` with coverage
- Store the `.coverage` file in `tests/python`
- Upload the HTML coverage report as a workflow artifact for download

#### Additional Notes

- The `.gitignore` is configured to exclude coverage output and artifacts.
- All test and coverage features work both locally and in CI.

For more details on pytest usage, see the [pytest documentation](https://docs.pytest.org/en/8.2.x/).

---

## Supporting Resources

The APIM team maintains an [APIM policy snippets repo](https://github.com/Azure/api-management-policy-snippets) with use cases we have seen. They are not immediately executable samples and require integrations such as in this repo.

---

## Acknowledgements

This project has its roots in work done by [Alex Vieira](https://github.com/vieiraae) on the excellent Azure API Management [AI Gateway](https://github.com/Azure-Samples/AI-Gateway) GitHub repository. Much of the structure is similar and its reuse resulted in significant time savings. Thank you, Alex!

Furthermore, [Houssem Dellai](https://github.com/HoussemDellai) was instrumental in setting up a working Front Door to API Management [private connectivity lab](https://github.com/Azure-Samples/AI-Gateway/tree/main/labs/private-connectivity). This created a working baseline for one of this repository's infrastructures. Thank you, Houssem! 
