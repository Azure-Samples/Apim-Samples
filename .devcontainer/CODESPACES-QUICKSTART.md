# APIM Samples Codespaces Quickstart

Welcome! Please follow these steps to get productive fast:

1. [Authenticate with Azure](#-authenticate-with-azure)

1. [Open notebooks and samples](#-work-with-notebooks-and-samples)

1. [Use common developer workflows](#-common-developer-workflows)

1. [Troubleshoot if anything looks off](#-troubleshooting-tips)

---

## Environment verification (already done for you)

The post-start script runs automatically and verifies that the virtual
environment, `.env` file, Azure CLI, and Python are all present. Look for the
first terminal tab titled **“APIM Samples Codespace Starting”** (or re-open the
first terminal in VS Code); it shows the output from `.devcontainer/post-start-setup.sh`.

If you ever want to rerun the verification manually, open a terminal and execute:

```bash
bash .devcontainer/post-start-setup.sh
```

---

## Authenticate with Azure

Use device login to make Azure CLI commands available inside the container. Run
one of the following in a new terminal:

```bash
az login
# or, specify a tenant explicitly
az login --tenant <your-tenant-id>
```

If you do not have Azure permissions, you can skip this step for local-only
experiments.

---

## Activate the virtual environment (if needed)

Every new terminal automatically activates `.venv`. If you do not see the
`(.venv)` prefix, run:

```bash
source .venv/bin/activate
```

This ensures `python`, `pip`, and all tooling reference the prebuilt environment.

---

## Run the verification script (optional)

To double-check that everything is connected properly, execute:

```bash
python setup/verify_local_setup.py
```

The script validates Azure CLI/Bicep, resource providers, and VS Code settings.

---

## Work with notebooks and samples

1. Open any notebook in `infrastructure/` or `samples/`.
2. If prompted to pick a kernel, choose **Python (.venv)**.
3. Execute cells as usual.

Need guidance for individual samples? Each subfolder contains a README with
deployment steps and policy details.

---

## Common developer workflows

| Task | Command |
|------|---------|
| Run tests | `pytest` or `tests/python/run_tests.sh` |
| Run pylint | `tests/python/run_pylint.sh` |
| Full quality checks | `tests/python/check_python.ps1` or `.sh` |
| Generate `.env` again | `python setup/local_setup.py --generate-env` |
| Launch environment setup | `python setup/local_setup.py --complete-setup` |

---

## ℹ️ Troubleshooting Tips

- **Extensions still installing?** Wait for the VS Code status bar to finish
  spinning. It can take a minute for Copilot and other extensions to activate.
- **Something feels off?** Check `.devcontainer/post-start-setup.sh` for the
  exact commands the container runs on startup.

---

Enjoy exploring the APIM Samples project! If you have ideas to improve this
quickstart, open an issue or PR so that everyone may benefit. Thank you!
