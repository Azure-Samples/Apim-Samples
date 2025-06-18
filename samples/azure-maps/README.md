# Samples: Api Management proxing calls to Azure Maps

This is a sample demonstrating how to use Azure API Management (APIM) to proxy calls to the Azure Maps service. This setup allows you to manage, secure, and monitor access to Azure Maps through APIM.

⚙️ **Supported infrastructures**: All infrastructures

👟 **Expected *Run All* runtime (excl. infrastructure prerequisite): ~[NOTEBOOK RUNTIME] minute**

## 🎯 Objectives

1. Learn how to set up APIM to proxy requests to Azure Maps on a path to operation based mapping.
1. Learn how to set up APIM to proxy requests to Azure Maps on a generic path.
1. See how to secure access to Azure Maps using APIM policies for all 3 authentication methods (subscription key, Azure Entra AD, and SAS Tokens).
1. Show how to connect to the v1 enpoint of Azure Maps using APIM.

## 📝 Scenario

This sample demonstrates how to use APIM to proxy requests to the Azure Maps service. By doing so, you can leverage APIM's capabilities to manage, secure, and monitor access to Azure Maps. This particular setup will show you how to map specific paths to Azure Maps APIs, as well as how to handle generic paths. Additionally, the sample will illustrate how to secure access to Azure Maps using different authentication methods supported by APIM policies.

## 🛩️ Lab Components

This lab sets up:

- An Azure Maps resource in Azure
- APIM managed identity with the following roles:
  - **Azure Maps Search and Render Data Reader:** Grants the ability to call the apis and render the maps
  - **Azure Maps Contributor:** Grants the ability to create the SAS Token from the APIM policy
- A User Assigned Managed Identity (UAMI) that is used as the principal id to emulate when creating the SAS Token for Azure Maps. It has the following roles asigned:
  - **Azure Maps Search and Render Data Reader:** Grants the ability to call the apis and render the maps
- An API that demonstrates proxying requests to Azure Maps specific to APIs (geocode, search, etc.)
  - Also in that api there will be an operation that demonstrates a generic path to Azure Maps

## ⚙️ Configuration

1. Decide which of the [Infrastructure Architectures](../../README.md#infrastructure-architectures) you wish to use.
    1. If the infrastructure _does not_ yet exist, navigate to the desired [infrastructure](../../infrastructure/) folder and follow its README.md.
    1. If the infrastructure _does_ exist, adjust the `user-defined parameters` in the _Initialize notebook variables_ below. Please ensure that all parameters match your infrastructure.
