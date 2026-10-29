# Samples: Load Balancing

Demonstrates APIM load balancing, circuit breaking, and recovery using the two infrastructure-owned MockAPI instances. The sample adds APIM resources and three mock endpoints, without deploying another container.

⚙️ **Supported infrastructures**: apim-aca, afd-apim-pe (with Container Apps enabled)

👟 **Expected _Run All_ runtime (excl. infrastructure prerequisite): ~7 minutes**

## 🎯 Objectives

1. Understand how backends can be configured to balance load in a prioritized, weighted manner.
1. Learn how circuit breakers aid with load balancing.
1. Configure how retries in API Management policies can result in more successful requests.

## ✅ Prerequisites

Beyond the [general prerequisites](../../README.md#getting-started), use an infrastructure deployed with MockAPI, persistent configuration, and the secret APIM Named Value `mockapi-key`. The notebook identity must be able to read the existing Container Apps secrets, and the notebook machine must reach the two HTTPS dashboard origins. Redeploy older infrastructures before running this sample.

> **Upgrade required for older deployments:** Redeploy the infrastructure to apply the repository's pinned MockAPI image, which fixes idle-window replenishment, before testing exact-wait recovery. The stricter assertion requires success on the first request after the first tracked wait, not eventual success after repeated waits.

## 🛩️ Lab Components

Explore the [MockAPI website](https://mockapi.simondoescloud.com) for product information and documentation.

This lab reuses the existing infrastructure and configures the following:

- Two existing infrastructure MockAPI containers, with their dashboards at HTTPS `/`. The sample follows URLs published on infrastructure-owned `aca-backend-1/2`, not Container App names or environment names. Public deployments may use `mockwebapi-1/2`; private-storage deployments may use `mockapi-1/2`. The existing `/hello` endpoint and all unrelated endpoint definitions and API descriptions are preserved.
- Three independent throttled endpoints: `/load-balancing/backend-0` and `/load-balancing/backend-2` on app 1, and `/load-balancing/backend-1` on app 2. Each allows five successful requests per rolling three-second window, then returns 429 with `Retry-After: 3`. This restores the original WebApi429 capacity and recovery timing. MockAPI uses rolling expiration rather than the old inactivity-reset counter; the models are not identical. Budgets are endpoint-local even when endpoints share a process.
- Three APIM backends inject `X-MockAPI-Key` through `credentialHeaders`, referencing `{{mockapi-key}}`; no literal key is stored in sample configuration. Existing `aca-webapi429-*` backend and pool resource IDs remain for compatibility, but there is no dependency on the old container or image.
- Four backend pools with varying priority and weight configurations.
- Sample backend circuit breakers trip for three seconds and accept `Retry-After`, matching the MockAPI permit window instead of inheriting the shared module's one-minute trip duration.
- Six APIs that each demonstrate a different load-balancing or error-handling behavior, including a `/lb-retry-tracked` endpoint that records the soonest backend recovery time as an absolute UTC timestamp and emits a decreasing `Retry-After` header until that instant elapses.
- Every policy uses a bounded retry count of `2`, allowing two retries after the initial attempt, for three total attempts. This may already be more than sufficient for interactive traffic. The limit is intentionally independent of pool size because circuit breakers remove failed backends from selection and repeated failures across recently eligible members are a signal to return control to the caller.

The sample-local setup helper composes two shared `MockApiDashboardClient` sessions using the [MockAPI management contract](https://github.com/simonkurtz-MSFT/MockAPI/blob/1.11.0/docs/CONFIGURATION.md). The shared client authenticates as the infrastructure dashboard user, exports the configuration and strong ETag, and creates or replaces only the requested deterministic endpoint IDs using `If-Match`. Concurrent edits trigger bounded refetch/retry rather than a whole-document overwrite. Ownership collisions fail closed. Management mutations autosave to `stmock<suffix>/mockapi-config/mockapi-1.json` and `mockapi-2.json`; an autosave failure retries persistence, not the already-active mutation. Infrastructure Hello World seeding uses the same client with `preserve_existing=True` to preserve user-edited `/hello` definitions by path and method.

The Bicep parameter `mockApiBaseUrls` can explicitly consume the infrastructure deployment's `mockApiDashboardUrls` output. When omitted, the existing infrastructure backend URLs supply the same origins. This keeps notebook infrastructure selection inside `NotebookHelper` and supports parallel app generations during private-network migration. The notebook never connects directly to Blob storage; only the MockAPI runtime needs private Blob connectivity.

MockAPI response bodies contain a static backend `index`, not a dynamic response-counter template. The traffic helper adds a client-observed success `count` per backend to notebook result bodies, restarting at 1 for each flow. This count excludes hidden APIM retries and is not a server-side lifetime counter. Raw MockAPI responses are not changed.

## 🧪 Test Matrix

The notebook exercises each load-balancing strategy with a dedicated test. Run order and run counts are fixed; behaviour varies by backend pool configuration and per-test sleep semantics.

| #   | Test                                 | API path                   | Runs | Expected behavior                                                                          |
| --- | ------------------------------------ | -------------------------- | ---- | ------------------------------------------------------------------------------------------ |
| 1   | Prioritized Distribution             | `/lb-prioritized`          | 15   | P1 first (index 0, observed count 1), then P2, then exhausted pool                         |
| 2   | Weighted (50/50)                     | `/lb-weighted-equal`       | 30   | Paced healthy traffic observes approximately equal shares across same-priority backends    |
| 3   | Weighted (80/20)                     | `/lb-weighted-unequal`     | 30   | Paced healthy traffic favors backend 0 across same-priority backends                       |
| 4   | Prioritized & Weighted               | `/lb-prioritized-weighted` | 25   | P1 first, then two equal-weight P2 members, followed by exhaustion                         |
| 5   | Prioritized & Weighted (500ms sleep) | `/lb-prioritized-weighted` | 20   | Same pool as flow 4, with time for rolling-window recovery                                 |
| 6   | Absolute-Time Retry-After Tracking   | `/lb-retry-tracked`        | 25   | Positive non-increasing pre-wait Retry-After; a 200 after the first exact Retry-After wait |
| 7   | 503-to-429 Error Handling            | `/lb-429-prioritized`      | 12   | At least one 429; Retry-After on every 429 and absent from every non-429 response          |

Tests 1-6 run in the _Verify Deployment_ cell; test 7 runs in the separate _Test 503-to-429 Error Handling_ cell. All charts apply a 95th-percentile cutoff when computing the mean so the cold-path first request does not skew the steady-state average.

The notebook waits four seconds before every flow, including the first and flows 6 and 7. This exceeds the shared three-second permit window and circuit-breaker duration, with a one-second buffer. Without isolation, an earlier flow can leave backend 0 unavailable and make a later priority flow start on a lower-priority backend. Concurrent traffic from other callers can still affect shared state.

Flows 2 and 3 send 30 requests spaced 700 ms apart. Even if every request selects the same backend, this pacing stays below its five-permit rolling-window capacity. This separates weight observation from exhaustion: equal budgets driven to exhaustion both produce five successes regardless of their weights, which cannot demonstrate an 80/20 share. Both weighted flows must have only successful responses and must exercise both backends; observed counts are printed without asserting an exact probabilistic ratio. Weighted selection is approximate, not guaranteed alternation, and APIM circuit-breaker state is gateway-local.

Flows 1 and 4 remain bursts that exercise priority and exhaustion; flow 5 keeps its 500 ms inter-request pause. Priority flows assert that the first successful request is backend 0. Flow 6 sleeps exactly each parseable 429 `Retry-After` value; its policy accepts backend delta-seconds and APIM pool HTTP-date headers, then emits integer seconds with a one-second recovery buffer. It reads the pool header even when a pool-generated 503 skips post-forward tracking or the cache is cold. Missing or malformed headers use the three-second sample window. The recovery assertion requires the very next request after the first wait to succeed, not merely an eventual success after more retries. Flow 7 preserves the backend header when present and falls back to the three-second window if APIM synthesizes a headerless 503.

**Expected error responses:** Burst flows deliberately exhaust five-permit backend budgets. They can return 429 or APIM-generated 503 once their pools are exhausted; the error-handling flows return 429. These HTTP errors are displayed, not hidden or treated as successful requests. Each structured flow must include successful backend traffic and contain only 200, 429, or 503 responses. An all-throttled flow fails its assertion instead of passing merely because the request count matches. The paced weighted flows additionally reject any throttling or server errors.

## ⚙️ Configuration

1. Decide which of the [Infrastructure Architectures](../../README.md#infrastructure-architectures) you wish to use.
    1. If the infrastructure _does not_ yet exist, navigate to the desired [infrastructure](../../infrastructure/) folder and follow its README.md.
    1. If the infrastructure _does_ exist, adjust the `user-defined parameters` in the _Initialize notebook variables_ below. Please ensure that all parameters match your infrastructure.
1. Run the initialization and deployment code cells in `create.ipynb`, then run verification, charts, and the final error-handling cell. The API prefix applies to all seven flows.
1. Keep the five-permit, three-second endpoint settings aligned with the APIM circuit-breaker duration and both policies' three-second fallback when experimenting. Rerun the sample deployment and backend configuration cells to apply changes; an infrastructure redeployment is not needed when its MockAPI image is already current.

## 🧹 Clean Up

The sample adds no containers or storage accounts. Its three namespaced endpoints remain in the infrastructure dashboards after the notebook finishes; remove only those endpoints if you no longer need the scenarios. Existing deployments may still contain the retired `ca-<suffix>-webapi429` container because incremental Bicep deployment does not delete old resources; after confirming the sample uses MockAPI, remove that retired container explicitly if desired. Use the selected infrastructure's clean-up notebook to remove the entire lab.
