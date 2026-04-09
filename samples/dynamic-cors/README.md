# Samples: Dynamic CORS

Implement dynamic, per-API CORS origin validation in Azure API Management using custom policy fragments instead of the built-in `<cors>` policy. The built-in policy requires a static list of allowed origins at deployment time and its `<origin>` elements [do not support policy expressions, Named Values, or context variables][cors-doc]. This sample shows how to evaluate origins dynamically at runtime with a maintainable mapping of API ID to allowed origins.

⚙️ **Supported infrastructures**: All infrastructures

👟 **Expected *Run All* runtime (excl. infrastructure prerequisite): ~5 minutes**

## 🎯 Objectives

1. Understand why the built-in APIM `<cors>` policy cannot support fully dynamic origin validation and how to replace it with custom policy fragments.
1. Build a reusable policy fragment that evaluates the `Origin` header against a per-API allowed-origins mapping, handling both OPTIONS preflight and actual request CORS headers.
1. Compare six mapping strategies side-by-side: **native `<cors>` policy** (Baseline), **hard-coded** (Option 1), **Named Values** (Option 2), **cache-backed** (Option 3), **per-API cache** (Option 4), and **per-API Named Values via context variables** (Option 5), understanding the trade-offs of each.
1. Use an admin API (`/admin/load-cache`) to populate the APIM internal cache at runtime, demonstrating the `/admin/` convention for operational endpoints.
1. Verify CORS behaviour with automated tests covering allowed origins, disallowed origins, missing `Origin` headers, and fail-closed cache behaviour.

## 📝 Scenario

Your organisation exposes multiple APIs through APIM. Different APIs serve different frontends:

| API           | Allowed Origins                                          | Rationale                                           |
| ------------- | -------------------------------------------------------- | --------------------------------------------------- |
| **Products**  | `https://shop.contoso.com`, `https://admin.contoso.com`  | Only the shop and admin portals may call this API.  |
| **Analytics** | `https://dashboard.contoso.com`                          | Only the analytics dashboard may call this API.     |

You need a single, reusable CORS mechanism that can be applied to any API while keeping the per-API origin configuration easy to maintain.

## 🛩️ Lab Components

This lab deploys all options **side-by-side** so you can inspect and compare them without redeployment:

- **Thirteen APIs** (two per option plus an admin API) with no backends. Each CORS demo API includes a GET operation returning a JSON response indicating whether CORS was allowed and an OPTIONS operation for preflight handling.
  - **Baseline** (`cors-bl-products`, `cors-bl-analytics`) - native APIM `<cors>` policy with static origins.
  - **Option 1** (`cors-opt1-products`, `cors-opt1-analytics`) - `DynamicCorsHardcoded` policy fragment.
  - **Option 2** (`cors-opt2-products`, `cors-opt2-analytics`) - `DynamicCorsNamedValues` policy fragment.
  - **Option 3** (`cors-opt3-products`, `cors-opt3-analytics`) - `DynamicCorsCached` policy fragment (single cache entry for all APIs).
  - **Option 4** (`cors-opt4-products`, `cors-opt4-analytics`) - `DynamicCorsCachedPerApi` policy fragment (per-API cache entries).
  - **Option 5** (`cors-opt5-products`, `cors-opt5-analytics`) - `DynamicCorsNvPerApi` policy fragment (per-API Named Values passed via context variable).
  - **Admin** (`cors-admin`) - `POST /load-cache/{cacheKey}` stores a value in the APIM internal cache and `POST /clear-cache/{cacheKey}` removes it (subscription required).

> [!IMPORTANT]
> **Production security:** The admin API in this sample is protected by a subscription key only. Subscription keys are shared secrets and are not a substitute for identity-based authentication. In production, you should add `validate-azure-ad-token` or `validate-jwt` to the admin API's inbound policy. See the [authX](../authX/) and [authX-pro](../authX-pro/) samples for implementation patterns. The policy XML includes a commented example of where to place the validation.

- **Five APIM policy fragments** (one per dynamic option) demonstrating different origin-mapping strategies:
  - `DynamicCorsHardcoded` - origins embedded in a C# `switch` expression.
  - `DynamicCorsNamedValues` - origins read from an APIM Named Value as JSON.
  - `DynamicCorsCached` - origins read from the APIM internal cache as a single JSON mapping. Returns `503` if the cache is not initialized (fail-closed).
  - `DynamicCorsCachedPerApi` - origins read from per-API cache entries (`corsOriginMapping-{apiId}`). Returns `503` if the current API's cache entry is missing (fail-closed).
  - `DynamicCorsNvPerApi` - origins passed via a context variable set by the API-level policy from a per-API Named Value. The fragment itself is environment-agnostic.
- **Three Named Values**: `CorsOriginMapping` (Option 2 JSON mapping), `CorsOrigins-cors-opt5-products` and `CorsOrigins-cors-opt5-analytics` (Option 5 per-API origin arrays).
- An **API-level policy** (`cors-api-policy.xml`) that includes the active CORS fragment in `<inbound>` and documents the outbound pattern for APIs with real backends.
- A **context-variable API-level policy** (`cors-api-policy-named-values.xml`) that sets an `allowedOriginsJson` context variable from a Named Value reference before including the Option 5 fragment.

### Options

