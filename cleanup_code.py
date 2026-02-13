#!/usr/bin/env python3
"""
Automated code cleanup script for CleanEnroll backend
Fixes common issues found by linters and improves code quality
"""
import os
import re
import subprocess
import sys
from pathlib import Path


def run_command(cmd, cwd=None):
    """Run a shell command and return output"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def fix_typing_imports(file_path):
    """Replace deprecated typing imports with modern equivalents"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Replace Dict, List, Tuple with dict, list, tuple
    content = re.sub(r'\bDict\[', 'dict[', content)
    content = re.sub(r'\bList\[', 'list[', content)
    content = re.sub(r'\bTuple\[', 'tuple[', content)
    
    # Update imports
    content = re.sub(
        r'from typing import (.*?)Dict(.*?)$',
        lambda m: f'from typing import {m.group(1)}{m.group(2)}' if 'dict' not in m.group(0).lower() else m.group(0),
        content,
        flags=re.MULTILINE
    )
    
    # Remove Dict, List, Tuple from typing imports if they exist
    content = re.sub(r',\s*Dict(?=[\s,\)])', '', content)
    content = re.sub(r',\s*List(?=[\s,\)])', '', content)
    content = re.sub(r',\s*Tuple(?=[\s,\)])', '', content)
    content = re.sub(r'Dict,\s*', '', content)
    content = re.sub(r'List,\s*', '', content)
    content = re.sub(r'Tuple,\s*', '', content)
    
    if content != original:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False


def fix_exception_chaining(file_path):
    """Add proper exception chaining with 'from' keyword"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Pattern: except SomeException as e: ... raise HTTPException(...)
    # Should be: raise HTTPException(...) from e
    pattern = r'(except\s+\w+\s+as\s+(\w+):.*?)(raise\s+\w+Exception\([^)]+\))'
    
    def add_from_clause(match):
        exception_block = match.group(1)
        exception_var = match.group(2)
        raise_statement = match.group(3)
        
        if ' from ' not in raise_statement:
            return f'{exception_block}{raise_statement} from {exception_var}'
        return match.group(0)
    
    content = re.sub(pattern, add_from_clause, content, flags=re.DOTALL)
    
    if content != original:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False


def fix_boolean_comparisons(file_path):
    """Fix == True and == False comparisons"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Replace == True with just the variable
    content = re.sub(r'(\w+(?:\.\w+)*)\s*==\s*True\b', r'\1', content)
    
    # Replace == False with not variable
    content = re.sub(r'(\w+(?:\.\w+)*)\s*==\s*False\b', r'not \1', content)
    
    if content != original:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False


def remove_unused_variables(file_path):
    """Remove unused variables from function signatures"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Replace unused 'cls' parameters with '_cls'
    content = re.sub(r'def\s+\w+\(cls,', 'def \\g<0>'.replace('cls,', '_cls,'), content)
    
    # Replace unused 'ctx' parameters with '_ctx'
    content = re.sub(r'async\s+def\s+\w+\(ctx,', lambda m: m.group(0).replace('ctx,', '_ctx,'), content)
    
    if content != original:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False


def fix_whitespace_issues(file_path):
    """Remove trailing whitespace and fix blank lines"""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    original_lines = lines.copy()
    
    # Remove trailing whitespace
    lines = [line.rstrip() + '\n' if line.strip() else '\n' for line in lines]
    
    if lines != original_lines:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        return True
    return False


def main():
    """Main cleanup function"""
    print("🧹 Starting code cleanup...")
    
    backend_dir = Path(__file__).parent
    app_dir = backend_dir / "app"
    
    if not app_dir.exists():
        print(f"❌ App directory not found: {app_dir}")
        return 1
    
    # Find all Python files
    python_files = list(app_dir.rglob("*.py"))
    print(f"📁 Found {len(python_files)} Python files")
    
    fixes_applied = {
        'typing': 0,
        'exceptions': 0,
        'booleans': 0,
        'unused_vars': 0,
        'whitespace': 0
    }
    
    for file_path in python_files:
        if '__pycache__' in str(file_path):
            continue
        
        print(f"  Processing: {file_path.relative_to(backend_dir)}")
        
        if fix_typing_imports(file_path):
            fixes_applied['typing'] += 1
        
        if fix_exception_chaining(file_path):
            fixes_applied['exceptions'] += 1
        
        if fix_boolean_comparisons(file_path):
            fixes_applied['booleans'] += 1
        
        if remove_unused_variables(file_path):
            fixes_applied['unused_vars'] += 1
        
        if fix_whitespace_issues(file_path):
            fixes_applied['whitespace'] += 1
    
    print("\n✅ Cleanup complete!")
    print(f"   - Typing fixes: {fixes_applied['typing']}")
    print(f"   - Exception chaining: {fixes_applied['exceptions']}")
    print(f"   - Boolean comparisons: {fixes_applied['booleans']}")
    print(f"   - Unused variables: {fixes_applied['unused_vars']}")
    print(f"   - Whitespace fixes: {fixes_applied['whitespace']}")
    
    # Run black formatter
    print("\n🎨 Running Black formatter...")
    success, stdout, stderr = run_command("python -m black app", cwd=backend_dir)
    if success:
        print("✅ Black formatting complete")
    else:
        print(f"⚠️  Black formatting had issues: {stderr}")
    
    # Run ruff with auto-fix
    print("\n🔍 Running Ruff linter...")
    success, stdout, stderr = run_command("ruff check app --fix", cwd=backend_dir)
    print("✅ Ruff fixes applied")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
