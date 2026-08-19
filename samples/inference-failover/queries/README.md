# Inference Failover Queries

These KQL queries help operators inspect AI gateway routing, fallback behavior, failures, latency, API delivery modes, estimated token cost, and LLM telemetry for the inference failover sample. Run them against the Log Analytics workspace used by the selected API Management infrastructure.

Return to the [Inference Failover sample](../README.md) for deployment steps and the broader scenario description.

## Common Parameters

The query files intentionally keep runtime values separate from their query bodies. Prepend these `let` bindings before running an operator-facing query:

```kql
let timeWindow = 1h;
let apiIds = dynamic(['inference-gpt-5-1', 'inference-gpt-4-1-mini']);
```

Adjust `timeWindow` when investigating a shorter incident window or a longer trend. Narrow `apiIds` when you only need one model-safe backend pool.

The retry-attempt query scopes Application Insights by request path instead. Its header includes the `apiPaths` binding for the two exercised inference routes.

## Signal Sources

- `ApiManagementGatewayLogs`: Caller-visible response codes, final backend response codes, backend placement, timing, APIM errors, and policy trace records.
- `AppRequests`: One Application Insights frontend request per APIM transaction, including complete request duration in `DurationMs`.
- `AppDependencies`: One Application Insights dependency per forwarded backend call, including each retry attempt's target, status, success state, and `DurationMs`.
- `ApiManagementGatewayLlmLog`: Correlated model deployment, prompt token, completion token, total token, and message-chunk telemetry.

The retry-aware gateway queries count compact `InferenceAttempt` entries in `TraceRecords`. Each entry includes the attempt budget, concrete backend member ID and URL, response code, and an optional `Retry-After` value for `429` responses. Exhausted fallback is derived from native `ResponseCode`, `BackendResponseCode`, and `LastErrorReason` fields. These policy records explain the retry decision but do not measure each attempt. Use `AppDependencies.DurationMs` for individual backend duration and `AppRequests.DurationMs` or `ApiManagementGatewayLogs.TotalTime` for end-to-end APIM duration.

## Query Catalog

### [api-delivery-modes.kql](api-delivery-modes.kql)

Use this query to compare Chat Completions and Responses API traffic and split each API surface into streaming and non-streaming delivery modes. It correlates token-bearing LLM telemetry with the APIM operation ID, then reports request and token totals by API, model, API surface, and delivery mode.

The automated sample harness currently produces Chat Completions non-streaming traffic. Other categories appear when those request types are routed through the sample APIs and recorded in `ApiManagementGatewayLlmLog`.

### [backend-distribution.kql](backend-distribution.kql)

Use this query to see where APIM ultimately placed inference requests. It parses the Azure OpenAI account name from the final backend URL, groups gateway rows by API, AOAI instance, and concrete backend URL or backend ID, then reports the exact caller and final-backend status sets, successes, non-throttling client errors, throttled responses, server errors, residual responses, average gateway `BackendTime`, and success rate. The outcome counts are mutually exclusive and add up to the request total.

This is a useful first view when validating weighted distribution or checking whether pressure moved traffic to a regional fallback tier. Because the gateway emits one row per APIM request, `BackendTime` does not provide a separate duration for every retry attempt. Use `backend-retry-attempts.kql` for that breakdown.

### [backend-retry-attempts.kql](backend-retry-attempts.kql)

Use this query to inspect only APIM operations that made more than one Azure OpenAI dependency call. It correlates `AppRequests` and `AppDependencies` by `OperationId`, sequences dependency spans by start time, and returns one row for every failed or successful backend attempt.

`Backend Duration (ms)` is the individual dependency duration. `Total APIM (ms)` is the complete frontend request duration and is repeated on each row in the operation so it can be compared with the sum of backend calls and APIM policy overhead. The matching **Retried Backend Requests** table is on the workbook's **Failover Trails** tab.

### [failover-outcomes.kql](failover-outcomes.kql)

Use this query to compare caller-visible results with the final backend response after APIM retry handling. It classifies requests as successful without failover, recovered after failover, fallback exhausted, caller-visible throttling, caller-visible server error, or another outcome.

The output includes average attempt count and average backend latency for each API, AOAI instance, outcome, caller response code, and final backend response code combination.

### [failure-analysis.kql](failure-analysis.kql)

Use this query when investigating degraded traffic or a failed pressure scenario. It filters out requests that succeeded without failover and classifies the remaining rows as recovered failovers, exhausted fallback chains, final-backend throttling, final-backend server errors, caller-visible errors, or native APIM pipeline errors.

The output includes the final AOAI instance, request count, average and maximum attempts, average total latency, P95 total latency, and APIM error source and reason where available.

### [llm-telemetry-coverage.kql](llm-telemetry-coverage.kql)

Use this query to confirm whether successful gateway requests received correlated LLM diagnostic rows. It joins gateway and LLM telemetry by `CorrelationId`, then distinguishes successful calls with token telemetry from successful calls missing token telemetry and non-success calls where token telemetry is not expected.

The output reports requests, token totals, LLM row counts, and request and response message-chunk counts by API and coverage category. This validates telemetry completeness without rendering prompt or completion bodies.

### [request-details.kql](request-details.kql)

Use this query for a per-request investigation after a summary query identifies an anomaly. It joins gateway and LLM rows by `CorrelationId` and returns one operator-focused row for each inference request.

The output includes caller and backend status codes, AOAI account and backend placement, latency, retry counts, the extracted attempt trail, fallback exhaustion state, token usage, message-chunk counts, native APIM errors, and raw trace records. Filter by `CorrelationId` when tracing one request end to end.

### [token-throughput.kql](token-throughput.kql)

Use this query to measure token-bearing model consumption across API routes and concrete backends. It joins token-bearing LLM rows to gateway placement rows by `CorrelationId`, then summarizes request count and prompt, completion, and total tokens by API, AOAI instance, backend, and model.

This view helps connect routing behavior to model usage and identify which fallback tiers served token-bearing requests.

### [token-cost-allocation.kql](token-cost-allocation.kql)

Use this query to estimate token cost by final AOAI account and backend, model, API surface, and delivery mode. In addition to `timeWindow`, prepend current prompt and completion rates per 1,000 tokens for both sample models, as shown in the query header. The workbook exposes the same values as editable parameters and defaults every rate to zero.

This estimate excludes PTU commitments, cached-input discounts, Batch pricing, taxes, negotiated adjustments, and requests without token telemetry. Confirm the configured rates and reconcile the result with Azure Cost Management before using it for financial reporting or showback.

### [verify-llm-ingestion.kql](verify-llm-ingestion.kql)

This is the notebook readiness probe used before local charts are rendered. It checks a shorter default window and returns one row only after gateway request rows and token-bearing LLM rows both reach Log Analytics.

When running it manually, prepend these bindings:

```kql
let timeWindow = 30m;
let apiIds = dynamic(['inference-gpt-5-1', 'inference-gpt-4-1-mini']);
```

The output reports gateway request rows, successful requests, unavailable responses, token-bearing correlation IDs, and total tokens. An empty result usually means telemetry is still ingesting or the selected time window does not include recent sample traffic.
