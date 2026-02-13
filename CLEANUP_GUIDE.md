# CleanEnroll Backend Cleanup & Refactoring Guide

## Quick Start

### 1. Install Development Tools

```bash
cd backend

# Install production dependencies
pip install -r requirements.txt

# Install development tools
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

### 2. Run Automated Cleanup

```bash
# Run all cleanup steps
python cleanup_script.py

# Or use Makefile commands
make format      # Format code with Black
make lint        # Run linters
make security    # Security scan
make dead-code   # Find unused code
make type-check  # Type checking
make all         # Run everything
```

### 3. Review Reports

After running cleanup, review these generated reports:
- `vulture_report.txt` - Dead code and unused imports
- `bandit_report.txt` - Security vulnerabilities
- `mypy_report.txt` - Type errors

### 4. Manual Fixes

Some issues require manual intervention:

#### Remove Dead Code
```bash
# Review vulture report
cat vulture_report.txt

# Remove unused imports, functions, variables
# Be careful with false positives!
```

#### Fix Security Issues
```bash
# Review bandit report
cat bandit_report.txt

# Fix each security issue:
# - Replace string concatenation in SQL with parameterized queries
# - Add input validation
# - Sanitize user inputs
# - Use secure random generators
```

#### Add Type Hints
```bash
# Review mypy report
cat mypy_report.txt

# Add type hints to functions:
def my_function(param: str) -> dict:
    return {"result": param}
```

## Detailed Cleanup Steps

### Step 1: Code Formatting

Black automatically formats code to PEP 8 standards:

```bash
black app/ --line-length 100
```

This fixes:
- Inconsistent indentation
- Line length issues
- Quote style
- Whitespace

### Step 2: Linting

Ruff catches common issues:

```bash
ruff check app/ --fix
```

This fixes:
- Unused imports
- Undefined variables
- Style violations
- Common bugs

### Step 3: Dead Code Detection

Vulture finds unused code:

```bash
vulture app/ --min-confidence 60 > vulture_report.txt
```

Review and remove:
- Unused functions
- Unused variables
- Unused imports
- Unreachable code

**Warning:** Some code may be used dynamically (e.g., SQLAlchemy models). Review carefully!

### Step 4: Security Scanning

Bandit finds security issues:

```bash
bandit -r app/ -f txt -o bandit_report.txt
```

Common issues to fix:
- Hardcoded passwords/secrets
- SQL injection risks
- Insecure random generators
- Unsafe file operations
- Missing input validation

### Step 5: Type Checking

MyPy ensures type safety:

```bash
mypy app/ --ignore-missing-imports > mypy_report.txt
```

Add type hints to:
- Function parameters
- Return values
- Class attributes
- Variables (when not obvious)

## Common Issues & Fixes

### Issue: Unused Imports

```python
# Before
import os
import sys
from typing import Optional

def my_function():
    return "hello"

# After (remove unused imports)
def my_function():
    return "hello"
```

### Issue: SQL Injection Risk

```python
# ❌ NEVER DO THIS
query = f"SELECT * FROM users WHERE id = {user_id}"
db.execute(query)

# ✅ DO THIS (parameterized query)
query = "SELECT * FROM users WHERE id = :user_id"
db.execute(query, {"user_id": user_id})

# ✅ OR THIS (SQLAlchemy ORM)
user = db.query(User).filter(User.id == user_id).first()
```

### Issue: Missing Input Validation

```python
# ❌ BEFORE
@router.post("/users")
def create_user(name: str, email: str):
    user = User(name=name, email=email)
    db.add(user)
    db.commit()

# ✅ AFTER
from pydantic import BaseModel, EmailStr, validator

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    
    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()

@router.post("/users")
def create_user(data: UserCreate):
    user = User(name=data.name, email=data.email)
    db.add(user)
    db.commit()
```

### Issue: Missing Type Hints

```python
# ❌ BEFORE
def calculate_total(items):
    return sum(item['price'] for item in items)

