# Azure API Management (APIM) Load Balancer Configuration

This topology assumes the following:

- Single APIM region: **East US 2**
- Model: **gpt-5-mini (2025-08-07)**
- PTUs: **300 in East US 2**

This load balancing design provides inference-backend failover. A single-region APIM deployment remains a gateway dependency, so an East US 2 APIM outage can make every backend in this pool unreachable. Use an appropriate multi-region APIM topology when gateway-region resilience is also required.

## Backend Pool

| Index | Subscription | AI Resource region | APIM backend                    | Deployment type      | Billing/capacity | Priority | Weight |
| :---: | :----------: | ------------------ | ------------------------------- | -------------------- | :--------------: | :------: | -----: |
|   1   |      1       | East US 2          | `gpt-5-mini-ptu-eastus2`        | `ProvisionedManaged` |     300 PTUs     |    1     |    100 |
|   2   |      1       | East US 2          | `gpt-5-mini-datazone-eastus2`   | `DataZoneStandard`   |       PAYG       |    2     |     25 |
|   3   |      2       | East US            | `gpt-5-mini-datazone-eastus`    | `DataZoneStandard`   |       PAYG       |    2     |     25 |
|   4   |      3       | Central US         | `gpt-5-mini-datazone-centralus` | `DataZoneStandard`   |       PAYG       |    2     |     25 |
|   5   |      4       | West US 3          | `gpt-5-mini-datazone-westus3`   | `DataZoneStandard`   |       PAYG       |    2     |     25 |
|   6   |      1       | East US 2          | `gpt-5-mini-global-eastus2`     | `GlobalStandard`     |       PAYG       |    3     |     25 |
|   7   |      2       | East US            | `gpt-5-mini-global-eastus`      | `GlobalStandard`     |       PAYG       |    3     |     25 |
|   8   |      3       | Central US         | `gpt-5-mini-global-centralus`   | `GlobalStandard`     |       PAYG       |    3     |     25 |
|   9   |      4       | West US 3          | `gpt-5-mini-global-westus3`     | `GlobalStandard`     |       PAYG       |    3     |     25 |

_Equal weights divide traffic approximately evenly among healthy backends in the same priority tier._

## Routing Strategy

The backend pool uses three priority tiers:

1. **Priority 1 - regional provisioned capacity:** Route to the 300-PTU `ProvisionedManaged` deployment in East US 2.

1. **Priority 2 - US data zone fallback:** Distribute traffic equally across the four `DataZoneStandard` deployments.

1. **Priority 3 - global fallback:** Distribute traffic equally across the four `GlobalStandard` deployments.

### Design Decisions

The priorities reflect capacity commitment and permitted processing scope, not physical distance from APIM alone:

- **Use the regional PTU deployment first.** The East US 2 `ProvisionedManaged` deployment provides reserved, predictable throughput and keeps inference processing in the same region as APIM.
- **Aggregate independently granted PAYG quota.** PAYG quota is assigned per subscription, resource region, model, and deployment type. APIM can balance across the four subscription-and-region allocations to expose the sum of quota explicitly approved and assigned to these deployments. Four subscriptions do not automatically provide four times the capacity, and multiple deployments within one quota scope do not create more quota. Tenant-level model usage tiers can also affect latency across subscriptions and regions.
- **Treat the four US data zone deployments as equal peers.** A `DataZoneStandard` resource created in East US 2 can process inference anywhere in the US data zone, so its resource location does not guarantee lower latency or East US 2 processing. Equal weights use the independently granted PAYG capacity and reduce dependence on one subscription, quota allocation, resource endpoint, or resource-location failure domain.
- **Do not give the East US 2 data zone resource its own priority without evidence.** Doing so would direct all post-PTU traffic to that one resource until its circuit breaker trips. This can be appropriate for a measured latency, cost-allocation, or subscription preference, but it does not provide regional inference locality.
- **Keep global deployments as the final tier.** `GlobalStandard` offers the broadest processing scope and additional PAYG capacity, but requests can be processed in any eligible Azure region. It therefore follows the US data zone tier when US-only processing is preferred.

> **Note: Simpler topology if quota aggregation was unnecessary:**
>
> If one subscription had enough approved PAYG quota and separate endpoint isolation is not required, the pool could be reduced from nine backends to three:
>
> 1. One East US 2 `ProvisionedManaged` backend at priority 1.
> 1. One US `DataZoneStandard` backend at priority 2.
> 1. One `GlobalStandard` backend at priority 3.
>
> The global backend can be omitted when US-only processing is mandatory, leaving a two-backend pool. Retain multiple backends in a tier when independent subscription quota, endpoint failure isolation, or operational ownership justifies the added complexity. A single `DataZoneStandard` or `GlobalStandard` deployment already uses the service's internal routing scope; multiple deployments are not required merely to reach multiple inference regions.

- **Keep the retry budget independent of pool size.** Use `2` retries as the bounded default, which permits three total attempts including the initial request. This may already be more than sufficient for interactive traffic. Do not use the number of backends minus one. The current circuit breaker trips a backend after one qualifying `408`, `429`, `499`, `500`, `502`, `503`, or `504` response, and later attempts handled by that APIM gateway avoid the unavailable backend. If the initial selection and two additional backends all fail while eligible, the request has enough evidence to stop rather than probe the full pool. The pool-specific cache in this policy stores the soonest `Retry-After` recovery time for an exhausted response; it does not select backends or replace circuit-breaker state.

> **Note: About potential retries:**
>
> Because we retry in the context of a load balancer with a backend pool (as opposed to a single backend), any failing request may trip that backend's configured circuit breaker. That backend is then immediately removed from the pool for the duration of the circuit breaker trip. APIM then immediately retries against another _healthy_ backend, if available, from the pool. **One retry represents the vast majority of retry occurrences.**
> More retries require several backends that were eligible moments earlier to fail during the same request. That condition should be uncommon and is sufficiently represented by the fixed maximum of two retries. Use observed conditional recovery by attempt and end-to-end latency to determine whether even one retry is enough.

## Availability Validation

**Availability checked:** `2026-06-12 13:32:15 UTC`

The official Microsoft Learn availability matrices list `gpt-5-mini` version `2025-08-07` as available for:

- [DataZoneStandard in East US 2, East US, Central US, and West US 3](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure-region-availability?pivots=standard#data-zone-standard).
- [GlobalStandard in East US 2, East US, Central US, and West US 3](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure-region-availability?pivots=standard#global-standard).
- [Regional ProvisionedManaged in East US 2](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure-region-availability?pivots=provisioned#regional-provisioned-managed).

The [`gpt-5-mini` model specification](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure#gpt-5) identifies version `2025-08-07`. The [deployment type comparison](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/deployment-types#deployment-type-comparison) defines the exact Azure SKU codes used in this table.

The [Azure OpenAI quota reference](https://learn.microsoft.com/azure/foundry/openai/quotas-limits#scope-of-quota) documents subscription-level quota scope and regional allocation. The [APIM backend reference](https://learn.microsoft.com/azure/api-management/backends#load-balanced-pool) defines pool priorities, relative weights, circuit breakers, and the distributed-gateway caveats. The [APIM retry policy reference](https://learn.microsoft.com/azure/api-management/retry-policy) defines retry-count and immediate-retry behavior.

**Model availability does not guarantee that PTUs are immediately allocatable in a specific subscription and region. Confirm the East US 2 provisioned quota and capacity before deployment.**
