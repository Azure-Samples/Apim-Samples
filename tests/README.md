# APIM Samples Testing

This directory contains all testing infrastructure and code quality tools for the APIM Samples repository.

## Quick Start

### Run All Checks (Recommended)

The fastest way to validate your code changes:

```powershell
# From repository root
.\tests\python\check_python.ps1
```

```bash
# From repository root
./tests/python/check_python.sh
```

This runs both pylint (code linting) and pytest (unit tests) with a single command.

## Code Quality Tools

### Combined Checks (check_python)

**Preferred method** - Runs both linting and testing:

```powershell
# Windows
.\tests\python\check_python.ps1                 # Run all checks
.\tests\python\check_python.ps1 -ShowLintReport # Include detailed pylint report
```

```bash
# Linux/macOS
./tests/python/check_python.sh                  # Run all checks
./tests/python/check_python.sh --show-report    # Include detailed pylint report
```

### Linting Only (pylint)

Run pylint separately when you only need linting:

```powershell
# Windows - from repository root
.\tests\python\run_pylint.ps1                   # Default: all Python code
.\tests\python\run_pylint.ps1 -ShowReport       # Show detailed report
.\tests\python\run_pylint.ps1 -Target "samples" # Lint specific folder
```

```bash
# Linux/macOS - from repository root
./tests/python/run_pylint.sh                    # Default: all Python code
./tests/python/run_pylint.sh samples --show-report # Lint specific folder with report
```

#### Pylint Reports

All pylint runs generate timestamped reports in `tests/python/pylint/reports/`:
- **JSON format**: Machine-readable for CI/CD integration
- **Text format**: Human-readable detailed analysis
- **Latest symlinks**: `latest.json` and `latest.txt` always point to the most recent run

The script automatically displays a **Top 10 Issues Summary** showing the most frequent code quality issues.

### Testing Only (pytest)

Run tests separately when you only need test execution:

```powershell
# Windows - from repository root
.\tests\python\run_tests.ps1
```

```bash
# Linux/macOS - from repository root
./tests/python/run_tests.sh
```

Both scripts:
- Run all tests in `tests/python` using pytest
- Generate code coverage reports:
  - HTML: `htmlcov/index.html` (at repository root)
  - XML: `coverage.xml` (for VS Code integration)
  - JSON: `coverage.json`
- Store the raw coverage data in `.coverage` (at repository root)

#### Viewing Coverage Reports

**In VS Code:**
- Coverage is automatically displayed in the file explorer (showing % next to Python files)
- Coverage gutters appear in open Python files (green/red/orange lines)
- Install the "Coverage Gutters" extension for enhanced visualization

**In Browser:**
- Open `htmlcov/index.html` in your browser for detailed coverage information

## Test Infrastructure

### Configuration Files

- `.pylintrc` - Pylint configuration and rules
- `.coveragerc` - Coverage.py configuration
- `pytest.ini` - Pytest configuration and markers
- `conftest.py` - Shared pytest fixtures

### Test Files

All test files follow the pattern `test_*.py` and test corresponding modules in `shared/python`.

### Pytest Markers

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.http` - Tests involving HTTP/mocking

Markers are registered in `pytest.ini`.

## Continuous Integration

On every push or pull request, GitHub Actions will:
- Install dependencies
- Run all Python tests with coverage
- Run pylint on all Python code
- Upload coverage reports as artifacts

## Sample Test Matrix

A comprehensive compatibility test matrix for samples and infrastructure types is maintained in [Test-Matrix.md](./Test-Matrix.md).

## Infrastructure Types

The repository currently supports the following infrastructure types:

1. **SIMPLE_APIM** - Simple API Management with no dependencies
2. **APIM_ACA** - Azure API Management connected to Azure Container Apps
3. **AFD_APIM_PE** - Azure Front Door Premium connected to Azure API Management (Standard V2) via Private Link

## Testing Requirements

To ensure robust functionality across environments, all samples should:

1. Be tested in both local development and Codespaces/Dev Container environments
2. Pass all tests for their supported infrastructures as indicated in the matrix above
3. Be verified that the `supported_infrastructures` variable in each sample's `create.ipynb` file is correctly reflected in this matrix

## Testing Workflow

1. Print this document for manual tracking or use markdown checkboxes in digital form
2. For each combination of sample, infrastructure, and environment:
   - Deploy the infrastructure and sample
   - Run tests
   - Mark the corresponding checkbox when tests pass
3. Document any issues encountered in the "Test Notes" section below

## Test Procedure

For each sample and infrastructure combination:

1. Deploy the infrastructure using the appropriate method:
   ```bash
   cd infrastructure/<infrastructure-name>
   # Execute the create.ipynb notebook
   ```

2. Deploy and test the sample:
   ```bash
   cd samples/<sample-name>
   # Execute the create.ipynb notebook with the matching infrastructure
   ```

3. Verify that all operations work correctly and no errors are reported

4. Clean up resources when testing is complete:
   ```bash
   # Execute the clean-up.ipynb notebook in the infrastructure directory
   ```

## Test Notes

| Date | Tester | Sample | Infrastructure | Environment | Notes |
|------|--------|--------|---------------|-------------|-------|
| YYYY-MM-DD | Name | sample-name | infra-name | Local/DevC | Any issues or observations |

## General Notes

- "N/A" indicates that the sample does not support that particular infrastructure type
- The `_TEMPLATE` sample is not meant for deployment; it's a template for creating new samples
- The test matrix should be updated whenever new samples or infrastructures are added
- Infrastructure limitations should be documented when a sample is incompatible with a specific infrastructure type
- Tester name, date, and detailed notes should be recorded for any failures or unexpected behavior
