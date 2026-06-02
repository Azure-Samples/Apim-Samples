# Simple API Management Infrastructure

This architecture provides a basic API gateway using Azure API Management, suitable for simple scenarios where secure API exposure and basic observability are required.

<img src="../../assets/diagrams/Simple API Management Architecture.svg" alt="Diagram showing a simple Azure API Management architecture. API Management acts as a gateway for API consumers. Telemetry is sent to Azure Monitor." title="Simple API Management Architecture" width="800" />

> Diagram created with the [Azure Draw.io MCP Server](https://github.com/simonkurtz-MSFT/drawio-mcp-server).

## 🎯 Objectives

1. Provide the simplest Azure API Management infrastructure with a public ingress to allow for easy testing
1. Enable observability by sending telemetry to Azure Monitor
1. Reveal the selected backend URL in the `X-Backend-URL` response header for learning and testing

## ⚙️ Configuration

Adjust the `user-defined parameters` in this lab's Jupyter Notebook's [Initialize notebook variables][init-notebook-variables] section.

The infrastructure enables `revealBackendApiInfo` by default so samples can show routing decisions. Disable it for production-like environments because `X-Backend-URL` exposes internal backend information to callers.

## ▶️ Execution

👟 **Expected *Run All* runtime: ~3 minutes**

1. Execute this lab's [Jupyter Notebook][infra-notebook] step-by-step or via *Run All*.

[infra-notebook]: ./create.ipynb
[init-notebook-variables]: ./create.ipynb#initialize-notebook-variables
