# Code Quality Guide - CleanEnroll Backend

## Overview
This guide covers all code quality tools installed and how to use them for maintaining clean, secure, and well-organized Python code.

## Installed Tools

### 1. Black - Code Formatter
**Purpose**: Automatic code formatting for consistent style
**Version**: 24.3.0

```bash
# Format all code
make format

# Or directly
black app/ --line-length 100

# Check without modifying
black --check app/
```

**What it does**:
- Enforces consistent code style
- Formats line length, indentation, quotes
- Removes manual formatting debates

### 2. Ruff - Fast Python Linter
**Purpose**: Lightning-fast linting for code quality
**Version**: 0.3.0

```bash
# Run linter with auto-fix
make lint

# Or directly
ruff check app/ --fix

# Check only (no fixes)
ruff check app/
```

**What it checks**:
- Unused imports (F401)
- Unused variables (F841)
- Code complexity
- Style violations
- Best practices

### 3. Autoflake - Unused Code Remover
**Purpose**: Automatically removes unused imports and variables
**Version**: 2.3.1

```bash
# Check for unused code
make unused-imports

# Auto-fix everything
make autofix

# Or directly
autoflake --in-place --recursive --remove-all-unused-imports --remove-unused-variables app/
```

**What it removes**:
- Unused imports
- Unused variables
- Duplicate keys in dictionaries

### 4. Vulture - Dead Code Detector
**Purpose**: Finds unused functions, classes, and variables
**Version**: 2.11

```bash
# Find dead code
make dead-code

# Or directly
vulture app/ vulture_whitelist.py --min-confidence 80
```

**What it finds**:
- Unused functions
- Unused classes
- Unused methods
- Unused properties
- Unused variables

**Whitelist**: `vulture_whitelist.py` contains intentionally unused code (framework requirements)

### 5. Unimport - Import Analyzer
**Purpose**: Finds and removes unused imports
**Version**: 1.2.1

```bash
# Check for unused imports
unimport --check app/

# Remove unused imports
unimport --remove app/
```

**What it does**:
- Detects unused imports
- Suggests removals
- More thorough than autoflake

### 6. MyPy - Type Checker
**Purpose**: Static type checking for Python
**Version**: 1.9.0

```bash
# Run type checker
make type-check

# Or directly
mypy app/ --ignore-missing-imports
```

**What it checks**:
- Type annotations
- Type consistency
- Function signatures
- Return types

### 7. Bandit - Security Scanner
**Purpose**: Finds common security issues
**Version**: 1.7.8

```bash
# Run security scan
make security

# Or directly
bandit -r app/ -ll -f txt
```

**What it finds**:
- SQL injection risks
- Hardcoded passwords
- Unsafe deserialization
- Weak cryptography
- Shell injection risks

### 8. Pylint - Comprehensive Linter
**Purpose**: Detailed code analysis
**Version**: 3.1.0

```bash
# Run pylint (included in make lint)
pylint app/ --max-line-length=100
```

**What it checks**:
- Code smells
- Refactoring opportunities
- Convention violations
- Error detection

### 9. pip-check-reqs - Dependency Checker
**Purpose**: Finds unused and missing dependencies
**Version**: 2.5.3

```bash
# Check dependencies
make check-deps

# Or directly
pip-extra-reqs app/  # Find unused
pip-missing-reqs app/  # Find missing
```

**What it finds**:
- Unused dependencies in requirements.txt
- Missing dependencies
- Version conflicts

## Quick Commands

### Daily Development
```bash
# Before committing
make autofix      # Auto-fix imports and format
make lint         # Check code quality
make type-check   # Verify types
make security     # Security scan
```

### Full Quality Check
```bash
# Run everything
make all
```

### Specific Checks
```bash
make format          # Just format code
make unused-imports  # Check for unused imports
make dead-code      # Find unused functions/classes
make check-deps     # Check dependencies
```

## Pre-commit Hooks

Install pre-commit hooks to run checks automatically:

```bash
make pre-commit
```

This will run on every commit:
- Black formatting
- Ruff linting
- Autoflake unused import removal
- Bandit security checks

## Configuration Files

### pyproject.toml
Main configuration for Black, Ruff, and other tools:
```toml
[tool.black]
line-length = 100
target-version = ['py39']

[tool.ruff]
line-length = 100
select = ["E", "F", "W", "I"]
```

### vulture_whitelist.py
Whitelist for intentionally unused code:
- Framework-required parameters (cls, ctx)
- SQLAlchemy event listener parameters
- Model imports for relationship resolution

### .pre-commit-config.yaml
Pre-commit hook configuration

## Best Practices

### 1. Run Before Committing
```bash
make autofix && make lint && make security
```

### 2. Fix Issues Incrementally
Don't try to fix everything at once. Focus on:
1. Security issues (high priority)
2. Unused imports/variables
3. Type errors
4. Style issues

### 3. Use Type Hints
```python
# Good
def calculate_price(base: float, tax: float) -> float:
    return base * (1 + tax)

# Bad
def calculate_price(base, tax):
    return base * (1 + tax)
```

### 4. Remove Dead Code
If Vulture finds unused code:
- Verify it's truly unused
- Remove it or add to whitelist
- Don't keep "just in case" code

### 5. Keep Dependencies Clean
```bash
# Regularly check
make check-deps

# Remove unused packages from requirements.txt
```

## CI/CD Integration

Add to your CI pipeline:

```yaml
# .github/workflows/quality.yml
- name: Code Quality Checks
  run: |
    pip install -r requirements-dev.txt
    make autofix
    make lint
    make type-check
    make security
    make test
```

## Metrics

### Current Status (After Cleanup)
- ✅ 0 high/medium security issues (Bandit)
- ✅ 4 files with unused imports fixed (Autoflake)
- ✅ 11 files reformatted (Black)
- ✅ All intentional unused code whitelisted (Vulture)
- ✅ 6 unused dependencies removed

### Goals
- Maintain 0 security issues
- Keep code coverage > 80%
- No unused imports/variables
- Consistent formatting (Black)
- Type hints on all public functions

## Troubleshooting

### "Too many issues found"
Start with high-priority issues:
```bash
bandit -r app/ -ll  # Only high severity
ruff check app/ --select F  # Only errors
```

### "False positives in Vulture"
Add to `vulture_whitelist.py`:
```python
_.your_variable  # unused variable (reason)
```

### "Type checking fails"
Add type stubs or ignore:
```bash
pip install types-package-name
# Or in code:
import package  # type: ignore
```

### "Autoflake removes needed imports"
Use `# noqa: F401` comment:
```python
from .models import User  # noqa: F401 - needed for SQLAlchemy
```

## Resources

- [Black Documentation](https://black.readthedocs.io/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Bandit Documentation](https://bandit.readthedocs.io/)
- [MyPy Documentation](https://mypy.readthedocs.io/)
- [Vulture Documentation](https://github.com/jendrikseipp/vulture)

## Summary

These tools help maintain:
- **Clean code**: No unused imports/variables
- **Consistent style**: Black formatting
- **Type safety**: MyPy checking
- **Security**: Bandit scanning
- **Quality**: Ruff + Pylint linting
- **Lean dependencies**: pip-check-reqs

Run `make help` to see all available commands!
