# APIM Samples Dev Container Setup

This directory contains the optimized dev container configuration for the Azure API Management (APIM) Samples project. The setup is designed for fast startup times through prebuild optimization while maintaining a robust development environment.

## 📋 Table of Contents

- [Overview](#overview)
- [Files in this Directory](#files-in-this-directory)
- [Setup Stages](#setup-stages)
- [Optimization Strategy](#optimization-strategy)
- [Prebuild Configuration](#prebuild-configuration)
- [Jupyter Kernel Configuration](#jupyter-kernel-configuration)
- [Troubleshooting](#troubleshooting)
- [Performance Notes](#performance-notes)

## 🎯 Overview

The dev container uses a **three-stage optimization approach** to minimize startup time:

1. **Build Stage** (Dockerfile): Base system setup, Azure CLI configuration, and VS Code extension pre-installation
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
- ✅ VS Code extension installation

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

## 🔌 Pre-installed VS Code Extensions

To further optimize the startup experience, several VS Code extensions are pre-installed in the container image rather than being installed at container startup:

| Extension ID | Description |
|-------------|-------------|
| ms-python.python | Python language support |
| ms-python.debugpy | Python debugging |
| ms-toolsai.jupyter | Jupyter notebook support |
| ms-toolsai.jupyter-keymap | Jupyter keyboard shortcuts |
| ms-toolsai.jupyter-renderers | Jupyter output renderers |
| ms-toolsai.vscode-jupyter-cell-tags | Jupyter cell tags |
| ms-toolsai.vscode-jupyter-slideshow | Jupyter slideshow |
| ms-azuretools.vscode-bicep | Bicep language support |
| ms-vscode.azurecli | Azure CLI support |
| ms-azure-devops.azure-pipelines | Azure Pipelines support |
| redhat.vscode-yaml | YAML language support |
| ms-vscode.vscode-json | JSON language support |
| donjayamanne.vscode-default-python-kernel | Default Python kernel |

A few extensions like GitHub Copilot and Copilot Chat are still installed at container startup because they require authentication or have licensing considerations.

This pre-installation happens in the Dockerfile and significantly reduces container startup time as VS Code doesn't need to download and install these extensions.

## 🏗️ Prebuild Configuration

### What is Devcontainer Prebuild?

**Devcontainer prebuild** is a GitHub Codespaces feature that pre-builds and caches container images with all dependencies and setup already completed. Instead of building the container from scratch every time someone opens a Codespace, GitHub builds and caches the container image ahead of time.

### How Prebuild Works

1. **Automatic Detection**: GitHub monitors changes to devcontainer configuration files (`.devcontainer/devcontainer.json`, `.devcontainer/Dockerfile`, etc.)
2. **Triggered Builds**: When changes are detected, GitHub automatically starts a prebuild process
3. **Full Setup Execution**: Runs the complete container build including:
   - Dockerfile instructions
   - `onCreateCommand` (virtual environment creation, package installation)
   - `updateContentCommand` (dependency updates, environment configuration)
4. **Image Caching**: Stores the resulting container image in GitHub's registry
5. **Fast Deployment**: When users open a Codespace, they get the pre-built image

### Prebuild Benefits

| Aspect | Without Prebuild | With Prebuild |
|--------|------------------|---------------|
| **Startup Time** | 5-10 minutes | 10-30 seconds |
| **User Experience** | Watch installation progress | See verification only |
| **Resource Usage** | Build every time | Build once, use many times |
| **Consistency** | May vary due to network/timing | Identical pre-configured environment |
| **Reliability** | Dependent on real-time installs | Pre-validated, cached environment |

### Prebuild Lifecycle Commands in This Project

Our devcontainer uses two key lifecycle commands optimized for prebuild:

#### `onCreateCommand` (Container Creation)
```bash
# Creates Python virtual environment and registers Jupyter kernel
echo '🚀 Creating Python virtual environment in workspace...' && 
/usr/local/bin/python3.12 -m venv /workspaces/Apim-Samples/.venv --copies && 
source /workspaces/Apim-Samples/.venv/bin/activate && 
pip install --upgrade pip setuptools wheel ipykernel && 
python -m ipykernel install --user --name=apim-samples --display-name='APIM Samples Python 3.12'
```

#### `updateContentCommand` (Content Updates)
```bash
# Installs Python packages and configures environment
source /workspaces/Apim-Samples/.venv/bin/activate && 
pip install -r requirements.txt && 
pip install pytest pytest-cov coverage && 
python setup/setup_python_path.py --generate-env && 
az config set core.login_experience_v2=off && 
az extension add --name containerapp --only-show-errors && 
az extension add --name front-door --only-show-errors
```

### When Prebuild is Triggered

Prebuild automatically occurs when you push changes to:
- `.devcontainer/devcontainer.json`
- `.devcontainer/Dockerfile`
- `requirements.txt` (when referenced in `updateContentCommand`)
- Any other files referenced in lifecycle commands

### Monitoring Prebuild Status

You can monitor prebuild status in several ways:

1. **GitHub Repository**:
   - Go to your repository on GitHub
   - Navigate to the "Code" tab
   - Look for the "Codespaces" section
   - Click on "View all" to see prebuild status

2. **Codespaces Settings**:
   - Visit [github.com/codespaces][github-codespaces]
   - Check the "Repository prebuilds" section
   - View build logs and status

3. **Build Indicators**:
   - ✅ Green checkmark: Prebuild successful
   - ❌ Red X: Prebuild failed
   - 🟡 Yellow circle: Prebuild in progress
   - ⚪ Gray circle: No recent prebuild

### Refreshing Prebuilt Containers

To refresh the prebuilt container (recommended periodically):

#### Method 1: Trigger via Configuration Change
1. Make a small change to `.devcontainer/devcontainer.json` (e.g., add a comment)
2. Commit and push the change
3. GitHub will automatically trigger a new prebuild

#### Method 2: Manual Trigger (if available)
1. Go to your repository's Codespaces settings
2. Find the prebuild configuration
3. Click "Trigger prebuild" if the option is available

#### Method 3: Update Dependencies
1. Update `requirements.txt` with newer package versions
2. Commit and push the changes
3. Prebuild will automatically run with updated dependencies

### Best Practices for Prebuild

1. **Keep Commands Idempotent**: Ensure commands can run multiple times safely
2. **Use Caching**: Leverage Docker layer caching and package managers' cache
3. **Minimize Build Time**: Move heavy operations to prebuild, keep runtime light
4. **Test Changes**: Verify prebuild success before merging configuration changes
5. **Monitor Logs**: Check prebuild logs for warnings or potential optimizations
6. **Regular Refresh**: Refresh prebuilds monthly or when dependencies change significantly

### Prebuild vs Runtime Separation

| Operation | Prebuild Stage | Runtime Stage |
|-----------|----------------|---------------|
| Python packages | ✅ Install all | ❌ Verify only |
| Virtual environment | ✅ Create and configure | ❌ Activate only |
| Azure CLI extensions | ✅ Install | ❌ Verify only |
| Jupyter kernel | ✅ Register | ❌ Validate only |
| Environment files | ✅ Generate | ❌ Check existence |
| VS Code extensions | ✅ Install | ❌ Load only |

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

For more details on kernel configuration in VS Code, see: [VS Code Issue #130946][vscode-issue-130946]

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
5. **Refresh Prebuilds Regularly**: Update prebuilt containers monthly or when major dependency changes occur

### Prebuild Refresh Recommendations

**When to refresh prebuilds**:
- Monthly maintenance (keep dependencies current)
- After major Python package updates
- When Azure CLI or extensions have significant updates
- If startup performance degrades over time
- Before important development cycles or team onboarding

**Quick refresh method**:
```bash
# Add a comment to trigger prebuild
# Edit .devcontainer/devcontainer.json and add/update a comment, then:
git add .devcontainer/devcontainer.json
git commit -m "Trigger prebuild refresh"
git push
```

---

## 🤝 Contributing

When modifying the dev container setup:

1. **Test Thoroughly**: Verify changes work in both fresh and existing containers
2. **Update Documentation**: Keep this README current with any changes
3. **Consider Performance**: Evaluate whether new operations belong in prebuild or runtime
4. **Maintain Fallbacks**: Ensure robust error handling and recovery options

---

*This dev container configuration is optimized for Azure API Management samples development with fast startup times and comprehensive tooling support.*



[github-codespaces]: https://github.com/codespaces
[vscode-issue-130946]: https://github.com/microsoft/vscode/issues/130946#issuecomment-1899389049
