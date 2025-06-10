# https://github.com/devcontainers/images/tree/main/src/python

# syntax=docker/dockerfile:1.4

# BUILD stage for dependencies - use MAJOR semantic image (1) with Python 3.12
FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm AS builder

# Set build arguments for flexibility
ARG VIRTUAL_ENV_PATH=/home/vscode/.venv
ARG PYTHON_VERSION=3.12

# Set environment variables early for better caching
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=${VIRTUAL_ENV_PATH} \
    PATH="${VIRTUAL_ENV_PATH}/bin:$PATH"

# Switch to vscode user for build
USER vscode

# Create virtual environment with optimized settings
RUN python3 -m venv $VIRTUAL_ENV --copies

# # Ensure pip is at latest version in virtual environment
# RUN . $VIRTUAL_ENV/bin/activate && \
#     python -m pip install --upgrade pip setuptools wheel

# Copy only requirements.txt first for better Docker layer caching
COPY --chown=vscode:vscode requirements.txt /tmp/requirements.txt

# Install Python packages with mount cache for pip
RUN --mount=type=cache,target=/home/vscode/.cache/pip,uid=1000,gid=1000 \
    set -ex && \
    . $VIRTUAL_ENV/bin/activate && \
    pip install --compile -r /tmp/requirements.txt && \
    pip install --compile pytest pytest-cov coverage ipykernel && \
    python -m ipykernel install --user --name=apim-samples --display-name="APIM Samples Python" && \
    pip list --format=freeze > /tmp/installed-packages.txt && \
    echo "✅ Pip version: $(pip --version)" > /tmp/pip-version.txt

###################################################################################################

# PRODUCTION stage - use MAJOR semantic image (1) with Python 3.12
FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm AS production

# Set build arguments for flexibility
ARG VIRTUAL_ENV_PATH=/home/vscode/.venv
ARG PYTHON_VERSION=3.12

# Set environment variables early for better caching
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/workspaces/Apim-Samples/shared/python:/workspaces/Apim-Samples \
    VIRTUAL_ENV=${VIRTUAL_ENV_PATH} \
    PATH="${VIRTUAL_ENV_PATH}/bin:$PATH" \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies as root with mount cache
USER root
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt/lists \
    apt-get update && \ 
    apt-get install -y --no-install-recommends curl wget jq tree git-lfs vim nano htop && \
    apt-get clean && \
    # Ensure latest pip is installed
    python3 -m pip install --upgrade pip setuptools wheel

# Copy the virtual environment from builder stage
COPY --from=builder --chown=vscode:vscode ${VIRTUAL_ENV_PATH} ${VIRTUAL_ENV_PATH}

# Copy Jupyter kernel config from builder
COPY --from=builder --chown=vscode:vscode /home/vscode/.local /home/vscode/.local

# Copy pip version info from builder
COPY --from=builder /tmp/pip-version.txt /tmp/pip-version.txt

# Switch to vscode user for all remaining operations
USER vscode

# Verify pip installation and display version info
RUN set -ex && \
    . $VIRTUAL_ENV/bin/activate && \
    pip --version && \
    python -c "import pip; print(f'✅ Pip version: {pip.__version__}')" && \
    cat /tmp/pip-version.txt && \
    # Configure shell environment with optimizations
    set -ex && \
    echo "# Virtual environment auto-activation" >> ~/.bashrc && \
    echo "export VIRTUAL_ENV=${VIRTUAL_ENV}" >> ~/.bashrc && \
    echo "export PATH=\"\${VIRTUAL_ENV}/bin:\$PATH\"" >> ~/.bashrc && \
    echo "source \${VIRTUAL_ENV}/bin/activate" >> ~/.bashrc && \
    echo "# Virtual environment auto-activation" >> ~/.zshrc && \
    echo "export VIRTUAL_ENV=${VIRTUAL_ENV}" >> ~/.zshrc && \
    echo "export PATH=\"\${VIRTUAL_ENV}/bin:\$PATH\"" >> ~/.zshrc && \
    echo "source \${VIRTUAL_ENV}/bin/activate" >> ~/.zshrc && \
    # Create helpful aliases and functions
    set -ex && \
    echo "# APIM Samples helpful aliases" >> ~/.bashrc && \
    echo "alias ll='ls -alF'" >> ~/.bashrc && \
    echo "alias la='ls -A'" >> ~/.bashrc && \
    echo "alias l='ls -CF'" >> ~/.bashrc && \
    echo "alias pipr='pip install -r requirements.txt'" >> ~/.bashrc && \
    echo "alias pytest-cov='python -m pytest --cov=. --cov-report=html'" >> ~/.bashrc && \
    echo "alias azlogin='az login --use-device-code'" >> ~/.bashrc

# Set working directory
WORKDIR /workspaces/Apim-Samples

# Add health check for the virtual environment
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys, pip; print(f'Python {sys.version}'); print(f'Pip {pip.__version__}'); import requests, jwt; print('Core packages OK')" || exit 1

# Add labels for better maintainability
LABEL maintainer="APIM Samples Team" \
      description="Optimized dev container for Azure API Management samples" \
      version="1.0" \
      python.version="3.12" \
      debian.version="bookworm"
