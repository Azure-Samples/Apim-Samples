# https://github.com/devcontainers/images/tree/main/src/python

# syntax=docker/dockerfile:1.4

# Use single-stage build with Python 3.12
FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

# Set build arguments for workspace virtual environment
ARG VIRTUAL_ENV_PATH=/workspaces/Apim-Samples/.venv
ARG PYTHON_VERSION=3.12

# Set environment variables for workspace virtual environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/workspaces/Apim-Samples/shared/python:/workspaces/Apim-Samples \
    VIRTUAL_ENV=${VIRTUAL_ENV_PATH} \
    PATH="${VIRTUAL_ENV_PATH}/bin:$PATH" \
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

# Switch to vscode user and set workspace as working directory
USER vscode
WORKDIR /workspaces/Apim-Samples

# Create virtual environment directly in workspace during build
RUN /usr/local/bin/python3.12 -m venv .venv --copies

# Copy requirements file and install packages
COPY --chown=vscode:vscode requirements.txt ./requirements.txt
RUN --mount=type=cache,target=/home/vscode/.cache/pip,uid=1000,gid=1000 \
    . .venv/bin/activate && \
    pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt && \
    pip install pytest pytest-cov coverage ipykernel && \
    echo "✅ Virtual environment created at /workspaces/Apim-Samples/.venv" && \
    echo "✅ Python version: $(python --version)" && \
    echo "✅ Pip version: $(pip --version)" && \
    echo "✅ Packages installed: $(pip list | wc -l)"
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

# Add health check for the virtual environment
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD . /workspaces/Apim-Samples/.venv/bin/activate && python -c "import sys, pip; print(f'Python {sys.version}'); print(f'Pip {pip.__version__}'); import requests, jwt; print('Core packages OK')" || exit 1

# Add labels for maintainability
LABEL maintainer="APIM Samples Team" \
      description="Simplified dev container for Azure API Management samples" \
      version="2.0" \
      python.version="3.12" \
      debian.version="bookworm" \
      venv.location="/workspaces/Apim-Samples/.venv"
