# Simple API Management Infrastructure

This architecture provides a basic API gateway using Azure API Management, suitable for simple scenarios where secure API exposure and basic observability are required.

<img src="./Simple API Management Architecture.svg" alt="Diagram showing a simple Azure API Management architecture. API Management acts as a gateway for API consumers. Telemetry is sent to Azure Monitor." title="Simple API Management Architecture" width="800" />

## 🎯 Objectives

1. Provide the simplest Azure API Management infrastructure with a public ingress to allow for easy testing
1. Enable observability by sending telemetry to Azure Monitor

## ⚙️ Configuration

Adjust the `user-defined parameters` in this lab's Jupyter Notebook's [Initialize notebook variables][init-notebook-variables] section.

## ▶️ Execution

👟 **Expected *Run All* runtime: ~3 minutes**

1. Execute this lab's [Jupyter Notebook][infra-notebook] step-by-step or via _Run All_.



[infra-notebook]: ./create.ipynb
[init-notebook-variables]: ./create.ipynb#initialize-notebook-variables
