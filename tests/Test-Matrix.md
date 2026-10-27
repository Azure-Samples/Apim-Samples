# APIM Samples Test Matrix

**Date / time**: __________________

## MockAPI verification

For each Container Apps-enabled infrastructure, verify the following in addition to the matrix runs:

- `/aca-1`, `/aca-2`, and `/aca-pool` still succeed using APIM subscription keys and reach the seeded MockAPI `/hello` endpoint.
- Both printed dashboard links open with the generated credentials from a network that can reach the Container Apps ingress.
- Direct `/hello` calls require `X-MockAPI-Key`; dashboard sign-in uses separate credentials.
- Configuration survives a Container App restart, and redeployment preserves existing `/hello` edits and unrelated endpoints.
- The Load Balancing sample reuses the two infrastructure instances without creating another container, where supported.
- Notebook outputs are cleared before saving or sharing credentials.

Simple API Management and optional deployments with Container Apps disabled do not deploy MockAPI. See the [operations guide](../infrastructure/apim-aca/README.md#mockapi-backends) for storage connectivity and migration checks.

## Execution matrix

| Sample / Infrastructure       | SIMPLE APIM                | APIM ACA                   | AFD APIM PE                | App Gateway APIM ACA       | App Gateway APIM PE        |
| :---------------------------- | -------------------------- | -------------------------- | -------------------------- | -------------------------- | -------------------------- |
| **INFRASTRUCTURE**            | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container |
| **AuthX**                     | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container |
| **AuthX Pro**                 | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container |
| **Azure Maps**                | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container |
| **Azure OpenAI v1 Migration** | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container |
| **Costing**                   | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container |
| **Dynamic CORS**              | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container |
| **Egress Control**            | **N/A**                    | **N/A**                    | **N/A**                    | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container |
| **General**                   | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container |
| **Inference Failover**        | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container |
| **Load Balancing**            | **N/A**                    | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | **N/A**                    | **N/A**                    |
| **OAuth 3rd-Party**           | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container |
| **Secure Blob Access**        | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container |
| **INFRASTRUCTURE clean-up**   | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container | ▢ Local<br>▢ Dev Container |
