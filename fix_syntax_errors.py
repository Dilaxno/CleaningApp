#!/usr/bin/env python3
"""
Fix syntax errors introduced by automated cleanup
"""
import re
from pathlib import Path


def fix_file(file_path):
    """Fix common syntax errors in a file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Fix: headers={"key": value from e} -> headers={"key": value}
    content = re.sub(r'(headers=\{[^}]+\})\s+from\s+\w+,', r'\1,', content)
    
    # Fix: detail=str(e) from e) -> detail=str(e)) from e
    content = re.sub(r'detail=([^)]+)\s+from\s+(\w+)\)', r'detail=\1) from \2', content)
    
    # Fix: detail=f"...{str(e) from e}" -> detail=f"...{str(e)}") from e
    content = re.sub(r'detail=f"([^"]*\{str\(\w+\))\s+from\s+(\w+)\}"', r'detail=f"\1}") from \2', content)
    
    # Fix: def def -> def
    content = re.sub(r'\bdef\s+def\s+', 'def ', content)
    
    # Fix malformed raise statements with from in wrong place
    # Pattern: raise HTTPException(...) from e) -> raise HTTPException(...)) from e
    content = re.sub(
        r'raise\s+(\w+Exception)\(([^)]+)\)\s+from\s+(\w+)\)',
        r'raise \1(\2)) from \3',
        content
    )
    
    if content != original:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Fixed: {file_path.name}")
        return True
    return False


def main():
    backend_dir = Path(__file__).parent
    app_dir = backend_dir / "app"
    
    files_to_fix = [
        "rate_limiter.py",
        "routes/billing.py",
        "routes/calendly.py",
        "routes/calendly_webhooks.py",
        "routes/clients.py",
        "routes/business.py",
        "routes/contracts.py",
        "routes/google_calendar.py",
        "routes/integration_requests.py",
        "routes/invoices.py",
        "routes/quickbooks.py",
        "routes/scheduling_calendly.py",
        "routes/subdomain.py",
        "routes/upload.py",
        "routes/verification.py",
        "routes/users.py",
    ]
    
    print("🔧 Fixing syntax errors...")
    fixed_count = 0
    
    for file_rel_path in files_to_fix:
        file_path = app_dir / file_rel_path
        if file_path.exists():
            if fix_file(file_path):
                fixed_count += 1
    
    print(f"\n✅ Fixed {fixed_count} files")


if __name__ == "__main__":
    main()
