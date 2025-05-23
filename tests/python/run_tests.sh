# Shell script to run pytest with coverage and store .coverage in tests/python
COVERAGE_FILE=tests/python/.coverage
export COVERAGE_FILE
pytest -v --cov=shared/python --cov-config=tests/python/.coveragerc --cov-report=html:tests/python/htmlcov tests/python/
