# Post-Migration Checklist

This file tracks the final steps to complete the uv migration.

## ✅ Completed

- [x] Created [pyproject.toml](pyproject.toml) with PEP 621 metadata
- [x] Updated [start.ps1](start.ps1) and [start.sh](start.sh) to use uv with pip fallback
- [x] Updated [setup/local_setup.py](setup/local_setup.py) to prefer uv for package installation
- [x] Updated [setup/verify_local_setup.py](setup/verify_local_setup.py) error messages to reference uv
- [x] Updated [README.md](README.md) with uv installation and setup instructions
- [x] Updated [setup/README.md](setup/README.md) with uv prerequisites
- [x] Updated [.devcontainer/Dockerfile](.devcontainer/Dockerfile) to install uv
- [x] Updated all devcontainer.json files (python312, python313, python314) to use uv
- [x] Updated [.devcontainer/post-start-setup.sh](.devcontainer/post-start-setup.sh) to use uv
- [x] Updated [.devcontainer/README.md](.devcontainer/README.md) documentation
- [x] Updated [.github/workflows/python-tests.yml](.github/workflows/python-tests.yml) to use uv
- [x] Added "Install Dependencies (uv)" task to [.vscode/tasks.json](.vscode/tasks.json)
- [x] Updated [.dockerignore](.dockerignore) to reference pyproject.toml
- [x] Updated project root detection in [shared/python/apimtypes.py](shared/python/apimtypes.py)
- [x] Updated project root detection in [shared/python/utils.py](shared/python/utils.py)
- [x] Added deprecation notice to [requirements.txt](requirements.txt)
- [x] Created [UV-MIGRATION.md](UV-MIGRATION.md) migration guide

## 🔄 Next Steps (User Action Required)

### 1. Install uv

**Windows:**
```powershell
winget install --id=astral-sh.uv -e
```

**macOS:**
```bash
brew install uv
```

**Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify:
```bash
uv --version
```

### 2. Generate uv.lock

```bash
cd c:\Dev\Azure-Samples\Apim-Samples
uv lock
```

This will create `uv.lock` with pinned versions for reproducible installs.

### 3. Test Local Setup

```bash
# Remove existing .venv to start fresh
Remove-Item -Recurse -Force .venv

# Create new environment with uv
uv venv
uv sync

# Complete environment setup
python setup/local_setup.py --complete-setup

# Verify setup
python setup/verify_local_setup.py

# Run tests to ensure everything works
uv run pytest
```

### 4. Commit Changes

```bash
git add .
git commit -m "Migrate from pip to uv for package management

- Add pyproject.toml with PEP 621 metadata
- Update all scripts and CI to use uv
- Add uv.lock for reproducible installs
- Update documentation and dev containers
- Maintain requirements.txt for backward compatibility

See UV-MIGRATION.md for details."
```

### 5. Update CI/CD Secrets (if needed)

If your CI/CD uses any pip-specific environment variables or secrets, update them to work with uv.

### 6. Communicate to Team

Share the [UV-MIGRATION.md](UV-MIGRATION.md) guide with your team and ensure everyone:
1. Installs uv
2. Runs `uv venv && uv sync` in their local environments
3. Updates any personal scripts or workflows

## 🧪 Validation Checklist

- [ ] Local development works: `uv venv && uv sync`
- [ ] Tests pass: `uv run pytest`
- [ ] Linting passes: `uv run pylint ...`
- [ ] Developer CLI works: `.\start.ps1` or `./start.sh`
- [ ] Devcontainer builds successfully
- [ ] CI pipeline is green on GitHub Actions
- [ ] Documentation is clear and helpful

## 📊 Expected Benefits

- **10-100x faster** package installation
- **Reproducible builds** via uv.lock
- **Reduced CI time** with aggressive caching
- **Modern tooling** aligned with Python ecosystem direction
- **Better developer experience** with faster iteration

## 🔄 Rollback Plan

If issues arise:

1. The migration includes pip fallback in bootstrap scripts
2. requirements.txt is still present for emergency rollback
3. To fully revert:
   ```bash
   git revert <commit-hash>
   ```

## 📝 Notes

- requirements.txt is kept for backward compatibility but marked as deprecated
- All scripts support both uv and pip for smooth transition
- uv.lock should be committed to version control
- Dev containers will need rebuild on first use after merge
