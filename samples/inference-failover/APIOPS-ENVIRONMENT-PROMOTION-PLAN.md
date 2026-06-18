# Inference Failover APIOps Environment Promotion Plan

<!-- markdownlint-disable MD013 -->
<!-- Long technical prose and wide planning tables are intentionally not hard-wrapped. -->

**Audience:** API platform owners, AI platform owners, security teams, operations teams, and delivery teams planning promotion across development (DEV), quality assurance (QA), and production (PROD) environments.

## Summary

- Use one version-controlled API and policy release and promote it through three APIM instances: DEV on **Developer stv2.1**, then separate QA and PROD instances on **Premium stv2.1**.
- Keep API definitions and policy XML identical across environments.
- Keep the sample's environment-specific Azure OpenAI resources, concrete APIM backends, backend pools, service-level diagnostics, and workbook under Bicep ownership.
- Give every policy-facing backend pool a stable ID, and express scalar policy differences through APIOps publisher configuration files that override non-secret Named Value values.

The recommended ownership boundary is:

- **Infrastructure as Code (IaC)** provisions APIM services, Azure OpenAI accounts and model deployments, networking, managed identities, role assignments, Key Vaults, monitoring destinations, concrete APIM backends, backend pools, loggers, and service-level diagnostics.
- **APIOps** manages the portable release layer: APIs, operations, policies, policy fragments, API-level diagnostics, products where applicable, and Named Values used by those policies.

This boundary prevents Bicep and APIOps from trying to manage the same APIM child resource. IaC must finish and publish a validated environment manifest before APIOps runs.

The current sample already supports this split with minimal change. Its `apis` parameter defaults to an empty array, and the API module runs only when that array is non-empty. The existing notebook can continue passing APIs for the self-contained learning experience. An APIOps pipeline can deploy the same Bicep template with `apis: []`, leaving the routing substrate in place for APIOps to publish the APIs and policies afterward.

## Recommended Outcome

The target operating model has the following properties:

1. DEV, QA, and PROD each have a separate APIM service.
1. DEV uses Developer stv2.1; QA and PROD each use Premium stv2.1.
1. One immutable source commit represents the APIM release candidate.
1. The same commit is promoted from DEV to QA and then PROD.
1. DEV uses canonical artifacts by default; QA uses `configuration.qa.yaml`; PROD uses `configuration.prod.yaml`.
1. Policies contain no environment names, Azure OpenAI hostnames, subscription IDs, or region-specific conditions.
1. Stable pool IDs select the routing contract; Bicep contains the environment-specific backend and pool topology.
1. Environment-specific scalar policy settings use stable Named Value names.
1. Every promotion is validated before publication and verified after publication.
1. API and policy rollback uses an APIOps revert release; routing rollback uses the corresponding IaC release.

## Architecture

```text
                        APIOps configuration repository
                      APIs + policies + Named Values
                                      |
                 same reviewed commit promoted in sequence
                                      |
             +------------------+------------------+
             |                  |                  |
             v                  v                  v
         DEV APIM           QA APIM            PROD APIM
         Developer stv2.1   Premium stv2.1     Premium stv2.1
         canonical          configuration.qa   configuration.prod

  IaC provisions each APIM service, Azure OpenAI topology, identity,
  networking, RBAC, APIM backends and pools, and telemetry beforehand.
```

One release pipeline runs Bicep first, validates the target manifest, then publishes the same APIOps commit to that environment. Each stage has independent IaC parameters, APIM coordinates, publisher configuration, validation evidence, and rollback.

## Minimal-Change Sample Integration

The sample can support two profiles without forking the Bicep template:

| Profile                 | Bicep `apis` input      | Bicep responsibility                                                               | APIOps responsibility                                         |
| ----------------------- | ----------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| Self-contained learning | Existing notebook array | All sample resources, routing resources, APIs, policies, diagnostics, and workbook | None                                                          |
| APIOps promotion        | Empty array or omitted  | Azure resources, concrete APIM backends, pools, service diagnostics, and workbook  | APIs, operations, policies, API diagnostics, and Named Values |

