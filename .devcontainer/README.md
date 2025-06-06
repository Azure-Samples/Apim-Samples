# Dev Container for APIM Samples

This directory contains the GitHub Dev Container configuration for the APIM Samples repository, providing a complete development environment with all necessary prerequisites.

## 🚀 Quick Start

### Using GitHub Codespaces

1. Navigate to the repository on GitHub
2. Click the green "Code" button
3. Select "Codespaces" tab
4. Click "Create codespace on main"
5. Wait for the environment to build and initialize

### Using VS Code Dev Containers

1. Install the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
2. Open the repository in VS Code
3. When prompted, click "Reopen in Container" or use Command Palette: "Dev Containers: Reopen in Container"
4. Wait for the container to build and initialize

## 📦 What's Included

### Core Tools
- **Python 3.12** - Primary development runtime
- **Azure CLI** - Latest version with useful extensions pre-installed
- **Git** - Version control with enhanced configuration

### VS Code Extensions
- **Python** - Full Python development support
- **Jupyter** - Complete Jupyter notebook support with renderers and tools
- **Azure Bicep** - Infrastructure as Code support
- **Azure CLI Tools** - Enhanced Azure development experience
- **GitHub Copilot** - AI-powered coding assistance (if licensed)
- **YAML & JSON** - Configuration file support

### Python Packages
All packages from `requirements.txt` are pre-installed:
- `requests` - HTTP library
- `pandas` - Data manipulation
- `matplotlib` - Data visualization
- `pyjwt` - JWT token handling
- `pytest` & `pytest-cov` - Testing framework
- `azure.storage.blob` & `azure.identity` - Azure SDK components

### Environment Configuration
- **PYTHONPATH** - Automatically configured to include shared Python modules
- **Jupyter Kernel** - Custom kernel named "APIM Samples Python"
- **Azure CLI** - Configured for container-friendly authentication
- **Port Forwarding** - Common development ports (3000, 5000, 8000, 8080) pre-configured

## 🔧 Post-Setup Steps

After the container starts, you'll need to:

1. **Sign in to Azure**:
   ```bash
   az login
   ```

2. **Verify your Azure setup**:
   Execute `shared/jupyter/verify-az-account.ipynb`

3. **Start exploring**:
   - Navigate to any infrastructure folder (`infrastructure/`)
   - Run the `create.ipynb` notebook to set up infrastructure
   - Explore samples in the `samples/` directory

## 🏗️ Architecture

The dev container is built on:
- **Base Image**: `mcr.microsoft.com/devcontainers/python:1-3.12-bullseye`
- **Features**: Azure CLI, Common utilities with Zsh/Oh My Zsh
- **Workspace**: Mounted at `/workspaces/Apim-Samples`
- **User**: `vscode` with proper permissions

## 🔄 Azure CLI Authentication

The container mounts your local `~/.azure` directory to preserve authentication state between container rebuilds. This means:
- Your Azure login persists across sessions
- Your Azure CLI configuration is maintained
- No need to repeatedly authenticate

## 🐛 Troubleshooting

### Python Path Issues
If you encounter import errors:
```bash
python setup/setup_python_path.py --generate-env
```

### Jupyter Kernel Not Found
Restart VS Code or refresh the Jupyter kernel list:
- Command Palette → "Jupyter: Refresh Kernels"

### Azure CLI Issues
Check Azure CLI status:
```bash
az account show
az account list
```

### Container Rebuild
If you need to rebuild the container:
- Command Palette → "Dev Containers: Rebuild Container"

## 🔒 Security Considerations

- Azure credentials are mounted from your local machine
- The container runs as a non-root user (`vscode`)
- All dependencies are installed from official sources
- Network access is controlled through VS Code's port forwarding

## 🤝 Contributing

When modifying the dev container configuration:
1. Test changes locally first
2. Update this README if adding new tools or changing behavior
3. Consider backward compatibility for existing users
4. Document any new environment variables or configuration options
