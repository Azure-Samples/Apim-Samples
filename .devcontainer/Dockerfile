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
    AZURE_CLI_VERSION=2.86.0 \
    BICEP_VERSION=v0.44.1 \
    CONTAINERAPP_EXTENSION_VERSION=1.3.0b4 \
    FRONT_DOOR_EXTENSION_VERSION=2.2.0 \
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
    apt-get install -y --no-install-recommends --no-install-suggests curl ca-certificates gnupg && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean && \
    curl -LsSf -o /tmp/uv-install.sh https://astral.sh/uv/${UV_VERSION}/install.sh && \
    echo "${UV_INSTALL_SHA256}  /tmp/uv-install.sh" | sha256sum -c - && \
    sh /tmp/uv-install.sh && \
    rm /tmp/uv-install.sh && \
    mv /root/.local/bin/uv /usr/local/bin/uv && \
    chmod +x /usr/local/bin/uv

# Prebuild project virtual environment template with verified locked Python dependencies (as root for /usr/local permissions)
COPY pyproject.toml uv.lock /tmp/project/
COPY setup/verify_dependency_age.py /tmp/project/setup/verify_dependency_age.py
RUN --mount=type=cache,target=/root/.cache/uv \
    cd /tmp/project && \
    python${PYTHON_VERSION} setup/verify_dependency_age.py --scope python && \
    uv venv /usr/local/share/venv-template --python /usr/local/bin/python${PYTHON_VERSION} && \
    VIRTUAL_ENV=/usr/local/share/venv-template uv sync --locked --no-install-project && \
    chown -R vscode:vscode /usr/local/share/venv-template && \
    rm -rf /tmp/project

# Install an exact Azure CLI package from Microsoft's signed Debian repository.
USER root
RUN curl -sSfL -o /tmp/microsoft.asc https://packages.microsoft.com/keys/microsoft.asc && \
        echo "2fa9c05d591a1582a9aba276272478c262e95ad00acf60eaee1644d93941e3c6  /tmp/microsoft.asc" | sha256sum -c - && \
        gpg --dearmor -o /usr/share/keyrings/microsoft.gpg /tmp/microsoft.asc && \
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/microsoft.gpg] https://packages.microsoft.com/repos/azure-cli/ bookworm main" \
            > /etc/apt/sources.list.d/azure-cli.list && \
        apt-get update && \
        apt-get install -y --no-install-recommends "azure-cli=${AZURE_CLI_VERSION}-1~bookworm" && \
        rm -rf /var/lib/apt/lists/* /tmp/microsoft.asc && \
    az --version

# Switch to vscode user
USER vscode

# Configure Azure CLI for Codespaces (prebuild optimization)
RUN az config set core.login_experience_v2=off 2>/dev/null || true && \
    az bicep install --version "${BICEP_VERSION}" 2>/dev/null || true && \
    az extension add --name containerapp --version "${CONTAINERAPP_EXTENSION_VERSION}" --only-show-errors 2>/dev/null || true && \
    az extension add --name front-door --version "${FRONT_DOOR_EXTENSION_VERSION}" --only-show-errors 2>/dev/null || true

# Set final working directory
WORKDIR /workspaces/Apim-Samples

# Add labels for maintainability
LABEL description="Dev container for Azure API Management samples" \
    python.version="${PYTHON_VERSION}"
