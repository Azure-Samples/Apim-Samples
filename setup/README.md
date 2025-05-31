# Python Environment Setup

Configures cross-platform PYTHONPATH for APIM Samples.

## Usage

```shell
python setup/setup_python_path.py --generate-env
```

This script auto-detects the project root and generates a `.env` file that VS Code uses for Python path configuration. If for some reason the `python` command is not found, please try adding your virtual environment's `bin` or `Scripts` directory to your system's PATH variable.  An example command to do this for a virtual environment named `venv` is:

```shell
source .venv/bin/activate
```
