# APIM Samples Dev Container Setup

This directory contains the optimized dev container configuration for the Azure API Management (APIM) Samples project. The setup is designed for fast startup times through prebuild optimization while maintaining a robust development environment.

## 📋 Table of Contents

- [Overview](#overview)
- [Files in this Directory](#files-in-this-directory)
- [Setup Stages](#setup-stages)
- [Optimization Strategy](#optimization-strategy)
- [Jupyter Kernel Configuration](#jupyter-kernel-configuration)
- [Troubleshooting](#troubleshooting)
- [Performance Notes](#performance-notes)

## 🎯 Overview

The dev container uses a **three-stage optimization approach** to minimize startup time:

1. **Build Stage** (Dockerfile): Base system setup and Azure CLI configuration
2. **Prebuild Stage** (devcontainer.json): Heavy installations and environment setup
3. **Runtime Stage** (post-start-setup.sh): Fast verification and user guidance

This approach ensures that time-consuming operations happen during container prebuild rather than every startup.

## 📁 Files in this Directory

### Core Configuration Files

| File | Purpose | Stage |
|------|---------|-------|
| `devcontainer.json` | Main dev container configuration | All |
| `Dockerfile` | Container image definition | Build |
| `post-start-setup.sh` | Runtime verification script | Runtime |
| `README.md` | This documentation | - |

### Configuration Details

#### `devcontainer.json`
- **Features**: Azure CLI, common utilities, Git, Docker-in-Docker
- **Extensions**: Python, Jupyter, Bicep, GitHub Copilot, and more
- **Lifecycle Commands**: Optimized three-stage setup
- **Port Forwarding**: Common development ports (3000, 5000, 8000, 8080)

#### `Dockerfile`
- **Base Image**: Microsoft's Python 3.12 dev container
- **System Dependencies**: Essential packages and tools
- **Azure CLI Setup**: Extensions and configuration for Codespaces
- **Virtual Environment**: Auto-activation configuration

#### `post-start-setup.sh`
- **Environment Verification**: Quick checks and status reporting
- **Fallback Installation**: Safety net for missing components
- **User Guidance**: Next steps and helpful information

## 🚀 Setup Stages

### Stage 1: Container Build (Dockerfile)
**When it runs**: During initial container build
**What it does**:
- Installs Python 3.12 and system dependencies
- Configures Azure CLI for Codespaces (device code authentication)
- Installs Azure CLI extensions (`containerapp`, `front-door`)
- Sets up shell auto-activation for virtual environment

### Stage 2: Content Update (devcontainer.json)
**When it runs**: During prebuild when content changes
**What it does**:
- Creates Python virtual environment
- Installs all Python packages from `requirements.txt`
- Generates environment configuration (`.env` file)
- Registers Jupyter kernel
- Configures Azure CLI settings

### Stage 3: Runtime Verification (post-start-setup.sh)
**When it runs**: Every time the container starts
**What it does**:
- Verifies environment setup (< 10 seconds)
- Provides status reporting and user guidance
- Performs fallback installation if needed
- Displays next steps for the user

## ⚡ Optimization Strategy

### What Moved to Prebuild
- ✅ Python package installation
- ✅ Virtual environment creation
- ✅ Azure CLI extension installation
- ✅ Jupyter kernel registration
- ✅ Environment file generation

### What Stays in Runtime
- ✅ Environment verification
- ✅ Status reporting and user guidance
- ✅ Fallback installation (safety net)
- ✅ Performance timing and completion messages

### Performance Benefits
- **Faster Startup**: Most heavy operations happen during prebuild
- **Better UX**: Users see verification instead of installation progress
- **Reliability**: Fallback mechanisms ensure robustness
- **Transparency**: Clear status reporting throughout

## 🔧 Jupyter Kernel Configuration

The dev container is configured with a custom Jupyter kernel for optimal Python development experience:

- **Kernel Name**: `apim-samples`
- **Display Name**: "APIM Samples Python 3.12"
- **Python Path**: `/workspaces/Apim-Samples/.venv/bin/python`

### Kernel Registration Details
The kernel is automatically registered during the prebuild stage using:
```bash
python -m ipykernel install --user --name=apim-samples --display-name="APIM Samples Python 3.12"
```

### VS Code Kernel Configuration
The `devcontainer.json` includes specific Jupyter settings to ensure proper kernel selection:

```jsonc
"jupyter.kernels.excludePythonEnvironments": [
    // Excludes system Python environments
],
"jupyter.kernels.trusted": [
    "/workspaces/Apim-Samples/.venv/bin/python"
]
```

For more details on kernel configuration in VS Code, see: [VS Code Issue #130946](https://github.com/microsoft/vscode/issues/130946#issuecomment-1899389049)

## 🛠️ Troubleshooting

### Common Issues and Solutions

#### Virtual Environment Not Found
**Symptom**: Error about missing virtual environment
**Solution**: The virtual environment should be created during prebuild. If missing:
```bash
python3.12 -m venv /workspaces/Apim-Samples/.venv
source /workspaces/Apim-Samples/.venv/bin/activate
pip install -r requirements.txt
```

#### Azure CLI Extensions Missing
**Symptom**: Commands fail with extension not found
**Solution**: Extensions should install during prebuild. If missing:
```bash
az extension add --name containerapp
az extension add --name front-door
```

#### Jupyter Kernel Not Available
**Symptom**: Kernel not visible in VS Code
**Solution**: Re-register the kernel:
```bash
python -m ipykernel install --user --name=apim-samples --display-name="APIM Samples Python 3.12"
```

#### Environment Variables Not Set
**Symptom**: Import errors or path issues
**Solution**: Regenerate the `.env` file:
```bash
python setup/setup_python_path.py --generate-env
```

### Debug Commands
Useful commands for troubleshooting:

```bash
# Check Python environment
which python
python --version
pip list

# Check virtual environment
echo $VIRTUAL_ENV
source /workspaces/Apim-Samples/.venv/bin/activate

# Check Azure CLI
az --version
az extension list

# Check Jupyter kernels
jupyter kernelspec list

# Verify environment file
cat .env
```

## 📊 Performance Notes

### Typical Timing
- **First Build**: ~5-10 minutes (includes all prebuild operations)
- **Subsequent Startups**: ~10-30 seconds (verification only)
- **Content Updates**: ~2-5 minutes (package updates during prebuild)

### Monitoring Setup Progress
The post-start script provides real-time feedback:
- **Terminal Output**: Keep the initial terminal open to see progress
- **Status Messages**: Clear indicators for each verification step
- **Error Handling**: Detailed messages for any issues encountered

### Best Practices
1. **Keep Initial Terminal Open**: Shows verification progress and status
2. **Wait for Completion**: Let the verification finish before starting work
3. **Check Status Messages**: Review any warnings or errors reported
4. **Use Fallback Commands**: If something fails, the script provides guidance

---

## 🤝 Contributing

When modifying the dev container setup:

1. **Test Thoroughly**: Verify changes work in both fresh and existing containers
2. **Update Documentation**: Keep this README current with any changes
3. **Consider Performance**: Evaluate whether new operations belong in prebuild or runtime
4. **Maintain Fallbacks**: Ensure robust error handling and recovery options

---

*This dev container configuration is optimized for Azure API Management samples development with fast startup times and comprehensive tooling support.*
