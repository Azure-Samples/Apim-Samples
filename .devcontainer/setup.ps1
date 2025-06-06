# PowerShell Setup Script for APIM Samples Dev Container
# This script mirrors the functionality of setup.sh for Windows environments

# ------------------------------
#    DEVCONTAINER SETUP SCRIPT
# ------------------------------

Write-Host "🚀 Setting up APIM Samples development environment..." -ForegroundColor Green

# ------------------------------
#    PYTHON ENVIRONMENT SETUP
# ------------------------------

Write-Host "📦 Installing Python dependencies..." -ForegroundColor Yellow
python -m pip install --upgrade pip
pip install -r requirements.txt

# Ensure pytest and coverage tools are available
pip install pytest pytest-cov coverage

Write-Host "🔧 Setting up Python path configuration..." -ForegroundColor Yellow
python setup/setup_python_path.py --generate-env

# ------------------------------
#    AZURE CLI SETUP
# ------------------------------

Write-Host "☁️ Configuring Azure CLI..." -ForegroundColor Yellow
# Set Azure CLI to use device code flow by default in codespaces/containers
try {
    az config set core.login_experience_v2=off 2>$null
} catch {
    # Ignore errors if config setting fails
}

# Install additional Azure CLI extensions that might be useful
Write-Host "📥 Installing Azure CLI extensions..." -ForegroundColor Yellow
try {
    az extension add --name containerapp --only-show-errors 2>$null
    az extension add --name front-door --only-show-errors 2>$null
} catch {
    Write-Host "⚠️ Some Azure CLI extensions could not be installed" -ForegroundColor Yellow
}

# ------------------------------
#    INTERACTIVE AZURE CONFIGURATION
# ------------------------------

Write-Host ""
Write-Host "🔧 Azure CLI Authentication Setup" -ForegroundColor Cyan
Write-Host "=================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To make working with Azure easier, you can configure how Azure CLI authentication works."
Write-Host "This only needs to be done once during initial setup."
Write-Host ""

# Check if we have an interactive session
$isInteractive = [Environment]::UserInteractive -and [Console]::In -and [Console]::Out

if ($isInteractive) {
    Write-Host "Running interactive Azure CLI configuration..." -ForegroundColor Yellow
    $env:APIM_SAMPLES_INITIAL_SETUP = "true"
    python .devcontainer/configure-azure-mount.py
    Remove-Item env:APIM_SAMPLES_INITIAL_SETUP -ErrorAction SilentlyContinue
    
    Write-Host ""
    Write-Host "⚠️  IMPORTANT: If you chose to mount Azure CLI config, you'll need to:" -ForegroundColor Yellow
    Write-Host "   1. Exit this container"
    Write-Host "   2. Rebuild the dev container to apply the mount configuration"
    Write-Host "   3. The container will restart with your Azure CLI authentication available"
    Write-Host ""
} else {
    Write-Host "⚠️  Non-interactive environment detected." -ForegroundColor Yellow
    Write-Host "   You can run the Azure CLI configuration later with:"
    Write-Host "   python .devcontainer/configure-azure-mount.py"
    Write-Host ""
}

# ------------------------------
#    JUPYTER SETUP
# ------------------------------

Write-Host "📓 Setting up Jupyter environment..." -ForegroundColor Yellow
# Install Jupyter kernel (with error handling)
try {
    python -c "import ipykernel" 2>$null
    if ($LASTEXITCODE -eq 0) {
        python -m ipykernel install --user --name=apim-samples --display-name="APIM Samples Python"
    } else {
        Write-Host "⚠️ Warning: ipykernel not found. Installing it now..." -ForegroundColor Yellow
        pip install ipykernel
        python -m ipykernel install --user --name=apim-samples --display-name="APIM Samples Python"
    }
} catch {
    Write-Host "⚠️ Warning: Failed to install Jupyter kernel, but continuing..." -ForegroundColor Yellow
}

