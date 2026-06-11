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

### Readability and Semantic Layout

Keep policy XML readable as its control flow grows:

- Add concise XML comments before non-obvious policy blocks to explain their intent, especially retry classification, fallback handling, cache behavior, and error normalization. Do not narrate self-explanatory individual statements.
- Separate semantic phases with a blank line, such as initialization, routing and authentication, retry tracking, telemetry, response classification, and response rendering.
- Break long policy elements across lines and place one attribute per line when that makes conditions or configuration easier to scan. Preserve the established indentation and policy execution order.
- Keep related policies together under a clear comment instead of allowing one uninterrupted block of XML. Use comments and whitespace for structure; do not add wrapper policies that change APIM behavior solely for visual grouping.
- Format multi-statement `@{}` expressions like ordinary C# blocks, with blank lines between distinct calculations or validation phases. Keep short `@()` expressions inline when they remain easy to read.

### Backend Section Cardinality (CRITICAL)

The `<backend>` section may contain only one direct child policy. APIM rejects a policy during deployment when `<backend>` contains sibling policies such as `<retry>` followed by `<choose>`, or `<base />` followed by `<retry>`.

When retrying a backend request, make `<retry>` the sole direct child of `<backend>` and place `<forward-request>` plus any policies that must execute on every attempt inside `<retry>`. Move terminal fallback handling to `<on-error>` or `<outbound>` as appropriate.

```xml
<backend>
    <retry count="3" interval="1" first-fast-retry="true"
        condition='@(context.Response.StatusCode == 429 || context.Response.StatusCode &gt;= 500)'>
        <forward-request buffer-request-body="true" />
    </retry>
</backend>
```

When a custom backend policy is not needed, keep `<base />` as the only direct child:

```xml
<backend>
    <base />
</backend>
```

## Policy Categories Quick Reference

| Category | Common Policies | Section |
| --- | --- | --- |
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
    <when condition='@(context.Request.Headers.GetValueOrDefault("X-Custom", "") == "value")'>
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
    condition='@(context.Response.StatusCode == 429 || context.Response.StatusCode &gt;= 500)'>
    <forward-request buffer-request-body="true" />
</retry>
```

## Policy Expressions

Policy expressions use C# syntax within `@()` for single statements or `@{}` for multi-statement blocks.

### Quotes in XML Attributes

Use single quotes around XML attribute values that contain policy expressions. This allows C# string literals and dictionary keys inside the expression to use normal double quotes without XML entity encoding.

```xml
<set-variable name="callerId" value='@((string)context.Variables["callerId"])' />
```

Keep ordinary non-expression XML attributes double-quoted. If an expression itself requires a single-quoted character or string literal, encode that apostrophe as `&apos;` or use a double-quoted XML attribute and encode its inner double quotes as `&quot;`.

Expressions in element text also use normal double quotes:

```xml
<value>@((string)context.Variables["callerId"])</value>
```

### XML Entity Encoding

Policy expressions are C# embedded in XML, so XML parsing occurs before APIM evaluates the expression. In XML attribute values and element text:

- Encode `&` as `&amp;`. Logical AND must therefore be written as `&amp;&amp;`.
- Encode `<` as `&lt;`. This is required for less-than comparisons and the opening angle bracket of generic type arguments.
- Encode `>` as `&gt;` for paired angle brackets and comparisons. A literal `>` is generally valid XML, but encoding it keeps expressions consistent and avoids ambiguity.

```xml
<set-variable name="attempt" value='@(context.Variables.GetValueOrDefault&lt;int&gt;("attempt", 0))' />
<when condition='@(attempt &lt;= retryLimit &amp;&amp; statusCode &gt;= 500)'>
    <!-- policies -->
