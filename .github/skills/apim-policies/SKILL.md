---
name: apim-policies
description: Guide for creating Azure API Management (APIM) XML policies. Use when users want to create, modify, or understand APIM policies including inbound/outbound processing, authentication, rate limiting, caching, transformations, and policy expressions. This skill provides policy syntax, examples, and C# policy expressions for request/response manipulation.
---

# APIM Policies

This skill provides guidance for creating Azure API Management XML policies.

## Policy Document Structure

Every APIM policy document follows this structure:

```xml
<policies>
    <inbound>
        <base />
        <!-- Policies applied to incoming requests -->
    </inbound>
    <backend>
        <base />
        <!-- Policies applied before forwarding to backend -->
    </backend>
    <outbound>
        <base />
        <!-- Policies applied to outgoing responses -->
    </outbound>
    <on-error>
        <base />
        <!-- Policies applied when errors occur -->
    </on-error>
</policies>
```

The `<base />` element inherits policies from parent scopes (Global → Product → API → Operation).

## Policy Categories Quick Reference

| Category | Common Policies | Section |
|----------|-----------------|---------|
| **Authentication** | `authentication-managed-identity`, `validate-azure-ad-token`, `validate-jwt` | inbound |
| **Rate Limiting** | `rate-limit-by-key`, `quota-by-key` | inbound |
| **Caching** | `cache-lookup`, `cache-store` | inbound/outbound |
| **Routing** | `set-backend-service`, `forward-request`, `retry` | inbound/backend |
| **Transformation** | `set-header`, `set-body`, `set-variable`, `rewrite-uri` | any |
| **Control Flow** | `choose`, `return-response`, `retry`, `wait` | any |

## Essential Policies

### Set Backend Service

Route requests to a specific backend:

```xml
<set-backend-service backend-id="my-backend" />
```

### Authentication with Managed Identity

Authenticate to Azure services using APIM's managed identity:

```xml
<authentication-managed-identity resource="https://cognitiveservices.azure.com"
    output-token-variable-name="managed-id-access-token" ignore-error="false" />
<set-header name="Authorization" exists-action="override">
    <value>@("Bearer " + (string)context.Variables["managed-id-access-token"])</value>
</set-header>
```

### Validate Azure AD Token

Validate JWT tokens from Microsoft Entra ID:

```xml
<validate-azure-ad-token tenant-id="{tenant-id}">
    <client-application-ids>
        <application-id>{client-app-id}</application-id>
    </client-application-ids>
</validate-azure-ad-token>
```

### Conditional Logic (Choose)

Apply policies based on conditions:

```xml
<choose>
    <when condition="@(context.Request.Headers.GetValueOrDefault("X-Custom","") == "value")">
        <!-- policies when condition is true -->
    </when>
    <otherwise>
        <!-- fallback policies -->
    </otherwise>
</choose>
```

### Return Custom Response

Return an immediate response without calling the backend:

```xml
<return-response>
    <set-status code="403" reason="Forbidden" />
    <set-header name="Content-Type" exists-action="override">
        <value>application/json</value>
    </set-header>
    <set-body>{"error": "Access denied"}</set-body>
</return-response>
```

### Retry Logic

Retry failed requests with conditions:

```xml
<retry count="3" interval="1" first-fast-retry="true"
    condition="@(context.Response.StatusCode == 429 || context.Response.StatusCode >= 500)">
    <forward-request buffer-request-body="true" />
</retry>
```

## Policy Expressions

Policy expressions use C# syntax within `@()` for single statements or `@{}` for multi-statement blocks.

### Common Expressions

```csharp
// Get header value
@(context.Request.Headers.GetValueOrDefault("header-name", "default"))

// Get query parameter
@(context.Request.Url.Query.GetValueOrDefault("param-name", "default"))

// Get URL path parameter
@(context.Request.MatchedParameters.GetValueOrDefault("param-name", "default"))

// Get subscription ID
@(context.Subscription.Id)

// Get client IP
@(context.Request.IpAddress)

// Read JSON body property
@(context.Request.Body.As<JObject>(preserveContent: true)["property"]?.ToString())

// Check header existence
@(context.Request.Headers.ContainsKey("header-name"))

// Get context variable
@(context.Variables.GetValueOrDefault<string>("var-name", "default"))
```

### Multi-Statement Expression

```xml
<set-variable name="result" value="@{
    string[] value;
    if (context.Request.Headers.TryGetValue("Authorization", out value))
    {
        if(value != null && value.Length > 0)
        {
            return Encoding.UTF8.GetString(Convert.FromBase64String(value[0]));
        }
    }
    return null;
}" />
```

## Reference Documentation

- **Shared policies in this repo**: `shared/apim-policies/` (reusable policy XML fragments)

## Official Documentation

- [APIM Policy Reference](https://learn.microsoft.com/azure/api-management/api-management-policies)
- [Policy Expressions](https://learn.microsoft.com/azure/api-management/api-management-policy-expressions)
- [Policy Snippets Repository](https://github.com/Azure/api-management-policy-snippets)