# ✅ AFTER
from typing import List, Dict, Any

def calculate_total(items: List[Dict[str, Any]]) -> float:
    return sum(float(item['price']) for item in items)
```

### Issue: Hardcoded Secrets

```python
# ❌ NEVER DO THIS
API_KEY = "sk_live_abc123xyz"

# ✅ DO THIS
import os
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY environment variable not set")
```

### Issue: Insecure Random

```python
# ❌ BEFORE
import random
token = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=32))

# ✅ AFTER
import secrets
token = secrets.token_urlsafe(32)
```

## Architecture Improvements

### Before: Business Logic in Routes

```python
# ❌ BEFORE - Fat controller
@router.post("/contracts")
async def create_contract(data: ContractCreate, user: User = Depends(get_current_user)):
    # Validation logic
    if not data.title:
        raise HTTPException(400, "Title required")
    
    # Business logic
    client = db.query(Client).filter(Client.id == data.clientId).first()
    if not client:
        raise HTTPException(404, "Client not found")
    
    # Database logic
    contract = Contract(
        user_id=user.id,
        client_id=data.clientId,
        title=data.title,
        status="new"
    )
    db.add(contract)
    db.commit()
    
    # Email logic
    await send_email(client.email, "Contract created", ...)
    
    return contract
```

### After: Thin Controller with Service Layer

```python
# ✅ AFTER - Thin controller
@router.post("/contracts", response_model=ContractResponse)
async def create_contract(
    data: ContractCreate,
    user: User = Depends(get_current_user),
    contract_service: ContractService = Depends(get_contract_service)
):
    """Create a new contract"""
    try:
        contract = await contract_service.create_contract(user.id, data)
        return contract
    except ClientNotFoundError:
        raise HTTPException(404, "Client not found")
    except ValidationError as e:
        raise HTTPException(400, str(e))

# services/contract_service.py
class ContractService:
    def __init__(self, db: Session, email_service: EmailService):
        self.db = db
        self.email_service = email_service
    
    async def create_contract(self, user_id: int, data: ContractCreate) -> Contract:
        """Create a new contract with validation and notifications"""
        # Validation
        if not data.title:
            raise ValidationError("Title required")
        
        # Get client
        client = self.db.query(Client).filter(
            Client.id == data.clientId,
            Client.user_id == user_id
        ).first()
        if not client:
            raise ClientNotFoundError()
        
        # Create contract
        contract = Contract(
            user_id=user_id,
            client_id=data.clientId,
            title=data.title,
            status="new"
        )
        self.db.add(contract)
        self.db.commit()
        self.db.refresh(contract)
        
        # Send notification
        await self.email_service.send_contract_created(client.email, contract)
        
        return contract
```

## Testing

After cleanup, ensure everything still works:

```bash
# Run tests
make test

# Run with coverage
make test-cov

# Manual testing
python run.py
# Test critical endpoints with Postman/curl
```

## Commit Strategy

Make small, focused commits:

```bash
# After formatting
git add .
git commit -m "style: format code with Black"

# After removing dead code
git add .
git commit -m "refactor: remove unused imports and dead code"

# After security fixes
git add .
git commit -m "security: fix SQL injection vulnerabilities"

# After adding type hints
git add .
git commit -m "feat: add type hints for better type safety"
```

## Next Steps

After cleanup:
1. Review and merge refactoring plan
2. Reorganize architecture (see REFACTORING_PLAN.md)
3. Write comprehensive tests
4. Update documentation
5. Deploy to staging for testing

## Resources

- [Black Documentation](https://black.readthedocs.io/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Bandit Documentation](https://bandit.readthedocs.io/)
- [MyPy Documentation](https://mypy.readthedocs.io/)
- [FastAPI Best Practices](https://fastapi.tiangolo.com/tutorial/)
- [SQLAlchemy Security](https://docs.sqlalchemy.org/en/14/core/security.html)
