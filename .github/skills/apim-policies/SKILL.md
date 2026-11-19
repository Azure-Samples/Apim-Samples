---
name: apim-policies
description: Guide for creating Azure API Management (APIM) XML policies. Use when users want to create, modify, or understand APIM policies including inbound/outbound processing, authentication, rate limiting, caching, transformations, and policy expressions. This skill provides policy syntax, examples, and C# policy expressions for request/response manipulation.
---

# APIM Policies

This skill provides guidance for creating Azure API Management XML policies.

Do not add policy tooling or package installation that bypasses the repository's eight-day release waiting period. Use the locked dependency workflow and verify release ages before running new tooling.

When this workflow creates or updates Markdown, follow `.markdownlint.json` and `.github/markdown.instructions.md` without flattening semantic structure. Before completion, run `npx --no-install markdownlint-cli2 "**/*.md" "#**/.venv/**" "#**/node_modules/**"` from the repository root and require zero violations.

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

### Policy Contract Header

Every full policy document must start with an XML comment block immediately inside `<policies>`, before `inbound` or any other policy section. Include:

- **Purpose:** Explain the scenario, policy scope and processing responsibilities.
- **Inputs:** Document required and optional request/context fields, deployment-time placeholders, Named Values and prerequisite resources or fragments.
- **Variables:** Explain relevant context variables, including those owned by included fragments: types, initial values, who sets them, and conditions under which they change or remain unset. Distinguish routing choices from telemetry labels.
- **Outputs:** Describe request/response mutations, preserved content, authentication, traces or other side effects, early-response status/error identities, and applicable forwarding timeout/retry behavior.

