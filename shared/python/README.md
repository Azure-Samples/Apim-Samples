# Shared Python Modules

This directory contains shared Python modules used across the APIM-Samples repository.

## Certificate Installer Module

The `certificate_installer.py` module provides cross-platform functionality for downloading and installing self-signed certificates from Azure Key Vault into the local machine's trusted root certificate store.

### Features

- **Cross-platform support**: Works on Windows, macOS, and Linux
- **Certificate grouping/tagging**: Organizes certificates by infrastructure type and index
- **Automated installation**: Downloads from Key Vault and installs to appropriate trust store
- **Management utilities**: List and remove installed certificates

### Usage

#### Install a Certificate

```python
from certificate_installer import install_certificate_for_infrastructure
from apimtypes import INFRASTRUCTURE

# Install certificate for AG-APIM-PE infrastructure (index 1)
success = install_certificate_for_infrastructure(
    INFRASTRUCTURE.AG_APIM_PE, 
    1,
    "my-resource-group-name"  # Optional - auto-detected if not provided
)
```

#### List Installed Certificates

```python
from certificate_installer import list_installed_certificates

list_installed_certificates()
```

#### Remove All APIM Certificates

```python
from certificate_installer import remove_all_apim_certificates

success = remove_all_apim_certificates()
```

### Platform-Specific Behavior

#### Windows
- Uses `certutil` to install certificates to the Current User's Trusted Root store
- Certificates are tagged with the APIM-Samples prefix for easy identification

#### macOS
- Uses `security` command to install certificates to the system keychain
- Requires `sudo` privileges for system-wide trust
- Uses OpenSSL to extract certificates from PFX format

#### Linux
- Saves certificates to `~/.local/share/ca-certificates/apim-samples/`
- Provides instructions for system-wide installation using `update-ca-certificates`
- Uses OpenSSL for certificate extraction

### Certificate Naming Convention

Certificates are named using the following pattern:
- Display Name: `APIM-Samples - {INFRASTRUCTURE_TYPE} - Index {INDEX}`
- File Name (Linux): `{infrastructure-type}-{index}.crt`

### Requirements

- Python 3.8+
- Azure CLI (`az`) installed and authenticated
- OpenSSL (for macOS and Linux certificate extraction)
- Platform-specific tools:
  - Windows: `certutil` (built-in)
  - macOS: `security` command (built-in)
  - Linux: `openssl` (usually pre-installed)

### Integration

This module is integrated into:
- Jupyter notebooks for certificate installation cells
- Infrastructure creation and cleanup utilities
- Cross-platform Python scripts for certificate management

### Security Considerations

- Certificates are only installed for the current user (except on macOS where system keychain is used)
- Self-signed certificates are only suitable for development and testing
- Production environments should use certificates from trusted CAs
- Certificates can be easily removed using the provided utilities
