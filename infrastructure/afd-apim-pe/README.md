# Front Door & API Management & Container Apps Infrastructure

Secure architecture that takes all traffic off the public Internet once Azure Front Door is traversed. Traffic behind the Front Door is subsequently inaccessible to the public. This is due to Front Door's use of a private link to Azure API Management.

<img src="./Azure Front Door, API Management & Container Apps Architecture.svg" alt="Diagram showing Azure Front Door, API Management, and Container Apps architecture. Azure Front Door routes traffic to API Management, which then routes to Container Apps. Telemetry is sent to Azure Monitor." title="Azure Front Door, API Management & Container Apps Architecture" width="1000" />

## 🎯 Objectives

1. Provide a secure pathway to API Management via a private link from Front Door
1. Maintain private networking by integrating API Management with a VNet to communicate with Azure Container Apps. (This can also be achieved via a private link there)
1. Empower users to use Azure Container Apps, if desired
1. Enable observability by sending telemetry to Azure Monitor

## ⚙️ Configuration

Adjust the `user-defined parameters` in this lab's Jupyter Notebook's [Initialize notebook variables][init-notebook-variables] section.

## ▶️ Execution

👟 **Expected *Run All* runtime: ~13 minutes**

1. Execute this lab's [Jupyter Notebook][infra-notebook] step-by-step or via _Run All_.



[init-notebook-variables]: ./create.ipynb#initialize-notebook-variables
[infra-notebook]: ./create.ipynb
