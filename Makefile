# CleanEnroll Backend - Development Makefile

.PHONY: help install install-dev format lint type-check security test test-cov clean all

help:
	@echo "CleanEnroll Backend Development Commands:"
	@echo ""
	@echo "  make install        - Install production dependencies"
	@echo "  make install-dev    - Install development dependencies"
	@echo "  make format         - Format code with Black"
	@echo "  make lint           - Run linters (Ruff + Pylint)"
	@echo "  make type-check     - Run MyPy type checker"
	@echo "  make security       - Run security scanners (Bandit)"
	@echo "  make dead-code      - Find unused code with Vulture"
	@echo "  make test           - Run tests"
	@echo "  make test-cov       - Run tests with coverage"
	@echo "  make pre-commit     - Install pre-commit hooks"
	@echo "  make clean          - Remove cache and build files"
	@echo "  make all            - Run format, lint, type-check, security, test"
	@echo ""

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

format:
	@echo "🎨 Formatting code with Black..."
	black app/ --line-length 100
	@echo "✅ Code formatted!"

lint:
	@echo "🔍 Running Ruff linter..."
	ruff check app/ --fix
	@echo "🔍 Running Pylint..."
	pylint app/ --max-line-length=100 --disable=C0111,R0903,R0913,W0511
	@echo "✅ Linting complete!"

type-check:
	@echo "🔍 Running MyPy type checker..."
	mypy app/ --ignore-missing-imports
	@echo "✅ Type checking complete!"

security:
	@echo "🔒 Running Bandit security scanner..."
	bandit -r app/ -c pyproject.toml
	@echo "✅ Security scan complete!"

dead-code:
	@echo "🔍 Finding unused code with Vulture..."
	vulture app/ --min-confidence 60
	@echo "✅ Dead code analysis complete!"

test:
	@echo "🧪 Running tests..."
	pytest
	@echo "✅ Tests complete!"

test-cov:
	@echo "🧪 Running tests with coverage..."
	pytest --cov=app --cov-report=term-missing --cov-report=html
	@echo "✅ Tests complete! Coverage report: htmlcov/index.html"

pre-commit:
	@echo "🪝 Installing pre-commit hooks..."
	pre-commit install
	@echo "✅ Pre-commit hooks installed!"

clean:
	@echo "🧹 Cleaning cache and build files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage
	@echo "✅ Cleanup complete!"

all: format lint type-check security test
	@echo "✅ All checks passed!"
