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
    UV_SYSTEM_PYTHON=1

# Install uv (https://docs.astral.sh/uv/) for fast Python package management
USER root
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt/lists \
    apt-get update && \
    apt-get install -y --no-install-recommends --no-install-suggests curl ca-certificates && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.local/bin/uv /usr/local/bin/uv && \
    chmod +x /usr/local/bin/uv

# Prebuild project virtual environment template with all Python dependencies (as root for /usr/local permissions)
COPY pyproject.toml /tmp/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    python3 -m venv /usr/local/share/venv-template --copies && \
    cd /tmp && \
    /usr/local/share/venv-template/bin/python -m pip install uv && \
    /usr/local/share/venv-template/bin/uv pip install --python /usr/local/share/venv-template/bin/python -e . && \
    chown -R vscode:vscode /usr/local/share/venv-template && \
    rm /tmp/pyproject.toml

# Install Azure CLI 2.82.0 (prebuild optimization)
USER root
RUN curl -sL https://aka.ms/InstallAzureCLIDeb | bash && \
    az --version

# Switch to vscode user
USER vscode

# Configure Azure CLI for Codespaces (prebuild optimization)
RUN az config set core.login_experience_v2=off 2>/dev/null || true && \
    az bicep install 2>/dev/null || true && \
    az extension add --name containerapp --only-show-errors 2>/dev/null || true && \
    az extension add --name front-door --only-show-errors 2>/dev/null || true

# Pre-install VS Code extensions (reduces startup time significantly)
RUN mkdir -p /home/vscode/.vscode-server/extensions && \
    code-server --install-extension ms-python.python && \
    code-server --install-extension ms-python.debugpy && \
    code-server --install-extension ms-toolsai.jupyter && \
    code-server --install-extension ms-azuretools.vscode-bicep && \
    code-server --install-extension ms-vscode.azurecli && \
    code-server --install-extension redhat.vscode-yaml && \
    code-server --install-extension ms-vscode.vscode-json && \
    code-server --install-extension GitHub.copilot && \
    code-server --install-extension GitHub.copilot-chat && \
    code-server --install-extension donjayamanne.vscode-default-python-kernel

# Set final working directory
WORKDIR /workspaces/Apim-Samples

# Add labels for maintainability
LABEL description="Dev container for Azure API Management samples" \
    python.version="${PYTHON_VERSION}"
