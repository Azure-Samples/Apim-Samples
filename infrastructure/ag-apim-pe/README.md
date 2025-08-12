# AG_APIM_PE

Azure Application Gateway in front of API Management (APIM) using Private Endpoint with HTTPS-only configuration. The Application Gateway uses a self-signed certificate for development and testing purposes.

- VNet with subnets: snet-appgw (dedicated), snet-pe (Private Endpoint)
- Private DNS zone: privatelink.azure-api.net with VNet link and PE DNS zone group
- App Gateway Standard_v2 on port 443 (HTTPS) -> APIM Private Link HTTPS backend
- APIM Developer tier (default)
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

After deployment, install the self-signed certificate in your local trusted root store to eliminate SSL warnings when testing HTTPS endpoints.

**Option 1: Python Module (Cross-Platform - Recommended)**
Run this from the Jupyter notebook cell or use the Python REPL:
```python
from utils import install_certificate_for_infrastructure
from apimtypes import INFRASTRUCTURE

install_certificate_for_infrastructure(INFRASTRUCTURE.AG_APIM_PE, 1)
```

**Option 2: Jupyter Notebook**
Use the certificate installation cell in the `create.ipynb` notebook for an integrated experience.

**Note**: For production environments, replace the self-signed certificate with a certificate from a trusted Certificate Authority.
