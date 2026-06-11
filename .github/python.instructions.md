---
description: 'Python coding conventions and guidelines'
applyTo: '**/*.py,**/*.ipynb'
---

# Copilot Instructions (Python)

## Critical: Load Ruff Configuration First

**BEFORE making any changes to Python files**, always load the ruff configuration into context:

1. Use `read_file` to load `pyproject.toml` and review the `[tool.ruff]` and `[tool.ruff.lint]` sections
2. Review the ignored rules and per-file exceptions
3. Apply these rules when writing or modifying Python code

This ensures all code changes comply with the project's linting standards from the start.

## Ruff Expectations

- Use explicit imports (avoid `from module import *`), especially in notebooks, to prevent `F403/F405`.
- Keep lines within the configured length limit (**150 characters** per `pyproject.toml`), and wrap long strings or calls. **Inline comments on assignments are the most commonly missed line-length offender** — when `var = value  # comment` would exceed 150 chars, move the comment to its own line(s) above the assignment.
- Avoid f-strings without placeholders (e.g., `F541`).
- **Ruff gap:** `PLC0415` (`import-outside-toplevel`) only flags imports inside functions and classes. It does **not** flag imports inside module-level `if` / `else` / `try` blocks. Ruff will not catch those, so the top-of-file import rule below must be enforced manually.
- **Notebook cells follow the same rules** as `.py` files except for `F821` and `F401` (suppressed via per-file-ignores because notebook cells share kernel state). Line-length, quote style, and import placement still apply. After editing notebook cells, run `get_errors` and resolve any ruff `compileError` entries; ignore only the `"X" is not defined` cross-cell false positives.

## Goals

- Make changes that are easy to review, test, and maintain.
- Keep scripts cross-platform (Windows, Linux, macOS).
- Prefer minimal, working implementations (MVP), then iterate.

## Project Context

- Python code lives primarily under `shared/python/`, `setup/`, `infrastructure/`, and `tests/python/`.
- The repository uses Azure CLI from Python for many operations.
- Follow `shared/python/README.md` as the authoritative architecture guide for notebook boundaries, helper placement, functions versus classes, explicit state, resource lifecycles, promotion criteria, and helper testing.

## Notebook and Helper Architecture

- Keep user configuration, scenario intent, APIM concepts, expected outcomes, and assertions in notebooks.
- Extract incidental mechanics such as parsers, retries, polling, persistence, Azure command composition, response normalization, repeated request setup, and multi-step cleanup into Python modules.
- Start one-sample behavior in a descriptive `samples/<sample>/<domain>_helpers.py` module. Promote directly to a focused `shared/python/` module only after a second active consumer establishes the same stable contract.
- Do not create a sample-local forwarding wrapper around a shared helper. Compose the narrowest owning contract directly.
- Helpers must use explicit inputs and return values or typed dataclasses. They must not read or mutate notebook globals, IPython state, or variables owned by another cell.
- Constructors capture and validate state; explicit methods perform Azure, network, file, sleep, or other observable work.
- A helper that creates an HTTP session, temporary file, or closeable resource owns deterministic cleanup on success and exceptions. Use a context manager when ownership spans multiple calls.
- Inject command runners, session factories, sleeps, clocks, or other external boundaries when this avoids live Azure access, network calls, or real waits in unit tests.
- Use module-qualified imports plus `utils.enable_module_autoreload('<module_name>')` for actively edited sample-local pure-Python modules. Do not use broad autoreload.
- Line count alone does not justify extraction. Extract when responsibility, lifecycle, repetition, or testability belongs outside the educational workflow.

## Style and Conventions

- Prefer Python 3.12+ features unless otherwise required.
- Keep **all** imports at the top of the file. Do not place `import` statements inside `if` / `else` / `try` blocks or inside functions. Hoist them even when only one branch uses the module. Ruff `PLC0415` will catch function-scope imports but will **not** catch imports inside module-level conditional blocks, so apply this rule manually.
- Use type hints and concise docstrings (PEP 257).
- Use 4-space indentation and PEP 8 conventions.
- Surround an equal sign by a space on each side.
- Use only straight quotes (U+0027 and U+0022), not typographic quotes.
- Use whitespace to separate logical sections and add a blank line before `return` statements.
- Use f-strings unless there is no interpolation.

## Import Style Guidelines

- Imports from this repo should be grouped, be imported last, and have a group header called `# APIM Samples imports`
- Only use multi-line imports when a single-line is too long
- Avoid mixing patterns: Don't use both `import module` and `from module import ...` for the same module
- Parentheses in imports: Only use parentheses for multi-line imports, not for single-line imports:
  - Good: `from console import print_error, print_val`
  - Bad: `from console import (print_error, print_val)`
  - Good (multi-line):
    ```python
    from console import (
        print_error,
        print_info,
        print_ok
    )
    ```
- Order within APIM Samples imports section:
  1. Module imports with aliases (e.g., `import azure_resources as az`)
  2. Specific type/constant imports (e.g., `from apimtypes import INFRASTRUCTURE`)
  3. Specific function imports (e.g., `from console import print_error`)

## Code Quality Checklist

Before completing any Python code changes, verify:

- All ruff warnings and errors are resolved (`ruff check <file>`)
  - Ruff rules cover these, but we don't see `pyproject.toml` being added to context. Therefore, please pay special attention to these common occurrences:
      - No trailing whitespace
      - No assertion of empty strings in tests (use `assert not`)
- Code follows PEP 8 and the style guidelines in this file
- Import statements for modules within this repo are placed last in the imports and are grouped with the `# APIM Samples imports` header
- Type hints are present where appropriate
- No unnecessary comments; docstrings are present for functions and classes
- Edge cases and error handling are implemented
- Prefer fixing root causes (e.g., import structure, error handling) over suppressions.

## Testing

- Aim for 95+% code coverage for each file.
- Slow tests (> 0.1s runtime) should be identified and fixed, if possible.
- Add or update pytest unit tests when changing behavior.
- Prefer focused tests for the code being changed.
- When testing cleanup after an exception, place `pytest.raises(...)` in an outer `with` block and the resource-owning context manager in a nested inner block. Do not combine them in one comma-separated `with` statement because static analysis may report the cleanup assertions as unreachable.
- If static analysis still treats assertions after `pytest.raises(...)` as unreachable because the test body contains a literal `raise`, trigger the expected exception through the exercised method or a mock `side_effect` instead. Keep the exception and post-block cleanup assertions unchanged.
- Avoid tests that require live Azure access; mock Azure CLI interactions and `azure_resources` helpers.
- Every extracted helper requires focused tests for its public success and failure contracts. Include malformed inputs and resource cleanup where applicable.
- Place sample-local helper tests in `tests/python/test_<sample>_helpers.py` and target at least 95% meaningful statement and branch coverage for changed helper modules.
- Abstract and consolidate common test overhead into the `test_helpers.py` file.

## Azure Helper Imports

- Prefer calling Azure resource helper functions via `import azure_resources as az`.
- Avoid calling Azure-resource helpers through `utils` re-exports in new code.
- When patching in tests, patch the symbol actually used by the module under test (e.g., `module.az.does_resource_group_exist`).
