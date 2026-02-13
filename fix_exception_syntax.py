#!/usr/bin/env python3
"""
Fix exception chaining syntax errors
"""
import re
from pathlib import Path


def fix_exception_chaining(file_path):
    """Fix exception chaining syntax"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Fix: raise HTTPException(...)) from e) -> raise HTTPException(...) from e
    content = re.sub(r'\)\)\s+from\s+(\w+)\)', r') from \1', content)
    
    # Fix: async def func(data: db: Session) -> async def func(data, db: Session)
    content = re.sub(r'async def (\w+)\((\w+):\s+db:\s+Session\)', r'async def \1(\2, db: Session)', content)
    
    # Fix: detail=f"...") from e, -> detail=f"...") from e
    content = re.sub(r'from\s+(\w+),\s*$', r'from \1', content, flags=re.MULTILINE)
    
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
        "routes/calendly.py",
        "routes/billing.py",
        "routes/google_calendar.py",
        "routes/contracts.py",
        "routes/invoices.py",
        "routes/quickbooks.py",
        "routes/upload.py",
        "routes/verification.py",
    ]
    
    print("🔧 Fixing exception chaining syntax...")
    fixed_count = 0
    
    for file_rel_path in files_to_fix:
        file_path = app_dir / file_rel_path
        if file_path.exists():
            if fix_exception_chaining(file_path):
                fixed_count += 1
    
    print(f"\n✅ Fixed {fixed_count} files")


if __name__ == "__main__":
    main()
