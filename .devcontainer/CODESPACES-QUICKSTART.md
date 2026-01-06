# APIM Samples Codespaces Quickstart

## ✅ What's ready for you

Your Codespace has automatically set up:
- Python virtual environment (`.venv`)
- Azure CLI
- All project dependencies
- VS Code extensions (still installing? Wait ~1 minute for the status bar to finish)

---

## 🎯 Next: Authenticate with Azure

Open a terminal and log in:

```bash
az login
```

Or, if you need to specify a tenant:

```bash
az login --tenant <your-tenant-id>
```

**This is required** before you can deploy any infrastructure or samples.

---

## 🚀 Ready to go?

### Start with a sample
1. Open any notebook in `infrastructure/` or `samples/`
2. If prompted, select the **Python (.venv)** kernel
3. Run the cells

Each folder has a `README.md` with full deployment steps.

### Use the Developer CLI
```bash
bash start.sh
```

---

## 📋 If something isn't working

| Issue | Solution |
|-------|----------|
| Virtual environment not active | New terminals auto-activate. If you see no `(.venv)` prefix, run: `source .venv/bin/activate` |
| Extensions not ready | Wait for VS Code status bar to stop spinning (~1 minute) |
| Need to verify setup | Run: `python setup/verify_local_setup.py` |
| Something else | Check `.devcontainer/post-start-setup.sh` for startup commands |

---


Ready? Start with the README in the root folder for the big picture!
