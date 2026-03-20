# Samples: Egress Control

Control APIM outbound internet traffic by routing it through a Network Virtual Appliance (NVA) — Azure Firewall — in a hub/spoke network topology.

⚙️ **Supported infrastructures**: appgw-apim, appgw-apim-pe

👟 **Expected *Run All* runtime (excl. infrastructure prerequisite): ~15 minutes**

> ⚠️ **Cost notice**: This sample deploys Azure Firewall (Standard SKU), which costs approximately **$1.25–$1.50 per hour** in addition to the underlying infrastructure cost. Remove the sample resources by deleting the resource group or re-deploying the infrastructure to reset the subnet when you are done.

## 🎯 Objectives

1. Understand how APIM outbound internet traffic can be forced through a Network Virtual Appliance (NVA).
1. Deploy Azure Firewall as the NVA in a dedicated hub virtual network.
1. Configure user-defined routes (UDRs) on the APIM subnet to route internet-bound traffic to the NVA.
1. Define Azure Firewall application rules that selectively allow or deny outbound connections to specific internet hosts.
1. Verify allowed and blocked internet traffic through APIM API calls.

## 📝 Scenario

Enterprise organisations typically deploy a centralised Network Virtual Appliance in a hub virtual network and require all internet-bound traffic to traverse it for security inspection, logging, and policy enforcement. APIM, when deployed in a spoke VNet, must route its outbound calls to internet-hosted backends through this NVA.

This sample demonstrates the hub/spoke pattern with:

- A **hub VNet** (`10.1.0.0/16`) hosting Azure Firewall as the NVA.
- A **spoke VNet** (the existing infrastructure VNet, `10.0.0.0/16`) hosting APIM.
- **VNet peering** connecting hub and spoke bidirectionally.
- A **route table** on the APIM subnet that redirects all internet traffic (`0.0.0.0/0`) to Azure Firewall, while keeping VNet-local traffic on its direct path.
- **Azure Firewall application rules** that permit HTTPS access to `api.weather.gov` and deny everything else.

Three APIM APIs demonstrate the routing behaviour:

| API | Backend | Expected result |
|-----|---------|-----------------|
| `egress-weather` | `https://api.weather.gov` (HTTPS) | ✅ 200 — allowed by firewall |
| `egress-blocked-http` | `http://api.weather.gov` (HTTP/port 80) | ❌ 5xx — HTTP blocked by firewall |
| `egress-blocked-host` | `https://api.accuweather.com` (HTTPS) | ❌ 5xx — host not in allow list |

## 🛩️ Lab Components

The sample deploys the following resources into the infrastructure resource group:

- **Hub VNet** (`10.1.0.0/16`) with an `AzureFirewallSubnet` (`10.1.0.0/26`).
- **Azure Firewall** (Standard SKU) with a Firewall Policy containing:
  - Application rules: allow HTTPS to `api.weather.gov`.
  - Network rules: allow APIM management-plane traffic to Azure Monitor, Storage, SQL, Azure Key Vault, and Microsoft Entra ID.
- **VNet peerings** between the hub and the infrastructure spoke VNet.
- **Route table** attached to the APIM subnet (`snet-apim`):
  - Route `0.0.0.0/0` → Azure Firewall private IP (internet traffic through NVA).
  - Route `10.0.0.0/16` → Virtual Network (VNet-local traffic bypasses the NVA).
- **Three APIM APIs** that proxy requests to internet backends to verify the firewall rules.

## ⚙️ Configuration

1. Decide which of the [Infrastructure Architectures](../../README.md#infrastructure-architectures) you wish to use.
    1. If the infrastructure _does not_ yet exist, navigate to the desired [infrastructure](../../infrastructure/) folder and follow its README.md.
    1. If the infrastructure _does_ exist, adjust the `user-defined parameters` in the _Initialize notebook variables_ cell below.
1. Adjust `apim_nsg_name` if your infrastructure was deployed with strict NSGs (`nsg-apim-strict`).

> **Supported VNet SKUs only**: APIM must be deployed with a VNet-capable SKU. For `appgw-apim-pe` (Private Link, default), use `STANDARDV2` or `PREMIUMV2`. For `appgw-apim`, use `DEVELOPER` or `PREMIUM` (VNet injection) or `STANDARDV2` or `PREMIUMV2` (VNet integration). Basic, Standard, and BasicV2 are not supported.

## 🧹 Clean Up

Use the infrastructure's `clean-up.ipynb` notebook to remove all resources including Azure Firewall, the hub VNet, and the route table.

## 🔗 Additional Resources

- [Azure Firewall documentation](https://learn.microsoft.com/azure/firewall/)
- [User-defined routes overview](https://learn.microsoft.com/azure/virtual-network/virtual-networks-udr-overview)
- [API Management in a virtual network](https://learn.microsoft.com/azure/api-management/virtual-network-concepts)
- [Hub-spoke network topology in Azure](https://learn.microsoft.com/azure/architecture/networking/architecture/hub-spoke)
- [Force-tunnel internet traffic through Azure Firewall](https://learn.microsoft.com/azure/firewall/forced-tunneling)