The APIOps profile uses behavior already present in `main.bicep`: `inferenceApis` is conditional on a non-empty `apis` array. No backend or pool needs to be blank. Bicep should create each one as a valid, usable environment resource, and APIOps should treat the stable pool IDs as external dependencies.

For the current topology, no Bicep resource split or module move is required. If environments use different pool membership, the smallest optional enhancement is to expose the two existing pool member arrays as parameters with their current arrays as defaults. Environment parameter files can then select complete pool shapes without changing API policies or moving routing ownership to APIOps.

The Bicep resources do not need to change to produce the manifest. The pipeline can query the deployed APIM backends and pools after Bicep completes. Adding non-secret backend and pool outputs to `main.bicep` is a useful convenience, but it is an output-only enhancement rather than a resource redesign.

The APIOps profile is a CI/CD path rather than a notebook `Run All` path. With `apis: []`, Bicep correctly returns no API subscription outputs. Post-publication tests must obtain a pipeline-managed test subscription through a secure credential mechanism rather than expecting `apiOutputs` from Bicep. The existing notebook remains unchanged for the self-contained learning profile.

Because the APIOps artifact set intentionally omits Bicep-owned backends and pools, APIOps relationship validation cannot prove those external dependencies from artifacts alone. The wrapper pipeline must validate every policy `backend-id` against the Bicep manifest before invoking APIOps. For a publisher release that treats an absent backend artifact as a missing predecessor, do not enable strict artifact-only predecessor validation for this profile; replace that specific check with the manifest gate while retaining all other static and dry-run validation.

## Policy Contract

The two model-specific pool IDs already used by the sample are the correct stable boundary:

| Model          | Stable backend pool ID        |
| -------------- | ----------------------------- |
| `gpt-5.1`      | `inference-gpt-5-1-pool`      |
| `gpt-4.1-mini` | `inference-gpt-4-1-mini-pool` |

Each model route should commit a concrete policy artifact containing its literal pool ID. The policy must not contain the sample's build-time `BACKEND_POOL_ID` or `RETRY_COUNT` placeholders after APIOps onboarding.

For example, the canonical `gpt-5.1` policy should contain:

```xml
<set-backend-service backend-id="inference-gpt-5-1-pool" />
```

The retry count can remain environment-neutral by referencing a stable Named Value:

```xml
<retry count="{{inference-gpt-5-1-retry-count}}"
       interval="0"
       first-fast-retry="true"
       condition="...">
    <forward-request buffer-request-body="true" />
</retry>
```

Configure the Named Value as the plain numeric string `2` in all three APIM services. Named Value substitution can supply a complete policy attribute value, so APIM resolves the policy to `count="2"`. This is substitution, not a runtime `@(...)` policy expression.

Two retries permit three total attempts. This may already be more than sufficient for interactive traffic. The limit is intentionally independent of pool size: after the initial failure, two more failures against backends that were eligible moments earlier are sufficient evidence to stop. The circuit breakers remove failed members from subsequent selection, so probing every member is neither required nor guaranteed. Use conditional recovery by attempt and end-to-end latency to determine whether the value should be reduced to `1`; require workload evidence before increasing it above `2`.

The optional retry-tracked route uses the same retry-count Named Value and determines whether every attempt in the bounded chain returned `429`; it does not require a backend-count Named Value. Named Value names and display names must remain identical in all three APIM services.

Named Values are appropriate for scalar policy settings and secret references. Backend URLs, pool members, priority, and weight are properties of the Bicep-owned APIM backend resources and should remain in Bicep and its environment parameters, not be calculated in policy.

## Stable Backend Identity

The policy-facing pool IDs are the compatibility contract and must remain identical in all three APIM services. The concrete backend IDs are internal to the Bicep-owned routing layer because policies do not reference them directly.

