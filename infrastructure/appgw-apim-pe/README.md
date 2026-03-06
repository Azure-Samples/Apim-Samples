# Application Gateway & API Management & Container Apps Infrastructure

Secure architecture that takes all traffic off the public Internet once Azure Application (App) Gateway is traversed. Traffic behind App Gateway is subsequently inaccessible to the public. This is due to App Gateway's use of Private Link to Azure API Management.

<img src="../../assets/diagrams/Azure Application Gateway, API Management & Container Apps Architecture.svg" alt="Diagram showing Azure Application Gateway, API Management, and Container Apps architecture. Azure Application Gateway routes traffic to API Management, which then routes to Container Apps. Telemetry is sent to Azure Monitor." title="Azure Application Gateway, API Management & Container Apps Architecture" width="1000" />

> Diagram created with the [Azure Draw.io MCP Server](https://github.com/simonkurtz-MSFT/drawio-mcp-server).

## 🎯 Objectives

1. Provide a secure pathway to API Management via Private Link from App Gateway
1. Maintain private networking by integrating API Management with a VNet to communicate with Azure Container Apps. (This can also be achieved via Private Link there)
1. Empower users to use Azure Container Apps, if desired
1. Enable observability by sending telemetry to Azure Monitor

## ⚙️ Configuration

Adjust the `user-defined parameters` in this lab's Jupyter Notebook's [Initialize notebook variables][init-notebook-variables] section.

The notebook also includes a `SYSTEM CONFIGURATION` flag named `use_strict_nsg`. It defaults to `False`.

We provide NSG deployment as an option for teams that want to explore subnet-level restrictions, but we intentionally keep it disabled by default. That keeps the sample focused on Application Gateway, private endpoints, and API Management without sliding too far toward Azure Landing Zone-style baseline networking complexity.

NSG behavior:
- `nsg-default`: Generic fallback NSG for subnets that do not have a service-specific NSG. It stays intentionally generic.
- `use_strict_nsg = False`: Service subnets get permissive service-aware NSGs: `nsg-appgw`, `nsg-apim`, and `nsg-aca`. These preserve Azure platform requirements and avoid unnecessary ingress restrictions.
- `use_strict_nsg = True`: Service subnets get strict NSGs: `nsg-appgw-strict`, `nsg-apim-strict`, and `nsg-aca-strict`. These keep required platform rules but restrict ingress so traffic follows App Gateway -> APIM -> ACA.

## ▶️ Execution

👟 **Expected *Run All* runtime: ~13 minutes**

1. Execute this lab's [Jupyter Notebook][infra-notebook] step-by-step or via _Run All_.

## 🧪 Testing

Unlike Azure Front Door, App Gateway does not presently support managed certificates. This complicates the infrastructure as it either requires the user to bring their own certificate, or a self-signed certificate needs to be generated and made available to App Gateway.

We opted for the latter as it is more conducive to generate a self-signed certificate and work with its appropriate and secure limitations. This does mean that, for the purpose of this being non-production, proof of concept infrastructure, we need to trust the self-signed cert appropriately. We do so by acknowledging and subsequently ignoring the self-signed certificate warnings and using IPs paired with `Host` header.

**Production workloads must not use this approach and, instead, be secured appropriately.**



[init-notebook-variables]: ./create.ipynb#initialize-notebook-variables
[infra-notebook]: ./create.ipynb
