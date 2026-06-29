# Terraform and APIOps Environment Operations Plan

<!-- markdownlint-disable MD013 -->
<!-- Long technical prose and wide planning tables are intentionally not hard-wrapped. -->

**Audience:** API platform, infrastructure, AI platform, security, and delivery teams that use Terraform and APIOps for Azure API Management (APIM).

---

## Contents

Main plan:

- [1. Purpose](#1-purpose)
- [2. Plan at a Glance](#2-plan-at-a-glance)
- [3. Key Terms](#3-key-terms)
- [4. What Stays the Same and What Changes](#4-what-stays-the-same-and-what-changes)
- [5. Ownership](#5-ownership)
- [6. Required Files](#6-required-files)
- [7. Terraform Manifest](#7-terraform-manifest)
- [8. Decisions Before Implementation](#8-decisions-before-implementation)
- [9. Implementation Plan](#9-implementation-plan)
- [10. Adding Another Regional APIM Service](#10-adding-another-regional-apim-service)
- [11. Release Checks](#11-release-checks)
- [12. Rollback and Emergency Changes](#12-rollback-and-emergency-changes)
- [13. Acceptance Criteria](#13-acceptance-criteria)

Appendices and references:

- [14. Transferring Ownership from Terraform](#14-transferring-ownership-from-terraform)
- [15. APIOps Publication Modes](#15-apiops-publication-modes)
- [16. Retry Count](#16-retry-count)
- [17. Risk and Control Matrix](#17-risk-and-control-matrix)
- [18. References](#18-references)

---

## 1. Purpose

- **Primary objective:** Establish a simple, robust, and efficient way to create, change, validate, release, and recover APIM environments through Infrastructure as Code (IaC).
- **Simple:** Use one repeatable environment pattern, clear ownership, and the fewest target-specific files needed to describe an APIM service.
- **Robust:** Validate infrastructure and APIM configuration together, prevent conflicting ownership, stop incorrect deployments before they write, and provide a tested rollback path.
- **Efficient:** Reuse shared configuration, automate environment checks, avoid manual portal changes, and add an environment by supplying only its infrastructure and target-specific values.
- **Consistent:** Apply the same workflow to the first East US 2 environment and to every environment added later.

> **Desired outcome:** An environment is represented by reviewed IaC and APIOps files, deployed by a repeatable pipeline, verified against its intended state, and recoverable without manual reconstruction.

The initial implementation uses one APIM service, `prod-eus2-01`, in East US 2. Shared APIs, policies, and backend definitions are reused across environments; only values that genuinely belong to one target, such as its APIM identity and backend-pool order, vary. These routing details support the operating model but are not its primary purpose.

---

## 2. Plan at a Glance

- **Repeatable environments:** Use the same IaC and APIOps workflow for every independently managed APIM service.
- **Clear ownership:** Assign every resource to Terraform or APIOps, never both.
- **Small differences:** Share common configuration and isolate only genuine target-specific values.
- **Safe releases:** Bind each target to an exact APIM resource, validate before writing, and record release evidence.
- **Predictable recovery:** Keep a last known-good release and test rollback before the environment is accepted.
- **Additive growth:** Add a target entry, manifest, and configuration without changing existing environment files.

For this scenario, independently managed environments use **independent APIM services**. Adding a gateway region to one Premium APIM service does not create a separate backend-pool configuration. Two regions can use different pool priorities only when they use separate APIM services.

---

## 3. Key Terms

- **Environment:** One independently managed APIM service and its supporting Azure resources, desired configuration, release history, and rollback point.
- **APIOps:** A toolkit that publishes APIM configuration from source-controlled files.
- **Shared artifact:** A source-controlled APIOps file that defines an API, policy, Named Value, concrete backend, or stable backend-pool resource. Shared artifacts are published to every target. A shared pool artifact provides the pool ID; target configuration provides its complete member list.
- **Concrete backend:** An APIM resource that describes one Azure OpenAI endpoint, including its URL, authentication, TLS settings, and circuit breaker.
- **Backend pool:** An APIM resource that groups concrete backends and assigns their priorities and weights.
- **Deployment target:** One APIM service and the files, release record, lock, and rollback point used to manage it.
- **Deployment lock:** Pipeline concurrency control keyed by the APIM resource ID. It prevents two releases from changing the same APIM service at the same time.
- **Terraform manifest:** A non-secret machine-readable description of the infrastructure that Terraform deployed. APIOps uses it to validate the target before publication.

---

## 4. What Stays the Same and What Changes

| Configuration                            | Shared Across Targets | Target-Specific |
| ---------------------------------------- | :-------------------: | :-------------: |
| API and policy files                     |          Yes          |       No        |
| Concrete backend IDs and properties      |          Yes          |       No        |
| Backend pool IDs                         |          Yes          |       No        |
| Retry-count Named Value                  |          Yes          |       No        |
| APIM service name and resource ID        |          No           |       Yes       |
| Pool membership, priority, and weight    |          No           |       Yes       |
| Deployment lock, release, and rollback   |          No           |       Yes       |

For example, both APIM services can contain the same concrete backend definitions, shown here with the illustrative IDs `gpt-5-1-PTU-eastus2` and `gpt-5-1-PTU-westus3`. The stable pool ID remains the same while each target changes only the pool priorities:

| Target         | Backend Pool ID          | `gpt-5-1-PTU-eastus2` Priority | `gpt-5-1-PTU-westus3` Priority |
| -------------- | ------------------------ | ------------------------------ | ------------------------------ |
| `prod-eus2-01` | `inference-gpt-5-1-pool` | `1`                            | `2`                            |
| `prod-wus3-01` | `inference-gpt-5-1-pool` | `2`                            | `1`                            |

The concrete backend IDs are examples and can follow the organization's naming convention. The policy references the stable pool ID in both services and does not contain regional routing logic.

---

## 5. Ownership

| Resource or Concern                                      | Owner                |
| -------------------------------------------------------- | -------------------- |
| APIM service, SKU, network, identity, and custom domains | Platform/IaC team    |
| Azure OpenAI accounts, deployments, and access roles     | Platform/IaC team    |
| Key Vault, monitoring, DNS, and private access           | Platform/IaC team    |
| APIs, operations, products, and subscriptions            | APIOps delivery team |
| Policies, fragments, diagnostics, and Named Values       | APIOps delivery team |
| Concrete APIM backends and backend pools                 | APIOps delivery team |

> **Single-owner requirement:** Terraform and APIOps must not retain steady-state ownership of the same APIM backend or pool. If Terraform currently manages these resources, complete the controlled no-destroy transfer in [Section 14](#14-transferring-ownership-from-terraform) before normal APIOps management begins.

---

## 6. Required Files

The APIOps repository needs the following target-related files:

```text
artifacts/
  apis/
  backends/
    <concrete-backend-id>/
    <stable-pool-id>/
  namedValues/
configuration.prod-eus2-01.yaml
deployment-targets.yaml
manifests/
  prod-eus2-01.infrastructure.json
```

### 6.1 Target Registry

The registry maps a target ID to exactly one APIM service, target configuration, and Terraform manifest:

```yaml
targets:
  prod-eus2-01:
    environment: prod
    apimResourceId: /subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.ApiManagement/service/apim-prod-eus2-01
    apimServiceName: apim-prod-eus2-01
    gatewayRegion: eastus2
    configurationPath: configuration.prod-eus2-01.yaml
    terraformManifestPath: manifests/prod-eus2-01.infrastructure.json
```

> **Target safety requirement:** Select a target only by its target ID. Never infer it from a branch, environment, or region. Before writing to APIM, confirm that the target ID, exact APIM resource ID, target configuration, Terraform manifest, and approved source commit belong to the same release. Any mismatch must stop publication.

### 6.2 East US 2 Pool Configuration

The concrete backend artifacts and retry-count Named Value are shared. The East US 2 target configuration supplies only the complete pool member list:

```yaml
apimServiceName: apim-prod-eus2-01

backends:
    - name: inference-gpt-5-1-pool
      properties:
          pool:
              services:
                  - id: /backends/gpt-5-1-PTU-eastus2
                    priority: 1
                    weight: 100
                  - id: /backends/gpt-5-1-PTU-westus3
                    priority: 2
                    weight: 100
```

Apply the same pattern to each model pool.

For a more complete publisher configuration based on this repository's inference-failover sample and `inference-api-policy.xml`, see [configuration.prod-eus2-01.sample.yaml](configuration.prod-eus2-01.sample.yaml). The example includes all nine concrete backends across East US 2, West US 3, and South Central US; both model-safe pools; TLS validation; the sample's circuit breaker; and retry-count Named Values. Its Azure OpenAI account hostnames are illustrative and must be replaced with endpoints from the validated Terraform manifest.

APIOps `v7.0.3` treats this YAML as a property override. Matching canonical `backendInformation.json` artifacts must still exist under `artifacts/backends/`; the YAML file alone is not an artifact inventory and cannot create an otherwise undiscoverable backend.

When an environment should receive only a subset of the canonical backend artifacts, use the tested [PowerShell staging script](prepare-apiops-artifacts.ps1) and follow the [APIOps environment backend filtering guide](APIOPS-BACKEND-FILTERING-GUIDE.md). This pre-publisher control treats the target configuration's top-level `backends` entries as an allowlist, validates pool and policy references, and passes a filtered temporary tree to the APIOps publisher without modifying the source artifacts.

This design is a backend-specific implementation of the temporary filtered-tree workaround discussed in [Azure/apiops issue #789](https://github.com/Azure/apiops/issues/789). It is a repository-owned preprocessing control, not a built-in APIOps resource-selection feature. [Issue #659](https://github.com/Azure/apiops/issues/659) documents the underlying distinction: publisher configuration overrides artifact properties, while artifact visibility or commit changes determine which resources the publisher processes.

> **Complete-array requirement:** APIOps replaces `properties.pool.services` as a whole. It does not update one member and keep the others. If an override lists only East US 2, the deployed pool will contain only East US 2. Every target configuration must list every member that should remain in the pool.

---

## 7. Terraform Manifest

Terraform produces one non-secret manifest for each target. The manifest describes available infrastructure; it does **not** own pool membership or priority.

The manifest must contain:

- Target ID, subscription, resource group, APIM resource ID, service name, gateway URL, region, and managed identity.
- Azure OpenAI endpoint, deployment name, model, version, region, SKU, and capacity for every concrete backend.
- Approved backend destinations and network, DNS, role assignment, Key Vault, and monitoring readiness.

The APIOps pipeline compares shared backend artifacts and target pool configuration with this manifest. It stops when:

- A backend endpoint or model does not match deployed infrastructure.
- A pool refers to a backend that is missing, incompatible, or not approved for the target.
- The APIM service identity or target ID does not match the registry.
- Required networking or Azure roles are not ready.
- The retry-count Named Value is missing or invalid.

> **Security requirement: Never place credentials or secret values in the manifest.** The manifest may contain resource identifiers and readiness status, but authentication material belongs in Key Vault or the pipeline's approved secret store. Manifest generation must fail rather than emit a credential.

---

## 8. Decisions Before Implementation

The platform owner and APIOps delivery owner must approve:

- [ ] The exact `prod-eus2-01` APIM resource ID and target name.
- [ ] The Terraform, provider, and APIOps versions. This plan is verified against APIOps `v7.0.3`.
- [ ] APIOps ownership of concrete backends and pools, including any required Terraform transfer.
- [ ] Stable backend IDs, pool IDs, and Named Value names.
- [ ] The complete set of shared concrete backends.
- [ ] The manifest generation and storage approach.
- [ ] Required reviewers, release evidence, drift-check schedule, and rollback approval.

Implementation must not begin while ownership or target identity is unresolved.

---

## 9. Implementation Plan

The team names below describe responsibilities. One team may perform more than one role, but each action must have a named owner. The five phases move from confirming the current state to steady-state operation, and each phase records a named owner and an exit gate that must pass before the next phase begins.

| Phase                              | Focus                                                         | Primary Owner                         |
| ---------------------------------- | ------------------------------------------------------------- | ------------------------------------- |
| 1. Confirm Current State           | Inventory resources and assign a single owner to each         | Platform/IaC with APIOps delivery     |
| 2. Build the Desired Configuration | Author shared artifacts, the manifest, and target files       | APIOps delivery                       |
| 3. Prove the Process in a Sandbox  | Validate publish, failover, and rollback on a disposable APIM | APIOps delivery with AI service owner |
| 4. Onboard East US 2               | Publish to production and record release evidence             | Release owner                         |
| 5. Operate the Target              | Run drift checks, telemetry reviews, and rollback drills      | API platform operations               |

### 9.1 Phase 1: Confirm Current State

**Owner:** Platform/IaC team with the APIOps delivery team.

**Inputs:** Terraform state, deployed East US 2 APIM resources, current APIOps files, and pinned tool versions.

**Actions:**

1. Record the exact APIM resource ID and assign `prod-eus2-01`.
1. Inventory APIs, policies, Named Values, concrete backends, and pools.
1. Record the current owner and future owner of each resource.
1. Approve the stable backend IDs, pool IDs, and shared backend inventory.
1. Identify any backends or pools that must move from Terraform to APIOps.

**Output:** Approved target record, resource inventory, ownership map, and version list.

**Exit gate:** Every resource has one future owner, and the APIM target is unambiguous.

### 9.2 Phase 2: Build the Desired Configuration

**Owner:** APIOps delivery team; Platform/IaC team supplies the manifest.

**Inputs:** Approved output from Phase 1.

**Actions:**

1. Create shared artifacts for APIs, policies, Named Values, concrete backends, and stable pools.
1. Generate the non-secret Terraform manifest for `prod-eus2-01`.
1. Create `deployment-targets.yaml` and `configuration.prod-eus2-01.yaml`.
1. Add pipeline checks for target identity, backend destinations, model compatibility, and complete pool arrays.
1. Transfer Terraform-owned backends or pools only when required; follow [Section 14](#14-transferring-ownership-from-terraform).

**Output:** Reviewable APIOps files, target registry, target configuration, manifest, and validation results.

**Exit gate:** All files parse, all references resolve, the pool arrays are complete, backend destinations match the manifest, and no resource has two owners.

### 9.3 Phase 3: Prove the Process in a Sandbox

**Owner:** APIOps delivery team with the AI service owner.

**Inputs:** Phase 2 files and a disposable APIM service.

**Actions:**

1. Run APIOps validation and dry run.
1. Perform the first full publication.
1. Read the deployed state through the Azure management API and compare it with the approved files.
1. Send healthy requests and confirm the preferred backend is used.
1. Simulate an eligible failure and confirm traffic moves to a compatible fallback.
1. Revert to the previous release and prove rollback.

**Output:** Publication log, deployed-state comparison, gateway test results, telemetry evidence, and rollback evidence.

**Exit gate:** Publication, readback, healthy traffic, failover, telemetry, and rollback all pass without manual portal repair.

### 9.4 Phase 4: Onboard East US 2

**Owner:** Release owner coordinates the Platform/IaC and APIOps delivery teams.

**Inputs:** Approved Phase 3 evidence and a release change record.

**Actions:**

1. Reconcile Terraform-owned infrastructure and generate the production manifest.
1. Validate the target registry, manifest, and configuration as one release.
1. Review the full publication summary and obtain approval.
1. Publish to the exact `prod-eus2-01` APIM resource ID.
1. Run deployed-state checks, gateway smoke tests, failover checks, and telemetry checks.
1. Record the source commit, target ID, APIM resource ID, file digests, tool versions, tests, and approver.

**Output:** Reproducible East US 2 deployment and complete release record.

**Exit gate:** The service matches the approved configuration, tests pass, and rollback remains available.

### 9.5 Phase 5: Operate the Target

**Owner:** API platform operations team.

**Actions:**

1. Compare deployed APIM configuration with source-controlled files on the approved schedule. This is the drift check.
1. Investigate and correct any difference that was not produced by an approved release.
1. Retest publication and rollback before changing the pinned APIOps version.
1. Review retry and failover telemetry before changing retry count or pool order.
1. Rehearse rollback at the agreed operational interval.

**Output:** Drift reports, upgrade evidence, routing reviews, and rollback drill records.

**Exit gate:** Named owners resolve drift and failed checks within the agreed operational process.

---

## 10. Adding Another Regional APIM Service

Add a regional target only after East US 2 is operating successfully.

**Owner:** Platform owner and release owner.

**Actions:**

1. Provision the independent APIM service, identity, networking, and access through Terraform.
1. Assign a target ID using `<environment>-<region>-<ordinal>`, for example `prod-wus3-01`.
1. Generate the target's Terraform manifest.
1. Append one registry entry. Do not modify the existing East US 2 entry.
1. Add `configuration.prod-wus3-01.yaml` with complete pool arrays. Set West US 3 to priority `1` and East US 2 to priority `2` when that is the approved routing order.
1. Publish the same shared APIOps artifacts and policy files.
1. Use a separate deployment lock, release record, test result, and rollback point.
1. Prove that publishing or rolling back one APIM service does not change the other.

**Exit gate:** The new APIM service uses the approved local-first pool order, existing target files remain unchanged, and both services can be released and rolled back independently.

---

## 11. Release Checks

**Owner:** The APIOps delivery team runs the checks. The release owner approves publication and stops the release when any required check fails.

### 11.1 Before Publication

- [ ] Confirm the exact target ID and APIM resource ID.
- [ ] Parse all JSON, YAML, and XML files and reject unresolved placeholders.
- [ ] Confirm that every policy, pool member, backend, and Named Value reference exists.
- [ ] Compare backend URL components and model metadata with the Terraform manifest.
- [ ] Confirm that each target pool contains its complete approved member list.
- [ ] Run APIOps validation and dry run.
- [ ] Review the complete change summary and selected publication mode. See [Section 15](#15-apiops-publication-modes).

### 11.2 After Publication

- [ ] Read back backend URLs, TLS settings, circuit breakers, pool members, priorities, weights, Named Values, and policy references through the Azure management API.
- [ ] Confirm healthy requests return `200` and client errors do not trigger backend retries.
- [ ] Confirm eligible capacity and transient failures move to compatible pool members.
- [ ] Confirm exhausted retries preserve the expected `429` and `503` responses.
- [ ] Confirm retry, Application Insights, and LLM diagnostic telemetry is available.
- [ ] Store the release evidence listed in Phase 4.

> **Verification requirement:** A dry run does not prove that APIM accepts the configuration or that runtime access works. A release is not complete until deployed-state checks and gateway tests both pass.

---

## 12. Rollback and Emergency Changes

**Owner:** The release owner authorizes rollback. The APIOps delivery team performs it with support from the API platform operations team.

**Inputs:** A failed release check or service incident, an approved rollback decision, and the last known-good release record.

**Actions:**

1. Revert the affected shared artifacts or target configuration.
1. Run the same pre-publication checks used for a normal release.
1. Publish only to the affected APIM resource ID.
1. Run deployed-state and gateway checks.
1. Record the rollback release and its approval.

**Output:** Rollback commit, publication log, deployed-state comparison, gateway test results, and updated incident or change record.

**Exit gate:** Deployed state matches the last known-good release, gateway checks pass, and the incident owner confirms service recovery.

> **Rollback requirement:** Keep previous Azure OpenAI deployments available for the entire agreed rollback window. Routing cannot return to a backend that Terraform has already removed.

The incident owner determines when an emergency portal change is required. Restore service first, then assign an owner to reproduce the change in the correct source repository, review it, and republish it. Do not automatically treat extracted production state as approved source.

---

## 13. Acceptance Criteria

The plan is complete when:

- [ ] The same documented IaC and APIOps workflow can create, change, validate, release, and recover an APIM environment without manual reconstruction.
- [ ] Terraform and APIOps have documented, non-overlapping ownership.
- [ ] `prod-eus2-01` maps to one APIM resource ID, manifest, target configuration, deployment lock, release record, and rollback point.
- [ ] Shared artifacts contain every approved concrete backend, stable pool, policy, and Named Value.
- [ ] Target configuration contains only complete pool arrays; concrete backend definitions remain shared and unchanged.
- [ ] Backend destinations match Terraform-provisioned infrastructure.
- [ ] Validation, dry run, full publication, deployed-state checks, gateway tests, telemetry checks, and rollback pass.
- [ ] Drift checks detect changes made outside the approved release process.
- [ ] A future environment can be added through the same workflow by appending its target files without changing existing environment files.

---

## 14. Transferring Ownership from Terraform

Use this procedure only when Terraform currently manages concrete APIM backends or pools that APIOps will own.

> **State security requirement:** Treat every Terraform state backup as sensitive. Store it only in an approved restricted location, never commit it, and delete the temporary copy according to the organization's retention policy after the transfer is verified.

1. Freeze Terraform and APIOps changes and retain state locking.
1. Save a restricted `terraform state pull` backup. Verify the workspace, state lineage, resource IDs, and exact state addresses.
1. Create APIOps artifacts with the same deployed resource IDs and properties.
1. Run static validation, APIOps dry run, and deployed-state comparison.
1. Publish APIOps over the unchanged resource IDs and verify routing.
1. Remove only Terraform's state binding:
   - Use a `removed` block with `lifecycle { destroy = false }` for a whole resource or module.
   - Use `terraform state rm -dry-run` followed by `terraform state rm` for selected resource instances.
1. Remove stale Terraform declarations and references.
1. Run an untargeted `terraform plan -detailed-exitcode`. Require exit code `0` with no deletion or recreation.
1. Repeat APIOps deployed-state and gateway checks before ending the freeze.

> **No-destroy requirement:** Stop immediately if a state command selects unexpected addresses or Terraform proposes any resource change. Ownership transfer removes only Terraform's state binding; it must not delete or recreate deployed resources. Do not use `ignore_changes` as permanent shared ownership.

---

## 15. APIOps Publication Modes

| Scenario                                          | Publication Mode                          |
| ------------------------------------------------- | ----------------------------------------- |
| First publication to a target                     | Full publication without `COMMIT_ID`      |
| Normal release to a synchronized target           | Change-based publication with `COMMIT_ID` |
| Shared artifact deletion                          | Change-based publication with `COMMIT_ID` |
| Target configuration change, fully covered        | Change-based publication on `v7.0.3`      |
| Target configuration change, coverage uncertain   | Reviewed full publication                 |
| Deliberate full reconciliation                    | Reviewed full publication                 |

A **full publication** processes the complete shared artifact set and selected target configuration. A **change-based publication** uses Git history and explicitly configured artifacts to determine what to process.

On APIOps `v7.0.3`, a change-based publication also processes artifact-backed resources named in target configuration. Use this mode for a target-configuration-only change only when every affected resource has a shared artifact and the target still matches the previous approved release. Otherwise, use a reviewed full publication.

Repeat these tests before every APIOps upgrade. Publisher behavior can change between versions.

---

## 16. Retry Count

Use a plain numeric Named Value as the complete retry `count` value:

```xml
<retry count="{{inference-gpt-5-1-retry-count}}"
       interval="0"
       first-fast-retry="true"
       condition="...">
    <forward-request buffer-request-body="true" />
</retry>
```

Set `inference-gpt-5-1-retry-count` to the non-secret string `"2"`. This permits one initial attempt and two retries. Retry count is independent of pool size because circuit breakers remove unhealthy members from selection. Change the default only when latency and retry telemetry support it.

---

## 17. Risk and Control Matrix

| Status   | Risk                                                    | Impact | Effort | Control                                                                                        |
| -------- | ------------------------------------------------------- | ------ | ------ | ---------------------------------------------------------------------------------------------- |
| 🔴 Red   | Terraform and APIOps manage the same backend or pool    | High   | Medium | Complete a no-destroy transfer and enforce one owner.                                          |
| 🔴 Red   | A pipeline publishes to the wrong APIM service          | High   | Low    | Bind the target ID to the exact resource ID, manifest, target configuration, and release lock. |
| 🔴 Red   | Terraform removes a deployment required for rollback    | High   | Low    | Retain old deployments through the rollback window.                                            |
| 🟠 Amber | A pool override contains only part of the desired array | High   | Low    | Require complete arrays and compare deployed state.                                            |
| 🟠 Amber | Change-based publication has incomplete coverage        | High   | Low    | Require a shared artifact for every affected resource or use a reviewed full publication.      |
| 🟠 Amber | A future target reuses the East US 2 configuration      | High   | Low    | Require one registry entry and complete configuration per APIM resource ID.                    |
| 🟠 Amber | Retry count is increased to match pool size             | Medium | Low    | Keep the default at `2` unless telemetry supports a change.                                    |
| 🟢 Green | Stable IDs keep policies identical across targets       | High   | Low    | Protect backend, pool, and Named Value names as compatibility contracts.                       |

---

## 18. References

- [APIOps Toolkit for Azure API Management](https://github.com/Azure/apiops)
- [APIOps Toolkit v7.0.3 release](https://github.com/Azure/apiops/releases/tag/v7.0.3)
- [APIOps publisher documentation](https://azure.github.io/apiops/apiops/3-apimTools/apiops-2-2-tools-publisher.html)
- [APIOps publisher configuration](https://github.com/Azure/apiops/wiki/Configuration)
- [Azure/apiops #789 - Selectively publish APIs across APIM environments](https://github.com/Azure/apiops/issues/789)
- [Azure/apiops #659 - Publisher configuration does not select resources](https://github.com/Azure/apiops/issues/659)
- [Azure/apiops #773 - Commit-aware deletion and full-publication behavior](https://github.com/Azure/apiops/issues/773)
- [Azure/apiops #154 - Changes between two environment deployments](https://github.com/Azure/apiops/issues/154)
- [Azure API Management retry policy](https://learn.microsoft.com/azure/api-management/retry-policy)
- [Named Values in Azure API Management](https://learn.microsoft.com/azure/api-management/api-management-howto-properties)
- [Backends in Azure API Management](https://learn.microsoft.com/azure/api-management/backends)
- [Terraform state removal](https://developer.hashicorp.com/terraform/language/state/remove)
- [Terraform state rm command](https://developer.hashicorp.com/terraform/cli/commands/state/rm)
- [Terraform state pull command](https://developer.hashicorp.com/terraform/cli/commands/state/pull)
- [Terraform plan command](https://developer.hashicorp.com/terraform/cli/commands/plan)