# ------------------------------
#    WORKSPACE CONFIGURATION
# ------------------------------

Write-Host "🛠️ Configuring workspace settings..." -ForegroundColor Yellow

# Create .vscode directory if it doesn't exist
if (-not (Test-Path ".vscode")) {
    New-Item -ItemType Directory -Path ".vscode" -Force
}

# Create settings.json for the workspace
$settingsJson = @'
{
  "python.terminal.activateEnvironment": true,
  "python.defaultInterpreterPath": "python",
  "jupyter.kernels.filter": [
    {
      "path": "python",
      "type": "pythonEnvironment"
    }
  ],
  "files.associations": {
    "*.bicep": "bicep"
  },
  "python.envFile": "${workspaceFolder}/.env"
}
'@

$settingsJson | Out-File -FilePath ".vscode/settings.json" -Encoding UTF8

# ------------------------------
#    FINAL VERIFICATION
# ------------------------------

Write-Host "✅ Verifying installation..." -ForegroundColor Green

Write-Host "Python version:" -ForegroundColor Cyan
python --version

Write-Host "Azure CLI version:" -ForegroundColor Cyan
$azVersion = az --version | Select-Object -First 1
Write-Host $azVersion

Write-Host "Pip packages installed:" -ForegroundColor Cyan
pip list | Select-String -Pattern "(requests|pandas|matplotlib|pytest|azure|jwt|jupyter|ipykernel)"

Write-Host "Jupyter kernels available:" -ForegroundColor Cyan
try {
    jupyter kernelspec list 2>$null
} catch {
    Write-Host "⚠️ Jupyter kernels could not be listed" -ForegroundColor Yellow
}

Write-Host "🎉 Development environment setup complete!" -ForegroundColor Green

Write-Host "🔍 Running final verification..." -ForegroundColor Yellow
python .devcontainer/verify-setup.py

Write-Host ""
Write-Host "📋 Next steps:\n" -ForegroundColor Yellow
# Check if Azure CLI config mounting is configured
if (Test-Path ".devcontainer/devcontainer.json") {
    $devcontainerContent = Get-Content ".devcontainer/devcontainer.json" -Raw

    if ($devcontainerContent -match '"mounts"') {
        Write-Host "✅ Azure CLI config mounting detected - your authentication should be available"
        Write-Host "1. Verify Azure access: az account show"
        Write-Host "2. If needed, switch tenant: az login --tenant <your-tenant-id-or-domain>"
        Write-Host "3. If needed, set subscription: az account set --subscription <your-subscription-id-or-name>"
    } else {
        Write-Host "1. Sign in to Azure with your specific tenant:"
        Write-Host "   az login --tenant <your-tenant-id-or-domain>"
        Write-Host "2. Set your target subscription:"
        Write-Host "   az account set --subscription <your-subscription-id-or-name>"
        Write-Host "3. Verify your context: az account show"
    }
} else {
    Write-Host "1. Sign in to Azure with your specific tenant:"
    Write-Host "   az login --tenant <your-tenant-id-or-domain>"
    Write-Host "2. Set your target subscription:"
    Write-Host "   az account set --subscription <your-subscription-id-or-name>"
    Write-Host "3. Verify your context: az account show"
}

Write-Host "\nFor any of the next steps, you will be asked to create (first-time) or select an environment. Create the virtual environment (.venv) if it does not yet exist. You do not need to reinstall `requirements.txt` as this has already been set up for you.\n"
Write-Host "4. Open shared/jupyter/verify-az-account.ipynb and execute the notebook to verify your Azure setup"
Write-Host "5. Navigate to any infrastructure folder and run the create.ipynb notebook"
Write-Host "6. Explore the samples in the samples/ directory"
Write-Host ""
Write-Host "💡 Tip: The Python path has been configured to include shared/python modules automatically." -ForegroundColor Cyan
Write-Host "🔧 To reconfigure Azure CLI authentication, run: python .devcontainer/configure-azure-mount.py" -ForegroundColor Cyan
