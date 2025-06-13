# https://github.com/devcontainers/images/tree/main/src/python

# syntax=docker/dockerfile:1.4

# Use single-stage build with Python 3.12
FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

# Set build arguments
ARG PYTHON_VERSION=3.12

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/workspaces/Apim-Samples/shared/python:/workspaces/Apim-Samples \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies as root
USER root
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt/lists \
    apt-get update && \
    # Remove Python 3.11 and other versions if they exist
    apt-get remove -y python3.11* python3-minimal python3.11-minimal || true && \
    apt-get autoremove -y && \
    # Install essential packages
    apt-get install -y --no-install-recommends curl wget jq tree git-lfs vim nano htop && \
    apt-get clean && \
    # Create symbolic links to ensure python3 points to Python 3.12
    ln -sf /usr/local/bin/python3.12 /usr/bin/python3 && \
    ln -sf /usr/local/bin/python3.12 /usr/bin/python && \
    # Ensure latest pip is installed for Python 3.12
    /usr/local/bin/python3.12 -m pip install --upgrade pip setuptools wheel

# Pre-install VS Code extensions
ARG USERNAME=vscode
RUN mkdir -p /home/$USERNAME/.vscode-server/extensions && \
    chown -R $USERNAME:$USERNAME /home/$USERNAME/.vscode-server
    
USER $USERNAME
# Install commonly used VS Code extensions to improve startup time
RUN umask 0002 && \
    code-server --install-extension ms-python.python && \
    code-server --install-extension ms-python.debugpy && \
    code-server --install-extension ms-toolsai.jupyter && \
    code-server --install-extension ms-toolsai.jupyter-keymap && \
    code-server --install-extension ms-toolsai.jupyter-renderers && \
    code-server --install-extension ms-toolsai.vscode-jupyter-cell-tags && \
    code-server --install-extension ms-toolsai.vscode-jupyter-slideshow && \
    code-server --install-extension ms-azuretools.vscode-bicep && \
    code-server --install-extension ms-vscode.azurecli && \
    code-server --install-extension ms-azure-devops.azure-pipelines && \
    code-server --install-extension redhat.vscode-yaml && \
    code-server --install-extension ms-vscode.vscode-json && \
    code-server --install-extension donjayamanne.vscode-default-python-kernel

# Configure Azure CLI for Codespaces (prebuild optimization)
RUN az config set core.login_experience_v2=off 2>/dev/null || true && \
    az extension add --name containerapp --only-show-errors 2>/dev/null || true && \
    az extension add --name front-door --only-show-errors 2>/dev/null || true

# Configure shell aliases and helpful commands (venv handled by devcontainer)
RUN echo "# APIM Samples helpful aliases" >> ~/.bashrc && \
    echo "alias ll='ls -alF'" >> ~/.bashrc && \
    echo "alias la='ls -A'" >> ~/.bashrc && \
    echo "alias l='ls -CF'" >> ~/.bashrc && \
    echo "alias pytest-cov='python -m pytest --cov=. --cov-report=html'" >> ~/.bashrc && \
    echo "" >> ~/.zshrc && \
    echo "# APIM Samples helpful aliases" >> ~/.zshrc && \
    echo "alias ll='ls -alF'" >> ~/.zshrc && \
    echo "alias la='ls -A'" >> ~/.zshrc && \
    echo "alias l='ls -CF'" >> ~/.zshrc && \
    echo "alias pytest-cov='python -m pytest --cov=. --cov-report=html'" >> ~/.zshrc

# Set final working directory
WORKDIR /workspaces/Apim-Samples

# Add health check for the virtual environment
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD . /workspaces/Apim-Samples/.venv/bin/activate && python -c "import sys, pip; print(f'Python {sys.version}'); print(f'Pip {pip.__version__}'); import requests, jwt; print('Core packages OK')" || exit 1

# Add labels for maintainability
LABEL maintainer="APIM Samples Team" \
      description="Simplified dev container for Azure API Management samples with Codespaces prebuild optimization" \
      version="2.1" \
      python.version="3.12" \
      debian.version="bookworm" \
      venv.location="/workspaces/Apim-Samples/.venv"
