# https://github.com/devcontainers/images/tree/main/src/python

# syntax=docker/dockerfile:1.4

# Use single-stage build with Python 3.14
FROM mcr.microsoft.com/devcontainers/python:1-3.14-bookworm

# Set build arguments
ARG PYTHON_VERSION=3.14

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
    # Create symbolic links to ensure python3 points to Python 3.14
    ln -sf /usr/local/bin/python3.14 /usr/bin/python3 && \
    ln -sf /usr/local/bin/python3.14 /usr/bin/python && \
    # Ensure latest pip is installed for Python 3.14
    /usr/local/bin/python3.14 -m pip install --upgrade pip setuptools wheel

# Switch to vscode user
USER vscode

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
      python.version="3.14" \
      debian.version="bookworm" \
      venv.location="/workspaces/Apim-Samples/.venv"
