# Inference Failover and WAF Throttling Guidance

This document compares the circuit-breaker, retry, and failover behavior in the Inference Failover sample with the Azure Well-Architected Framework (WAF) guidance in [Design throttling to improve resilience][waf-throttling].

The WAF guidance describes a broad, workload-level throttling strategy across callers, gateways, application components, and downstream dependencies. This sample has a narrower purpose: demonstrate how Azure API Management (APIM) can route one synchronous inference request across model-compatible Azure OpenAI deployments when a selected deployment is constrained or unavailable.

> The differences described here are deliberate and correct for the sample's learning objectives. They should not be interpreted as accidental noncompliance or as general production guidance. A production workload should combine this gateway failover pattern with the broader admission control, concurrency, client, and operational controls described by WAF.

## Scope of the Comparison

The sample owns the APIM-to-Azure OpenAI boundary. It demonstrates:

- Model-specific backend pools that prevent cross-model routing.
- Priority and weighted selection across regional deployments.
- Per-backend circuit breakers that remove constrained destinations.
- Bounded in-request failover with a buffered request body.
- Caller-visible terminal `429` and `503` responses.
- Retry, backend, latency, outcome, and token telemetry.

The sample does not attempt to implement the complete throttling architecture for an application that calls the gateway. In particular, it does not define workload identity contracts, tenant quotas, application queues, end-user priorities, or application-level concurrency limits. Those decisions depend on the workload that adopts the pattern.

## Implemented Behavior

The deployed behavior is defined in [main.bicep](main.bicep), the primary [inference-api-policy.xml](apim-policies/inference-api-policy.xml), and the optional [inference-api-policy-with-retry-tracked.xml](apim-policies/inference-api-policy-with-retry-tracked.xml):

- One qualifying `408`, `429`, `499`, `500`, `502`, `503`, or `504` response opens that backend's circuit.
- The normal circuit interval and trip duration are one minute.
- `acceptRetryAfter: true` allows APIM to honor backend recovery guidance when opening a circuit.
- Both model routes permit two retries after the initial attempt, for three total attempts. This may already be more than sufficient for interactive traffic.
- The retry budget is independent of pool size; circuit-open backends are removed from subsequent selection.
- Retryable responses are handled immediately with `interval="0"` and `first-fast-retry="true"`.
- A circuit-open backend is excluded from subsequent pool selection, so an immediate retry normally selects another eligible backend.
- The primary routes preserve the final backend `429`; the optional retry-tracked gpt-5.1 route rewrites `429` with the soonest observed relative `Retry-After` only when every attempt in the bounded retry chain returned `429`.
- Exhausted infrastructure or transport failure is returned as a generic `503` without unsupported recovery guidance.
- `X-Backend-Retry` and `InferenceAttempt` trace records expose the attempts absorbed by the gateway.

Although APIM calls this mechanism a `retry` policy, its role in this sample is primarily **bounded cross-backend failover**. It is not a general-purpose loop that repeatedly calls a backend already known to be throttled.

## Comparison Matrix

