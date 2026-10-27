# Python Helper Strategy

This document defines how Python helpers and supporting classes are designed, located, consumed, tested, and promoted in the APIM Samples repository. It is the authoritative architecture guide for Python code used by notebooks.

The goal is to keep notebooks educational and independently understandable while moving incidental mechanics into testable Python modules. Helpers should reduce repetition and runtime coupling without hiding the APIM concept being demonstrated.

## Design Principles

1. **Keep the scenario visible.** Configuration, deployment parameters, APIM concepts, traffic intent, and verification outcomes stay in the notebook.
2. **Extract incidental mechanics.** Parsing, retries, polling, persistence, request setup, response normalization, and repeated orchestration belong in helpers.
3. **Prefer the narrowest ownership.** Start sample-local. Promote code to `shared/python/` only after it has a stable cross-sample contract.
4. **Make state explicit.** Return typed values or context objects. Do not create hidden notebook globals or depend on variables created by another cell.
5. **Own resource lifecycles.** Classes that create sessions, files, or other resources must close them predictably, preferably with a context manager.
6. **Compose established helpers.** Extend or compose `NotebookHelper`, `InfrastructureNotebookHelper`, `ApimRequests`, and `ApimTesting` before creating parallel abstractions.
7. **Keep Azure access truthful.** Azure operations use `azure_resources` and return results that distinguish success, absence, and failure. Tests mock the Azure boundary.
8. **Design for reruns.** Notebook operations and helpers should be idempotent where practical and safe to execute again after partial progress.

## Ownership Model

Use the following decision table before adding Python logic.

| Location                             | Use when                                                                | Do not use for                                                 |
| ------------------------------------ | ----------------------------------------------------------------------- | -------------------------------------------------------------- |
| `create.ipynb`                       | Educational configuration, scenario sequence, key APIM concepts, output | Retry loops, parsers, persistence formats, repeated HTTP setup |
| `samples/<sample>/<name>_helpers.py` | Mechanics owned by one sample or still evolving with that sample        | Behavior already needed by multiple samples                    |
| `shared/python/<domain>.py`          | Stable capability reused by multiple samples or infrastructures         | A one-off sample workflow with no demonstrated second consumer |
| `shared/python/utils.py`             | Small repository-wide notebook and deployment coordination              | Unrelated domain helpers that deserve a focused module         |
| `infrastructure/<name>/*.py`         | Infrastructure-specific creation mechanics                              | Sample deployment or cross-infrastructure behavior             |
| `setup/*.py`                         | Developer environment, validation, export, and repository maintenance   | Runtime behavior imported by sample notebooks                  |
| `tests/python/test_*.py`             | Unit tests and test-only support                                        | Runtime helpers                                                |

A helper should move from sample-local to shared only when all of these are true:

- At least two real consumers need substantially the same behavior.
- Inputs and outputs can be named without sample-specific terminology.
- Error behavior and lifecycle rules are understood.
- Unit tests cover the shared contract and important failure paths.
- Promotion removes duplication rather than merely anticipating reuse.

When promoting a helper, migrate all consumers in the same change and remove the sample-local duplicate.

## Helper Placement Decision Sequence

Use this sequence for each extracted behavior:

1. Leave educational configuration, scenario definitions, and expected outcomes in the notebook.
2. Extract only mechanics that can be expressed through explicit inputs and outputs.
3. Keep behavior sample-local while it has one consumer or uses sample-specific vocabulary.
4. Move behavior directly to a focused shared module when two active consumers already need the same contract.
5. Extend an established shared class only when the behavior belongs to that class's existing state and lifecycle.

The number of lines is a signal to inspect a notebook, not a reason by itself to create a helper. Ownership follows the narrowest real consumer set.

