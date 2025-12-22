# https://github.com/devcontainers/images/tree/main/src/python

# syntax=docker/dockerfile:1.4

# Use single-stage build with Python 3.14
FROM mcr.microsoft.com/devcontainers/python:3.14-bookworm

# Set build arguments
ARG PYTHON_VERSION=3.14

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/workspaces/Apim-Samples/shared/python:/workspaces/Apim-Samples \
    DEBIAN_FRONTEND=noninteractive

# Install minimal system dependencies as root
USER root
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt/lists \
    apt-get update && \
    apt-get install -y --no-install-recommends curl git-lfs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    /usr/local/bin/python3.14 -m pip install --upgrade pip setuptools wheel

# Switch to vscode user
USER vscode

# Configure Azure CLI for Codespaces (prebuild optimization)
RUN az config set core.login_experience_v2=off 2>/dev/null || true && \
    az extension add --name containerapp --only-show-errors 2>/dev/null || true && \
    az extension add --name front-door --only-show-errors 2>/dev/null || true

# Set final working directory
WORKDIR /workspaces/Apim-Samples

# Add health check for the virtual environment
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD . /workspaces/Apim-Samples/.venv/bin/activate && python -c "import sys, pip; print(f'Python {sys.version}'); print(f'Pip {pip.__version__}')" || exit 1

# Add labels for maintainability
LABEL maintainer="APIM Samples Team" \
    description="Optimized dev container for Azure API Management samples with Codespaces prebuild support" \
    version="2.2" \
    python.version="3.14" \
    debian.version="bookworm" \
    venv.location="/workspaces/Apim-Samples/.venv"