</when>
```

These entities are decoded before C# evaluation, so APIM receives `GetValueOrDefault<int>`, `<=`, `&&`, and `>=`. Code shown outside an XML context, such as a `csharp` fenced block, should use ordinary C# characters without XML entity encoding.

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
<set-variable name="result" value='@{
    string[] value;
    if (context.Request.Headers.TryGetValue("Authorization", out value))
    {
        if(value != null &amp;&amp; value.Length &gt; 0)
        {
            return Encoding.UTF8.GetString(Convert.FromBase64String(value[0]));
        }
    }
    return null;
}' />
```

### Allowed .NET Types and Members (CRITICAL)

Policy expressions may **only** reference the .NET Framework types and members on APIM's [allow-list](https://learn.microsoft.com/azure/api-management/api-management-policy-expressions#CLRTypes). Anything outside the list causes a deploy-time `ValidationError: One or more fields contain incorrect values` with no further detail, which is hard to diagnose.

Before using a type or member in a policy expression, verify it appears on the official allow-list. Common pitfalls:

- **Whole namespaces are absent.** `System.Globalization` (e.g. `DateTimeStyles`, `CultureInfo`), `System.Threading`, `System.IO` (except `StringReader`/`StringWriter`), `System.Net.Http`, `System.Reflection`, and `System.Diagnostics` are not allowed.
- **`System.DateTime` is restricted.** Allowed members include `Parse`, `UtcNow`, `Now`, `AddSeconds`, `Subtract`, `ToString`, `Ticks`. **Not allowed:** `TryParse`, `TryParseExact`, `ParseExact`, `ToUniversalTime`, `ToLocalTime`, `SpecifyKind`. For round-trip-safe time math, prefer `System.DateTimeOffset` (`All` members allowed) and `ToUnixTimeSeconds()` / `ToUnixTimeMilliseconds()`.
- **`System.Enum` is restricted to** `Parse`, `TryParse`, `ToString`. No `GetValues`, `GetNames`, `IsDefined`.
- **`System.Text.RegularExpressions.Regex` is restricted to** the constructor plus `IsMatch`, `Match`, `Matches`, `Replace`, `Unescape`, `Split`. No `CompileToAssembly`, `CacheSize`.
- **Numeric primitives are fully allowed**, so `int.TryParse`, `long.TryParse`, `double.TryParse` are safe.
- **JSON via `Newtonsoft.Json`** is the only supported JSON library — do not use `System.Text.Json`.

When a member you need is not allowed, refactor to an equivalent that is. Examples:

| Disallowed | Allowed replacement |
| --- | --- |
| `DateTime.TryParse(s, ..., DateTimeStyles.RoundtripKind, out dt)` | Store as Unix epoch via `DateTimeOffset.UtcNow.ToUnixTimeSeconds()`, parse with `long.TryParse` |
| `DateTime.ParseExact(s, fmt, CultureInfo.InvariantCulture)` | `DateTime.Parse(s)` (allowed) or epoch-based representation |
| `Enum.GetValues(typeof(T))` | Hard-code the comparison values or store as a string |
| `System.Text.Json.JsonSerializer.Deserialize<T>(s)` | `JsonConvert.DeserializeObject<T>(s)` |

If you are unsure whether a member is allowed, fetch the [allowed types table](https://learn.microsoft.com/azure/api-management/api-management-policy-expressions#CLRTypes) and confirm before writing the expression.

## Reference Documentation

- **Sample-owned policies in this repo**: `samples/<sample-name>/apim-policies/` (all XML policies specific to one sample)
- **Shared policies in this repo**: `shared/apim-policies/` (reusable policy XML fragments)

Policy-loading helpers must check the sample's `apim-policies/` directory first. During migration only, they may check the sample root second so existing root-level policies continue to work. New policy files must not use the fallback location.

## Official Documentation

- [APIM Policy Reference](https://learn.microsoft.com/azure/api-management/api-management-policies)
- [Policy Expressions](https://learn.microsoft.com/azure/api-management/api-management-policy-expressions)
- [Policy Snippets Repository](https://github.com/Azure/api-management-policy-snippets)