The sample's current concrete IDs contain physical placement, such as `gpt-5-1-PTU-eastus2`. Retain those IDs when the corresponding region and routing role remain true in every environment. If a target maps the same slot to a different region or capacity product, a future Bicep cleanup can introduce environment-neutral logical backend IDs.

DEV may use fewer pool members when cost reduction is worth reduced fidelity. Keep QA production-like while allowing reviewed capacity differences from PROD. Bicep must always create a valid pool whose stable ID exists before APIOps publishes a policy that references it.

## Environment Model

The following topology is an illustrative starting point. Azure OpenAI model availability, capacity, data residency, latency, and cost requirements must determine the final regional choices.

| Concern                    | DEV                                      | QA                                      | PROD                                     |
| -------------------------- | ---------------------------------------- | --------------------------------------- | ---------------------------------------- |
| APIM service               | Separate DEV service                     | Separate QA service                     | Separate PROD service                    |
| APIM SKU                   | Developer stv2.1                         | Premium stv2.1                          | Premium stv2.1                           |
| Publisher configuration    | Canonical artifacts by default           | `configuration.qa.yaml`                 | `configuration.prod.yaml`                |
| Goal                       | Fast developer feedback                  | Production-like release qualification   | Customer traffic                         |
| Active backends per model  | At least two when demonstrating failover | Production-like topology                | Approved production topology             |
| Capacity                   | Lowest practical capacity                | Production placement; reviewed capacity | Capacity and resilience plan             |
| Pool shape                 | Preferred plus fallback                  | Production-like routing                 | Approved routing design                  |
| Retry count for each model | `2`                                      | `2`                                     | `2`                                      |
| Fault injection            | Allowed on isolated test routes          | Controlled fault and recovery tests     | Canary checks only                       |
| Approval                   | Team review                              | Platform and service owner approval     | Change approval and separation of duties |

Do not reduce DEV to a single backend if the sample must demonstrate failover. The fixed retry budget does not require four distinct backends, but at least two members are needed to observe cross-backend selection.

Because QA is isolated from PROD, it can run controlled fault and recovery tests against its own resources. Keep fault-injection controls out of PROD.

## Source Repository Layout

The exact root folder can follow the customer's APIOps bootstrap repository. The important distinction is between canonical APIM artifacts and environment overlays.

```text
samples/inference-failover/
  main.bicep
  apiops/
    artifacts/
      apis/
      namedValues/
    environments/
      configuration.qa.yaml
      configuration.prod.yaml
    manifests/
      development.infrastructure.json
      qa.infrastructure.json
      production.infrastructure.json
```

The `artifacts` directory is the source of truth for APIs and policy behavior. The overlay files are the source of truth for environment-specific Named Value properties. Bicep and its parameter files are the source of truth for backends, pool membership, priority, weight, and diagnostics. Infrastructure manifests are generated by the IaC pipeline and consumed by APIOps validation; they should not contain credentials.

## Publisher Configuration Pattern

The following example is illustrative APIOps publisher configuration, not a ready-to-run file. Routing resources are intentionally absent because Bicep owns them.

```yaml
namedValues:
    - name: inference-gpt-5-1-retry-count
      properties:
          displayName: inference-gpt-5-1-retry-count
          value: "2"
          secret: false
```

Apply the same pattern to `gpt-4.1-mini`. Keep the value at `2` unless telemetry supports reducing it to `1` or workload testing justifies a reviewed increase. Pool arrays no longer pass through APIOps publisher configuration, so APIOps array-merge behavior is not part of this sample profile.

## IaC And APIOps Ownership