| Option         | Policy                                            | Mapping location                     | Trade-offs                                                                                        |
| -------------- | ------------------------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------- |
| **Baseline**   | Native `<cors>`                                   | Static XML attribute list            | Same origins for all APIs; cannot vary per API                                                    |
| **Option 1**   | `DynamicCorsHardcoded` fragment                   | Inline `switch/case` in C#           | Per-API control; requires redeploying the fragment to change origins                              |
| **Option 2**   | `DynamicCorsNamedValues` fragment                 | JSON string in a Named Value         | Updateable in the portal; **4,096-char limit** per Named Value                                    |
| **Option 3**   | `DynamicCorsCached` fragment + admin API          | APIM internal cache (single entry)   | No size limit; updated via admin API; fail-closed when cache is empty; can swap to external Redis |
| **Option 4**   | `DynamicCorsCachedPerApi` fragment + admin API    | APIM internal cache (per-API entry)  | Per-API cache isolation; smaller cache reads; update one API without touching others              |
| **Option 5**   | `DynamicCorsNvPerApi` fragment                    | Per-API Named Value via context var  | Environment-agnostic fragment; no cache warm-up; origins available at deploy time                 |

### Comparison Matrix

| Criterion                                   | Baseline | Option 1 | Option 2 | Option 3 | Option 4 | Option 5 |
| ------------------------------------------- | :------: | :------: | :------: | :------: | :------: | :------: |
| Per-API origin control                      |    ❌    |    ✅    |    ✅    |    ✅    |    ✅    |    ✅    |
| No fragment redeployment to change origins  |    ✅    |    ❌    |    ✅    |    ✅    |    ✅    |    ✅    |
| No size limit on origin mapping             |    ✅    |    ✅    |    ❌    |    ✅    |    ✅    |    ❌    |
| Zero additional infrastructure              |    ✅    |    ✅    |    ✅    |    ❌    |    ❌    |    ✅    |
| Update origins via API                      |    ➖    |    ❌    |    ❌    |    ✅    |    ✅    |    ❌    |
| Fail-closed when mapping is absent          |    ➖    |    ➖    |    ➖    |    ✅    |    ✅    |    ➖    |
| Observability (trace logging)               |    ❌    |    ✅    |    ✅    |    ✅    |    ✅    |    ✅    |
| Swap to external Redis without code changes |    ➖    |    ➖    |    ➖    |    ✅    |    ✅    |    ➖    |
| Update single API without full cache reload |    ➖    |    ➖    |    ➖    |    ❌    |    ✅    |    ✅    |
| Smaller per-request cache reads             |    ➖    |    ➖    |    ➖    |    ❌    |    ✅    |    ➖    |
| Environment-agnostic fragment               |    ➖    |    ❌    |    ❌    |    ❌    |    ❌    |    ✅    |
| Origins available immediately at deploy     |    ✅    |    ✅    |    ✅    |    ❌    |    ❌    |    ✅    |
| Complexity                                  |   Low    |   Low    |   Low    |  Medium  |  Medium  |   Low    |

**Legend:** ✅ = advantage, ❌ = limitation, ➖ = not applicable to this approach.

- **Baseline** is the simplest starting point but cannot differentiate origins per API.
- **Option 1** adds per-API control with zero infrastructure overhead, ideal for a small, stable set of origins.
- **Option 2** removes the need to redeploy fragments when origins change, but is constrained by the 4,096-character Named Value limit.
- **Option 3** lifts all size limits, enables runtime updates via an admin API, and adopts a fail-closed posture. The trade-off is the additional admin API surface and the requirement to initialise the cache after an APIM restart or scale-out.
- **Option 4** builds on Option 3 by storing each API's origins in a separate cache entry (`corsOriginMapping-{apiId}`). This means each request reads only its own API's origin array (smaller payload), and updating one API's origins does not require reloading the entire mapping. The trade-off is the same as Option 3 plus the need to load each API's cache entry individually.
- **Option 5** takes a different approach: each API's policy sets a context variable (`allowedOriginsJson`) from its own Named Value (`CorsOrigins-{apiId}`) before including a shared, environment-agnostic fragment. The fragment has no knowledge of where the data comes from. This mirrors the pattern used by the [authX-pro](../authX-pro/) sample. Origins are available immediately at deployment time with no cache warm-up. The trade-off is the same 4,096-character Named Value limit as Option 2 (per API, not shared), and updating origins requires portal or CLI access.

## ⚙️ Configuration

1. Decide which of the [Infrastructure Architectures](../../README.md#infrastructure-architectures) you wish to use.
    1. If the infrastructure *does not* yet exist, navigate to the desired [infrastructure](../../infrastructure/) folder and follow its README.md.
    1. If the infrastructure *does* exist, adjust the `user-defined parameters` in the *Initialize notebook variables* below. Please ensure that all parameters match your infrastructure.

## 🔗 Additional Resources

- [APIM CORS policy reference][cors-doc]
- [APIM policy fragments](https://learn.microsoft.com/azure/api-management/policy-fragments)
- [APIM Named Values](https://learn.microsoft.com/azure/api-management/api-management-howto-properties)
- [APIM policy expressions](https://learn.microsoft.com/azure/api-management/api-management-policy-expressions)
- [APIM internal cache](https://learn.microsoft.com/azure/api-management/api-management-howto-cache)
- [APIM cache-store-value / cache-lookup-value policies](https://learn.microsoft.com/azure/api-management/cache-store-value-policy)
- [Azure Cache for Redis with APIM](https://learn.microsoft.com/azure/api-management/api-management-howto-cache-external)
- [MDN CORS documentation](https://developer.mozilla.org/docs/Web/HTTP/CORS)

[cors-doc]: https://learn.microsoft.com/azure/api-management/cors-policy
