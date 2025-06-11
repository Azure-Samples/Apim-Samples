# Dev Container for APIM Samples

This directory contains the GitHub Dev Container configuration for the APIM Samples repository, providing a complete development environment with all necessary prerequisites.

## 🚀 Quick Start

### Using GitHub Codespaces (Recommended)

This repository is optimized for GitHub Codespaces prebuilds, which significantly reduces startup time:

1. Navigate to the repository on GitHub
2. Click the green "Code" button
3. Select "Codespaces" tab
4. Click "Create codespace on main"
5. The prebuild will provide a fast startup experience
6. Your Python environment will be ready immediately!

### Using VS Code Dev Containers

1. Install the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
2. Open the repository in VS Code
3. When prompted, click "Reopen in Container" or use Command Palette: "Dev Containers: Reopen in Container"
4. Wait for the container to build and initialize
5. Your Python environment will be ready immediately!

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

### Python Environment
- **Single Virtual Environment** - Located at `/workspaces/Apim-Samples/.venv`
- **Auto-Selected by VS Code** - No manual environment selection needed
- **All Dependencies Pre-Installed** - From `requirements.txt` plus development tools:
  - `requests` - HTTP library
  - `pandas` - Data manipulation
  - `matplotlib` - Data visualization
  - `pyjwt` - JWT token handling
  - `pytest` & `pytest-cov` - Testing framework
  - `azure.storage.blob` & `azure.identity` - Azure SDK components
  - `jupyter`, `ipykernel`, `notebook` - Jupyter notebook support

### Environment Configuration
- **Automatic .env File** - Generated with proper PYTHONPATH configuration
- **VS Code Integration** - Python interpreter automatically configured
- **Azure CLI Extensions** - containerapp and front-door extensions pre-installed
- **Port Forwarding** - Common development ports (3000, 5000, 8000, 8080) pre-configured

## 🏗️ How It Works

### Container Setup Process
This dev container uses GitHub Codespaces best practices for optimal prebuild performance:

1. **Docker Build (prebuild)**: Creates base container with Python 3.12 and system dependencies
2. **onCreateCommand (prebuild)**: Creates virtual environment in workspace  
3. **updateContentCommand (prebuild refresh)**: Installs/updates packages from requirements.txt when repository content changes
4. **postStartCommand (every startup)**: Verifies environment and configures Azure CLI

This three-stage approach ensures:
- **Prebuild Optimization**: Heavy lifting (environment creation) happens during prebuild
- **Content Freshness**: Requirements are updated when the repository changes
- **Fast Startup**: Only verification and Azure CLI setup happen on each startup
- **Single Environment**: Only one Python environment, located in the workspace
- **VS Code Ready**: Automatically detected and configured

### Prebuild Benefits
- **Fast Codespace Creation**: Pre-built environments start in seconds rather than minutes
- **Always Fresh Dependencies**: `updateContentCommand` ensures packages match current requirements.txt
- **Reliable Setup**: Each stage handles a specific concern for maximum reliability

### Environment Location
```
/workspaces/Apim-Samples/.venv/    ← Your Python virtual environment
├── bin/python                     ← Python 3.12 executable
├── lib/python3.12/site-packages/  ← All your packages
└── ...
```

## 🔧 Using the Environment

### Manual Azure Login (When Needed)
To use Azure resources, you'll need to authenticate:

```bash
# Log in to your specific tenant
az login --tenant <your-tenant-id-or-domain>

# Set your target subscription
az account set --subscription <your-subscription-id-or-name>

# Verify your authentication context
az account show
```

### Start Developing
After the container is ready:
1. **Verify your setup**: All packages should be working immediately
2. **Check your Azure setup**: Execute `shared/jupyter/verify-az-account.ipynb`
3. **Start exploring**:
   - Navigate to any infrastructure folder (`infrastructure/`)
   - Run the `create.ipynb` notebook to set up infrastructure
   - Explore samples in the `samples/` directory

## 🔧 Troubleshooting

### Common Issues

**"Module not found" errors:**
```bash
# Regenerate .env file
python setup/setup_python_path.py --generate-env

# Verify environment
python -c "import sys; print(sys.path)"
```

**Wrong Python environment:**
- The environment should be automatically selected in VS Code
- Check that VS Code shows `/workspaces/Apim-Samples/.venv/bin/python` in the status bar
- If not, use Command Palette: "Python: Select Interpreter"

**Environment issues:**
```bash
# Check if virtual environment exists and is activated
which python
echo $VIRTUAL_ENV

# Should show:
# /workspaces/Apim-Samples/.venv/bin/python
# /workspaces/Apim-Samples/.venv
```

### Rebuild Container
If you encounter persistent issues:
1. Use Command Palette: "Dev Containers: Rebuild Container"
2. This will recreate the environment from scratch

## 🏗️ Technical Details

### Architecture
- **Base Image**: `mcr.microsoft.com/devcontainers/python:1-3.12-bookworm`
- **Features**: Azure CLI, Common utilities with Zsh/Oh My Zsh, Docker-in-Docker
- **Workspace**: Mounted at `/workspaces/Apim-Samples`
- **User**: `vscode` with proper permissions

### File Structure
```
.devcontainer/
├── Dockerfile              ← Container definition
├── devcontainer.json       ← VS Code configuration
├── post-start-setup.sh     ← Environment verification script
└── README.md              ← This file

/workspaces/Apim-Samples/
├── .venv/                 ← Python virtual environment (auto-created)
├── .env                   ← Environment variables (auto-generated)
├── requirements.txt       ← Python dependencies
└── ... (your code)
```

### Key Configuration Files

**`.devcontainer/devcontainer.json`**:
- VS Code extensions and settings
- Python interpreter path configuration
- Port forwarding setup
- Container lifecycle commands

**`.devcontainer/Dockerfile`**:
- Base Python 3.12 environment
- System dependencies
- Shell configuration

**`requirements.txt`**:
- All Python package dependencies
- Automatically installed in the virtual environment

### Environment Variables
The `.env` file is automatically generated with:
- `PROJECT_ROOT`: Path to workspace root
- `PYTHONPATH`: Includes shared Python modules

## 🤝 Contributing

When modifying the dev container configuration:

1. **Test your changes**: Rebuild the container and verify all functionality
2. **Update documentation**: Keep this README current with any changes
3. **Consider performance**: Changes to Dockerfile affect build time for all users
4. **Maintain simplicity**: Keep the environment focused and minimal

## 📝 Version History

- **v2.1**: Added `updateContentCommand` for Codespaces prebuild optimization
- **v2.0**: Simplified single virtual environment approach
- **v1.x**: Multi-stage build with environment moving (deprecated)

---

*This dev container provides a complete, ready-to-use development environment for Azure API Management samples. No additional setup required!*

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
