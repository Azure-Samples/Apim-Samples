# AG_APIM_VNET

Azure Application Gateway in front of API Management (APIM) with APIM in External VNet mode using Developer SKU. The Application Gateway uses HTTPS-only listeners with a self-signed certificate for development and testing. NSGs restrict APIM subnet to ingress only from the App Gateway subnet.

- VNet with subnets: snet-appgw (dedicated), snet-apim (delegated)
- App Gateway Standard_v2 on port 443 (HTTPS) -> APIM HTTPS backend
- APIM Developer tier with public access enabled (External VNet)
- Key Vault for certificate storage with managed identity access
- Basic policy fragments and Hello World API supported via shared modules

Deploy using the shared Python script or notebooks in this folder.

## HTTPS Configuration

The Application Gateway is configured with HTTPS-only listeners (port 443) using a self-signed certificate for development and testing purposes.

### Certificate Management

- **Creation**: A self-signed certificate is automatically created during deployment using a deployment script
- **Storage**: The certificate is stored in Azure Key Vault
- **Access**: The Application Gateway User-Assigned Managed Identity has permissions to access the certificate

### Local Trust Setup

After deployment, install the certificate in your local trusted root store to eliminate SSL warnings when testing HTTPS endpoints.

The system uses a **Root Certificate Authority (CA)** approach for better security and easier management:
- **One-time setup**: Install the APIM Samples Root CA once per machine
- **Automatic trust**: All future infrastructure certificates are automatically trusted
- **Better security**: Proper certificate hierarchy instead of individual self-signed certificates
- **Easy management**: Remove all certificates at once if needed

#### Certificate Installation Options

**Option 1: Jupyter Notebook (Recommended)**
Use the certificate installation cell in the `create.ipynb` notebook for an integrated experience.

**Option 2: Python Module (Cross-Platform)**
Run this from the Python REPL:
```python
from certificate_installer import install_certificate_for_infrastructure
from apimtypes import INFRASTRUCTURE

install_certificate_for_infrastructure(INFRASTRUCTURE.AG_APIM_VNET, index, resource_group_name)
```

#### OpenSSL Prerequisites

The certificate system requires OpenSSL for Root CA management. If OpenSSL is not installed on your system, you can install it using:

**Windows:**
```powershell
# Option 1: Light version (recommended for most users)
winget install --id ShiningLight.OpenSSL.Light

# Option 2: Development version (includes additional tools)
winget install --id ShiningLight.OpenSSL.Dev

# Option 3: Alternative provider
winget install --id FireDaemon.OpenSSL

# Option 4: Chocolatey
choco install openssl

# Option 5: Scoop
scoop install openssl
```

**⚠️ Important - Add OpenSSL to PATH:**
After installation, you may need to add OpenSSL to your PATH environment variable:

*Option A - GUI Method:*
1. Open System Properties → Advanced → Environment Variables
2. Under 'User variables', select 'PATH' and click 'Edit'
3. Click 'New' and add: `C:\Program Files\OpenSSL-Win64\bin`
4. Click 'OK' to save
5. Restart your terminal/notebook

*Option B - PowerShell Method (run as user):*
```powershell
$env:PATH += ";C:\Program Files\OpenSSL-Win64\bin"
[Environment]::SetEnvironmentVariable("PATH", $env:PATH, [EnvironmentVariableTarget]::User)
```

**macOS:**
```bash
# Homebrew (recommended)
brew install openssl
```

**Linux:**
```bash
# Ubuntu/Debian
sudo apt-get install openssl

# RHEL/CentOS/Fedora
sudo yum install openssl

# Arch Linux
sudo pacman -S openssl
```

**After Installation:**
- Restart your terminal/notebook
- If OpenSSL is not in PATH, you may need to add the installation directory to your PATH environment variable
  - Windows: `C:\Program Files\OpenSSL-Win64\bin`
  - macOS/Linux: Usually installed to system PATH automatically

**Fallback Option:**
If you prefer not to install OpenSSL, the system will automatically fall back to individual certificate installation (less convenient but functional).

**Note**: For production environments, replace the self-signed certificate with a certificate from a trusted Certificate Authority.
