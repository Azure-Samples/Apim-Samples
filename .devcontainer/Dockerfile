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

# Switch to vscode user
USER vscode

# Configure Azure CLI for Codespaces (prebuild optimization)
RUN az config set core.login_experience_v2=off 2>/dev/null || true && \
    az extension add --name containerapp --only-show-errors 2>/dev/null || true && \
    az extension add --name front-door --only-show-errors 2>/dev/null || true

# Configure shell to auto-activate virtual environment
RUN echo "# Auto-activate APIM Samples virtual environment" >> ~/.bashrc && \
    echo "if [ -f /workspaces/Apim-Samples/.venv/bin/activate ]; then" >> ~/.bashrc && \
    echo "    source /workspaces/Apim-Samples/.venv/bin/activate" >> ~/.bashrc && \
    echo "fi" >> ~/.bashrc && \
    echo "# Auto-activate APIM Samples virtual environment" >> ~/.zshrc && \
    echo "if [ -f /workspaces/Apim-Samples/.venv/bin/activate ]; then" >> ~/.zshrc && \
    echo "    source /workspaces/Apim-Samples/.venv/bin/activate" >> ~/.zshrc && \
    echo "fi" >> ~/.zshrc && \
    # Add helpful aliases
    echo "alias ll='ls -alF'" >> ~/.bashrc && \
    echo "alias la='ls -A'" >> ~/.bashrc && \
    echo "alias l='ls -CF'" >> ~/.bashrc && \
    echo "alias pytest-cov='python -m pytest --cov=. --cov-report=html'" >> ~/.bashrc

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
