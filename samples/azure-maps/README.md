# Samples: Api Management proxying calls to Azure Maps

This sample demonstrates how to use Azure API Management (APIM) to proxy calls to Azure Maps service using **three different authentication methods**. This setup allows you to manage, secure, and monitor access to Azure Maps through APIM while showcasing various authentication patterns for different use cases.

⚙️ **Supported infrastructures**: All infrastructures

👟 **Expected *Run All* runtime (excl. infrastructure prerequisite): ~2 minutes**

## 🎯 Objectives

1. **Demonstrate three Azure Maps authentication patterns:**
   - **Shared Key Authentication** - Using Azure Maps subscription keys
   - **Azure Entra ID (Managed Identity)** - Recommended approach for production scenarios
   - **SAS Token Authentication** - Dynamic token generation with fine-grained control
2. Learn path-to-operation mapping vs. generic proxy patterns in APIM
3. Understand how APIM can enable chargeback/cost allocation scenarios for Azure Maps usage
4. Show integration with both v1 and v2 Azure Maps API endpoints

## 📝 Scenario

Organizations migrating from services like Bing Maps to Azure Maps often need flexible authentication and billing models. This sample addresses common questions about:

- **Authentication flexibility**: While Azure Entra ID with Managed Identity is the recommended production approach, some scenarios require shared keys or SAS tokens
- **Cost allocation**: Using APIM subscription keys to enable chargeback models and usage tracking per department/application
- **Migration patterns**: Supporting different authentication methods during transition periods
- **API management**: Centralizing access control, rate limiting, and monitoring for Azure Maps

### Authentication Scenarios Demonstrated:

1. **🔑 Shared Key (Subscription Key)**: Direct use of Azure Maps primary/secondary keys - simpler but less granular control
2. **🛡️ Azure Entra ID (Managed Identity)**: Recommended for production - leverages Azure RBAC and eliminates key management
3. **🎫 SAS Token**: Dynamic token generation with configurable expiration, rate limits, and regional restrictions - ideal for fine-grained access control

> **Note**: In production scenarios, SAS token generation would typically be handled by a separate Azure Function or API service. This sample demonstrates in-policy generation for simplicity and educational purposes.

## 🛩️ Lab Components

This lab sets up:

- **Azure Maps Account** with Gen2 pricing tier
- **APIM Managed Identity** with roles:
  - **Azure Maps Data Reader**: Read access to Maps APIs
  - **Azure Maps Contributor**: Ability to generate SAS tokens
- **User Assigned Managed Identity (UAMI)** for SAS token principal, with:
  - **Azure Maps Data Reader**: Used as the identity for SAS token operations
- **Three API Operations** demonstrating each authentication method:
  - `/geocode` - Azure Entra ID authentication
  - `/geocode/batch/async` - Shared key authentication  
  - `/default/*` - SAS token authentication with caching

## ⚙️ Configuration

1. Decide which of the [Infrastructure Architectures][infrastructure-architectures] you wish to use.
  1. If the infrastructure _does not_ yet exist, navigate to the desired [infrastructure][infrastructure-folder] folder and follow its README.md.
  1. If the infrastructure _does_ exist, adjust the `user-defined parameters` in the _Initialize notebook variables_ below. Please ensure that all parameters match your infrastructure.



[infrastructure-architectures]: ../../README.md#infrastructure-architectures
[infrastructure-folder]: ../../infrastructure/