| WAF practice                                                         | Sample behavior                                                                                                                                                                   | Relationship               | Sample-specific rationale                                                                                                                                                                                    |
| -------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Treat overload as a normal operating mode                            | The notebook deliberately uses small Azure OpenAI deployments and pressure scenarios to produce observable throttling and recovery.                                               | Direct alignment           | Failure and recovery are part of the main scenario rather than exceptional test-only behavior.                                                                                                               |
| TP-2: Apply user and service limits at multiple entry points         | APIM subscription validation protects the APIs, but the sample does not define workload-identity token quotas or operation-level admission limits.                                | Outside sample scope       | The sample studies downstream failover. Caller contracts and service-wide admission limits belong to the adopting workload.                                                                                  |
| TP-3: Return `429` for user limits and `503` for service constraints | The primary routes preserve the final downstream `429`, while infrastructure exhaustion becomes `503`; the optional comparison route rewrites only retry-budget `429` exhaustion. | Deliberate specialization  | Keeping capacity exhaustion distinct makes Azure OpenAI throttling and recovery observable. The sample is not claiming that the caller violated an APIM user quota.                                          |
| TP-3: Provide useful retry guidance                                  | The optional retry-tracked route preserves the soonest relative recovery delay observed across constrained pool members.                                                          | Direct alignment           | A relative delay avoids absolute-time and clock-skew problems and gives the caller an actionable capacity signal without burdening every route with tracking logic.                                          |
| TP-3: Add standardized rate-limit metadata                           | The sample returns `Retry-After` and its educational `X-Backend-Retry` header, but not `RateLimit-Policy`, `RateLimit`, or `x-ms-ratelimit-used`.                                 | Outside sample scope       | APIM does not own a user or tenant rate contract in this sample, so publishing one would imply limits that the sample does not enforce.                                                                      |
| TP-5: Respect downstream backpressure                                | A throttled backend is removed from selection by its circuit, including an APIM circuit duration informed by `Retry-After`.                                                       | Direct alignment           | The gateway stops sending traffic to the constrained deployment and uses independent regional capacity instead.                                                                                              |
| TP-5: Keep retries bounded                                           | Each route permits two retries after the initial attempt, independent of pool size.                                                                                               | Direct alignment           | Three consecutive failures across recently eligible backends are enough evidence to return control to the caller; even this retry budget may be more than sufficient for interactive traffic.                |
| TP-5: Do not retry before `Retry-After` elapses                      | The gateway immediately tries another eligible backend instead of waiting for the constrained backend.                                                                            | Deliberate specialization  | Waiting inside a synchronous gateway request would consume request lifetime without using available alternative capacity. The constrained backend remains circuit-open for its recovery window.              |
| TP-5: Do not retry `503` without retry guidance                      | The policy can immediately fail over after a backend `503`, even without `Retry-After`.                                                                                           | Deliberate specialization  | This is a bounded attempt against a different regional deployment, not a delayed retry against the same failing dependency. If alternatives are exhausted, the caller receives `503` without retry guidance. |
| TP-5: Annotate downstream retries                                    | The sample records attempts in traces and returns `X-Backend-Retry`, but does not send a `retry-attempt` request header to Azure OpenAI.                                          | Partial alignment          | The sample emphasizes gateway and operator observability. A production contract with a dependency that consumes retry metadata should add the request header where supported.                                |
| TP-5: Use circuit breakers to fail fast                              | Each concrete Azure OpenAI deployment has isolated circuit state and is removed after one configured failure.                                                                     | Direct alignment           | Isolation prevents one model or regional deployment from suppressing an otherwise healthy destination.                                                                                                       |
| TP-5: Gradually reintroduce recovered traffic                        | A backend becomes eligible when APIM closes its circuit; the sample does not implement a separate ramp-up controller.                                                             | Deliberate simplification  | Fixed recovery behavior makes the lab repeatable. Progressive re-entry requires workload-specific health, capacity, and priority signals.                                                                    |
| TP-7: Apply egress bulkheads                                         | Backend pools bound attempts per request, but the sample does not impose a gateway-wide in-flight concurrency limit.                                                              | Outside sample scope       | Pool failover and workload concurrency control solve different problems. Production callers and gateways should add concurrency controls based on their capacity model.                                      |
| TP-9: Keep throttling accounting out of the critical path            | Circuit state is managed by APIM. Telemetry is emitted to Log Analytics and the optional Event Hub without synchronous analytical queries in request processing.                  | Direct alignment           | Observability does not require a workbook or Log Analytics query to complete before inference proceeds.                                                                                                      |
| TP-11: Reassess and validate limits                                  | The notebook runs low-capacity pressure, recovery, and exhaustion scenarios and provides controlled fault-testing guidance.                                                       | Direct alignment for a lab | Production adoption should automate periodic load, chaos, and regional outage validation.                                                                                                                    |
| TP-12: Use state-aware throttling                                    | Backend eligibility reacts to response status and `Retry-After`, but priorities and weights remain static.                                                                        | Partial alignment          | Response-aware circuit state is sufficient for the sample. Business-priority brownouts and dynamic token admission require application context not available here.                                           |
| TP-14: Shed load before the hard ceiling                             | The sample intentionally drives low-capacity deployments to their limit rather than randomly rejecting traffic early.                                                             | Deliberate specialization  | Reaching the limit makes circuit breaking and failover visible. Random early drop would obscure the behavior the lab is designed to teach.                                                                   |

## Why Immediate Retry Is Appropriate Here

WAF warns against immediate retries because repeated calls to a constrained dependency amplify load. That warning applies directly when a client retries the same dependency without respecting its backpressure signal.

This sample uses a different sequence:

1. APIM selects one concrete model-compatible backend.
1. A configured capacity or infrastructure response opens that backend's circuit.
1. The retry policy immediately asks the pool for another eligible backend.
1. The open backend remains unavailable for the circuit duration or accepted `Retry-After` window.
1. The gateway stops after the bounded retry budget is exhausted.

The zero interval therefore avoids holding a synchronous inference request idle while healthy regional capacity might be available. The circuit breaker, model-safe pool, and bounded attempt count are all required for that choice to remain appropriate. Copying `interval="0"` into a policy without those controls would not preserve the same safety properties.

