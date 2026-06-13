# Samples: Load Balancing

Sets up an APIM instance that demonstrates load balancing and circuit breaking across backends.

⚙️ **Supported infrastructures**: apim-aca, afd-apim-pe

👟 **Expected *Run All* runtime (excl. infrastructure prerequisite): ~3 minutes**

## 🎯 Objectives

1. Understand how backends can be configured to balance load in a prioritized, weighted manner.
1. Learn how circuit breakers aid with load balancing.
1. Configure how retries in API Management policies can result in more successful requests.

## 🛩️ Lab Components

This lab integrates into an existing Azure Container Apps architecture and sets up the following:

- One container app that serves multiple mock Web API endpoints returning 429 error codes.
- Three separate backends are set up in APIM that each point to a different endpoint on this container app (e.g. /api/0, /api/1, etc.).
- Four separate backend pool with varying load balancer setups are configured using these three backends.
- Six APIs that each demonstrate a different load-balancing or error-handling behavior, including a `/lb-retry-tracked` endpoint that records the soonest backend recovery time as an absolute UTC timestamp and emits a decreasing `Retry-After` header until that instant elapses.

## 🧪 Test Matrix

The notebook exercises each load-balancing strategy with a dedicated test. Run order and run counts are fixed; behaviour varies by backend pool configuration and per-test sleep semantics.

| # | Test | API path | Runs | Pool / Backends | Sleep semantics | Key behaviour verified | Chart |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Prioritized Distribution | `/lb-prioritized` | 15 | 2 backends, priorities P1 -> P2 | None | First request lands on P1 (index 0, count 1); P1 serves until exhaustion, then P2 takes over until the pool is unhealthy | Yes |
| 2 | Weighted (50/50) | `/lb-weighted-equal` | 15 | 2 backends, equal weight | None | Requests alternate across the two backends until exhaustion | Yes |
| 3 | Weighted (80/20) | `/lb-weighted-unequal` | 15 | 2 backends, 80/20 weight | None | Distribution roughly tracks the configured 80/20 weighting until exhaustion | Yes |
| 4 | Prioritized & Weighted | `/lb-prioritized-weighted` | 25 | 3 backends, P1 then 2 x P2 equal weight | None | P1 serves first; P2 pair then takes over with equal weighting until the pool is unhealthy | Yes |
| 5 | Prioritized & Weighted (500ms sleep) | `/lb-prioritized-weighted` | 20 | Same as #4 | 500 ms sleep between every request | The sleep gives backends time to recover, so the pool keeps serving longer before exhaustion | Yes |
| 6 | Absolute-Time `Retry-After` Tracking | `/lb-retry-tracked` | 25 | 2 backends, priorities P1 -> P2 | On every 429 with a parseable `Retry-After`, the loop sleeps exactly that many seconds (the policy bakes in a +1s buffer) | Pre-first-wait `Retry-After` values are non-increasing; first emitted value is > 0; at least one request after the first wait returns 200 (pool recovered) | Yes |
| 7 | 503-to-429 Error Handling | `/lb-429-prioritized` | 12 | 2 backends, priorities P1 -> P2 | None | At least one 429 is returned once the pool is exhausted; 429 responses carry a `Retry-After` header and non-429 responses do not | No |

Tests 1-6 run in the *Verify Deployment* cell; test 7 runs in the separate *Test 503-to-429 Error Handling* cell. All charts apply a 95th-percentile cutoff when computing the mean so the cold-path first request does not skew the steady-state average.

## ⚙️ Configuration

1. Decide which of the [Infrastructure Architectures](../../README.md#infrastructure-architectures) you wish to use.
    1. If the infrastructure *does not* yet exist, navigate to the desired [infrastructure](../../infrastructure/) folder and follow its README.md.
    1. If the infrastructure *does* exist, adjust the `user-defined parameters` in the *Initialize notebook variables* below. Please ensure that all parameters match your infrastructure.