| Resource or concern                             | IaC owner | APIOps owner | Notes                                                                         |
| ----------------------------------------------- | --------- | ------------ | ----------------------------------------------------------------------------- |
| APIM service and SKU                            | Yes       | No           | Must exist before publication.                                                |
| APIM networking and custom domains              | Yes       | No           | Includes private endpoints, certificates, DNS, and gateway ingress.           |
| Azure OpenAI accounts and deployments           | Yes       | No           | IaC validates model version, capacity, region, and quota.                     |
| APIM managed identity                           | Yes       | No           | Identity lifecycle remains with the APIM service.                             |
| Azure OpenAI and Key Vault role assignment      | Yes       | No           | Apply least privilege before smoke tests.                                     |
| Key Vault and secrets                           | Yes       | No           | APIOps stores only stable Key Vault references where required.                |
| Log Analytics, Application Insights, Event Hubs | Yes       | No           | IaC owns destinations and access.                                             |
| Concrete APIM backends                          | Yes       | No           | Existing Bicep modules own URLs, TLS, and circuit breakers.                   |
| APIM backend pools                              | Yes       | No           | Existing Bicep modules own membership, priorities, and weights.               |
| APIM loggers and service-level diagnostics      | Yes       | No           | Keeps the current Azure Monitor, Application Insights, and Event Hub wiring.  |
| APIs, operations, and products                  | No        | Yes          | Canonical, version-controlled APIM artifacts in APIOps mode.                  |
| API-level diagnostics                           | No        | Yes          | Travel with each API so Application Insights and LLM telemetry remain active. |
| Policies and policy fragments                   | No        | Yes          | One canonical policy release is promoted unchanged.                           |
| Named Values                                    | No        | Yes          | Stable names; environment values or Key Vault identifiers come from overlays. |

There must be no steady-state dual ownership. The APIOps artifact filter and repository layout must exclude backends, pools, loggers, and service-level diagnostics while retaining API-level diagnostics. In the self-contained learning profile, Bicep may still deploy APIs; in the APIOps profile, the pipeline must pass an empty `apis` array so only APIOps owns them and their child diagnostics.

## Infrastructure Contract

The IaC pipeline should publish a machine-readable manifest for each APIM deployment target. At minimum, it should identify:

- Subscription, resource group, and APIM service name.
- APIM gateway URL and managed identity principal ID.
- Azure OpenAI endpoint and deployment name for every concrete backend.
- Model name, model version, region, SKU, and capacity for each deployment.
- Concrete APIM backend IDs and their expected URLs.
- Stable pool IDs, complete member lists, priorities, weights, and active member counts.
- Required role assignment status.
- Key Vault secret identifiers used by APIM Named Values, if any.
- Logger and diagnostic destination resource IDs.
- Network and DNS readiness status.

The manifests must identify three distinct APIM resource IDs and map DEV, QA, and PROD to their corresponding services and manifests.

The APIOps pipeline should fail before publication when a policy references a pool absent from the manifest, the retry-count Named Value is missing or invalid, an endpoint is not HTTPS, a hostname is not in the approved Azure OpenAI allowlist, a model deployment is missing, or APIM's managed identity lacks the required role.

## Promotion Pipeline

### Pull Request Validation

1. Parse every JSON, YAML, and XML artifact.
1. Reject unresolved template tokens such as `BACKEND_POOL_ID` and `RETRY_COUNT`.
1. Validate that API, policy, and Named Value names are unique and every overlay uses a matching canonical artifact name.
1. Validate every policy `backend-id` against the expected pool IDs in each deployment-target manifest.
1. Validate that each retry-count Named Value resolves to the plain numeric string `2`, or to a reviewed bounded exception supported by workload evidence.
1. Validate the Bicep manifest's backend URLs by parsing scheme, hostname, port, and path components.
1. Validate positive priorities, valid weights, and model compatibility from the Bicep manifest.
1. Compare canonical policy content across deployment targets; overlays must not contain policy bodies.
1. Run APIOps with `DRY_RUN=true` using the validation mode approved for external Bicep-owned dependencies.
1. Produce one human-readable change summary containing the Bicep routing changes and the APIOps API, policy, and Named Value changes.

For Azure/apiops `v7.0.3`, `DRY_RUN=true` prevents resource writes and `STRICT_VALIDATION=true` makes a missing artifact predecessor fail instead of producing a warning. In this hybrid profile, a policy's backend pool is deliberately external to the APIOps artifact set. The pipeline must therefore use manifest validation for that relationship and confirm the pinned publisher's behavior before enabling strict artifact-only validation. Dry run does not prove that APIM will accept every property or that backend runtime access works, so it remains one gate rather than the final gate.

