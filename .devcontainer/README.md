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
- `jupyter`, `ipykernel`, `notebook` - Jupyter notebook support

### Environment Configuration
- **PYTHONPATH** - Automatically configured to include shared Python modules
- **Jupyter Kernel** - Custom kernel named "APIM Samples Python"
- **Azure CLI** - Installed and ready for authentication (requires tenant-specific `az login` inside container)
- **Port Forwarding** - Common development ports (3000, 5000, 8000, 8080) pre-configured

## 🔧 Post-Setup Steps

The dev container automatically handles most setup during initialization. During the first build, you'll be prompted to configure Azure CLI authentication.

### Automated Interactive Setup (During First Build)
When the container starts for the first time, the setup script will automatically:
1. **Install all dependencies** (Python packages, Azure CLI extensions)
2. **Configure Jupyter environment** with custom kernel
3. **Prompt for Azure CLI configuration**:
   - Mount local Azure config (preserves login between rebuilds)
   - Use manual login (run tenant-specific `az login` each time)
   - Configure manually later

### Manual Configuration (If Needed Later)
If you skipped the initial configuration or want to change it:

**Interactive Setup**:
```bash
python .devcontainer/configure-azure-mount.py
```

**Manual Azure Login**:
```bash
# Log in to your specific tenant
az login --tenant <your-tenant-id-or-domain>

# Set your target subscription
az account set --subscription <your-subscription-id-or-name>

# Verify your authentication context
az account show
```

### Continue with Development
After setup is complete:
1. **Verify your Azure setup**: Execute `shared/jupyter/verify-az-account.ipynb`
2. **Test your environment**: Run `python .devcontainer/verify-setup.py`
3. **Start exploring**:
   - Navigate to any infrastructure folder (`infrastructure/`)
   - Run the `create.ipynb` notebook to set up infrastructure
   - Explore samples in the `samples/` directory

## 🔧 Troubleshooting

If you encounter import errors or module resolution issues, see:
- [Import Troubleshooting Guide](.devcontainer/IMPORT-TROUBLESHOOTING.md)
- [Setup Notes](.devcontainer/SETUP-NOTES.md)

Common quick fixes:
```bash
# Fix Python path for local development
python setup/setup_python_path.py --generate-env

# Verify setup
python .devcontainer/verify-setup.py

# Rebuild dev container if needed
Dev Containers: Rebuild Container
```

## 🏗️ Architecture

The dev container is built on:
- **Base Image**: `mcr.microsoft.com/devcontainers/python:1-3.12-bullseye`
- **Features**: Azure CLI, Common utilities with Zsh/Oh My Zsh
- **Workspace**: Mounted at `/workspaces/Apim-Samples`
- **User**: `vscode` with proper permissions

## 🔄 Azure CLI Authentication

### Quick Setup (Recommended)

Run the interactive configuration script to automatically set up Azure CLI authentication for your platform:

**Python (Cross-platform)**:
```bash
python .devcontainer/configure-azure-mount.py
```

**PowerShell (Windows)**:
```powershell
.\.devcontainer\configure-azure-mount.ps1
```

**Bash (Linux/macOS)**:
```bash
./.devcontainer/configure-azure-mount.sh
```

### Configuration Options

The setup script provides three choices:

**Option 1: Mount local Azure CLI config**
- ✅ Preserves login between container rebuilds
- ✅ Uses your existing tenant-specific `az login` from host machine
- ✅ Works on Windows (`${localEnv:USERPROFILE}/.azure`) and Unix (`${localEnv:HOME}/.azure`)
- ✅ Best for: Personal development with stable logins

**Option 2: Use manual login inside container [RECOMMENDED]**
- ✅ Run tenant-specific `az login` each time container starts
- ✅ More secure, fresh authentication each session  
- ✅ Works universally across all platforms and environments
- ✅ Best for: Shared environments, GitHub Codespaces
- ✅ Ensures you're working with the correct tenant and subscription

**Option 3: Configure manually later**
- ✅ No changes made to devcontainer.json
- ✅ You can edit the configuration files yourself
- ✅ Full control over mount configuration

### Mount Preservation

The configuration script intelligently preserves any existing mounts (like SSH keys, additional volumes) while only managing Azure CLI mounts. This ensures your custom development setup remains intact.

### Non-Interactive Environments

In environments like GitHub Codespaces automation, the script automatically detects non-interactive contexts and safely defaults to Option 2 (manual login) for maximum reliability.

### Manual Options

**Option 1: Mount Local Azure Config**
- Preserves authentication between container rebuilds
- Platform-specific (configured automatically by the setup script)

**Option 2: Manual Login**
- Log in to your specific tenant: `az login --tenant <your-tenant-id-or-domain>`
- Set your target subscription: `az account set --subscription <your-subscription-id-or-name>`
- Verify context: `az account show`
- Works universally across all platforms
- Requires re-authentication after container rebuilds

## 🐛 Troubleshooting

### Container Creation Failed with ipykernel Error
If you see an error like `/usr/local/bin/python: No module named ipykernel`:
1. This has been fixed in the latest version
2. If you're still experiencing issues, manually rebuild the container:
   - Command Palette → "Dev Containers: Rebuild Container"
3. Or run the manual setup:
   ```bash
   pip install ipykernel jupyter notebook
   python -m ipykernel install --user --name=apim-samples --display-name="APIM Samples Python"
   ```

### Python Path Issues
If you encounter import errors:
```bash
python setup/setup_python_path.py --generate-env
```

### Jupyter Kernel Not Found
Restart VS Code or refresh the Jupyter kernel list:
- Command Palette → "Jupyter: Refresh Kernels"
- Or manually check available kernels: `jupyter kernelspec list`

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

- Azure credentials are handled through tenant-specific `az login` inside the container (or optionally mounted)
- The container runs as a non-root user (`vscode`)
- All dependencies are installed from official sources
- Network access is controlled through VS Code's port forwarding

## 🤝 Contributing

When modifying the dev container configuration:
1. Test changes locally first
2. Update this README if adding new tools or changing behavior
3. Consider backward compatibility for existing users
4. Document any new environment variables or configuration options
