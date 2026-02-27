# 🔐 Samples: Secure Blob Access via API Management

This sample demonstrates implementing the **valet key pattern** with Azure API Management (APIM) to provide direct, secure, time-limited access to blob storage using **User Delegation SAS** tokens. Shared key access is disabled on the storage account entirely. While APIM provides the SAS token, it is deliberately not the conduit for downloading the actual blob.

⚙️ **Supported infrastructures**: All infrastructures

👟 **Expected *Run All* runtime (excl. infrastructure prerequisite): ~3 minutes**

## 🎯 Objectives

1. Learn how the [valet key pattern][valet-key-pattern] works.
1. Understand how APIM generates a User Delegation SAS token for direct download from storage.
1. Experience how you can secure the caller from APIM with your own mechanisms and use APIM's managed identity to interact with Azure Storage.
1. Learn why User Delegation SAS is preferred over account-key SAS for security.

## 📝 Scenario

This sample demonstrates how a Human Resources (HR) application or user can securely gain access to an HR file. The authentication and authorization between the application or the user is with APIM. Once verified, APIM then uses its own managed identity to verify the blob exists, obtains a user delegation key from Azure Storage, and creates a User Delegation SAS token for direct, secure, time-limited access to the blob. This token is then combined with the URL to the blob before it is returned to the API caller. Once received, the caller can then _directly_ access the blob on storage. 

This is an implementation of the valet key pattern, which ensures that APIM is not used as the download (or upload) conduit of the blob, which could potentially be quite large. Instead, APIM is used very appropriately for facilitating means of secure access to the resource only. 

This sample builds upon knowledge gained from the _AuthX_ and _AuthX-Pro_ samples. 

## 🛩️ Lab Components

This lab sets up:
- A simple Azure Storage account with LRS redundancy and shared key access disabled
- A blob container with a sample text file
- APIM managed identity with Storage Blob Data Reader and Storage Blob Delegator permissions
- An API that generates User Delegation SAS tokens for secure blob access URLs using the valet key pattern
- Sample files: a text file for testing



[valet-key-pattern]: https://learn.microsoft.com/azure/architecture/patterns/valet-key