### Deployment Target Publication

1. Deploy or reconcile the target's infrastructure through IaC.
1. Generate and validate the infrastructure manifest.
1. Verify that the manifest contains both stable backend pool IDs expected by the policies.
1. Select the immutable APIOps artifact commit and matching Named Value overlay from the same reviewed source state.
1. Select the full or incremental publication mode described below.
1. Run APIOps dry run with manifest-backed dependency validation against the target configuration and selected mode.
1. Publish using a workload identity and the target APIM coordinates.
1. Verify the resulting APIM resources through management-plane reads.
1. Run gateway smoke tests and model-specific contract tests.
1. Record the commit SHA, APIOps version, overlay digest, IaC deployment ID, test result, and approver as release evidence.

### Promotion Sequence

| Stage | Required evidence before promotion                                                                                                     |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------- |
| DEV   | Static and manifest validation, dry run, publish success, deterministic failure tests, and basic gateway contracts                     |
| QA    | DEV evidence, full QA publication, production-like routing and recovery tests, security review, and telemetry validation               |
| PROD  | QA evidence, approved change record, capacity and quota confirmation, rollback readiness, canary test, and post-publication monitoring |

Promote the same commit without rebuilding or re-extracting artifacts. A change after DEV or QA creates a new candidate that restarts promotion. QA and PROD each receive a separate publication with their own reviewed configuration and APIM coordinates.

### Publication Modes

The pipeline must choose publication mode deliberately:

| Scenario                                              | Mode                                 | Reason                                                                                                                                                                 |
| ----------------------------------------------------- | ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| First APIOps publication to a target                  | Full publish without `COMMIT_ID`     | The target does not yet contain the parent desired state; processing one commit might omit unchanged dependencies and baseline artifacts.                              |
| Normal artifact release to a synchronized environment | Incremental publish with `COMMIT_ID` | The target already matches the candidate commit's parent; APIOps can process the artifacts changed by the candidate commit.                                            |
| Canonical artifact deletion                           | Incremental publish with `COMMIT_ID` | The publisher needs the parent commit to identify and order deletions.                                                                                                 |
| Configuration-only change on `v7.0.3`                 | Commit-aware if fully covered        | Publisher processes artifact-backed resources explicitly named in configuration. Use a full publication when coverage is uncertain.                                    |
| Deliberate full reconciliation                        | Full publish without `COMMIT_ID`     | Re-applies the complete canonical artifact set plus the selected overlay; use with separate drift review because it does not infer deleted artifacts from Git history. |

Before a commit-aware promotion, verify that the target's recorded release is the candidate commit's parent. If it is not, either apply the missing releases in order or run an approved full reconciliation and separately account for deletions.

