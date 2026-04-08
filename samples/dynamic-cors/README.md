# Samples: Dynamic CORS

Implement dynamic, per-API CORS origin validation in Azure API Management using custom policy fragments instead of the built-in `<cors>` policy. The built-in policy requires a static list of allowed origins at deployment time; this sample shows how to evaluate origins dynamically at runtime with a maintainable mapping of API ID to allowed origins.

⚙️ **Supported infrastructures**: All infrastructures

👟 **Expected *Run All* runtime (excl. infrastructure prerequisite): ~5 minutes**

## 🎯 Objectives

1. Understand why the built-in APIM `<cors>` policy cannot support fully dynamic origin validation and how to replace it with custom policy fragments.
1. Build a reusable policy fragment that evaluates the `Origin` header against a per-API allowed-origins mapping, handling both OPTIONS preflight and actual request CORS headers.
1. Compare three mapping strategies side-by-side: **hard-coded** (Phase 1), **Named Values** (Phase 2), and **cache-backed** (Phase 3), understanding the trade-offs of each.
1. Use an admin API (`/admin/load-cache`) to populate the APIM internal cache at runtime, demonstrating the `/admin/` convention for operational endpoints.
1. Verify CORS behaviour with automated tests covering allowed origins, disallowed origins, missing `Origin` headers, and fail-closed cache behaviour.

## 📝 Scenario

Your organisation exposes multiple APIs through APIM. Different APIs serve different frontends:

| API | Allowed Origins | Rationale |
| --- | --------------- | --------- |
| **Products** | `https://shop.contoso.com`, `https://admin.contoso.com` | Only the shop and admin portals may call this API. |
| **Analytics** | `https://dashboard.contoso.com` | Only the analytics dashboard may call this API. |

You need a single, reusable CORS mechanism that can be applied to any API while keeping the per-API origin configuration easy to maintain.

## 🛩️ Lab Components

This lab deploys all phases **side-by-side** so you can inspect and compare them without redeployment:

- **Nine APIs** (two per phase plus an admin API) with no backends. Each CORS demo API includes a GET operation returning a JSON response indicating whether CORS was allowed and an OPTIONS operation for preflight handling.
  - **Baseline** (`cors-bl-products`, `cors-bl-analytics`) - native APIM `<cors>` policy with static origins.
  - **Phase 1** (`cors-ph1-products`, `cors-ph1-analytics`) - `DynamicCorsHardcoded` policy fragment.
  - **Phase 2** (`cors-ph2-products`, `cors-ph2-analytics`) - `DynamicCorsNamedValues` policy fragment.
  - **Phase 3** (`cors-ph3-products`, `cors-ph3-analytics`) - `DynamicCorsCached` policy fragment.
  - **Admin** (`cors-admin`) - `POST /load-cache/{cacheKey}` stores a value in the APIM internal cache and `POST /clear-cache/{cacheKey}` removes it (subscription required).

> [!IMPORTANT]
> **Production security:** The admin API in this sample is protected by a subscription key only. Subscription keys are shared secrets and are not a substitute for identity-based authentication. In production, you should add `validate-azure-ad-token` or `validate-jwt` to the admin API's inbound policy. See the [authX](../authX/) and [authX-pro](../authX-pro/) samples for implementation patterns. The policy XML includes a commented example of where to place the validation.

- **Three APIM policy fragments** demonstrating different origin-mapping strategies:
  - `DynamicCorsHardcoded` - origins embedded in a C# `switch` expression.
  - `DynamicCorsNamedValues` - origins read from an APIM Named Value as JSON.
  - `DynamicCorsCached` - origins read from the APIM internal cache. Returns `503` if the cache is not initialized (fail-closed).
- **One Named Value** (`CorsOriginMapping`) holding the JSON origin mapping for Phase 2.
- An **API-level policy** (`cors-api-policy.xml`) that includes the active CORS fragment in `<inbound>` and documents the outbound pattern for APIs with real backends.

### Progression

| Phase | Policy | Mapping location | Trade-offs |
| ----- | ------ | ---------------- | ---------- |
| **Baseline** | Native `<cors>` | Static XML attribute list | Same origins for all APIs; cannot vary per API |
| **Phase 1** | `DynamicCorsHardcoded` fragment | Inline `switch/case` in C# | Per-API control; requires redeploying the fragment to change origins |
| **Phase 2** | `DynamicCorsNamedValues` fragment | JSON string in a Named Value | Updateable in the portal; **4,096-char limit** per Named Value |
| **Phase 3** | `DynamicCorsCached` fragment + admin API | APIM internal cache | No size limit; updated via admin API; fail-closed when cache is empty; can swap to external Redis |

### Comparison Matrix

| Criterion                                    | Baseline | Phase 1 | Phase 2 | Phase 3 |
| -------------------------------------------- | :------: | :-----: | :-----: | :-----: |
| Per-API origin control                       |    -     |    +    |    +    |    +    |
| No fragment redeployment to change origins   |    +     |    -    |    +    |    +    |
| No size limit on origin mapping              |    +     |    +    |    -    |    +    |
| Zero additional infrastructure               |    +     |    +    |    +    |    -    |
| Update origins without Azure portal access   |   n/a    |    -    |    -    |    +    |
| Fail-closed when mapping is absent           |   n/a    |   n/a   |   n/a   |    +    |
| Observability (trace logging)                |    -     |    +    |    +    |    +    |
| Swap to external Redis without code changes  |   n/a    |   n/a   |   n/a   |    +    |
| Complexity                                   |   Low    |   Low   |   Low   |  Medium |

**Legend:** `+` = advantage, `-` = limitation, `n/a` = not applicable to this approach.

- **Baseline** is the simplest starting point but cannot differentiate origins per API.
- **Phase 1** adds per-API control with zero infrastructure overhead, ideal for a small, stable set of origins.
- **Phase 2** removes the need to redeploy fragments when origins change, but is constrained by the 4,096-character Named Value limit.
- **Phase 3** lifts all size limits, enables runtime updates via an admin API, and adopts a fail-closed posture. The trade-off is the additional admin API surface and the requirement to initialise the cache after an APIM restart or scale-out.

## ⚙️ Configuration

1. Decide which of the [Infrastructure Architectures](../../README.md#infrastructure-architectures) you wish to use.
    1. If the infrastructure *does not* yet exist, navigate to the desired [infrastructure](../../infrastructure/) folder and follow its README.md.
    1. If the infrastructure *does* exist, adjust the `user-defined parameters` in the *Initialize notebook variables* below. Please ensure that all parameters match your infrastructure.

## 🔗 Additional Resources

- [APIM CORS policy reference](https://learn.microsoft.com/azure/api-management/cors-policy)
- [APIM policy fragments](https://learn.microsoft.com/azure/api-management/policy-fragments)
- [APIM Named Values](https://learn.microsoft.com/azure/api-management/api-management-howto-properties)
- [APIM policy expressions](https://learn.microsoft.com/azure/api-management/api-management-policy-expressions)
- [APIM internal cache](https://learn.microsoft.com/azure/api-management/api-management-howto-cache)
- [APIM cache-store-value / cache-lookup-value policies](https://learn.microsoft.com/azure/api-management/cache-store-value-policy)
- [Azure Cache for Redis with APIM](https://learn.microsoft.com/azure/api-management/api-management-howto-cache-external)
- [MDN CORS documentation](https://developer.mozilla.org/docs/Web/HTTP/CORS)
