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

| Behavior                                           | Placement                                      | Reason                                                        |
| -------------------------------------------------- | ---------------------------------------------- | ------------------------------------------------------------- |
| Dynamic CORS cache orchestration                   | `samples/dynamic-cors/dynamic_cors_helpers.py` | One sample owns the behavior and vocabulary                   |
| Costing-specific API construction                  | `samples/costing/_helpers.py`                  | One sample owns the evolving cost model                       |
| Role-based JWT request execution for AuthX samples | `shared/python/auth_testing.py`                | AuthX and AuthX-Pro use the same request and session contract |
| APIM endpoint resolution                           | `NotebookHelper`                               | Broad notebook coordination using existing helper state       |

Do not create both a sample-local wrapper and a shared helper for the same operation. A notebook should call the narrowest owning contract directly.

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

Register an actively edited pure-Python module once after its directory is on `sys.path`:

```python
utils.enable_module_autoreload('dynamic_cors_helpers')
```

Selective autoreload checks only registered modules and reloads them only after their source changes. It preserves deployment outputs and other notebook variables. It does not replace rerunning a cell that already computed values, rebuilding existing class instances, restarting after native-extension changes, or redeploying changed Bicep.

## Shared Module Design

Prefer focused shared modules over continued growth of `utils.py`.

- Name modules by capability, such as `azure_resources.py`, `azure_cost.py`, or `apimrequests.py`.
- Keep Azure command execution behind `azure_resources.py`.
- Keep data models and enums in `apimtypes.py` when they are broadly shared APIM concepts.
- Keep output formatting in `console.py` and chart rendering in `charts.py`.
- Keep authentication construction in `authfactory.py`.
- Add a new module when a capability has a distinct vocabulary, dependencies, and test surface.

A shared module should not know which notebook cell called it. Its behavior must be usable and testable from ordinary Python.

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
7. Add selective autoreload only for actively edited pure-Python modules.
8. Promote to `shared/python/` later if a second real consumer establishes a stable shared contract.
