.PHONY: help install test lint format check clean build

help:  ## Show this help
	@egrep -h '\s##\s' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install package in development mode
	pip install -e ".[dev]"

test:  ## Run tests
	pytest tests/ -v

test-cov:  ## Run tests with coverage
	pytest tests/ -v --cov=src/kanban --cov-report=term-missing --cov-report=html

test-cov-xml:  ## Run tests with XML coverage report
	pytest tests/ -v --cov=src/kanban --cov-report=xml

coverage-report:  ## Generate coverage reports (HTML and terminal)
	pytest tests/ --cov=src/kanban --cov-report=html --cov-report=term-missing

coverage-html:  ## Generate HTML coverage report and open in browser
	pytest tests/ --cov=src/kanban --cov-report=html
	@echo "Coverage report generated in htmlcov/index.html"

coverage-clean:  ## Clean coverage files
	rm -rf htmlcov/
	rm -f coverage.xml
	rm -f .coverage

coverage-check:  ## Check coverage meets minimum threshold
	python3 scripts/check_coverage.py

lint:  ## Run linter
	ruff check src/ tests/

format:  ## Format code
	ruff format src/ tests/

check:  ## Run all quality checks
	ruff check src/ tests/
	ruff format --check src/ tests/
	mypy src/

fix:  ## Fix auto-fixable issues
	ruff check src/ tests/ --fix
	ruff format src/ tests/

clean:  ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf htmlcov/
	rm -f coverage.xml
	rm -f .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +

build:  ## Build the package
	python -m build

publish-test:  ## Publish to test PyPI
	python -m twine upload --repository testpypi dist/*

publish:  ## Publish to PyPI
	python -m twine upload dist/*

pre-commit-install:  ## Install pre-commit hooks
	pre-commit install

pre-commit-run:  ## Run pre-commit on all files
	pre-commit run --all-files