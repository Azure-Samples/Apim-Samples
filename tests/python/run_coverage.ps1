# PowerShell script to run pytest with coverage and store .coverage in tests/python
$env:COVERAGE_FILE = "tests/python/.coverage"
pytest --cov=shared/python --cov-config=tests/python/.coveragerc --cov-report=html:tests/python/htmlcov tests/python/
