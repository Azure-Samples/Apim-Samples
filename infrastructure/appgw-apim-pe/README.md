# Application Gateway & API Management & Container Apps Infrastructure

Secure architecture that takes all traffic off the public Internet once Azure Application (App) Gateway is traversed. Traffic behind the App Gateway is subsequently inaccessible to the public. This is due to App Gateways's use of a private link to Azure API Management.

<img src="./Azure Application Gateway, API Management & Container Apps Architecture.svg" alt="Diagram showing Azure Application Gateway, API Management, and Container Apps architecture. Azure Application Gateway routes traffic to API Management, which then routes to Container Apps. Telemetry is sent to Azure Monitor." title="Azure Application Gateway, API Management & Container Apps Architecture" width="1000" />

## 🎯 Objectives

1. Provide a secure pathway to API Management via a private link from App Gateway
1. Maintain private networking by integrating API Management with a VNet to communicate with Azure Container Apps. (This can also be achieved via a private link there)
1. Empower users to use Azure Container Apps, if desired
1. Enable observability by sending telemetry to Azure Monitor

## ⚙️ Configuration

Adjust the `user-defined parameters` in this lab's Jupyter Notebook's [Initialize notebook variables][init-notebook-variables] section.

## ▶️ Execution

👟 **Expected *Run All* runtime: ~13 minutes**

1. Execute this lab's [Jupyter Notebook][infra-notebook] step-by-step or via _Run All_.

## 🧪 Testing

Unlike Azure Front Door, App Gateway does not presently support managed certificates. This complicates the infrastructure as it either requires the user to bring their own certificate, or a self-signed certificate needs to be generated and made available to App Gateway.

We opted for the latter as it is more conducive to generate a self-signed certificate and work with its appropriate and secure limitations. This does mean that, for the purpose of this being non-production, proof of concept infrastructure, we need to trust the self-signed cert appropriately. We do so by acknowledging and subsequently ignoring the self-signed certificate warnings and using IPs paired with `Host` header.

**Production workloads must not use this approach and, instead, be secured appropriately.**



[init-notebook-variables]: ./create.ipynb#initialize-notebook-variables
[infra-notebook]: ./create.ipynb