Use `None` when a section has no applicable entries. Keep the header specific to that policy and maintain it alongside code changes; do not include secrets or live environment identifiers. Adding comments must not change policy execution order or behavior. Fragments follow the [fragment contract header](#fragment-contract-header) format below, with typed variables documented in their inputs and outputs.

Write these headers for someone learning the sample. Explain the routing choice in plain language before listing implementation details. Separate caller-provided inputs from deployment configuration, give a short example where useful, and explain what each variable means rather than repeating its name. State when values are empty or unset and distinguish local rejections, model-service responses and APIM failures. Use blank lines between sections and avoid compressed phrases such as "local validation error identity/status".

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
    <retry count="2" interval="1" first-fast-retry="true"
        condition='@(context.Response.StatusCode == 429 || context.Response.StatusCode >= 500)'>
        <forward-request timeout="60" buffer-request-body="true" />
    </retry>
</backend>
```

When a custom backend policy is not needed, keep `<base />` as the only direct child:

```xml
<backend>
    <base />
</backend>
```

## Policy Fragment Composition

Keep each endpoint's routing choices visible in its own policy and extract only shared mechanics into fragments. A fragment must have a `<fragment>` root and must not contain policy sections, `<base />`, or another `<include-fragment>`. APIM does not support nested fragments; compose them in the endpoint policy instead. Deploy fragments before the policies that reference them.

### Fragment Contract Header

Every shared or sample-owned policy fragment must have an XML comment block immediately inside `<fragment>`, before any executable policy, with these explicit sections:

- **Purpose:** State what the fragment does and where it runs (`inbound`, `outbound`, `backend`, or `on-error`, as applicable).
- **Inputs:** List required and optional context variables with their types, request/response fields, Named Values, and deployment-time placeholders consumed by the fragment. State defaults and prerequisite policy steps; use `None` if it has no inputs.
- **Outputs:** List context variables created or modified with their types and conditional behavior, request/response mutations, other side effects such as cache writes or traces, and early responses with their status codes. State what remains unchanged or when processing continues if relevant; use `None` if it has no outputs or side effects.

Keep the header concise and accurate when creating or updating the fragment. Describe the caller-visible contract, not each implementation statement. Preserve execution order and behavior when adding documentation, and do not include secrets or environment-specific identifiers.

```xml
<fragment>
    <!--
        Purpose: Select an optional model hint in inbound without reading the body.
        Inputs:
          - Request header x-ai-model; missing or blank values default to "".
        Outputs:
          - headerModel (string): header value, trimmed, or "".
          - Request body is unchanged; processing continues.
    -->
    <set-variable name="headerModel"
        value='@(context.Request.Headers.GetValueOrDefault("x-ai-model", "").Trim())' />
</fragment>
```

## Policy Categories Quick Reference

| Category           | Common Policies                                                              | Section          |
| ------------------ | ---------------------------------------------------------------------------- | ---------------- |
| **Authentication** | `authentication-managed-identity`, `validate-azure-ad-token`, `validate-jwt` | inbound          |
| **Rate Limiting**  | `rate-limit-by-key`, `quota-by-key`                                          | inbound          |
| **Caching**        | `cache-lookup`, `cache-store`                                                | inbound/outbound |
| **Routing**        | `set-backend-service`, `forward-request`, `retry`                            | inbound/backend  |
| **Transformation** | `set-header`, `set-body`, `set-variable`, `rewrite-uri`                      | any              |
| **Control Flow**   | `choose`, `return-response`, `retry`, `wait`                                 | any              |

## Essential Policies

### Set Backend Service

Route requests to a specific backend:

```xml
<set-backend-service backend-id="my-backend" />
```

### Forward Request Timeout

Set `timeout="60"` explicitly on every `forward-request` policy. This bounds each backend attempt to 60 seconds, including each attempt nested inside a `retry` policy.

Use a different timeout only when measured workload behavior requires it, such as a documented long-running synchronous backend contract. Record the reason next to the policy and account for the total worst-case duration across the initial request and all retries. Do not omit the attribute to rely on the platform default.

```xml
<forward-request timeout="60" />
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
<retry count="2" interval="1" first-fast-retry="true"
    condition='@(context.Response.StatusCode == 429 || context.Response.StatusCode >= 500)'>
    <forward-request timeout="60" buffer-request-body="true" />
</retry>
```

For backend-pool failover, bound the retry budget independently of pool size. Use `count="2"` as the default unless workload testing justifies another value. This permits two retries after the initial attempt, for three total attempts. Two retries may already be more than sufficient for interactive traffic: a circuit-breaking pool removes a failed member from selection, and three consecutive failures against backends that were eligible moments earlier are a strong signal to stop and return control to the caller. Use retry-attempt and latency telemetry to justify reducing the count to `1` or increasing it above `2`.

When the value must be managed outside the policy, use a plain numeric Named Value as the complete attribute value, for example `count="{{backend-retry-count}}"`, and set that Named Value to `2`. Keep pool cardinality as a separate concern only when policy behavior genuinely needs to count pool members.

## Policy Expressions

Policy expressions use C# syntax within `@()` for single statements or `@{}` for multi-statement blocks.

### Quotes in XML Attributes

Use single quotes around XML attribute values that contain policy expressions. This allows C# string literals and dictionary keys inside the expression to use normal double quotes without XML entity encoding.

```xml
<set-variable name="callerId" value='@((string)context.Variables["callerId"])' />
```

Keep ordinary non-expression XML attributes double-quoted. The `rawxml` format preserves native C# string and character literals. For the strict `xml` format, encode a quote matching the enclosing attribute delimiter as `&apos;` or `&quot;`.

Expressions in element text also use normal double quotes:

```xml
<value>@((string)context.Variables["callerId"])</value>
```

### Raw Policy Expressions and XML Entity Encoding

Match expression encoding to the deployed policy format. The repository's shared API and policy-fragment modules use `format: 'rawxml'`, which accepts native C# expressions without XML entity encoding. Prefer readable expressions in new or updated policies deployed through these modules:

```xml
<set-variable name="attempt" value='@(context.Variables.GetValueOrDefault<int>("attempt", 0))' />
<when condition='@(attempt <= retryLimit && statusCode >= 500)'>
    <!-- policies -->
</when>
```

Do not introduce a compiler, deployment-time replacement or CDATA wrapper just to avoid encoding. CDATA cannot be placed inside attribute values. A `rawxml` policy is not necessarily standards-compliant XML; structural tests may encode expression attributes in memory for an XML parser, but must deploy the source unchanged and must not hide malformed policy markup.

Only when an integration explicitly requires `format: 'xml'`, encode reserved characters in attribute values and element text:

- Encode `&` as `&amp;`. Logical AND must therefore be written as `&amp;&amp;`.
- Encode `<` as `&lt;`. This is required for less-than comparisons and the opening angle bracket of generic type arguments.
- Encode `>` as `&gt;` for paired angle brackets and comparisons. A literal `>` is generally valid XML, but encoding it keeps expressions consistent and avoids ambiguity.

```xml
<set-variable name="attempt" value='@(context.Variables.GetValueOrDefault&lt;int&gt;("attempt", 0))' />
<when condition='@(attempt &lt;= retryLimit &amp;&amp; statusCode &gt;= 500)'>
    <!-- policies -->
</when>
```

These entities are decoded before C# evaluation in the `xml` format. Outside expressions, retain ordinary XML escaping for literal text and attribute values. See Microsoft's [policy output-format guidance](https://github.com/Azure/azure-api-management-policy-toolkit/blob/main/docs/OutputFormat.md) for the distinction.

### String Interpolation

Prefer C# string interpolation (`$"..."`) over `+` concatenation when combining literal text and values in policy expressions. Keep the intended output format visible, particularly for resource identifiers, paths and diagnostic messages.

```xml
<set-variable name="backendPool" value='@($"aoai-v1-routing-1-{(string)context.Variables["model"]}-{(string)context.Variables["family"]}-pool")' />
```

Keep constant-only strings as plain literals. When replacing concatenation, preserve existing types, null handling, formatting and escaping; interpolation is a readability convention, not a performance guarantee. Use C# 7-compatible syntax and the expression quoting and deployment-format rules above. Do not rewrite unrelated policies solely to apply this preference.

### Compact Result Objects

When one policy decision produces several related outputs, prefer a single C# execution block returning a compact `JObject` through `set-variable`. This shares computation and retains only small decision data in context.

- Keep parsing, validation and selection together when they form one decision. Deserialize a payload at most once per executed path; keep the full parsed payload and intermediate values local to the block.
- Return only fields needed downstream, with explicit names and types. Use supported APIM expression return types and allow-listed members; do not serialize the result to a string only to parse it again.
- APIM expressions return one value and `context.Variables` is read-only. Expose result fields through short typed lookups or policy assignments, not additional payload reads or casts.
- Include explicit error outcomes when validation can fail. Preserve existing status codes, earlier-error precedence and trace/response handling; never represent a failed decision as a successful default.
- Keep `preserveContent: true` when forwarding the original payload, and skip body reads entirely on header-only paths. Test single-read behavior, result field types, success and malformed-input outcomes.
- Apply this pattern to cohesive multi-output decisions, not trivial scalar expressions or unrelated policy phases. If separate expressions genuinely need the full parsed object, reuse a supported context-variable type rather than repeating deserialization.

For example, the block can return only the selected model and validation outcome:

```csharp
return new JObject(
    new JProperty("model", selectedModel),
    new JProperty("errorCode", errorCode),
    new JProperty("errorStatus", errorStatus));
```

The [Azure OpenAI v1 Routing body-model fragment](../../../samples/aoai-v1-routing/apim-policies/fragments/body-model.xml) is the reference implementation: it processes the body in one block, returns a compact `bodySelection` result and uses short assignments to expose its fields.

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
        if(value != null && value.Length > 0)
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
- **JSON via `Newtonsoft.Json`** is the only supported JSON library; do not use `System.Text.Json`.

When a member you need is not allowed, refactor to an equivalent that is. Examples:

| Disallowed                                                        | Allowed replacement                                                                             |
| ----------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `DateTime.TryParse(s, ..., DateTimeStyles.RoundtripKind, out dt)` | Store as Unix epoch via `DateTimeOffset.UtcNow.ToUnixTimeSeconds()`, parse with `long.TryParse` |
| `DateTime.ParseExact(s, fmt, CultureInfo.InvariantCulture)`       | `DateTime.Parse(s)` (allowed) or epoch-based representation                                     |
| `Enum.GetValues(typeof(T))`                                       | Hard-code the comparison values or store as a string                                            |
| `System.Text.Json.JsonSerializer.Deserialize<T>(s)`               | `JsonConvert.DeserializeObject<T>(s)`                                                           |

If you are unsure whether a member is allowed, fetch the [allowed types table](https://learn.microsoft.com/azure/api-management/api-management-policy-expressions#CLRTypes) and confirm before writing the expression.

## Reference Documentation

- **Sample-owned policies in this repo**: `samples/<sample-name>/apim-policies/` (all XML policies specific to one sample)
- **Shared policies in this repo**: `shared/apim-policies/` (reusable policy XML fragments)

Policy-loading helpers must check the sample's `apim-policies/` directory first. During migration only, they may check the sample root second so existing root-level policies continue to work. New policy files must not use the fallback location.

## Official Documentation

- [APIM Policy Reference](https://learn.microsoft.com/azure/api-management/api-management-policies)
- [Policy Expressions](https://learn.microsoft.com/azure/api-management/api-management-policy-expressions)
- [Policy Snippets Repository](https://github.com/Azure/api-management-policy-snippets)
