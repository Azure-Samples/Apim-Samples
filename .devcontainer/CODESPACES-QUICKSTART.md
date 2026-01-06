# APIM Samples Codespaces Quickstart

Welcome! Please follow these steps to get productive fast:

1. [Authenticate with Azure](#-authenticate-with-azure)

1. [Infrastructures and Samples](#-infrastructures-and-samples)

1. [Developer CLI](#-developer-cli)

1. [Troubleshooting](#-troubleshooting)

---

## Environment verification (already done for you)

The `post-start-setup.sh` script runs automatically and verifies that the virtual
environment, `.env` file, Azure CLI, Python, etc. are all present. You can see details
in the terminal window if you just started your Codespace.

You can also run the command in the terminal yourself:

```bash
bash .devcontainer/post-start-setup.sh
```

---

## Authenticate with Azure

Use device login to make Azure CLI commands available inside the container:

```bash
az login
# or, specify a tenant explicitly
az login --tenant <your-tenant-id>
```

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

## Infrastructures and Samples

1. Open any notebook in `infrastructure/` or `samples/`.
2. If prompted to pick a kernel, choose **Python (.venv)**.
3. Execute cells as usual.

Need guidance for individual samples? Each subfolder contains a README with
deployment steps and policy details.

---

## Developer CLI

Use the **APIM Samples Developer CLI** for setup and testing:

```bash
bash start.sh
```

---

## ℹ️ Troubleshooting

- **Extensions still installing?** Wait for the VS Code status bar to finish
  spinning. It can take a minute for Copilot and other extensions to activate.
- **Something feels off?** Check `.devcontainer/post-start-setup.sh` for the
  exact commands the container runs on startup.

---

Enjoy exploring the APIM Samples project! If you have ideas to improve this
quickstart, open an issue or PR so that everyone may benefit. Thank you!
