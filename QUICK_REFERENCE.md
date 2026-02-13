# 🚀 Quick Reference - CleanEnroll Backend Cleanup

## One-Line Commands

```bash
# Windows - Run everything
.\run_cleanup.ps1

# Linux/Mac - Run everything
./run_cleanup.sh

# Or use Makefile
make all
```

## Individual Commands

```bash
# Format code
python -m black app/ --line-length 100

# Fix linting
python -m ruff check app/ --fix

# Find dead code
python -m vulture app/ --min-confidence 60 > vulture_report.txt

# Security scan
python -m bandit -r app/ -f txt -o bandit_report.txt

# Type check
python -m mypy app/ --ignore-missing-imports > mypy_report.txt
```

## Makefile Commands

```bash
make install-dev    # Install development tools
make format         # Format code with Black
make lint           # Run linters (Ruff + Pylint)
make security       # Run security scan (Bandit)
make dead-code      # Find unused code (Vulture)
make type-check     # Run type checker (MyPy)
make test           # Run tests
make test-cov       # Run tests with coverage
make clean          # Remove cache files
make all            # Run format, lint, type-check, security, test
```

## File Guide

| File | Purpose | When to Read |
|------|---------|--------------|
| `START_HERE.md` | Overview & quick start | Read first |
| `CLEANUP_README.md` | Complete guide | For detailed instructions |
| `CLEANUP_GUIDE.md` | Examples & solutions | When fixing issues |
| `REFACTORING_PLAN.md` | Architecture plan | For major refactoring |
| `IMPLEMENTATION_SUMMARY.md` | Current state | To understand what's done |
| `QUICK_REFERENCE.md` | This file | For quick commands |

## Reports Generated

| Report | What It Shows | Action Required |
|--------|---------------|-----------------|
| `vulture_report.txt` | Dead code, unused imports | Remove unused code |
| `bandit_report.txt` | Security vulnerabilities | Fix security issues |
| `mypy_report.txt` | Type errors | Add type hints |

## Common Fixes

### Remove Unused Imports
```python
# Before
import os
import sys  # ← Remove if unused
from typing import Optional

# After
import os
from typing import Optional
```

### Fix Security Issues
```python
# Before - Hardcoded secret ❌
API_KEY = "sk_live_abc123"

# After - Environment variable ✅
import os
API_KEY = os.getenv("API_KEY")
```

### Add Type Hints
```python
# Before ❌
def calculate(x, y):
    return x + y

# After ✅
def calculate(x: int, y: int) -> int:
    return x + y
```

### Add Docstrings
```python
# Before ❌
def create_user(name, email):
    return User(name=name, email=email)

# After ✅
def create_user(name: str, email: str) -> User:
    """
    Create a new user.
    
    Args:
        name: User's full name
        email: User's email address
        
    Returns:
        Created user instance
    """
    return User(name=name, email=email)
```

## Workflow

```
1. Backup Code
   ↓
2. Run Cleanup Script
   ↓
3. Review Reports
   ↓
4. Fix Issues
   ↓
5. Test Application
   ↓
6. Commit Changes
```

## Time Estimates

| Task | Time |
|------|------|
| Setup | 5 min |
| Automated cleanup | 15 min |
| Review reports | 30-60 min |
| Manual fixes | 1-2 hours |
| Testing | 30 min |
| **Total** | **2-3 hours** |

## Safety Commands

```bash
# Before starting - Backup
git add .
git commit -m "chore: checkpoint before cleanup"
git checkout -b backup-before-cleanup
git checkout main

# If something breaks - Restore
git checkout backup-before-cleanup

# Or revert last commit
git revert HEAD
```

## Testing Commands

```bash
# Run application
python run.py

# Run tests (if available)
pytest

# Run with coverage
pytest --cov=app --cov-report=html
```

## Git Commit Messages

```bash
# After formatting
git commit -m "style: format code with Black"

# After removing dead code
git commit -m "refactor: remove unused imports and dead code"

# After security fixes
git commit -m "security: fix vulnerabilities from Bandit scan"

# After adding type hints
git commit -m "feat: add type hints for better type safety"

# After full cleanup
git commit -m "refactor: comprehensive code cleanup

- Format code with Black
- Fix linting issues with Ruff
- Remove dead code identified by Vulture
- Fix security vulnerabilities from Bandit
- Add type hints for MyPy compliance
- Add docstrings to functions"
```

## Tool Versions

```bash
# Check installed versions
python -m black --version
python -m ruff --version
python -m vulture --version
python -m bandit --version
python -m mypy --version
```

## Configuration Files

| File | Tool | Purpose |
|------|------|---------|
| `pyproject.toml` | All tools | Central configuration |
| `.pre-commit-config.yaml` | Pre-commit | Git hooks |
| `requirements-dev.txt` | Pip | Dev dependencies |
| `Makefile` | Make | Convenient commands |

## Pre-commit Hooks

```bash
# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files

# Update hooks
pre-commit autoupdate

# Skip hooks (emergency only)
git commit --no-verify
```

## Troubleshooting

### Issue: Command not found
```bash
# Solution: Install development tools
pip install -r requirements-dev.txt
```

### Issue: Import errors after cleanup
```python
# Solution: Keep imports needed by SQLAlchemy
from . import models  # noqa: F401
```

### Issue: Bandit false positives
```python
# Solution: Add nosec comment
user = db.query(User).filter(User.id == id).first()  # nosec B608
```

### Issue: Pre-commit hooks failing
```bash
# Solution: Fix issues first
make format
make lint

# Or bypass (not recommended)
git commit --no-verify
```

## Success Criteria

After cleanup, you should have:
- ✅ Consistently formatted code
- ✅ No linting errors
- ✅ No unused code
- ✅ No security vulnerabilities
- ✅ Type hints on functions
- ✅ Docstrings on functions
- ✅ Professional appearance

## Next Steps

1. ✅ Run cleanup script
2. ✅ Review reports
3. ✅ Fix issues
4. ✅ Test application
5. ✅ Commit changes
6. ⏭️ Optional: Full refactoring (see REFACTORING_PLAN.md)

## Resources

- [Black Docs](https://black.readthedocs.io/)
- [Ruff Docs](https://docs.astral.sh/ruff/)
- [Bandit Docs](https://bandit.readthedocs.io/)
- [MyPy Docs](https://mypy.readthedocs.io/)
- [FastAPI Docs](https://fastapi.tiangolo.com/)

---

**Ready? Run:** `.\run_cleanup.ps1` (Windows) or `./run_cleanup.sh` (Linux/Mac)
