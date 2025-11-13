.PHONY: help pip-compile pip-sync test test-unit test-integration test-stress test-cov test-fast clean-test

help:
	@echo "Available commands:"
	@echo "  make pip-compile        - Compile requirements.in to requirements.txt"
	@echo "  make pip-sync           - Sync installed packages with requirements.txt"
	@echo "  make test               - Run all tests"
	@echo "  make test-unit          - Run unit tests only"
	@echo "  make test-integration   - Run integration tests only"
	@echo "  make test-stress        - Run stress tests only"
	@echo "  make test-cov           - Run tests with coverage report"
	@echo "  make test-fast          - Run tests in parallel"
	@echo "  make clean-test         - Clean test cache and coverage files"

pip-compile:
	pip-compile requirements.in -o requirements.txt

pip-sync:
	pip-sync requirements.txt

# Test commands
test:
	pytest -v

test-unit:
	pytest -v -m unit

test-integration:
	pytest -v -m integration

test-stress:
	pytest -v -m stress --timeout=120

test-cov:
	pytest --cov=app --cov-report=html --cov-report=term-missing
	@echo "Coverage report generated in htmlcov/index.html"

test-fast:
	pytest -n auto

clean-test:
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete