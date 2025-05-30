# API Management & Container Apps Infrastructure

This architecture secures API traffic by routing requests through Azure API Management, which is integrated with Azure Container Apps for backend processing. Telemetry is sent to Azure Monitor for observability.

<img src="./API Management & Container Apps Architecture.svg" alt="Diagram showing Azure API Management and Container Apps architecture. API Management routes traffic to Container Apps. Telemetry is sent to Azure Monitor." title="API Management & Container Apps Architecture" width="800" />

## 🎯 Objectives

1. Provide a secure API gateway using Azure API Management
1. Integrate API Management with Azure Container Apps for backend services
1. Enable observability by sending telemetry to Azure Monitor

## ⚙️ Configuration

Adjust the `user-defined parameters` in this lab's Jupyter Notebook's [Initialize notebook variables](./create.ipynb#initialize-notebook-variables) section.

## ▶️ Execution

1. Execute this lab's [Jupyter Notebook](./create.ipynb) step-by-step or via _Run All_.