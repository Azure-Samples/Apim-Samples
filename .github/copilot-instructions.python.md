---
applyTo: "**/*.py"
---

# Copilot Instructions (Python)

## Goals

- Make changes that are easy to review, test, and maintain.
- Keep scripts cross-platform (Windows, Linux, macOS).
- Prefer minimal, working implementations (MVP), then iterate.

## Project Context

- Python code lives primarily under `shared/python/`, `setup/`, `infrastructure/`, and `tests/python/`.
- The repository uses Azure CLI from Python for many operations.

## Style and Conventions

- Prefer Python 3.12+ features unless otherwise required.
- Keep all imports at the top of the file.
- Use type hints and concise docstrings (PEP 257).
- Use 4-space indentation and PEP 8 conventions.
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

## Linting (pylint)

- Respect the repository pylint configuration at `tests/python/.pylintrc`.
- When changing Python code, run pylint and ensure changes do not worsen the pylint rating unexpectedly.
- Prefer fixing root causes (e.g., import structure, error handling) over suppressions.

## Testing

- Add or update pytest unit tests when changing behavior.
- Prefer focused tests for the code being changed.
- Avoid tests that require live Azure access; mock Azure CLI interactions and `azure_resources` helpers.

## Azure Helper Imports

- Prefer calling Azure resource helper functions via `import azure_resources as az`.
- Avoid calling Azure-resource helpers through `utils` re-exports in new code.
- When patching in tests, patch the symbol actually used by the module under test (e.g., `module.az.does_resource_group_exist`).
