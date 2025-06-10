# Use the modern Python dev container with latest Debian
FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

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
    PATH="${VIRTUAL_ENV_PATH}/bin:$PATH"

# Install system dependencies as root (better caching)
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    jq \
    tree \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Switch to vscode user for all Python operations
USER vscode

# Create virtual environment with optimized settings
RUN python3 -m venv $VIRTUAL_ENV --copies

# Copy only requirements.txt first for better Docker layer caching
COPY --chown=vscode:vscode requirements.txt /tmp/requirements.txt

# Install Python packages with optimizations
RUN set -ex && \
    . $VIRTUAL_ENV/bin/activate && \
    pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --compile -r /tmp/requirements.txt && \
    pip install --no-cache-dir --compile pytest pytest-cov coverage ipykernel && \
    python -m ipykernel install --user --name=apim-samples --display-name="APIM Samples Python" && \
    pip list --format=freeze > /tmp/installed-packages.txt && \
    rm /tmp/requirements.txt

# Configure shell environment with optimizations
RUN set -ex && \
    echo "# Virtual environment auto-activation" >> ~/.bashrc && \
    echo "export VIRTUAL_ENV=${VIRTUAL_ENV}" >> ~/.bashrc && \
    echo "export PATH=\"\${VIRTUAL_ENV}/bin:\$PATH\"" >> ~/.bashrc && \
    echo "source \${VIRTUAL_ENV}/bin/activate" >> ~/.bashrc && \
    echo "# Virtual environment auto-activation" >> ~/.zshrc && \
    echo "export VIRTUAL_ENV=${VIRTUAL_ENV}" >> ~/.zshrc && \
    echo "export PATH=\"\${VIRTUAL_ENV}/bin:\$PATH\"" >> ~/.zshrc && \
    echo "source \${VIRTUAL_ENV}/bin/activate" >> ~/.zshrc

# Create helpful aliases and functions
RUN set -ex && \
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
    CMD python -c "import sys; print(f'Python {sys.version}'); import requests, jwt; print('Core packages OK')" || exit 1

# Add labels for better maintainability
LABEL maintainer="APIM Samples Team" \
      description="Optimized dev container for Azure API Management samples" \
      version="1.0" \
      python.version="3.12" \
      debian.version="bookworm"
