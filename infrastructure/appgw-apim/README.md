# Application Gateway & API Management (VNet Internal) Infrastructure

This architecture provides secure ingress through Azure Application Gateway (WAF_v2) to Azure API Management (APIM) deployed in a Virtual Network using Internal mode (private IP only). No Private Endpoints are used; traffic stays on private networking after the gateway, and APIM cannot be accessed aside from traversing Application Gateway.

<!-- TODO: Generate diagram -->
<!-- <img src="./Azure Application Gateway + APIM (Internal).svg" alt="Diagram showing Application Gateway routing to APIM in VNet Internal mode. Optional Container Apps shown behind APIM. Telemetry to Azure Monitor." title="Application Gateway + APIM (Internal)" width="1000" /> -->

## 🎯 Objectives

1. Expose APIs publicly via Application Gateway while keeping APIM private (VNet Internal)
2. Maintain private networking end-to-end without Private Endpoints
3. Enable optional backends with Azure Container Apps (ACA)
4. Provide observability via Log Analytics and Application Insights

## 💡 Why Developer SKU?

- Significant cost savings for learning, demos, and dev/test:
  - Developer is a fraction of Premium costs (often >90% cheaper)
  - No SLA and single-instance only, which is acceptable for the purpose of this repo
- Trade-offs:
  - Longer deployment times compared to v2/Premium SKUs (APIM creation can be slow)

We choose the Developer SKU here to dramatically lower costs for experimentation. If you need SLAs, scaling, or production-grade features, use Premium/Premiumv2 as those are the only SKUs that support VNet *injection*.

## ⚙️ Configuration

Adjust the user-defined parameters in this lab's Jupyter Notebook's Initialize notebook variables section.

Key parameters:
- `apimSku`: Defaults to `Developer`
- `useACA`: Enable to provision a private ACA environment and sample apps

## ▶️ Execution

1. Execute this lab's Jupyter Notebook step-by-step or via Run All.

👟 Expected Run All runtime: longer than v2 SKUs for APIM creation. We will measure and update this value after testing.

- TODO: Measure actual runtime on Developer SKU and update this section accordingly.

## 🧪 Testing

Because we use a self-signed certificate for Application Gateway TLS termination (for convenience in this sample), testing can be done with curl by ignoring certificate warnings and sending the Host header:

```
curl -v -k -H "Host: api.apim-samples.contoso.com" https://<APPGW_PUBLIC_IP>/status-0123456789abcdef
```

A 200 status from the health endpoint indicates success through App Gateway to APIM.

## 🔐 Security Notes

- Self-signed certificates are for demos only. Use managed or trusted certs for production.
- This sample uses RBAC-enabled Key Vault with minimal role assignments for App Gateway certificate retrieval.
- **Azure limitation**: APIM must be created with public access enabled initially. You can disable public access in a subsequent update if desired.
- Review and harden NSGs/WAF policy as needed for your environment.
