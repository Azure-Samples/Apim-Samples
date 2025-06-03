# Secure Blob Access with Valet Key Pattern

This sample demonstrates how to implement the [valet key pattern](https://learn.microsoft.com/azure/architecture/patterns/valet-key) for secure blob storage access through Azure API Management (APIM). The pattern allows clients to access blob storage directly without exposing storage account keys or requiring the API to stream large files.

## 🎯 Overview

The valet key pattern provides secure, time-limited access to Azure Blob Storage through APIM-generated URLs. This approach:

- **Avoids streaming large files** through the API layer
- **Maintains security** by using managed identity and JWT authentication
- **Reduces bandwidth costs** on the API Management service
- **Provides audit trails** for file access requests

## 📝 Architecture

```
[Client] → [APIM] → [Blob Storage]
    ↓         ↓
[JWT Auth] → [Managed Identity]
```

1. Client authenticates with JWT token containing required role
2. APIM validates JWT and authorizes based on role claims
3. APIM uses managed identity to generate secure blob access URL
4. Client receives time-limited URL for direct blob access

## 🚀 Sample Files Created by Infrastructure

Unlike traditional approaches that require manual file uploads, this sample uses **Infrastructure as Code (IaC)** to automatically create sample files during deployment:

### Files Created
- **`sample.txt`** - Text file with sample content demonstrating secure access
- **`sample.json`** - JSON file with structured data for testing
- **`sample.svg`** - SVG image file for binary content testing

### Benefits of IaC-based File Creation
✅ **Consistent deployments** across environments  
✅ **No manual intervention** required  
✅ **Secure managed identity** authentication  
✅ **Files available immediately** after deployment  
✅ **No authentication issues** in notebooks or scripts  

## 🛠️ Technical Implementation

### Infrastructure Components

1. **Storage Account** - LRS redundancy with private access
2. **Blob Container** - Private container for sample files
3. **Managed Identity** - APIM service identity for blob access
4. **Role Assignment** - Storage Blob Data Reader permissions
5. **Deployment Script** - PowerShell script to create sample files

### API Configuration

- **Endpoint**: `GET /{api-prefix}secure-files/{filename}`
- **Authentication**: JWT with role-based authorization
- **Authorization**: Requires `HR_MEMBER_ROLE_ID` role
- **Template Parameters**: Filename parameter for dynamic blob access

### Security Features

- JWT token validation with role-based authorization
- Managed identity for storage access (no keys exposed)
- Time-limited secure URLs
- RBAC permissions on storage account
- Private blob container access

## 📋 Prerequisites

1. **Infrastructure**: Deploy one of the supported infrastructures:
   - Simple APIM
   - APIM + Container Apps
   - Azure Front Door + APIM + Private Endpoints

2. **Azure Permissions**: 
   - Resource group contributor access
   - Ability to create managed identities and role assignments

## 🚀 Getting Started

1. **Navigate to Infrastructure**: Choose and deploy infrastructure from `/infrastructure/` folder
2. **Update Parameters**: Modify user-defined parameters in the notebook
3. **Run Deployment**: Execute the notebook to deploy the sample
4. **Test API**: Use the provided test code to verify functionality

## 🔧 Configuration

### User-Defined Parameters
```python
rg_location = 'eastus2'              # Azure region
index = 2                            # Resource group index
deployment = INFRASTRUCTURE.SIMPLE_APIM  # Infrastructure type
api_prefix = 'blob-'                 # API prefix to avoid collisions
```

### JWT Configuration
The sample automatically generates a signing key and configures JWT validation policies with role-based authorization.

## 🧪 Testing

The notebook includes comprehensive testing scenarios:

1. **Authorized Access**: JWT with required role gets secure URL
2. **Unauthorized Access**: JWT without role receives 403 Forbidden
3. **No Authentication**: Unauthenticated requests receive 401 Unauthorized
4. **Direct Blob Access**: Test generated URLs for actual file access

## 🔐 Security Considerations

- **Managed Identity**: Uses Azure managed identity (no secrets in code)
- **Least Privilege**: RBAC permissions limited to specific storage account
- **Token Validation**: JWT tokens validated with proper signature verification
- **Role-Based Access**: Authorization based on JWT role claims
- **Time-Limited URLs**: Generated URLs have expiration times
- **Private Storage**: Blob container configured for private access only

## 📚 Related Patterns

- [Valet Key Pattern](https://learn.microsoft.com/azure/architecture/patterns/valet-key)
- [Managed Identity for Azure Resources](https://learn.microsoft.com/azure/active-directory/managed-identities-azure-resources/)
- [Azure RBAC](https://learn.microsoft.com/azure/role-based-access-control/)

## 🔄 Next Steps

After running this sample, consider:

1. **Custom Policies**: Implement organization-specific authorization rules
2. **Monitoring**: Add Application Insights for API usage tracking
3. **Caching**: Implement caching for frequently accessed files
4. **Scale**: Configure autoscaling for high-traffic scenarios
5. **Compliance**: Add audit logging for regulatory requirements

## 📞 Support

For issues or questions:
- Review the notebook output for detailed error messages
- Check Azure portal for resource deployment status
- Verify RBAC permissions on storage account
- Ensure infrastructure prerequisites are met

---

**Note**: This sample uses deployment scripts to create files automatically. No manual upload steps are required!
