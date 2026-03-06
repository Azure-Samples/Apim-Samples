# https://github.com/devcontainers/images/tree/main/src/python

# syntax=docker/dockerfile:1.4

# PYTHON_VERSION must be passed as a build argument. We deliberately do not default it.
ARG PYTHON_VERSION

# Note: The base image cannot be pinned by digest because PYTHON_VERSION is a build argument;
# a digest would lock us to a single tag. This is an accepted trade-off. The image is published
# by Microsoft (mcr.microsoft.com) and Dependabot monitors it for updates. This yields a very high
# degree of safety and backwards compatibility while allowing flexibility to choose Python versions.
FROM mcr.microsoft.com/devcontainers/python:${PYTHON_VERSION}-bookworm

# Set build arguments
ARG PYTHON_VERSION

# Set environment variables
# When bumping UV_VERSION, recompute UV_INSTALL_SHA256:
#   curl -LsSf https://astral.sh/uv/<version>/install.sh | sha256sum
ENV UV_VERSION=0.9.24 \
    UV_INSTALL_SHA256=f6e468855afb4e653fa96ed68a7cad0b2534794ece25ec202f6543c589eb04dc \
    PYTHONPATH=/workspaces/Apim-Samples/shared/python:/workspaces/Apim-Samples \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1

# Install uv (https://docs.astral.sh/uv/) for fast Python package management
# The installer script is downloaded to disk, verified against a known SHA-256 checksum,
# and only then executed. This satisfies OpenSSF Scorecard's Pinned-Dependencies check.
USER root
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt/lists \
    apt-get update && \
    apt-get install -y --no-install-recommends --no-install-suggests curl ca-certificates && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean && \
    curl -LsSf -o /tmp/uv-install.sh https://astral.sh/uv/${UV_VERSION}/install.sh && \
    echo "${UV_INSTALL_SHA256}  /tmp/uv-install.sh" | sha256sum -c - && \
    sh /tmp/uv-install.sh && \
    rm /tmp/uv-install.sh && \
    mv /root/.local/bin/uv /usr/local/bin/uv && \
    chmod +x /usr/local/bin/uv

# Prebuild project virtual environment template with all Python dependencies (as root for /usr/local permissions)
COPY pyproject.toml /tmp/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv /usr/local/share/venv-template --python /usr/local/bin/python${PYTHON_VERSION} && \
    cd /tmp && \
    uv pip install --python /usr/local/share/venv-template/bin/python -e . && \
    chown -R vscode:vscode /usr/local/share/venv-template && \
    rm /tmp/pyproject.toml

# Install Azure CLI (prebuild optimization)
# Note: The installer script cannot be pinned by hash (aka.ms redirect). This is an accepted
# trade-off; the script is maintained by Microsoft and installs from the official apt repository.
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

# Set final working directory
WORKDIR /workspaces/Apim-Samples

# Add labels for maintainability
LABEL description="Dev container for Azure API Management samples" \
    python.version="${PYTHON_VERSION}"
