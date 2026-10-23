# API Management & Container Apps Infrastructure

This architecture routes API traffic through Azure API Management to two HTTPS-accessible [MockAPI](https://github.com/simonkurtz-MSFT/MockAPI) backends in Azure Container Apps. Authenticated dashboards let you edit backend endpoints. A dedicated VNet and private Blob endpoint protect persistent configuration, while Azure Monitor receives telemetry for observability.

![Diagram showing Azure API Management and Container Apps architecture. API Management routes traffic to Container Apps. Telemetry is sent to Azure Monitor.](../../assets/diagrams/API%20Management%20%26%20Container%20Apps%20Architecture.svg "API Management & Container Apps Architecture")

> Diagram created with the [Azure Draw.io MCP Server](https://github.com/simonkurtz-MSFT/drawio-mcp-server).

The diagram shows request routing and telemetry. The private Blob storage connection used for MockAPI persistence is described below.

## 🎯 Objectives

1. Provide a secure API gateway using Azure API Management
1. Integrate API Management with editable, persistent MockAPI backend services in Azure Container Apps
1. Enable observability by sending telemetry to Azure Monitor

## ⚙️ Configuration

Adjust the `user-defined parameters` in this lab's Jupyter Notebook's [Initialize notebook variables][init-notebook-variables] section.

### MockAPI backends

Explore the [MockAPI website](https://mockapi.simondoescloud.com) for product information and documentation.

The two generic backends use [MockAPI](https://mockapi.simondoescloud.com), pinned by image digest. Backend IDs and APIM paths (`/aca-1`, `/aca-2`, and `/aca-pool`) are preserved. The deployment helper seeds `GET /hello` and the APIM policy rewrites requests to that exact path. Responses include `X-Mock-Backend: 1` or `2`.

MockAPI images are exempt from the eight-day dependency waiting period and can be used immediately after release. The exact version tag and immutable image digest remain pinned.

#### Credentials and access

The final infrastructure summary prints **MockAPI Dashboard 1** and **MockAPI Dashboard 2**, linking to each Container App's HTTPS root with `?tutorial=skip` so the introductory tutorial does not open automatically. Users can still start it from the dashboard's Help menu. The plain HTTPS origins remain available in the `mockApiDashboardUrls` deployment output for all four ACA-capable infrastructures, without the query parameter so management API setup can reuse them; optional deployments with ACA disabled return an empty list. Private-ingress dashboards still require network access to the Container Apps environment.

- Dashboard username: `admin`.
- Dashboard password: a cryptographically random, URL-safe **16-character** password. MockAPI receives its PBKDF2-SHA256 hash, not the plaintext password.
- Invocation key: an independently generated **256-bit** secret, encoded as 43 URL-safe characters.
- Both backends share the generated credentials. The deployment helper reuses them on subsequent runs, including recovery when only one backend exists.
- APIM stores the key in the secret Named Value `mockapi-key` and injects `X-MockAPI-Key` through backend credentials. APIM callers continue using their APIM subscription key; they do not need the MockAPI key. Caller-supplied `X-MockAPI-Key` headers are removed.
- Direct Container App requests to `/hello` require `X-MockAPI-Key`. The dashboard at `/` uses the username and password instead. Health probes are unauthenticated. Access remains subject to the architecture's existing network restrictions.

The successful infrastructure summary prints **MockAPI Username** (`admin`) and **MockAPI Password** once for both dashboards, using the generated or recovered password. This applies to all four ACA-capable infrastructures when dashboards are deployed. A warning reminds users to clear notebook output before saving or sharing it. API keys and password hashes are not printed, and credentials are not returned as deployment outputs.

To recover credentials later, open either Container App's **Secrets** page in the Azure portal. The secret names are `dashboard-password`, `dashboard-password-hash`, and `mock-api-key`. The recoverable password is stored as a Container Apps secret, not passed into the container environment. Secret-bearing local parameter files are temporary and removed after success or failure.

The deployment-supplied key is a **bootstrap value**, not an automatic rotation mechanism. Existing security blobs take precedence. Do not rotate keys independently in the two dashboards, disable enforcement, or change only one deployment secret: coordinate persisted security, both Container Apps, and the APIM Named Value. If both apps lose their recoverable secrets while storage remains, deployment stops rather than generating incompatible credentials. Restore the original secrets or explicitly reset the lab's retained state.

#### Persistence and reruns

One storage account contains private blobs under `mockapi-config`, using a user-assigned managed identity. Each backend has its own configuration and security document. Shared-key authorization and anonymous blob access are disabled.

**APIM-ACA uses private storage connectivity.** A dedicated VNet contains the Container Apps subnet and a separate Blob private endpoint subnet. A linked private DNS zone resolves the storage hostname to its private IP. Storage public network access stays `Disabled`, including when organizational Azure Policy enforces that setting. Container App ingress remains HTTPS-accessible so APIM and authenticated dashboard users can reach it without a VPN.

After the revisions become healthy, the helper creates a missing `GET /hello` from the [Hello World fixture](../../shared/mockapi/hello-world.json) through each authenticated dashboard's management API. The app persists the endpoint over its private Blob connection; the developer's machine does not need direct storage access. Existing `/hello` edits and unrelated endpoints are preserved. ETag preconditions protect concurrent dashboard edits. No restart is required for this path.

When upgrading a previous non-VNet APIM-ACA deployment, the template creates a new `cae-<suffix>-private` environment and `ca-<suffix>-mockapi-1/2` apps alongside the old environment. Credentials are recovered from either generation and must agree. This avoids deleting the only recoverable credentials before migration succeeds. Once startup and the sample have been verified, remove the old `ca-<suffix>-mockwebapi-1/2` apps, the obsolete `ca-<suffix>-webapi429` app if present, and the old `cae-<suffix>` environment. Do not delete the shared MockAPI storage account or identity.

The other ACA-capable infrastructures retain their existing storage upload path and Container App names. Their authenticated public Blob endpoint must be reachable by both the uploader and runtime. If Azure Policy disables it, provide private connectivity rather than bypassing the policy. The helper checks public-network access before Blob retries and prints Azure CLI errors for failed inspections and uploads rather than reporting every failure as a missing role.

Each app uses one replica to avoid presenting process-local counters as shared state. This is a learning setup, not a highly available production service. The Simple APIM infrastructure and optional deployments with ACA disabled are unchanged. The Load Balancing sample reuses these MockAPI instances for its throttling and recovery scenarios instead of deploying a separate backend image.

#### Permissions and cost

The deployment principal must be allowed to create role assignments, in addition to deploying resources. For example, use Contributor with an appropriately scoped Role Based Access Control Administrator assignment, or Owner. The template grants Storage Blob Data Contributor on the configuration container to the runtime identity. Public-storage variants also grant it to the deployment principal for local configuration uploads; private-storage APIM-ACA seeds through the authenticated dashboard instead.

The additional Standard LRS storage account adds storage and transaction charges. APIM-ACA also incurs private endpoint and private DNS charges. Two always-on replicas can cost more than a scale-to-zero configuration. Side-by-side upgrades temporarily retain the legacy apps until verification. Use the infrastructure's clean-up notebook to remove the lab resources when finished.

## ▶️ Execution

👟 **Expected *Run All* runtime: ~5 minutes**

1. Execute this lab's [Jupyter Notebook][infra-notebook] step-by-step or via _Run All_.

[init-notebook-variables]: ./create.ipynb#initialize-notebook-variables
[infra-notebook]: ./create.ipynb
