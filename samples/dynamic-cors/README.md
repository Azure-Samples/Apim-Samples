# Samples: Dynamic CORS

Implement dynamic, per-API CORS origin validation in Azure API Management using custom policy fragments instead of the built-in `<cors>` policy. The built-in policy requires a static list of allowed origins at deployment time; this sample shows how to evaluate origins dynamically at runtime with a maintainable mapping of API ID to allowed origins.

⚙️ **Supported infrastructures**: All infrastructures

👟 **Expected *Run All* runtime (excl. infrastructure prerequisite): ~5 minutes**

## 🎯 Objectives

1. Understand why the built-in APIM `<cors>` policy cannot support fully dynamic origin validation and how to replace it with custom policy fragments.
1. Build a reusable policy fragment that evaluates the `Origin` header against a per-API allowed-origins mapping, handling both OPTIONS preflight and actual request CORS headers.
1. Compare two mapping strategies side-by-side: **hard-coded** (Phase 1) and **Named Values** (Phase 2), understanding the trade-offs of each.
1. Verify CORS behaviour with automated tests covering allowed origins, disallowed origins, and missing `Origin` headers.

## 📝 Scenario

Your organisation exposes multiple APIs through APIM. Different APIs serve different frontends:

| API | Allowed Origins | Rationale |
| --- | --------------- | --------- |
| **Products** | `https://shop.contoso.com`, `https://admin.contoso.com` | Only the shop and admin portals may call this API. |
| **Analytics** | `https://dashboard.contoso.com` | Only the analytics dashboard may call this API. |

You need a single, reusable CORS mechanism that can be applied to any API while keeping the per-API origin configuration easy to maintain.

## 🛩️ Lab Components

This lab deploys all phases **side-by-side** so you can inspect and compare them without redeployment:

- **Six mock APIs** (two per phase) with no backends. Each API includes a GET operation returning a JSON response indicating whether CORS was allowed and an OPTIONS operation for preflight handling.
  - **Baseline** (`cors-bl-products`, `cors-bl-analytics`) - native APIM `<cors>` policy with static origins.
  - **Phase 1** (`cors-ph1-products`, `cors-ph1-analytics`) - `DynamicCorsHardcoded` policy fragment.
  - **Phase 2** (`cors-ph2-products`, `cors-ph2-analytics`) - `DynamicCorsNamedValues` policy fragment.
- **Two APIM policy fragments** demonstrating different origin-mapping strategies:
  - `DynamicCorsHardcoded` - origins embedded in a C# `switch` expression.
  - `DynamicCorsNamedValues` - origins read from an APIM Named Value as JSON.
- **One Named Value** (`CorsOriginMapping`) holding the JSON origin mapping for Phase 2.
- An **API-level policy** (`cors-api-policy.xml`) that includes the active CORS fragment in `<inbound>` and documents the outbound pattern for APIs with real backends.

### Progression

| Phase | Policy | Mapping location | Trade-offs |
| ----- | ------ | ---------------- | ---------- |
| **Baseline** | Native `<cors>` | Static XML attribute list | Same origins for all APIs; cannot vary per API |
| **Phase 1** | `DynamicCorsHardcoded` fragment | Inline `switch/case` in C# | Per-API control; requires redeploying the fragment to change origins |
| **Phase 2** | `DynamicCorsNamedValues` fragment | JSON string in a Named Value | Updateable in the portal; **4,096-char limit** per Named Value |

> **Phase 3 (future):** A cache-backed approach using APIM's internal cache or Azure Cache for Redis could support arbitrarily large origin registries. The fragment architecture is designed to accommodate this extension.

## ⚙️ Configuration

1. Decide which of the [Infrastructure Architectures](../../README.md#infrastructure-architectures) you wish to use.
    1. If the infrastructure *does not* yet exist, navigate to the desired [infrastructure](../../infrastructure/) folder and follow its README.md.
    1. If the infrastructure *does* exist, adjust the `user-defined parameters` in the *Initialize notebook variables* below. Please ensure that all parameters match your infrastructure.

## 🔗 Additional Resources

- [APIM CORS policy reference](https://learn.microsoft.com/azure/api-management/cors-policy)
- [APIM policy fragments](https://learn.microsoft.com/azure/api-management/policy-fragments)
- [APIM Named Values](https://learn.microsoft.com/azure/api-management/api-management-howto-properties)
- [APIM policy expressions](https://learn.microsoft.com/azure/api-management/api-management-policy-expressions)
- [MDN CORS documentation](https://developer.mozilla.org/docs/Web/HTTP/CORS)