| Behavior                                           | Placement                                                  | Reason                                                        |
| -------------------------------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------- |
| Dynamic CORS cache orchestration                   | `samples/dynamic-cors/dynamic_cors_helpers.py`             | One sample owns the behavior and vocabulary                   |
| Costing-specific API construction                  | `samples/costing/costing_helpers.py`                       | One sample owns the evolving cost model                       |
| Load-balancing traffic and retry tracking          | `samples/load-balancing/load_balancing_helpers.py`         | One sample owns the traffic scenarios and timing contract     |
| OAuth credential validation and Spotify parsing    | `samples/oauth-3rd-party/oauth_helpers.py`                 | One sample owns the provider-specific payload contract        |
| Secure blob upload and valet-key download          | `samples/secure-blob-access/secure_blob_access_helpers.py` | One sample owns the blob and SAS lifecycle                    |
| Role-based JWT request execution for AuthX samples | `shared/python/auth_testing.py`                            | AuthX and AuthX-Pro use the same request and session contract |
| APIM endpoint resolution                           | `NotebookHelper`                                           | Broad notebook coordination using existing helper state       |

Do not create both a sample-local wrapper and a shared helper for the same operation. A notebook should call the narrowest owning contract directly.

Infrastructure-owned MockAPI provisioning follows the same rule: [mockapi.py](mockapi.py) owns credential reuse, configuration seeding, and restart/readiness mechanics shared by four infrastructures. [infrastructures.py](infrastructures.py) composes those operations through the existing Azure CLI boundary. See the [MockAPI operations guide](../../infrastructure/apim-aca/README.md#mockapi-backends) for credential recovery and persistence behavior.

[mockapi_dashboard.py](mockapi_dashboard.py) owns authenticated management sessions, conditional endpoint updates, concurrency retries, and autosave recovery. Both private-storage infrastructure initialization and the Load Balancing sample consume this client; endpoint definitions and scenario-specific traffic remain with their respective owners. The client never requires direct Blob access from the notebook machine.

## Notebook Boundary

A notebook is the user-facing workflow, not a general-purpose Python module. Each code cell should communicate one operation and remain understandable when read from top to bottom.

Keep these concerns in the notebook:

- User configuration and feature toggles.
- The selected infrastructure and supported infrastructure list.
- Bicep parameters that teach the deployment model.
- Calls to `nb_helper.deploy_sample()` and extraction of deployment outputs.
- Traffic scenarios, expected behavior, and verification summaries.
- Small transformations that directly explain the scenario.

Move these concerns to a helper:

- Repeated request construction or HTTP session configuration.
- Polling schedules, retries, backoff, and timeout handling.
- JSON, token, response, or command-output parsing.
- Local persistence and merge behavior.
- Resource discovery or Azure CLI command composition used in several places.
- Multi-step orchestration whose details do not teach the sample concept.
- Repeated table preparation or result normalization.

A helper call should still read like the scenario. Prefer:

```python
with DynamicCorsTestRunner(deployment, rg_name, apim_gateway_url, results_path, ['Option 1']) as runner:
    runner.run_option_tests(tests, 'Option 1', products_path, analytics_path)
```

over a generic engine configured by an opaque dictionary.

## Dependency Direction

Dependencies flow toward stable, focused modules:

```text
notebook
  -> sample-local helper
      -> shared domain helpers
          -> azure_resources / requests / standard library
```

Follow these rules:

- Shared modules must never import a sample-local helper.
- Sample-local helpers may import shared modules.
- Helpers must not import or execute notebook files.
- `azure_resources` is the Azure CLI and ARM boundary. New code should import it as `import azure_resources as az` rather than use re-exports from `utils`.
- Console output goes through `console.py` when repository formatting is desired.
- HTTP verification should use `ApimRequests` and `ApimTesting`; high-volume traffic may use a focused session-owning helper.
- Avoid circular imports by keeping data types and low-level adapters below orchestration modules.

### Shared Capability Boundaries

- [policy_files.py](policy_files.py) owns policy-file loading, replacement, and path resolution, including the legacy sample-root fallback.
- [bicep_deployment.py](bicep_deployment.py) owns template-directory resolution, parameter-file writing, deployment invocation, and sample working-directory restoration.
- [infrastructure_cli.py](infrastructure_cli.py) owns the common parser, deployment dispatch, and Container Apps demo APIs for the five infrastructure creation scripts. Each script keeps its architecture-specific specification and existing callable entry point.
- [apimtypes.py](apimtypes.py) owns repository-root discovery alongside shared types. `find_project_root()` walks upward from the current directory; `get_project_root()` supports the configured root and module-based discovery.
- [utils.py](utils.py) keeps notebook orchestration and infrastructure selection. Choice construction, table presentation, prompting, and creation are separate methods; selecting an infrastructure does not redesign the deployment workflow.

Existing policy, root-discovery, and Bicep imports from [utils.py](utils.py) remain direct compatibility re-exports, not forwarding wrappers. This preserves caller-frame-sensitive policy resolution. Its explicit `__all__` retains the complete historical public namespace, including imported names, without lint suppressions. New code should import the owning module. Tests should patch collaborators where their implementation looks them up, such as `bicep_deployment.find_project_root` rather than `utils.find_project_root`.

Bicep directory resolution retains its current-directory fallback for expected filesystem, path-value, and runtime root-discovery errors, recording the cause at DEBUG level. Unexpected programming errors propagate rather than being hidden by the fallback.

## Functions, Data Types, and Classes

### Use a function when

- The operation is stateless or all state is passed explicitly.
- One call produces one result.
- Resource ownership does not extend beyond the call.
- A pure transformation can be tested with values alone.

Functions should return a meaningful value instead of mutating module globals. Use a private function for an implementation detail that is not part of the module contract.

### Use a dataclass when

- Several related values travel together across cells or module boundaries.
- Field names make tuple positions or dictionary keys safer and clearer.
- The value represents a result or context, not an active service.

Examples include deployment context, resolved endpoint configuration, or a traffic summary. Prefer immutable data where mutation is not part of the contract.

### Use a class when

- Several operations share configuration or validated state.
- The object owns a lifecycle, such as an HTTP session.
- Invariants should be established once in the constructor.
- The methods form a cohesive domain capability.

Do not create a class only to namespace unrelated static methods. A class should have one clear responsibility and a concise public surface.

### Use a context manager when

- The helper opens an HTTP session, file, temporary resource, or other closeable object.
- Cleanup must happen after success and exceptions.

Implement `__enter__` and `__exit__`, or provide a focused factory that returns an existing context-managed type. Cleanup must not depend on a later notebook cell.

## Contracts and State

Public helper contracts must make inputs, outputs, side effects, and failures apparent.

- Add type annotations to public functions and methods.
- Add concise docstrings to public functions and classes.
- Prefer typed dataclasses for multi-value results with stable meaning.
- Use dictionaries for genuinely dynamic external payloads, not as a substitute for a known internal type.
- Return created or resolved values; do not inject names into notebook globals.
- Do not read arbitrary notebook globals through `globals()`, `locals()`, or IPython state.
- Accept dependencies or test hooks explicitly when doing so avoids network calls or real waits in unit tests.
- Raise a specific exception for invalid programmer input.
- At the notebook boundary, convert expected operational failures into clear user-facing messages when recovery is possible.

Notebook variables remain explicit and flow forward through cells. A later cell may validate a prerequisite with `if 'variable_name' not in locals():`, but helper modules must not depend on that mechanism.

## Established Supporting Classes

Use these classes according to their existing ownership boundaries.

| Class                          | Responsibility                                                        | Extend when                                                                  |
| ------------------------------ | --------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| `InfrastructureNotebookHelper` | Infrastructure creation and infrastructure-notebook orchestration     | Behavior applies to infrastructure creation across architectures             |
| `NotebookHelper`               | Sample deployment, deployment context, endpoint and notebook services | Behavior applies broadly to sample notebooks and needs selected deployment   |
| `ApimRequests`                 | Configured APIM HTTP requests and session ownership                   | Request behavior is broadly reusable and belongs at the APIM client boundary |
| `ApimTesting`                  | Verification recording and human-readable test summaries              | Assertion/reporting behavior is shared by sample verification                |

Before extending one of these classes, confirm the new method uses the class's existing state and belongs to the same lifecycle. Otherwise, add a focused module-level function or domain class.

Avoid adding convenience methods that merely forward arguments to another helper without reducing complexity or enforcing an invariant.

## Sample-Local Helper Pattern

Use a descriptive module name such as `dynamic_cors_helpers.py`; avoid a generic `_helpers.py` for new samples when a domain name is practical. Keep the module at the sample root unless the sample grows enough to justify a package.

A sample-local helper should:

- Contain only mechanics owned by that sample.
- Avoid user configuration constants that belong in the notebook.
- Expose a small public surface.
- Use module-qualified calls in notebooks when helpers are under active development.
- Have tests in `tests/python/test_<sample>_helpers.py`.
- Remain importable after the sample directory is added to `sys.path`.

Every notebook configures repository-scoped autoreload immediately after its first code cell's imports:

```python
from notebook_autoreload import configure_notebook_autoreload

configure_notebook_autoreload()
```

Sample-local modules still need their directory on `sys.path` before importing. Prefer `import dynamic_cors_helpers` and module-qualified calls. When runtime path setup is needed, put `import importlib` at the top of the cell and use `sample_helpers = importlib.import_module('<domain>_helpers')` after path setup, rather than adding a late `from ... import ...`.

### Notebook Autoreload Policy

[notebook_autoreload.py](notebook_autoreload.py) uses IPython's selective `%autoreload 1` mode. It registers already imported Python modules under this checkout's [shared helpers](.), [samples](../../samples/), and [infrastructures](../../infrastructure/), including transitive dependencies. Dependencies imported by later cells are registered after those cells finish. It does not eagerly import unrelated modules, reload third-party packages, or configure ordinary Python processes.

Each runtime module must declare exactly one of these identifiers in its opening docstring, followed by the reason or limitation:

- `reload_safe`: ordinary function and method edits support automatic reload.
- `reload_conditional`: ordinary code edits support reload, but stored state, constructor changes, or result schemas require explicit recreation or recomputation.
- `reload_unsafe`: excluded from automatic reload; restart the kernel after editing the module.

```python
"""Runtime helpers for a sample.

Autoreload: reload_conditional
Method edits reload. Recreate clients after constructor changes and close
existing sessions normally.
"""
```

The docstring declaration is the registration policy, not merely a comment for readers. Missing, invalid, or duplicate declarations produce a visible configuration error. Classifications describe **reload safety**, not whether importing the module normally is safe. Restart after changing a classification or the autoreload implementation itself.

Before each subsequent cell, IPython checks registered modules' source modification timestamps and reloads changed files only. It does not compare file contents: touching or saving identical source can still trigger a reload. Repeated configuration does not duplicate callbacks, replace notebook bindings, or reset deployment outputs. It never automatically reruns cells or Azure operations.

The default exclusions deliberately include [apimtypes.py](apimtypes.py), [users.py](users.py), and [infrastructure_cli.py](infrastructure_cli.py): even an ordinary edit can cause a full reload to recreate their enums and break identity checks against existing objects. [logging_config.py](logging_config.py) retains process-wide configuration, [_runtime_locks.py](_runtime_locks.py) retains command and output locks, and [show_soft_deleted_resources.py](show_soft_deleted_resources.py) can wrap stdout at import time. All are `reload_unsafe`. Infrastructure creation scripts executed as subprocesses already load fresh source on each run.

Supported function and method edits do not require a restart. However:

- Existing computed results, imported constants, generated tokens, figures, reports, and deployed resources are not recomputed. Rerun the relevant cell explicitly.
- Existing objects can pick up supported method edits, but constructors are not rerun. Recreate objects after changing initialization or stored-state requirements.
- Dataclass fields, inheritance, slots, and method/property conversions are structural changes. Recreate affected objects; restart when old and new types cannot safely coexist.
- Native extensions and installed package changes generally require a kernel restart.
- Changed Bicep, XML policies, and KQL are not Python reload events. Reread files and redeploy or rerun queries as appropriate.
- IPython reports reload errors rather than hiding them, but may retain old code. Correct the file and save again before continuing; restart if recovery is uncertain.

To enable this in an already running notebook, rerun its first code cell once. That cell still performs its normal initialization and may reset configuration or, in infrastructure notebooks, start deployment or cleanup. For activation without those effects, execute only the import and configuration call above in a separate cell. The existing `utils.enable_module_autoreload()` remains available for legacy explicit registration; notebooks use the classified default instead.

## Shared Module Design

Prefer focused shared modules over continued growth of `utils.py`.

- Name modules by capability, such as `azure_resources.py`, `azure_cost.py`, or `apimrequests.py`.
- Keep Azure command execution behind `azure_resources.py`.
- Keep data models and enums in `apimtypes.py` when they are broadly shared APIM concepts.
- Keep output formatting in `console.py` and chart rendering in `charts.py`.
- Keep authentication construction in `authfactory.py`.
- Add a new module when a capability has a distinct vocabulary, dependencies, and test surface.

A shared module should not know which notebook cell called it. Its behavior must be usable and testable from ordinary Python.

### Deployment Lifecycle

[bicep_deployment.py](bicep_deployment.py) owns template execution for samples, infrastructure creation and updates, and public-access lockdown. Its `deploy_bicep_template()` function accepts an explicit template path and parameters, serializes the ARM parameter document, and executes the Azure CLI with the existing 30-minute timeout. It never changes the process working directory or creates a resource group.

- Omit `parameters_path` to use an owned temporary directory. Sensitive deployments always use temporary parameters and suppress CLI debug, even when a persistent path or debug mode was requested.
- Temporary parameters are removed on success, failed deployment, and exceptions. Non-sensitive callers may explicitly retain a parameter file for inspection.
- An optional recovery callback can authorize one retry with the same command and parameter file. Infrastructure orchestration owns legacy diagnostic migration before execution and only authorizes recovery when migration removes a legacy setting.
- The existing `create_bicep_deployment_group()` and sample wrapper retain their public calling conventions. Legacy directory discovery remains available, while the sample wrapper passes an explicit template path without changing directories.

[infrastructures.py](infrastructures.py) constructors capture configuration only. `deploy_infrastructure()` explicitly prepares the resource group, ARM naming suffix, and account context before building parameters. Application Gateway architectures prepare this context before creating their Key Vault certificate. Preparation is reused across stages of the same instance; a failed preparation can be retried. Azure-derived attributes such as `resource_suffix` and `subscription_id` become available after preparation, not construction.

Architecture-specific private-link approval, connectivity checks, MockAPI initialization, and final verification remain in infrastructure orchestration rather than the template executor.

### Command Execution and Results

Prefer argument lists when calling `azure_resources.run()`. Arguments are passed with `shell=False`, preserving spaces, quotes, query expressions, and shell metacharacters as literal values. Existing string callers remain supported as legacy shell commands; strings are not automatically split or converted. Template deployments and deployment-operation diagnostics use argument lists.

On Windows, Azure CLI MSI batch launchers are resolved to their bundled Python executable and `azure.cli` module rather than running arguments through a batch shell. Other Windows batch launchers are rejected for argument-list execution; use their native executable instead. Native Azure CLI launchers on Windows, Linux, and macOS are resolved from `PATH`. A missing launcher or unsupported batch layout produces an explicit failed result, not a shell fallback. Azure CLI execution remains serialized.

`Output(success, text)` and its JSON/deployment accessors remain compatible. Command results additionally expose `stdout`, `stderr`, `returncode`, `timed_out`, `attempts`, `elapsed_seconds`, and `execution_error`. Successful `text` contains stdout only; failed `text` combines available streams and execution errors. Timeouts retain partial streams and have no exit code. Manually constructed outputs have no process metadata (`returncode=None`, `attempts=0`). Raw streams can contain secrets and must not be logged directly.

- The default `retry_policy='transient'` retries only recognized throttling and service-unavailability failures, within the existing `retries` limit. Permanent failures, unknown errors, local execution failures, and ambiguous timeouts are not automatically repeated.
- Use `retry_policy='never'` or `retries=0` when an operation owns polling/recovery or must execute once. Template deployments disable command-level retries; infrastructure diagnostic recovery remains the only retry authority.
- `retry_policy='always'` explicitly restores retry-on-any-failure behavior for callers that know repeating their operation is safe, including after a timeout.
- Sensitive operations withhold command arguments and output from logs and suppress automatic CLI debug by default. `APIM_SAMPLES_UNMASK_SENSITIVE_HEADERS=true` bypasses Python-side secret masking and sensitive-output suppression, including JSON stdout and deployment outputs, so complete APIM subscription keys and other request/response data can be logged. [unmasked_logging.py](unmasked_logging.py) overrides Azure Core and legacy msrest logging redactors only in the current Python process. **Azure CLI still masks its own sensitive parameters and headers; its built-in masking is not overridden.** Python cannot recover values already masked by the CLI or a remote service. Use `DEBUG` for complete Python diagnostics and clear all resulting logs and notebook outputs before sharing.

## Naming and API Surface

- Use verbs for operations: `load_test_results()`, `wait_for_gateway_dns()`.
- Use nouns for stateful capabilities: `DynamicCorsTestRunner`, `SampleDeploymentContext`.
- Prefix private implementation details with `_`.
- Avoid ambiguous names such as `Helper`, `Manager`, `process()`, or `handle()` without a domain qualifier.
- Keep public method names consistent with established repository vocabulary.
- Do not preserve obsolete aliases indefinitely. Migrate callers and remove dead compatibility layers when the repository controls every consumer.

## Side Effects and Idempotency

Document or make obvious every side effect: Azure changes, HTTP traffic, local files, console output, environment access, and sleeps.

- Constructors validate and capture state; avoid network or Azure operations in constructors.
- Explicit methods perform remote work.
- Persistence helpers write atomically when partial files would be harmful.
- Repeated execution should update or replace owned state without duplicating unrelated state.
- Session-owning classes close sessions in `finally` paths or context-manager exit.
- Temporary files are deleted in `finally` blocks.
- Polling accepts an injectable sleep function or schedule when unit tests need to avoid delays.

## Testing Strategy

Every extracted helper needs tests proportional to its risk.

### Sample-local helpers

Test:

- Pure transformations and parsing.
- Resource cleanup on success and exceptions.
- Persistence merge and replacement behavior.
- Missing, empty, and malformed local data.
- Request construction with mocked sessions.

### Shared helpers

Test:

- Public success and failure contracts.
- Edge cases and invalid inputs.
- Azure CLI behavior with mocked `azure_resources` calls.
- Cross-platform command and path handling.
- Context-manager cleanup.
- Backward compatibility only where an active consumer requires it.

Tests must not require live Azure resources. Live notebook validation remains a separate publication check and must not be inferred from unit-test success.

Run the combined checks from the repository root:

```powershell
.\tests\python\check_python.ps1
```

```bash
./tests/python/check_python.sh
```

Target at least 95% coverage for changed helper modules, while prioritizing meaningful branch and failure coverage over line-count padding.

## Review Checklist

Before merging a helper or supporting-class change, verify:

- [ ] The APIM concept and user configuration remain visible in the notebook.
- [ ] The code lives at the narrowest correct ownership level.
- [ ] Existing helpers were composed or extended where their responsibility matched.
- [ ] Inputs, outputs, side effects, and failure behavior are explicit.
- [ ] No helper depends on hidden notebook globals or another cell's runtime objects.
- [ ] Resource ownership and cleanup are deterministic.
- [ ] Public contracts use type annotations and concise docstrings.
- [ ] Sample-local code has not been promoted without a real second consumer.
- [ ] Unit tests cover success, failure, and cleanup paths.
- [ ] Notebook outputs are cleared and every code cell parses.
- [ ] Ruff and the combined Python checks pass.
- [ ] Live Azure scenarios still requiring execution are stated explicitly.

## Refactoring Sequence

Use this order when moving mechanics out of a notebook:

1. Identify the educational intent and leave that sequence visible.
2. Define a small helper contract from explicit inputs and outputs.
3. Place it sample-local unless reuse already exists.
4. Add unit tests for behavior and failure paths.
5. Replace notebook mechanics with a readable call.
6. Remove cross-cell functions, sessions, and mutable runtime dependencies.
7. Declare the module's reload classification and initialize the notebook's repository-scoped selective autoreload.
8. Promote to `shared/python/` later if a second real consumer establishes a stable shared contract.
