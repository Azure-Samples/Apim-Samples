# Python Environment Setup

Configures cross-platform PYTHONPATH for APIM Samples and provides streamlined local development setup.

## Prerequisites

Install the eligible uv 0.9.24 release before proceeding:

**Windows:**

```powershell
# Using winget
winget install --id=astral-sh.uv --version 0.9.24 -e
```

**macOS:**

```bash
curl -LsSf -o uv-install.sh https://astral.sh/uv/0.9.24/install.sh
echo "f6e468855afb4e653fa96ed68a7cad0b2534794ece25ec202f6543c589eb04dc  uv-install.sh" | shasum -a 256 -c -
sh uv-install.sh
rm uv-install.sh
```

**Linux:**

```bash
curl -LsSf -o uv-install.sh https://astral.sh/uv/0.9.24/install.sh
echo "f6e468855afb4e653fa96ed68a7cad0b2534794ece25ec202f6543c589eb04dc  uv-install.sh" | sha256sum -c -
sh uv-install.sh
rm uv-install.sh
```

Verify installation:

```bash
uv --version
```

## Quick Setup

For complete local environment setup that matches the dev container experience:

```shell
uv venv
python setup/verify_dependency_age.py --scope python
uv sync --locked
python setup/local_setup.py --complete-setup
```

The repository excludes packages published within the last seven days. Use the guarded helper to refresh the lockfile and sync the environment:

```shell
python setup/sync_dependencies.py --upgrade
```

The helper isolates lock generation from user package-index configuration, resolves the lock against canonical public PyPI with `exclude-newer = "7 days"`, and then runs the age verifier before installation. If canonical PyPI's artifact host is unreachable, the helper preserves the existing lock and syncs its verified packages through the configured index instead.

Generate `uv.lock` only against canonical public PyPI. The uv lock format requires registry sources and artifact URLs, so do not remove those fields manually or replace them with organization-specific package mirror URLs.

If your network cannot access the artifact URLs stored in `uv.lock`, install the same locked packages through an approved package mirror. The temporary export contains package names, versions, environment markers, and hashes without carrying the lock's index URLs:

```shell
python setup/verify_dependency_age.py --scope python
uv export --frozen --no-emit-project --no-header --no-annotate --output-file <temporary-requirements-file>
uv pip sync <temporary-requirements-file> --no-config --default-index <mirror-url> --require-hashes --system-certs --strict
```

Delete the temporary requirements file after installation and do not commit it. In this fallback, `--no-config` prevents uv from reevaluating the already-verified age cutoff against mirrors that omit upload timestamps. The guarded helper also uses `--no-config` while updating the lock so user mirror configuration cannot affect canonical resolution; do not use it for other dependency operations.

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

## Cleaning Up Local Artifacts

To remove cached, temporary, and build artifacts from your local environment, use the cleanup scripts or the Developer CLI.

**Via the Developer CLI (recommended):**

```shell
# PowerShell (Windows)
./start.ps1    # then choose  c) Clean local artifacts

# Bash (Linux/macOS)
./start.sh     # then choose  c) Clean local artifacts
```

**Directly:**

```shell
# PowerShell (Windows)
pwsh setup/clean-local-artifacts.ps1

# Bash (Linux/macOS)
bash setup/clean-local-artifacts.sh
```

The following are removed:

| Type                    | Items                                               |
| ----------------------- | --------------------------------------------------- |
| Cache directories       | `.pytest_cache`, `.ruff_cache`, `__pycache__`       |
| Test/coverage artifacts | `htmlcov`, `.coverage`, `.coverage.*`               |
| Build/package artifacts | `build`, `dist`, `.eggs`, `*.egg-info`              |
| Temporary files         | `*.pyc`, `*.pyo`, `*.tmp`, `*.temp`                 |

> **Note:** `.env` is intentionally left in place.
