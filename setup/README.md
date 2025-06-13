# Python Environment Setup

Configures cross-platform PYTHONPATH for APIM Samples and provides streamlined local development setup.

## Quick Setup

For complete local environment setup that matches the dev container experience:

```shell
python setup/setup_python_path.py --complete-setup
```

This will:
- Generate `.env` file for Python path configuration
- Register the standardized "APIM Samples Python 3.12" Jupyter kernel
- Configure VS Code settings for automatic kernel selection
- Set up optimal workspace configuration

## Individual Commands

If you prefer to run setup steps individually:

```shell
# Generate .env file only
python setup/setup_python_path.py --generate-env

# Register Jupyter kernel only
python setup/setup_python_path.py --setup-kernel

# Configure VS Code settings only
python setup/setup_python_path.py --setup-vscode

# Basic PYTHONPATH setup for current session
python setup/setup_python_path.py --run-only

# Show help and available options
python setup/setup_python_path.py
```

## Verification

After setup, verify everything is working correctly:

```shell
python setup/verify_local_setup.py
```

This checks:
- Virtual environment activation
- Required package installation
- Shared module imports
- Jupyter kernel registration
- VS Code settings configuration
- Environment file setup

## Troubleshooting

If the `python` command is not found, add your virtual environment to your system's PATH:

```shell
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows
```
