# APIOps Backend Selection Proof of Concept

This proof of concept (POC) demonstrates how a GitHub Actions workflow can publish different subsets of one canonical APIOps backend artifact inventory to
multiple API Management instances. It keeps ten fictitious gpt-5.1 concrete backends and one stable model-safe backend pool in source control, then creates a
temporary target-specific artifact tree before the APIOps publisher discovers resources.

This is a **custom repository-owned preprocessing pattern**, not a built-in APIOps backend allowlist. The APIOps configuration continues to provide normal
property overrides. The POC script additionally interprets its top-level `backends[].name` values as the selection contract for the temporary staged tree.

The design follows the selective-publishing discussion in [Azure/apiops issue #789](https://github.com/Azure/apiops/issues/789) and the repository's
[Terraform and APIOps Environment Operations Plan](../TERRAFORM-APIOPS-BACKEND-ENVIRONMENT-PLAN.md). See
[Related APIOps Discussions](#related-apiops-discussions) for the upstream behavior that shapes this POC.

## What the POC Proves

| Environment | Canonical concrete backends | Selected concrete backends | Pool ID                  |
| ----------- | --------------------------- | -------------------------- | ------------------------ |
| DEV         | 10                          | 10                         | `inference-gpt-5-1-pool` |
| QA          | 10                          | 2                          | `inference-gpt-5-1-pool` |
| PROD        | 10                          | 7 per regional APIM        | `inference-gpt-5-1-pool` |

- DEV selects all ten concrete gpt-5.1 backends: three simulated PTU backends and seven PAYG backends.
- QA selects `gpt-5-1-PTU-eastus2` and `gpt-5-1-PTU-westus3`.
- Both PROD targets select one simulated PTU and two PAYG backends in each primary region, plus `gpt-5-1-PAYG-southcentralus` as a tertiary fallback.

The pool name and APIM resource ID remain `inference-gpt-5-1-pool` in every environment. Only its complete `properties.pool.services` array changes. DEV places
three equal-priority simulated PTU members ahead of seven equal-priority PAYG members, QA uses a preferred simulated PTU backend plus one simulated PTU
fallback, and each PROD APIM uses seven members across five priority tiers.

### Backend Naming Decision

The environment plan treats stable backend and pool IDs as compatibility contracts. This POC therefore follows its descriptive `<model>-<capacity>-<region>`
convention instead of ordinal names such as `backend-01`:

- `gpt-5-1-PTU-eastus2` identifies the model, provisioned capacity, and physical Azure region.
- `gpt-5-1-PAYG-westus3` identifies the same model using pay-as-you-go capacity in West US 3.
- `gpt-5-1-PAYG-eastus2-02` adds an ordinal only because a second deployment has the same model, capacity type, and region.
- `inference-gpt-5-1-pool` identifies a model-safe pool that must never contain a backend for another model.

These IDs are shared unchanged across APIM targets. Regional target configurations change the pool's complete priority and weight array, not backend identity.
This keeps policy references stable and makes the physical placement encoded by each backend ID truthful in every environment.

The workflow template models four target APIM instances:

| Target            | Logical environment | GitHub environment | Configuration                     |
| ----------------- | ------------------- | ------------------ | --------------------------------- |
| `dev-eastus2-01`  | DEV                 | `apiops-dev`       | `configuration.dev.yaml`          |
| `qa-eastus2-01`   | QA                  | `apiops-qa`        | `configuration.qa.yaml`           |
| `prod-eastus2-01` | PROD                | `apiops-prod`      | `configuration.prod-eastus2.yaml` |
| `prod-westus3-01` | PROD                | `apiops-prod`      | `configuration.prod-westus3.yaml` |

`PTU` is simulated in this POC: it is an identity and routing label, not a claim that the `.example.net` endpoint has provisioned Azure OpenAI capacity. This
keeps the artifact set offline while demonstrating the production naming and priority model.

Each independently managed APIM instance has its own configuration. Both PROD configurations select the same seven concrete backend IDs and stable pool ID, but
replace the complete pool services array with a region-specific priority order:

| Capacity and location | Backend IDs                                       | East US 2 APIM | West US 3 APIM |
| --------------------- | ------------------------------------------------- | -------------- | -------------- |
| East US 2 PTU         | `gpt-5-1-PTU-eastus2`                             | Priority 1     | Priority 2     |
| East US 2 PAYG        | `gpt-5-1-PAYG-eastus2`, `gpt-5-1-PAYG-eastus2-02` | Priority 3     | Priority 4     |
| West US 3 PTU         | `gpt-5-1-PTU-westus3`                             | Priority 2     | Priority 1     |
| West US 3 PAYG        | `gpt-5-1-PAYG-westus3`, `gpt-5-1-PAYG-westus3-02` | Priority 4     | Priority 3     |
| Tertiary PAYG         | `gpt-5-1-PAYG-southcentralus`                     | Priority 5     | Priority 5     |

APIM tries the lowest available priority first. Each APIM therefore exhausts simulated local PTU and then simulated peer-region PTU before using any PAYG
capacity. PAYG follows the same locality order: local, peer-region, then tertiary fallback. The weights distribute traffic within each PAYG priority group. This
capacity-first behavior is independent of global traffic routing between the two APIM instances; use Azure Front Door or another global entry point when clients
need automatic regional APIM failover.

## Processing Flow

1. GitHub checks out the complete tree containing ten concrete backends and one stable pool.
1. The script reads direct backend resource IDs and pool members from the target APIOps configuration.
1. The script validates **all configured IDs** against the canonical artifact inventory.
1. The script verifies that every selected pool has a complete, non-empty services array whose members are selected concrete backends.
1. If any configured ID is missing, the script exits before staging and APIOps does not run.
1. The script copies the complete artifact tree to an isolated runner-temporary directory. **Source remains safe as it is NOT modified!**
1. The script effectively includes only the desired backends by removing the unselected direct descendants of the staged `backends` directory.
1. The APIOps publisher receives the staged path through `API_MANAGEMENT_SERVICE_OUTPUT_FOLDER_PATH`.
1. The original configuration is passed through `CONFIGURATION_YAML_PATH` for normal APIOps property overrides.
1. A JSON selection manifest is uploaded as release evidence.

The workflow deliberately does not set `COMMIT_ID`. A staged tree is generated during the workflow and does not have meaningful Git commit history of its own,
so the publisher must process the complete staged snapshot.

## Package Contents

```text
POC/
|-- README.md
|-- artifacts/
|   |-- backends/
|   |   |-- gpt-5-1-PTU-eastus2/backendInformation.json
|   |   |-- ...
|   |   |-- gpt-5-1-PAYG-southcentralus/backendInformation.json
|   |   `-- inference-gpt-5-1-pool/backendInformation.json
|-- configurations/
|   |-- configuration.dev.yaml
|   |-- configuration.qa.yaml
|   |-- configuration.prod-eastus2.yaml
|   `-- configuration.prod-westus3.yaml
|-- scripts/
|   `-- prepare-apiops-artifacts.ps1
|-- tests/
|   |-- fixtures/
|   |   |-- configuration.missing-backend.yaml
|   |   `-- configuration.pool-member-not-selected.yaml
|   `-- test-prepare-apiops-artifacts.ps1
`-- workflow-templates/
    |-- publish-apiops.yml
    `-- run-publisher-with-backend-selection.yml
```

## Run the Offline Test Harness

The harness requires PowerShell 7. It does not require Azure credentials, an APIM instance, the APIOps publisher, Pester, or a YAML module.

From this directory:

```powershell
./APIOps-variable-publish/tests/test-prepare-apiops-artifacts.ps1
```

The harness creates disposable copies under the operating system's temporary directory. It injects a temporary `poc-marker` Named Value into those copies to
prove that filtering preserves non-backend artifact collections without shipping a synthetic resource to APIM. It verifies:

- [ ] DEV stages 10 concrete backends and `inference-gpt-5-1-pool` with 10 members.
- [ ] QA stages 2 concrete backends and `inference-gpt-5-1-pool` with 2 members.
- [ ] Both regional PROD targets stage 7 concrete backends and `inference-gpt-5-1-pool` with 7 members.
- [ ] Each PROD configuration assigns priorities 1 through 5 to local PTU, peer-region PTU, local PAYG, peer-region PAYG, and tertiary PAYG respectively.
- [ ] Every successful run records concrete backend counts, pool counts, and effective membership in an audit manifest.
- [ ] Non-backend artifact collections remain present.
- [ ] A configuration containing absent `gpt-5-1-PTU-japaneast` exits with code `4`.
- [ ] The missing-backend error names the ID, expected artifact path, and available IDs.
- [ ] No staging directory is created after missing-ID preflight validation fails.
- [ ] A pool member omitted from direct selection exits with code `3` before staging.
- [ ] Invalid source and overlapping audit paths exit with code `2` before staging.
- [ ] The canonical source tree remains byte-for-byte unchanged.

Pass `-KeepTemporaryFiles` to retain generated trees for manual inspection:

```powershell
pwsh ./samples/inference-failover/POC/tests/test-prepare-apiops-artifacts.ps1 -KeepTemporaryFiles
```

## Run One Selection Manually

The following command produces a QA tree with `gpt-5-1-PTU-eastus2`, `gpt-5-1-PTU-westus3`, and the stable `inference-gpt-5-1-pool` artifact. The QA
configuration overrides the pool with those two concrete members:

```powershell
pwsh ./samples/inference-failover/POC/scripts/prepare-apiops-artifacts.ps1 `
  -SourceArtifactsPath ./samples/inference-failover/POC/artifacts `
  -DestinationArtifactsPath ./samples/inference-failover/POC/out/qa `
  -ConfigurationPath ./samples/inference-failover/POC/configurations/configuration.qa.yaml
```

Generated `out` directories are demonstrations only and should not be committed. The GitHub workflow uses `${{ runner.temp }}` instead.

## Missing Backend Failure

The negative fixture selects `gpt-5-1-PTU-japaneast`, which is not part of the canonical inventory. The script aggregates every missing configured ID and
reports:

```text
[POC004] CONFIGURED BACKEND ARTIFACTS ARE MISSING
Configuration: .../configuration.missing-backend.yaml
Canonical backend root: .../artifacts/backends
Configured backend IDs not found (1): gpt-5-1-PTU-japaneast
Expected artifact path(s): .../artifacts/backends/gpt-5-1-PTU-japaneast/backendInformation.json
Available backend IDs (11): gpt-5-1-PAYG-centralus, ..., inference-gpt-5-1-pool
The APIOps publisher was not started and no staging directory was created.
Resolution: Restore or extract each missing backend artifact, or remove the incorrect ID from the target configuration, then rerun the preparation step.
```

This validation happens before the destination is created. A typo or stale configuration therefore cannot silently produce an incomplete publication set.

## Script Exit Codes

| Exit code | Meaning                                                              |
| --------- | -------------------------------------------------------------------- |
| `0`       | Staging completed and audit evidence was written.                    |
| `2`       | An input path, overlapping path, or existing destination is invalid. |
| `3`       | The configuration or selected backend-pool composition is invalid.   |
| `4`       | A configured backend artifact is missing or has invalid JSON.        |
| `5`       | Staging or audit output failed; partial staging is removed.          |
| `99`      | An unexpected failure escaped categorized handling.                  |

## Configuration Contract

Each selected concrete backend must be a direct item in the top-level `backends` array:

```yaml
backends:
    - name: gpt-5-1-PTU-eastus2
      properties:
          url: https://qa-gpt-5-1-ptu-eastus2.example.net/inference
```

The stable pool is another direct backend resource. Every environment supplies its complete member array:

```yaml
- name: inference-gpt-5-1-pool
  properties:
      type: Pool
      pool:
          services:
              - id: /backends/gpt-5-1-PTU-eastus2
                priority: 1
                weight: 100
              - id: /backends/gpt-5-1-PTU-westus3
                priority: 2
                weight: 100
```

APIOps replaces `properties.pool.services` as a complete array. It does not merge individual members with the canonical pool artifact. Every pool member must
therefore also appear as a direct top-level backend entry in the same environment configuration.

The dependency-free parser intentionally supports this narrow APIOps shape:

- `backends:` begins at the top level.
- Every direct item uses two spaces followed by `- name:`.
- IDs are case-sensitive.
- IDs contain only ASCII letters, numbers, periods, underscores, and hyphens.
- Duplicate IDs are rejected.
- Pool members use the literal `/backends/<backend-id>` resource form beneath `properties.pool.services`.
- Every selected canonical pool must have a non-empty target services array.
- Pool members must be selected canonical concrete backends; pools cannot contain filtered backends or another pool.
- Other nested properties are ignored by selection parsing and remain available to APIOps.

Use a full YAML parser if a production configuration requires anchors, aliases, tags, flow-style arrays, or another YAML feature outside this contract.

## Adopt the Workflow Templates

The files under `workflow-templates` are inert while they remain inside the POC. To use them in another repository:

1. Place both workflow files in that repository's `.github/workflows/` directory without renaming them.
1. Update the matrix values in `publish-apiops.yml` with real APIM service and resource group names.
1. Update `source-artifacts-path`, configuration paths, and the preprocessing script path if the POC layout changes.
1. Create protected GitHub environments named `apiops-dev`, `apiops-qa`, and `apiops-prod`, or update the matrix names.
1. Add the following secrets to each protected environment:
    - `AZURE_CLIENT_ID`
    - `AZURE_TENANT_ID`
    - `AZURE_SUBSCRIPTION_ID`
1. Configure the federated credential for each client ID to trust the repository and matching GitHub environment.
1. Grant the workload identity only the Azure permissions required to publish to its target APIM instance.
1. Add required reviewers and deployment protections, especially for `apiops-prod`.
1. Run the workflow manually and choose `dev`, `qa`, `prod`, or `all`.

The reusable workflow uses OIDC through the SHA-pinned `azure/login` action. It downloads the APIOps `v7.0.3` Linux publisher, verifies the published SHA-256
digest, and then executes it. Review and update both the release version and checksum together when adopting a newer APIOps release.

Selecting `all` starts all matching targets as independent matrix jobs. GitHub environment approvals still apply, but this POC does not impose DEV-to-QA-to-PROD
sequencing. Add explicit promotion dependencies or separate workflows when successful lower-environment deployment must gate the next environment.

## Safety Boundaries

- The script never changes the canonical source tree.
- The destination must not equal, contain, or be contained by the source path.
- The audit manifest must remain outside both artifact trees.
- An existing destination is rejected unless `-Force` is explicit.
- All configured IDs are validated before staging begins.
- Every selected pool composition is validated for dependency closure before staging begins.
- Only direct child directories of staged `backends` are filtered.
- Partial staging is removed after staging or audit failure.
- The workflow does not pass secrets through command text.
- GitHub Actions are pinned to immutable commit SHAs.
- The publisher archive is pinned to a release and verified by SHA-256.

This POC does not delete backend resources that already exist in APIM. A full APIOps publication processes artifacts visible in the staged tree; absence from
that tree is not a deletion declaration. Treat backend retirement as a separate, reviewed cleanup operation.

## Adapting the POC

Before using this pattern with real inference backends:

- [ ] Replace all `.example.net` URLs with validated target endpoints.
- [ ] Replace fictitious APIM service and resource group names.
- [ ] Create one configuration per independently routed APIM instance and map it to the correct workflow target.
- [ ] Classify every production backend by region and assign local, peer-region, and tertiary priorities.
- [ ] Preserve stable pool IDs across environments and provide complete target-specific service arrays.
- [ ] Include every pool member as a direct selected concrete backend.
- [ ] Validate literal policy backend references for dependency closure.
- [ ] Review the generated selection manifest before publisher execution.
- [ ] Define a separate process for deliberate backend deletion from APIM.
- [ ] Test the adopted workflow in a non-production APIM instance.

This POC validates selected backend-pool members directly. The more complete parent implementation in
[prepare-apiops-artifacts.ps1](../prepare-apiops-artifacts.ps1) additionally validates literal policy references. Use that policy dependency validation when
adopting the POC with real API policy artifacts.

## Related APIOps Discussions

- [Issue #789: selectively publish APIs across different APIM environments](https://github.com/Azure/apiops/issues/789) closely matches the canonical-superset
  and temporary-filtered-copy pattern demonstrated here.
- [Issue #659: configuration file behavior](https://github.com/Azure/apiops/issues/659) explains that publisher configuration overrides properties but does not
  natively select resources.
- [Issue #417: selective publishing configuration](https://github.com/Azure/apiops/issues/417) records why an earlier artifact-selection capability was
  reverted.
- [Issue #504: exclude selected artifacts from UAT and PROD](https://github.com/Azure/apiops/issues/504) confirms that configuration cannot exclude artifacts by
  itself.
- [Issue #773: publisher deletion behavior](https://github.com/Azure/apiops/issues/773) distinguishes commit-based deletion from full artifact publication.
- [Issue #154: publishing environments that missed commits](https://github.com/Azure/apiops/issues/154) describes the gap between one-commit publication and a
  complete repository publication.
