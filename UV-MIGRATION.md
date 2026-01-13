# UV Migration Guide

This repository has migrated from pip to **uv** for faster and more reliable Python package management.

## What Changed

### Core Changes
- **Package management**: pip → uv
- **Dependency declaration**: `requirements.txt` → `pyproject.toml`
- **Lock file**: Added `uv.lock` for reproducible installs
- **Environment creation**: `python -m venv` → `uv venv`
- **Package installation**: `pip install -r requirements.txt` → `uv sync`

### Files Modified
- ✅ [pyproject.toml](pyproject.toml) - New PEP 621 metadata and dependencies
- ✅ [start.ps1](start.ps1) - Uses `uv run` when available (pip fallback)
- ✅ [start.sh](start.sh) - Uses `uv run` when available (pip fallback)
- ✅ [README.md](README.md) - Updated setup instructions with uv
- ✅ [setup/README.md](setup/README.md) - Added uv installation steps
- ✅ [setup/local_setup.py](setup/local_setup.py) - Prefers uv for ipykernel install
- ✅ [setup/verify_local_setup.py](setup/verify_local_setup.py) - Updated error messages to uv commands
- ✅ [.devcontainer/Dockerfile](.devcontainer/Dockerfile) - Installs uv, uses it for dependency management
- ✅ [.devcontainer/python312/devcontainer.json](.devcontainer/python312/devcontainer.json) - Uses uv venv + uv sync
- ✅ [.devcontainer/python313/devcontainer.json](.devcontainer/python313/devcontainer.json) - Uses uv venv + uv sync
- ✅ [.devcontainer/python314/devcontainer.json](.devcontainer/python314/devcontainer.json) - Uses uv venv + uv sync
- ✅ [.devcontainer/post-start-setup.sh](.devcontainer/post-start-setup.sh) - Prefers uv run
- ✅ [.devcontainer/README.md](.devcontainer/README.md) - Updated docs to reference uv
- ✅ [.github/workflows/python-tests.yml](.github/workflows/python-tests.yml) - Uses uv for CI with caching
- ✅ [.vscode/tasks.json](.vscode/tasks.json) - Added "Install Dependencies (uv)" task
- ✅ [.dockerignore](.dockerignore) - Updated to reference pyproject.toml

## Installing UV

### Windows
```powershell
# Using winget (recommended)
winget install --id=astral-sh.uv -e

# Or using scoop
scoop install uv
```

### macOS
```bash
# Using Homebrew
brew install uv

# Or using the official installer
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Linux
```bash
# Using the official installer
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify installation:
```bash
uv --version
```

## Quick Start (Local Development)

```bash
# 1. Install uv (see above)

# 2. Create virtual environment
uv venv

# 3. Install dependencies
uv sync

# 4. Complete environment setup
python setup/local_setup.py --complete-setup

# 5. Activate environment (if needed)
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
```

## Developer CLI

The [start.ps1](start.ps1) and [start.sh](start.sh) scripts now automatically use uv when available:

**Windows:**
```powershell
.\start.ps1
```

**macOS/Linux:**
```bash
./start.sh
```

The scripts will:
- Automatically run `uv venv && uv sync` if uv is detected
- Use `uv run python` for all Python invocations
- Fall back to direct Python execution if uv is not installed

## CI/CD

GitHub Actions workflows now:
- Install uv via `astral-sh/setup-uv@v4`
- Use `uv sync` to install dependencies
- Run tests with `uv run pytest`
- Cache uv dependencies for faster builds

## Dev Container / Codespaces

All devcontainer configurations:
- Install uv in the Dockerfile
- Use `uv venv` to create virtual environments
- Use `uv sync` to install dependencies from pyproject.toml
- Execute Python via `uv run` when appropriate

## Rollback Strategy

If you encounter issues and need to revert to pip temporarily:

1. The bootstrap scripts ([start.ps1](start.ps1), [start.sh](start.sh)) include pip fallback - they'll work without uv
2. You can still create a venv and install from pyproject.toml using pip:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows
   pip install -e .
   ```

## Benefits

- **Speed**: uv is 10-100x faster than pip for package resolution and installation
- **Reliability**: Lock file ensures reproducible builds across all environments
- **Modern**: PEP 621 pyproject.toml is the standard for Python projects
- **Caching**: Aggressive caching reduces network usage and speeds up CI
- **Compatibility**: Fully compatible with existing pip-based workflows

## Resources

- uv documentation: https://docs.astral.sh/uv/
- uv GitHub: https://github.com/astral-sh/uv
- PEP 621 (pyproject.toml): https://peps.python.org/pep-0621/

## Questions?

If you encounter any issues with the uv migration, please:
1. Check this guide for common solutions
2. Verify uv is installed: `uv --version`
3. Try the rollback strategy above
4. File an issue with details about your environment