## Why the Optional Route Tracks Capacity Exhaustion

WAF recommends `429` for a caller exceeding a user limit and `503` for a service-wide constraint. The optional retry-tracked route's terminal `429` is a deliberate educational contract for **downstream Azure OpenAI capacity exhaustion**, not an APIM user-limit decision. The primary routes simply preserve a final backend `429` after bounded failover.

This choice preserves two signals that the lab needs to demonstrate:

- Capacity exhaustion remains distinguishable from infrastructure and transport failure.
- A caller of the optional route receives the earliest known `Retry-After` delay from the attempted capacity pool only when every attempt in the bounded retry chain returned `429`.

The sample returns `503` when it cannot make a supported capacity statement, such as mixed exhaustion, infrastructure failures, or backend connection failures. A production API can instead normalize pool-wide capacity exhaustion to `503` if its public contract follows the WAF user-limit versus service-limit distinction strictly. That is a contract decision at the workload boundary, not evidence that the sample's internal failover behavior is wrong.

## Responsibility Boundaries

| Boundary             | This sample demonstrates                                                                                              | Production workload responsibility                                                                                |
| -------------------- | --------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Caller to APIM       | Subscription authentication and terminal backpressure signals.                                                        | Backoff, jitter, retry budgets, deadlines, cancellation, workload identity, and safe replay semantics.            |
| APIM ingress         | API and operation matching before the inference policy runs.                                                          | User and service token limits, differentiated priorities, blocking controls, and standardized rate-limit headers. |
| APIM to Azure OpenAI | Model-safe selection, bounded failover, per-backend circuits, managed identity, and terminal response classification. | Concurrency limits, total request deadlines, dependency contracts, and production-specific timeout budgets.       |
| Operations           | Retry traces, backend distribution, terminal outcomes, latency, and token telemetry.                                  | Current limit saturation, top callers, alert thresholds, automated mitigation, drills, and periodic limit review. |
| Adaptive control     | Response-aware backend exclusion and recovery.                                                                        | Brownouts, progressive re-entry, dynamic token costs, borrowing, and random early drop when required.             |

## Production Adoption

The following sample behaviors are useful building blocks for production:

- Keep one backend resource and circuit state per model-compatible deployment.
- Bound attempts to the available alternatives and to the caller's total deadline.
- Preserve request bodies only when the operation is safe to replay.
- Do not retry caller, authentication, authorization, or configuration errors.
- Distinguish downstream capacity from infrastructure and transport failure.
- Keep retry and backend-selection telemetry without exposing backend identities publicly.

A production workload should add controls based on its own saturation vectors and service-level objectives:

- Enforce token-based user limits by workload identity and service limits by operation.
- Limit concurrent in-flight inference calls and account for retry amplification.
- Define whether terminal downstream capacity is exposed as `429` or normalized to `503` in the public API contract.
- Add `RateLimit-Policy`, `RateLimit`, and related headers only for limits the gateway actually enforces.
- Apply caller-side jitter, total retry budgets, deadlines, and cancellation.
- Add progressive recovery, brownouts, or early load shedding when business priorities require them.
- Monitor current limits, saturation, top callers, and high-water marks, then validate them through regular load and regional failure drills.

## Verification and Evidence

The sample provides several ways to inspect the behavior described above:

- [create.ipynb](create.ipynb) runs deterministic contract probes and pressure, recovery, and terminal exhaustion scenarios against the two primary routes. It deploys but does not exercise the retry-tracked comparison route.
- [failover-outcomes.kql](queries/failover-outcomes.kql) separates successful requests, recovered failovers, caller throttling, and exhausted fallback.
- [failure-analysis.kql](queries/failure-analysis.kql) classifies backend failures and APIM pipeline errors.
- [token-throughput.kql](queries/token-throughput.kql) reports the AI-specific saturation dimension of token volume.
- [request-details.kql](queries/request-details.kql) correlates gateway, retry, backend, and LLM telemetry for an individual request.
- [README.md](README.md#failure-test-coverage) lists deterministic and controlled tests for each response class.

## Conclusion

The sample and WAF guidance are complementary. WAF explains how an entire workload should control overload across ingress, internal components, egress, clients, and operations. This sample isolates one important part of that system and makes it observable: fast, bounded failover across independent Azure OpenAI capacity targets.

Its immediate cross-backend attempts, one-failure circuit trips, optional capacity-tracked `429`, static recovery, and intentionally low deployment capacity are purpose-built for that demonstration. They are correct within the sample's boundary and should be carried into production only together with the broader workload controls appropriate to the adopting system.

[waf-throttling]: https://learn.microsoft.com/azure/well-architected/design-guides/throttling
