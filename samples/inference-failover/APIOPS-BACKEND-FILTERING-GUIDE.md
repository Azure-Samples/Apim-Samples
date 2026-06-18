# APIOps Environment Backend Filtering

This guide describes a controlled way to publish a different subset of Azure API Management (APIM) backends to each environment while retaining one canonical APIOps artifact superset.

The implementation filters a temporary copy of the artifact tree before the APIOps publisher discovers resources. The source artifacts remain unchanged, and the target APIOps configuration acts as an explicit allowlist of backend resources for that environment.

The need for selective environment publication and the temporary filtered-tree approach are discussed in [Azure/apiops issue #789](https://github.com/Azure/apiops/issues/789). This guide applies that general community workaround specifically to APIM backends and adds dependency validation, audit evidence, and fail-closed behavior. The PowerShell staging step is a repository-owned workflow extension; it is not a built-in APIOps publisher feature, and it does not change the publisher configuration file into a native allowlist.

## Executive Summary

Use this pattern when DEV, QA, and PROD have different backend inventories or when PROD should receive only an approved subset, such as 5 of 10 available backends.

```text
Canonical artifact superset
          |
          v
configuration.<environment>.yaml backend allowlist
          |
          v
PowerShell validation and temporary staging
          |
          v
APIOps publisher reads only the staged artifact tree
```

The design is fail closed. A new canonical backend is not published to an environment until its name is added to that environment's top-level `backends` array.

## Package Contents

- [prepare-apiops-artifacts.ps1](prepare-apiops-artifacts.ps1) creates and validates the staged artifact tree.
- [configuration.prod-eus2-01.sample.yaml](configuration.prod-eus2-01.sample.yaml) demonstrates the selection contract with nine concrete backends and two backend pools.
- [Terraform and APIOps backend environment plan](TERRAFORM-APIOPS-BACKEND-ENVIRONMENT-PLAN.md) covers ownership, target manifests, release validation, and rollback in more detail.

The script is dependency-free and supports PowerShell 7 on Windows, Linux, and macOS. It intentionally parses only the constrained APIOps YAML structure described below; it is not a general-purpose YAML parser.

## Before You Begin

The script prepares files for the APIOps publisher. It does not connect to Azure or run the publisher itself.

Confirm the following before the first run:

- [ ] PowerShell 7 or later is installed on the workstation or CI runner.
- [ ] The APIOps extractor has produced a complete canonical artifact tree.
- [ ] The artifact root contains a `backends/` directory.
- [ ] Every backend that may be selected has its own `backendInformation.json` file.
- [ ] The target configuration contains exactly one top-level `backends` array.
- [ ] Backend pools and every concrete backend used by those pools are listed in that array.
- [ ] The destination is a temporary or generated directory, not the source artifact directory.

View the complete built-in script documentation at any time:

```powershell
Get-Help ./samples/inference-failover/prepare-apiops-artifacts.ps1 -Full
```

Use `-Verbose` during initial setup or troubleshooting to include resolved paths and cleanup details.

## Selection Contract

Each backend resource that should exist in the target environment must have a direct entry under the configuration's top-level `backends` property. Backend pools are APIM backend resources, so they must also be listed.

```yaml
backends:
  - name: gpt-5-1-PTU-eastus2
    properties:
      url: https://aoai-prod-eus2.openai.azure.com/openai/deployments/gpt-5-1

  - name: inference-gpt-5-1-pool
    properties:
      type: Pool
      pool:
        services:
          - id: /backends/gpt-5-1-PTU-eastus2
            priority: 1
            weight: 100
```

In this example, the script retains the concrete backend and the pool. Every other directory under the canonical `backends/` folder is removed only from the staged copy.

Apply these rules:

- Treat backend names as case-sensitive artifact directory names.
- List every concrete backend that the environment may publish.
- List every backend pool used by an API policy.
- Supply the complete `properties.pool.services` array when overriding pool membership.
- Ensure every pool member is also selected as a top-level backend.
- Keep backend credentials out of configuration. The inference-failover policy uses APIM managed identity.

The script rejects an empty or missing `backends` property, duplicate or unsafe names, selected artifacts that do not exist, and pool or literal policy references to filtered backends.

## Artifact Layout

The source path must be the APIOps artifact root, not the `backends` directory itself.

```text
artifacts/
  apis/
  backends/
    backend-a/
      backendInformation.json
    backend-b/
      backendInformation.json
    inference-pool/
      backendInformation.json
  namedValues/
  products/
```

The complete tree is copied. Only directories directly beneath staged `backends/` are filtered. APIs, policies, Named Values, products, and other artifact collections are preserved.

## How the Script Works

The script follows six phases in a fixed order. Publication should begin only after all six phases succeed.

1. **Validate input paths.** Resolve the source, destination, configuration, and audit paths. Reject missing paths, overlapping artifact trees, and an audit path inside either artifact tree.
1. **Read the environment allowlist.** Read direct `name` entries beneath the configuration's top-level `backends` property and collect pool members from `properties.pool.services`.
1. **Validate source artifacts.** Confirm that every selected name has a canonical backend directory and a parseable `backendInformation.json` file.
1. **Create the staged tree.** Copy the entire source artifact tree, then remove only unselected directories directly beneath staged `backends/`.
1. **Validate dependencies.** Confirm that effective pool members and literal `set-backend-service` policy references resolve to selected backend resources.
1. **Write release evidence.** Atomically write a JSON audit manifest with the configuration hash, counts, selected names, and removed names.

If phases 4, 5, or 6 fail, the script attempts to remove the partial staging directory before returning an error. This prevents a later workflow step from publishing incomplete artifacts.

## Script Parameters

- **`SourceArtifactsPath` (required):** Canonical APIOps artifact root containing `backends/`, `apis/`, and other artifact collections. The script reads but never changes this directory.
- **`DestinationArtifactsPath` (required):** Separate staging root passed to the APIOps publisher after success. It must not overlap the source path.
- **`ConfigurationPath` (required):** Target `configuration.<environment>.yaml` whose top-level `backends` entries define the environment allowlist.
- **`AuditManifestPath` (optional):** JSON release-evidence path. The default is `<DestinationArtifactsPath>.selection.json`, adjacent to the staged directory.
- **`Force` (optional):** Replaces an existing destination. Without this switch, an existing destination produces exit code `2`. It never permits source and destination overlap.
- **`Verbose` (optional):** Standard PowerShell common parameter that includes resolved paths, replacement details, cleanup confirmation, and exception stack context.

The first three values are validated inside the script instead of relying only on PowerShell parameter binding. This allows missing values to produce the documented exit code `2` and a complete corrective message.

## Run Locally

Run the script from the repository root with PowerShell 7. For a first run, omit `-Force` so an unexpected existing destination cannot be replaced:

```powershell
./samples/inference-failover/prepare-apiops-artifacts.ps1 `
  -SourceArtifactsPath ./artifacts `
  -DestinationArtifactsPath ./out/apimartifacts-prod `
  -ConfigurationPath ./configuration.prod.yaml `
  -AuditManifestPath ./out/apimartifacts-prod.selection.json `
  -Verbose
```

After reviewing the generated path, use `-Force` in repeatable automation where replacement is intentional:

```powershell
./samples/inference-failover/prepare-apiops-artifacts.ps1 `
    -SourceArtifactsPath ./artifacts `
    -DestinationArtifactsPath ./out/apimartifacts-prod `
    -ConfigurationPath ./configuration.prod.yaml `
    -AuditManifestPath ./out/apimartifacts-prod.selection.json `
    -Force
```

`-Force` replaces an existing destination. It never permits the source directory, the destination directory, or either directory's parent tree to overlap.

On success, inspect:

- The staged `backends/` directory. It must contain exactly the configured backend names.
- The staged non-backend collections. They must match the source.
- The selection manifest. It records the resolved paths, configuration SHA-256, selected resources, removed resources, counts, and UTC generation time.

The selection manifest is written next to the staged directory by default, not inside it. This prevents the publisher from interpreting audit data as an APIOps artifact.

## Understanding the Result

### Successful Run

A successful run reports every phase and ends with an explicit success block:

```text
=== APIOps Environment Artifact Preparation ===
[1/6] Validating and resolving input paths...
[2/6] Reading the target backend allowlist...
  Selected 6 backend resources, including pools.
[3/6] Checking selected resources against the source artifacts...
  Found 11 backend resources in the canonical superset.
[4/6] Copying the artifact tree and filtering staged backends...
  Removed 5 unselected backend resources from staging.
[5/6] Validating pool members and policy backend references...
[6/6] Writing the backend selection audit manifest...

[SUCCESS] APIOps artifact preparation completed.
Exit code : 0
Staged at : /runner/temp/apimartifacts-prod
Audit file: /runner/temp/apimartifacts-prod.selection.json
Selected  : 6 backend resources
Filtered  : 5 backend resources
```

Exit code `0` means both the staged tree and audit manifest are complete. The workflow may proceed to the APIOps publisher.

### Failed Run

An expected failure prints one error block to standard error:

```text
[ERROR] APIOps artifact preparation failed.
Category : Invalid backend references
Exit code: 5
Message  : The selected backend set is not dependency-complete. Selected backend pool 'inference-gpt-5-1-pool' references filtered backend 'gpt-5-1-PAYG-westus3'.
Resolution: Select every backend referenced by a retained pool or literal set-backend-service policy, then rerun the script.
```

Do not invoke the publisher after any nonzero exit code. Correct the reported condition and rerun artifact preparation from the canonical source tree.

## Exit Codes

The numeric code is the automation contract. The category and resolution text provide the human-readable diagnosis.

- **`0` - Success:** Staging, reference validation, and audit generation completed. Continue to the APIOps publisher.
- **`1` - PowerShell startup or binding:** PowerShell could not parse the invocation or bind a supplied parameter. Check parameter spelling, value types, PowerShell availability, and script syntax.
- **`2` - Invalid input:** A required value is missing, paths overlap, or destination handling is unsafe. Correct the invocation or choose separate source, destination, and audit locations.
- **`3` - Invalid configuration:** The top-level backend allowlist or supported pool YAML shape is invalid. Correct the target configuration using the selection contract in this guide.
- **`4` - Invalid source artifacts:** A selected directory or `backendInformation.json` file is missing, invalid, or unreadable. Restore or re-extract the canonical APIOps artifacts.
- **`5` - Invalid backend references:** A selected pool or literal policy refers to a backend that is not selected. Add the referenced backend or remove the reference, then rerun validation.
- **`6` - Staging failure:** The destination could not be replaced, created, copied, filtered, or cleaned up. Check permissions, locks, path length, disk capacity, and stale files.
- **`7` - Audit failure:** The JSON selection manifest could not be written atomically. Check the audit directory permissions and disk capacity, then rerun.
- **`99` - Unexpected failure:** An unclassified runtime error occurred. Rerun with `-Verbose` and provide the complete error block to the script maintainer if it persists.

In PowerShell, read the code immediately after the script finishes:

```powershell
./samples/inference-failover/prepare-apiops-artifacts.ps1 @parameters
$preparationExitCode = $LASTEXITCODE

if ($preparationExitCode -ne 0) {
    throw "APIOps artifact preparation failed with exit code $preparationExitCode."
}
```

GitHub Actions automatically fails the preparation step when the script returns a nonzero code. The script also emits a GitHub error annotation and, after success, adds selection counts and names to the job summary.

## Common Errors

### The Destination Already Exists

Confirm that the destination is generated output. Rerun with `-Force` only when replacing it is intentional. Never point the destination at the canonical source tree.

### A Configured Backend Does Not Exist in Source

The configuration is an allowlist and an override, not a replacement for canonical artifacts. Restore `backends/<name>/backendInformation.json` through extraction or remove the name from the target configuration.

### A Pool References a Filtered Backend

Add every pool member as its own direct top-level backend entry. A pool entry alone does not select its concrete members.

### A Policy References a Filtered Backend or Pool

Retain the referenced backend resource or update the policy to use a selected stable pool ID. Dynamic expressions and Named Values require a separate target-aware validation because their runtime values cannot be determined from static artifacts.

### Partial Staging Cleanup Reports a Warning

The primary failure code remains authoritative, but the staging path may still contain partial output. Remove it manually before rerunning and investigate file locks or runner permissions.

## GitHub Actions Integration

Insert the preparation step after checkout and APIOps publisher download, but before the publisher executable runs. Keep the existing Azure authentication and publisher acquisition steps.

The following fragment is designed for a fixed PROD job protected by a GitHub environment approval. Actions are pinned to full commit SHAs. Workflow expressions are assigned through `env` rather than interpolated into the PowerShell command.

```yaml
permissions:
  contents: read
  id-token: write

jobs:
  publish-prod:
    runs-on: ubuntu-latest
    environment: prod
    env:
      SOURCE_ARTIFACTS_PATH: ${{ github.workspace }}/artifacts
      TARGET_CONFIGURATION_PATH: ${{ github.workspace }}/configuration.prod.yaml
      STAGED_ARTIFACTS_PATH: ${{ runner.temp }}/apimartifacts-prod
      SELECTION_AUDIT_PATH: ${{ runner.temp }}/apimartifacts-prod.selection.json

    steps:
      - name: Check out repository
        uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10 # v6.0.3

      # Keep the customer's existing Azure login and APIOps publisher download steps here.

      - name: Prepare target APIOps artifacts
        shell: pwsh
        run: |
          ./samples/inference-failover/prepare-apiops-artifacts.ps1 `
            -SourceArtifactsPath $env:SOURCE_ARTIFACTS_PATH `
            -DestinationArtifactsPath $env:STAGED_ARTIFACTS_PATH `
            -ConfigurationPath $env:TARGET_CONFIGURATION_PATH `
            -AuditManifestPath $env:SELECTION_AUDIT_PATH `
            -Force

      - name: Run APIOps publisher
        shell: pwsh
        env:
          API_MANAGEMENT_SERVICE_OUTPUT_FOLDER_PATH: ${{ runner.temp }}/apimartifacts-prod
          CONFIGURATION_YAML_PATH: ${{ github.workspace }}/configuration.prod.yaml
          API_MANAGEMENT_SERVICE_NAME: ${{ vars.API_MANAGEMENT_SERVICE_NAME }}
          PUBLISHER_EXECUTABLE_PATH: ${{ runner.temp }}/apiops/publisher
        run: |
          & $env:PUBLISHER_EXECUTABLE_PATH

      - name: Upload backend selection audit
        if: always()
        uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
        with:
          name: apiops-prod-backend-selection
          path: ${{ runner.temp }}/apimartifacts-prod.selection.json
          if-no-files-found: error
          retention-days: 30
```

Adapt `PUBLISHER_EXECUTABLE_PATH` to the location produced by the customer's existing APIOps download step. Preserve all required APIOps authentication environment variables from that workflow.

Use a full APIOps publication for the generated staging tree. Do not set `COMMIT_ID` initially. Commit-aware publication calculates changes from the canonical Git tree, while the filtered tree is generated after checkout and has different resource visibility.

## Validation Behavior

Before the publisher runs, the script verifies:

- The source, destination, and configuration paths are distinct and valid.
- The source contains a `backends/` collection.
- Every configured backend has `backends/<name>/backendInformation.json`.
- The staged backend names equal the configured selection.
- Pool service IDs from configuration overrides resolve to selected backends.
- Pool service IDs from retained canonical pool artifacts resolve to selected backends when configuration does not override the pool.
- Literal `set-backend-service` policy references resolve to selected backends or pools.

Dynamic policy references, including policy expressions and Named Value substitutions, cannot be resolved statically by this script. Validate those references in a separate target-specific release check.

This control validates resource selection and dependency closure. It does not validate backend URLs against Terraform state, test network reachability, or confirm Azure role assignments. Those controls remain part of the target manifest and release validation process.

## Related Azure/apiops Discussions

The following issues provide upstream context for this pattern. Several discuss APIs rather than backends, but the same publisher discovery and configuration semantics apply to both artifact types. Issue state and implementation details can change, so verify the selected APIOps release before relying on any behavior.

- [#789 - Selectively publish APIs across APIM environments](https://github.com/Azure/apiops/issues/789) (open) is the primary discussion of environment allowlists, separate environment artifact folders, and custom scripts that prepare a temporary filtered artifact tree before publication.
- [#659 - API not present in configuration is still deployed](https://github.com/Azure/apiops/issues/659) (open) contains the contributor clarification that publisher configuration overrides properties but does not select resources; artifacts or commit changes determine publication scope.
- [#417 - `PUBLISH_CONFIGURATION_ARTIFACTS` setting is ignored](https://github.com/Azure/apiops/issues/417) (closed) records that configuration-based selection was reverted because of complexity and confirms that configuration entries are used as overrides in current publisher behavior.
- [#504 - Publish selected APIs to UAT or PROD](https://github.com/Azure/apiops/issues/504) (closed) is an earlier environment-promotion question whose response states that publisher configuration cannot exclude artifacts and points to extraction or repository partitioning instead.
- [#773 - Deleting objects in Git does not delete them from APIM](https://github.com/Azure/apiops/issues/773) (open) clarifies that deletion is commit-aware: with `COMMIT_ID`, artifacts deleted in that commit are removed; without it, a full publication creates or updates but does not reconcile.
- [#154 - Deploy all changes between two deployments](https://github.com/Azure/apiops/issues/154) (open) tracks the gap between single-commit publication and full publication when an environment has missed multiple commits, including community sequencing and staging workarounds.

## Existing Resource Cleanup

Filtering controls what the publisher discovers and creates or updates. It does not automatically delete a backend that was deployed to APIM by an earlier release and is now absent from the staged tree.

Use a separate, explicitly approved cleanup for existing unwanted resources:

1. Remove the backend from all pool definitions and policy references.
1. Publish and verify the updated routing configuration.
1. Confirm through APIM telemetry that the backend is no longer receiving traffic.
1. Delete the dormant backend with the approved APIOps deletion process or a reviewed Azure management operation.
1. Record the deletion in the release evidence and verify that rollback artifacts remain available.

Do not infer deletion merely from absence in the staged tree.

## Security and Operational Controls

- Use GitHub environments and required reviewers for QA and PROD publication.
- Grant the workflow identity only the permissions required by the APIOps publisher.
- Keep the target APIM service name in protected environment variables.
- Keep secrets in the approved secret store; do not place credentials in backend configuration or audit manifests.
- Upload the selection manifest as release evidence and retain it according to the customer's audit policy.
- Review configuration changes as code. Adding a backend name expands the target environment's resource inventory.
- Keep one immutable canonical artifact revision and record its commit SHA separately from the generated selection manifest.
- Run target-specific smoke tests after publication, including failover and retry behavior for each retained pool.

## Rollout Plan

1. Add the script and one environment configuration to a non-production APIOps branch.
1. Run the script without invoking the publisher and review the staged tree and audit manifest.
1. Publish to DEV and verify backend inventory, pool membership, policy references, and API traffic.
1. Repeat in QA with environment approval and rollback rehearsal.
1. Inventory dormant backends already present in PROD and approve a separate cleanup plan where needed.
1. Enable PROD staging and full publication behind required reviewers.
1. Add release evidence retention and post-publication smoke tests.

## Acceptance Checklist

- [ ] Every target configuration contains an explicit, reviewed top-level backend allowlist.
- [ ] Every selected pool is listed and references only selected concrete backends.
- [ ] The script runs on the customer's hosted runner with PowerShell 7.
- [ ] The source artifact tree is unchanged after staging.
- [ ] The staged backend inventory exactly matches the target configuration.
- [ ] Non-backend APIOps artifact collections are preserved.
- [ ] The APIOps publisher receives the staged path, not the canonical source path.
- [ ] `COMMIT_ID` is omitted for the initial generated-tree implementation.
- [ ] The audit manifest is retained with the release evidence.
- [ ] Existing unwanted APIM resources have an explicit cleanup decision.
- [ ] DEV and QA failover tests pass before PROD enablement.

Record the completed checklist with the approved release evidence.
