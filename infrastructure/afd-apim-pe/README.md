# Front Door & API Management & Container Apps Infrastructure

Secure architecture that takes all traffic off the public Internet once Azure Front Door is traversed. Traffic behind Front Door is subsequently inaccessible to the public. This is due to Front Door's use of Private Link to Azure API Management.

<img src="../../assets/diagrams/Azure Front Door, API Management & Container Apps Architecture.svg" alt="Diagram showing Azure Front Door, API Management, and Container Apps architecture. Azure Front Door routes traffic to API Management, which then routes to Container Apps. Telemetry is sent to Azure Monitor." title="Azure Front Door, API Management & Container Apps Architecture" width="1000" />

> Diagram created with the [Azure Draw.io MCP Server](https://github.com/simonkurtz-MSFT/drawio-mcp-server).

## 🎯 Objectives

1. Provide a secure pathway to API Management via Private Link from Front Door
1. Maintain private networking by integrating API Management with a VNet to communicate with Azure Container Apps. (This can also be achieved via Private Link there)
1. Empower users to use Azure Container Apps, if desired
1. Enable observability by sending telemetry to Azure Monitor

## ⚙️ Configuration

Adjust the `user-defined parameters` in this lab's Jupyter Notebook's [Initialize notebook variables][init-notebook-variables] section.

The notebook also includes a `SYSTEM CONFIGURATION` flag named `use_strict_nsg`. It defaults to `False`.

We provide NSG deployment as an option for teams that want to experiment with subnet-level controls, but we intentionally keep it disabled by default. The goal of these samples is to stay approachable and focused on APIM scenarios rather than drifting into full Azure Landing Zone-style network governance complexity.

NSG behavior:
- `nsg-default`: Generic fallback NSG for subnets that do not have a service-specific NSG. It stays intentionally generic.
- `use_strict_nsg = False`: Service subnets get permissive service-aware NSGs: `nsg-apim` and `nsg-aca`. These preserve Azure platform requirements and avoid unnecessary ingress restrictions.
- `use_strict_nsg = True`: Service subnets get strict NSGs: `nsg-apim-strict` and `nsg-aca-strict`. These keep required platform rules but restrict ingress so traffic follows Front Door -> APIM -> ACA.

## ▶️ Execution

👟 **Expected *Run All* runtime: ~13 minutes**

1. Execute this lab's [Jupyter Notebook][infra-notebook] step-by-step or via _Run All_.



[init-notebook-variables]: ./create.ipynb#initialize-notebook-variables
[infra-notebook]: ./create.ipynb
