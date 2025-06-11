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
RUN /usr/local/bin/python3.12 -m venv $VIRTUAL_ENV --copies

# Copy only requirements.txt first for better Docker layer caching
COPY --chown=vscode:vscode requirements.txt /tmp/requirements.txt

# Install Python packages with mount cache for pip
RUN --mount=type=cache,target=/home/vscode/.cache/pip,uid=1000,gid=1000 \
    . $VIRTUAL_ENV/bin/activate && \
    /usr/local/bin/python3.12 -m pip install --upgrade pip setuptools wheel && \
    pip install --compile -r /tmp/requirements.txt && \
    pip install --compile pytest pytest-cov coverage ipykernel && \
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

# Remove any existing Python installations to ensure clean Python 3.12 only environment
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

# Copy the virtual environment from builder stage
COPY --from=builder --chown=vscode:vscode ${VIRTUAL_ENV_PATH} ${VIRTUAL_ENV_PATH}

# Copy pip version info from builder
COPY --from=builder /tmp/pip-version.txt /tmp/pip-version.txt

# Switch to vscode user for all remaining operations
USER vscode

# Create virtual environment with Python 3.12 explicitly
RUN /usr/local/bin/python3.12 -m venv ${VIRTUAL_ENV_PATH} --copies && \
    # Verify virtual environment was created correctly
    ls -la ${VIRTUAL_ENV_PATH} && \
    ls -la ${VIRTUAL_ENV_PATH}/bin/ && \
    # Activate virtual environment and verify Python version
    . ${VIRTUAL_ENV_PATH}/bin/activate && \
    python --version && \
    which python && \
    # Ensure pip is up to date in virtual environment
    python -m pip install --upgrade pip setuptools wheel && \
    pip --version

# Configure shell environment with optimizations
RUN echo "# Virtual environment auto-activation" >> ~/.bashrc && \
    echo "export VIRTUAL_ENV=${VIRTUAL_ENV_PATH}" >> ~/.bashrc && \
    echo "export PATH=\"\${VIRTUAL_ENV}/bin:\$PATH\"" >> ~/.bashrc && \
    echo "source \${VIRTUAL_ENV}/bin/activate" >> ~/.bashrc && \
    echo "# Virtual environment auto-activation" >> ~/.zshrc && \
    echo "export VIRTUAL_ENV=${VIRTUAL_ENV_PATH}" >> ~/.zshrc && \
    echo "export PATH=\"\${VIRTUAL_ENV}/bin:\$PATH\"" >> ~/.zshrc && \
    echo "source \${VIRTUAL_ENV}/bin/activate" >> ~/.zshrc && \
    # Create helpful aliases and functions
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
    CMD . ${VIRTUAL_ENV_PATH}/bin/activate && python -c "import sys, pip; print(f'Python {sys.version}'); print(f'Pip {pip.__version__}'); import requests, jwt; print('Core packages OK')" || exit 1

# Add labels for better maintainability
LABEL maintainer="APIM Samples Team" \
      description="Optimized dev container for Azure API Management samples" \
      version="1.0" \
      python.version="3.12" \
      debian.version="bookworm"