The publisher-scope limitation behind this rule is discussed in [Azure/apiops issue #789](https://github.com/Azure/apiops/issues/789) and clarified in [issue #659](https://github.com/Azure/apiops/issues/659): publisher configuration supplies property overrides rather than a native resource allowlist. [Issue #154](https://github.com/Azure/apiops/issues/154) tracks the related gap between publishing one commit and publishing the full repository, while [issue #773](https://github.com/Azure/apiops/issues/773) clarifies commit-aware deletion behavior. In this hybrid plan, those issues explain API artifact publication only; Bicep remains the owner of backends and pools, so the backend staging script is not part of this profile.

## Dependency And Publication Behavior

APIOps still orders dependencies that are inside its artifact set, such as Named Values referenced by policies. Bicep-owned backend pools are external predecessors: Bicep creates them before APIOps starts, and the manifest gate proves that each expected stable ID exists with the intended topology.

The onboarding proof of concept must exercise this external-dependency profile against the pinned APIOps release. It must verify that Bicep completes first, manifest validation catches a missing or renamed pool, dry run succeeds with the selected validation settings, APIM accepts the policy, and the gateway reaches only the model-compatible members recorded in the manifest.

## Validation Strategy

### Management-Plane Checks

- Every expected API, policy, Named Value, backend, pool, logger, service diagnostic, and API diagnostic exists under its designated owner.
- Every concrete backend URL matches the environment manifest exactly.
- Every pool's members, priorities, and weights match the Bicep manifest.
- No pool references a backend from another model.
- Policy files resolve to the expected static pool IDs.
- Named Value display names and resolved non-secret values match the environment contract.
- Circuit-breaker settings are present on each concrete backend.
- APIM managed identity role assignments exist for every active Azure OpenAI resource.

### Gateway Contract Checks

- Healthy requests return `200` and report zero retries.
- Client errors remain client errors and do not cause failover.
- Capacity and transient infrastructure failures move to the next eligible backend.
- Exhausted capacity keeps the final `429` contract.
- Exhausted infrastructure and transport failures return the generic `503` contract.
- A model route never reaches a backend for a different model.
- `X-Backend-Retry`, APIM gateway logs, trace records, and LLM telemetry remain consistent.

Use controlled fault origins in DEV and QA. Do not expose fault-injection controls on production inference routes.

### Policy Equality

Compute a source hash for each canonical policy file and attach it to the release evidence for all three APIM targets. After publication, compare normalized XML semantics because management-plane serialization can alter insignificant formatting.

## Security And Separation Of Duties

- Use workload identity federation for pipelines; do not store long-lived Azure credentials in repository secrets.
- Give the APIOps publisher identity the least privilege required on the target APIM service scope.
- Use a different infrastructure deployment identity for Azure OpenAI, networking, role assignments, and Key Vault provisioning.
- Require protected environment approval for QA and production.
- Prevent the same unapproved principal from changing source, approving production, and publishing production.
- Keep credentials and secret values out of artifacts and overlays.
- Prefer APIM managed identity for Azure OpenAI access, as the sample already does.
- Use Key Vault-backed Named Values when a secret is unavoidable.
- Treat diagnostic destinations as sensitive because LLM prompt or completion content may be enabled.
- Retain immutable pipeline logs and deployment evidence according to the customer's audit policy.

## Drift Management

Git is the desired-state source of truth. Portal changes should be restricted in QA and production and treated as emergency exceptions.

Run a scheduled drift job that reads the managed APIM resource types and compares each one with its designated source: backends, pools, loggers, and service-level diagnostics against the Bicep manifest; APIs, policies, API-level diagnostics, and Named Values against the APIOps artifacts plus environment overlay. The job should report drift but must not automatically commit production state or overwrite either desired-state source.

For an approved emergency portal change:

1. Record the incident or emergency change reference.
1. Reproduce the intended change in Bicep or APIOps according to the ownership table.
1. Review and merge it normally.
1. Republish and verify the managed resource.
1. Confirm that the drift report is clear.

## Rollback

API or policy rollback is a forward-moving APIOps Git revert:

1. Create a new commit that restores the last known-good API, policy, and Named Value state.
1. Review the generated APIOps change summary.
1. Run manifest validation and APIOps dry run.
1. Publish the revert commit to the affected APIM target.
1. Run smoke tests and confirm telemetry recovery.

Routing rollback is an IaC deployment that restores the last known-good Bicep parameters and backend-pool topology, followed by the same manifest and gateway checks. When a release changes both layers, roll back in dependency order: restore Bicep routing first, verify the manifest, then restore the APIOps policy release if needed.

Use commit-aware APIOps publication for changes that delete canonical API artifacts so the publisher can process removals relative to the parent commit. Use a full publication for an overlay-only Named Value revert unless the pinned APIOps release and pipeline wrapper have been proven to map configuration-file changes to affected artifacts. Do not use a force push or move a branch pointer backward as the operational rollback mechanism.

Keep Azure OpenAI deployments available through the rollback window. Removing an old deployment immediately after promotion can make an otherwise valid APIM configuration rollback impossible.

For a routing-only incident, an expedited IaC revert can restore the previous backend URLs or pool membership. It must still pass referential, URL, model compatibility, manifest, and gateway checks.

## Adoption Roadmap

| Phase | Objective                    | Key activities                                                                                                                                             | Exit criteria                                                                          |
| ----- | ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| 0     | Confirm decisions            | Confirm the three-service topology, APIOps release, CI/CD platform, stable pool contract, ownership boundary, and approvals.                               | Architecture decision record approved with no unresolved ownership questions.          |
| 1     | Prove mechanics in a sandbox | Deploy Bicep with `apis: []`, generate a manifest, publish one API and its Named Values, then test validation, dry run, readback, and rollback.            | Repeatable publication and rollback pass without moving Bicep-owned routing resources. |
| 2     | Onboard DEV                  | Normalize APIs, policies, and Named Values, remove placeholders, and establish the combined Bicep-then-APIOps pipeline.                                    | DEV on Developer stv2.1 is reproducible from Git and its drift report is clear.        |
| 3     | Onboard QA                   | Add `configuration.qa.yaml`, validate the QA manifest, publish to Premium stv2.1, and run production-like routing, failure, security, and telemetry tests. | One immutable candidate passes QA with complete evidence.                              |
| 4     | Onboard PROD                 | Add `configuration.prod.yaml`, validate quota and identity, rehearse rollback, publish the QA-tested candidate, run canaries, and monitor.                 | Production publication and revert are demonstrated; operating procedures are approved. |
| 5     | Operate and improve          | Schedule owner-aware drift checks, review permissions, track APIOps upgrades, test disaster recovery, and tune capacity using telemetry.                   | Regular evidence review and upgrade cadence are owned by named teams.                  |

During Phase 2, the existing Bicep backend, pool, diagnostic, and workbook declarations remain in place. The only deployment-mode change is that the APIOps pipeline supplies an empty `apis` array. The notebook's current self-contained path remains available for learning and demonstration.

## Risk And Control Matrix

| Status   | Risk                                                     | Impact | Effort | Required control                                                                                                        |
| -------- | -------------------------------------------------------- | ------ | ------ | ----------------------------------------------------------------------------------------------------------------------- |
| 🔴 Red   | Bicep and APIOps both manage the same API child resource | High   | Low    | Exclude routing artifacts from APIOps and pass `apis: []` to Bicep in APIOps mode.                                      |
| 🔴 Red   | A pipeline publishes to the wrong APIM instance          | High   | Low    | Verify subscription, resource group, APIM name, configuration digest, and protected environment before every write.     |
| 🔴 Red   | Bicep maps a pool member to an incompatible model        | High   | Medium | Validate manifest model/version metadata before publication and run model-specific smoke tests.                         |
| 🔴 Red   | Production has insufficient quota or missing RBAC        | High   | Low    | Make capacity, deployment existence, network readiness, and managed identity access pre-publication gates.              |
| 🟠 Amber | APIOps cannot validate an external pool from artifacts   | High   | Low    | Validate policy pool IDs against the validated Bicep manifest and prove publisher settings in a disposable environment. |
| 🟠 Amber | QA does not represent production routing                 | Medium | Medium | Keep QA production-like and document intentional differences from PROD.                                                 |
| 🟠 Amber | Manual portal changes create drift                       | Medium | Medium | Restrict write access, run scheduled normalized comparisons, and reconcile emergency changes through Git.               |
| 🟠 Amber | Retry count is increased to probe a larger pool          | Medium | Low    | Keep the Named Value at `2`; note that it may already be more than sufficient and require evidence for any increase.    |
| 🟢 Green | Stable pool IDs isolate policy from topology changes     | High   | Low    | Protect pool names as a compatibility contract and block renames without an explicit migration.                         |
| 🟢 Green | Immutable promotion provides traceability                | High   | Low    | Record commit, overlay digest, APIOps version, IaC deployment, test evidence, and approval for every stage.             |

## Customer Decisions Required

Before implementation starts, the customer must approve:

1. The Azure subscription and resource group placement for DEV, QA, and PROD APIM services.
1. The APIOps release to pin and the upgrade cadence.
1. The definitive hybrid ownership boundary and APIOps artifact filter.
1. The stable policy-facing pool IDs.
1. The production backend topology, regions, model versions, capacity types, priorities, and weights.
1. Which topology differences are acceptable among DEV, QA, and PROD.
1. The required QA fidelity, controlled fault tests, and evidence before PROD promotion.
1. Whether optional Bicep pool-array parameters are needed for environment-specific pool shapes.
1. Whether the optional retry-tracked API is in promotion scope.
1. The Named Values that may vary by environment and which must use Key Vault.
1. The approval, separation-of-duties, and emergency change process.
1. The required smoke, failure, performance, security, and rollback evidence.
1. The drift detection schedule and operational ownership.

## Acceptance Criteria

The APIOps design is ready for production adoption only when:

- The inventory records three distinct APIM services: DEV on Developer stv2.1, QA on Premium stv2.1, and PROD on Premium stv2.1.
- The same canonical policy files are promoted through DEV, QA, and PROD.
- No policy contains environment-specific branches, hostnames, regions, or secrets.
- Pool and Named Value names are identical in all three APIM services.
- DEV, QA, and PROD resolve to distinct APIM resource IDs and environment manifests.
- Backend URLs and pool arrays differ only through reviewed Bicep source and parameters.
- Every APIM-owned artifact has exactly one deployment owner.
- IaC readiness checks pass before APIOps begins.
- Manifest relationship validation, dry run, publication, management-plane verification, and gateway smoke tests pass.
- DEV deterministic failover tests cover recovery and exhausted behavior.
- QA proves the production-like routing, failure, security, and observability contracts before PROD publication.
- Owner-specific Git reverts restore the previous known-good routing and API configuration without manual portal repair.
- Drift detection identifies an out-of-band change and the team successfully reconciles it through source control.

## Vetting Notes

This plan was checked against the current inference-failover sample, the APIM backend pool resource model, and the Azure/apiops publisher implementation. The sample already allows Bicep API deployment to be skipped by supplying an empty `apis` array, while its existing backend, pool, diagnostic, and workbook resources remain deployable. The review also confirmed that APIOps can discover policy-to-backend relationships from its artifact set, which is why this hybrid profile requires a manifest gate for the deliberately external Bicep-owned pools.

The design must still be proven against the exact APIOps release selected by the customer. At the time of this review, Azure/apiops `v7.0.3` was the latest published release. Pin a version rather than following a floating latest build, and repeat the sandbox proof when upgrading.

## References

- [APIOps Toolkit for Azure API Management](https://github.com/Azure/apiops)
- [APIOps publisher configuration](https://github.com/Azure/apiops/wiki/Configuration)
- [Azure/apiops #789 - Selectively publish APIs across APIM environments](https://github.com/Azure/apiops/issues/789)
- [Azure/apiops #659 - Publisher configuration does not select resources](https://github.com/Azure/apiops/issues/659)
- [Azure/apiops #773 - Commit-aware deletion and full-publication behavior](https://github.com/Azure/apiops/issues/773)
- [Azure/apiops #154 - Changes between two environment deployments](https://github.com/Azure/apiops/issues/154)
- [Automated API deployments using APIOps](https://learn.microsoft.com/azure/architecture/example-scenario/devops/automated-api-deployments-apiops)
- [Backends in Azure API Management](https://learn.microsoft.com/azure/api-management/backends)
- [Named Values in Azure API Management](https://learn.microsoft.com/azure/api-management/api-management-howto-properties)
- [Retry policy reference](https://learn.microsoft.com/azure/api-management/retry-policy)
- [Set backend service policy reference](https://learn.microsoft.com/azure/api-management/set-backend-service-policy)
