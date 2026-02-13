#!/usr/bin/env python3
"""
Final comprehensive syntax fix
"""
import re
from pathlib import Path


def fix_all_syntax_errors(file_path):
    """Fix all remaining syntax errors"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Fix: ) from e) -> from e
    content = re.sub(r'\)\s+from\s+(\w+)\)', r' from \1', content)
    
    # Fix: "...") from e -> "...") from e (remove extra closing paren)
    content = re.sub(r'"\)\s+from\s+(\w+)\)', r'") from \1', content)
    
    # Fix: {str(e)}" from e -> {str(e)}") from e
    content = re.sub(r'\{str\((\w+)\)\}"\s+from\s+\1', r'{str(\1)}") from \1', content)
    
    # Fix incomplete raise statements
    content = re.sub(r'raise\s+HTTPException\([^)]+\)\s+from\s+(\w+)$', lambda m: m.group(0).rstrip() if m.group(0).count('(') == m.group(0).count(')') else m.group(0) + ')', content, flags=re.MULTILINE)
    
    # Fix: detail=f"..." from e -> detail=f"...") from e
    content = re.sub(r'detail=f"([^"]+)"\s+from\s+(\w+)\s*$', r'detail=f"\1") from \2', content, flags=re.MULTILINE)
    
    # Fix: ) from e, -> ) from e
    content = re.sub(r'\)\s+from\s+(\w+),', r') from \1', content)
    
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
        "routes/invoices.py",
        "routes/quickbooks.py",
        "routes/upload.py",
        "routes/verification.py",
    ]
    
    print("🔧 Final syntax fixes...")
    fixed_count = 0
    
    for file_rel_path in files_to_fix:
        file_path = app_dir / file_rel_path
        if file_path.exists():
            if fix_all_syntax_errors(file_path):
                fixed_count += 1
    
    print(f"\n✅ Fixed {fixed_count} files")


if __name__ == "__main__":
    main()
