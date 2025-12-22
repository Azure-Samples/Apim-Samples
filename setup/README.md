# Python Environment Setup

Configures cross-platform PYTHONPATH for APIM Samples and provides streamlined local development setup.

## Quick Setup

For complete local environment setup that matches the dev container experience:

```shell
python setup/local_setup.py --complete-setup
```

This will:
- Generate `.env` file for Python path configuration
- Register the standardized "APIM Samples Python 3.12" Jupyter kernel
- Configure VS Code settings for automatic kernel selection
- Enforce kernel consistency to prevent auto-changes
- Set up optimal workspace configuration

## Individual Commands

If you prefer to run setup steps individually:

```shell
# Generate .env file only
python setup/local_setup.py --generate-env

# Register Jupyter kernel only
python setup/local_setup.py --setup-kernel

# Configure VS Code settings only
python setup/local_setup.py --setup-vscode

# Force kernel consistency (fix kernel switching issues)
python setup/local_setup.py --force-kernel

# Basic PYTHONPATH setup for current session
python setup/local_setup.py --run-only

# Show help and available options
python setup/local_setup.py
```

## Verification

After setup, verify everything is working correctly:

```shell
python setup/verify_setup.py
```

This checks:
- Virtual environment activation
- Required package installation
- Shared module imports
- Jupyter kernel registration with correct name/display name
- VS Code settings configuration
- Environment file setup
- Kernel consistency enforcement

## Kernel Consistency

To ensure notebooks always use the correct kernel ("APIM Samples Python 3.12" instead of ".venv" or "python3"):

1. **Run the complete setup**: `python setup/local_setup.py --complete-setup`
2. **Restart VS Code** completely
3. **Verify with**: `python setup/verify_setup.py`

If you still see incorrect kernel names, run:
```shell
python setup/local_setup.py --force-kernel
```

## Troubleshooting

### Kernel Issues
- **Problem**: Notebooks show ".venv" or "python3" instead of "APIM Samples Python 3.12"
- **Solution**: Run `--force-kernel` and restart VS Code

### Python Command Issues

```shell
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows
```
