# Inference Failover Queries

These KQL queries help operators inspect AI gateway routing, fallback behavior, failures, latency, and LLM telemetry for the inference failover sample. Run them against the Log Analytics workspace used by the selected API Management infrastructure.

Return to the [Inference Failover sample](../README.md) for deployment steps and the broader scenario description.

## Common Parameters

The query files intentionally keep runtime values separate from their query bodies. Prepend these `let` bindings before running an operator-facing query:

```kql
let timeWindow = 1h;
let apiIds = dynamic(['inference-gpt-5-1', 'inference-gpt-4-1-mini']);
```

Adjust `timeWindow` when investigating a shorter incident window or a longer trend. Narrow `apiIds` when you only need one model-safe backend pool.

## Signal Sources

- `ApiManagementGatewayLogs`: Caller-visible response codes, final backend response codes, backend placement, timing, APIM errors, and policy trace records.
- `ApiManagementGatewayLlmLog`: Correlated model deployment, prompt token, completion token, total token, and message-chunk telemetry.

The retry-aware queries count compact `InferenceAttempt` entries in `TraceRecords`. Exhausted fallback is derived from native `ResponseCode`, `BackendResponseCode`, and `LastErrorReason` fields.

## Query Catalog

### [backend-distribution.kql](backend-distribution.kql)

Use this query to see where APIM ultimately placed inference requests. It parses the Azure OpenAI account name from the final backend URL, groups gateway rows by API, AOAI instance, and concrete backend URL or backend ID, then reports the exact caller and final-backend status sets, successes, non-throttling client errors, throttled responses, server errors, residual responses, average backend latency, and success rate. The outcome counts are mutually exclusive and add up to the request total.

This is a useful first view when validating weighted distribution or checking whether pressure moved traffic to a regional fallback tier.

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

### [verify-llm-ingestion.kql](verify-llm-ingestion.kql)

This is the notebook readiness probe used before local charts are rendered. It checks a shorter default window and returns one row only after gateway request rows and token-bearing LLM rows both reach Log Analytics.

When running it manually, prepend these bindings:

```kql
let timeWindow = 30m;
let apiIds = dynamic(['inference-gpt-5-1', 'inference-gpt-4-1-mini']);
```

The output reports gateway request rows, successful requests, unavailable responses, token-bearing correlation IDs, and total tokens. An empty result usually means telemetry is still ingesting or the selected time window does not include recent sample traffic.
