# Python Environment Auto-Configuration for VS Code

## Problem Solved ✅

**Issue**: When running Jupyter notebooks or Python scripts for the first time in the devcontainer, VS Code prompts to select a Python environment instead of automatically using the pre-configured virtual environment.

**Root Cause**: VS Code wasn't properly detecting or defaulting to the virtual environment created during container build.

## Solution Overview

This solution ensures that VS Code automatically uses the virtual environment (`/home/vscode/.venv`) without requiring manual interpreter selection.

### 🔧 Components Implemented

#### 1. **Enhanced devcontainer.json Settings**
```json
{
  "customizations": {
    "vscode": {
      "settings": {
        "python.defaultInterpreterPath": "/home/vscode/.venv/bin/python",
        "python.pythonPath": "/home/vscode/.venv/bin/python",
        "python.terminal.activateEnvironment": true,
        "python.terminal.activateEnvInCurrentTerminal": true,
        "jupyter.defaultKernel": "apim-samples",
        "jupyter.askForKernelRestart": false,
        "jupyter.notebookFileRoot": "${workspaceFolder}"
      }
    }
  }
}
```

#### 2. **Updated Workspace Settings (.vscode/settings.json)**
- Added explicit Python interpreter paths for devcontainer
- Configured Jupyter to use the pre-installed kernel
- Set up automatic environment activation

#### 3. **Environment Configuration (.env)**
```bash
# Devcontainer Python environment settings
VIRTUAL_ENV=/home/vscode/.venv
PATH=/home/vscode/.venv/bin:$PATH
```

#### 4. **Automated Configuration Script**
- **File**: `.devcontainer/configure-python-interpreter.py`
- **Purpose**: Automatically registers the Python interpreter with VS Code
- **Features**:
  - Verifies virtual environment exists and works
  - Tests all required packages
  - Creates environment markers VS Code recognizes
  - Provides clear feedback and troubleshooting guidance

#### 5. **Enhanced Post-Start Setup**
- **File**: `.devcontainer/post-start-light.sh`
- **Addition**: Runs the Python interpreter configuration automatically
- **Result**: Environment is ready immediately when container starts

## 🎯 How It Works

### During Container Startup:
1. **Devcontainer loads** with pre-configured Python settings
2. **Post-start script runs** and configures Python interpreter
3. **VS Code recognizes** the virtual environment automatically
4. **Jupyter kernels** are pre-registered and ready to use

### When Opening Notebooks:
1. **Jupyter automatically uses** the "apim-samples" kernel
2. **No interpreter selection** prompt appears
3. **All packages are immediately available**
4. **Environment is fully configured**

## ✅ Verification Steps

After rebuilding your devcontainer, you should see:

### 1. **No Python Interpreter Prompts**
- Opening `.py` files should use the virtual environment automatically
- Running notebooks should use the pre-configured kernel

### 2. **Correct Python Path in VS Code**
- Bottom status bar should show: `Python 3.12.x (/home/vscode/.venv/bin/python)`
- No "Select Python Interpreter" notifications

### 3. **Working Package Imports**
```python
import requests
import jwt
import pandas
import matplotlib
import azure.storage.blob
import azure.identity
# All should work without issues
```

### 4. **Jupyter Integration**
- Notebooks should automatically use "APIM Samples Python" kernel
- No kernel selection prompts

## 🛠️ Troubleshooting

### If You Still See Interpreter Selection Prompts:

#### Manual Selection (One-time fix):
1. Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
2. Type: `Python: Select Interpreter`
3. Choose: `/home/vscode/.venv/bin/python`

#### Verify Configuration:
```bash
# Run in devcontainer terminal
python .devcontainer/configure-python-interpreter.py
```

#### Check Environment:
```bash
# Verify virtual environment
echo $VIRTUAL_ENV
# Should show: /home/vscode/.venv

# Check Python location
which python
# Should show: /home/vscode/.venv/bin/python

# Test packages
python -c "import requests, jwt, pandas; print('✅ Packages OK')"
```

### If Jupyter Kernels Don't Appear:

```bash
# List available kernels
jupyter kernelspec list

# Reinstall APIM kernel if needed
python -m ipykernel install --user --name=apim-samples --display-name="APIM Samples Python"
```

## 📊 Performance Impact

### Before Configuration:
- **Manual step required** every time for new notebooks
- **Potential package import errors** if wrong interpreter selected
- **Inconsistent development experience**

### After Configuration:
- **Zero manual steps** - everything works immediately
- **Consistent environment** across all Python operations
- **Faster development workflow**

## 📁 Files Modified

1. **`.devcontainer/devcontainer.json`** - Enhanced Python settings
2. **`.vscode/settings.json`** - Updated interpreter paths for devcontainer
3. **`.env`** - Added virtual environment configuration
4. **`.devcontainer/post-start-light.sh`** - Added interpreter configuration
5. **`.devcontainer/configure-python-interpreter.py`** - New automated setup script

## 🎉 Expected Result

**After rebuilding your devcontainer:**

1. **Open any Python file** → Virtual environment automatically selected
2. **Create new Jupyter notebook** → "APIM Samples Python" kernel automatically used
3. **Run Python scripts** → All packages immediately available
4. **No configuration prompts** → Everything works out of the box

## 🔄 Rebuilding Your Container

To apply these changes:

```bash
# In VS Code Command Palette (Ctrl+Shift+P)
> Dev Containers: Rebuild Container

# Or from terminal
docker container prune  # Optional: clean up old containers
```

The first rebuild will take a few minutes, but subsequent starts will be fast and fully configured.

## 💡 Additional Benefits

- **Consistent team experience** - Everyone gets the same configuration
- **Faster onboarding** - New team members don't need Python setup knowledge
- **Reduced support requests** - No more "which Python interpreter?" questions
- **Better CI/CD integration** - Same environment everywhere

This solution transforms your devcontainer from "almost ready" to "completely ready" for Python development!
