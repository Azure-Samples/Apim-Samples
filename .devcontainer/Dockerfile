# https://github.com/devcontainers/images/tree/main/src/python

# syntax=docker/dockerfile:1.4

# PYTHON_VERSION must be passed as a build argument. We deliberately do not default it.
ARG PYTHON_VERSION

FROM mcr.microsoft.com/devcontainers/python:${PYTHON_VERSION}-bookworm

# Set build arguments
ARG PYTHON_VERSION

# Set environment variables
ENV PYTHONPATH=/workspaces/Apim-Samples/shared/python:/workspaces/Apim-Samples \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install minimal system dependencies as root
# Use cache mounts for apt and pip to speed up rebuilds while keeping image lean
USER root
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt/lists \
    --mount=type=cache,target=/root/.cache/pip \
    apt-get update && \
    apt-get install -y --no-install-recommends --no-install-suggests && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean && \
    python3 -m pip install --upgrade --no-cache-dir pip setuptools wheel

# Prebuild project virtual environment template with all Python dependencies (as root for /usr/local permissions)
COPY requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m venv /usr/local/share/venv-template --copies && \
    /usr/local/share/venv-template/bin/pip install --upgrade pip setuptools wheel && \
    /usr/local/share/venv-template/bin/pip install -r /tmp/requirements.txt && \
    chown -R vscode:vscode /usr/local/share/venv-template && \
    rm /tmp/requirements.txt

# Switch to vscode user
USER vscode

# Configure Azure CLI for Codespaces (prebuild optimization)
RUN az config set core.login_experience_v2=off 2>/dev/null || true && \
    az extension add --name containerapp --only-show-errors 2>/dev/null || true && \
    az extension add --name front-door --only-show-errors 2>/dev/null || true

# Set final working directory
WORKDIR /workspaces/Apim-Samples

# Add labels for maintainability
LABEL description="Dev container for Azure API Management samples" \
    python.version="${PYTHON_VERSION}"
