#!/usr/bin/env python3
"""
Professional code cleanup script - removes debug logs and verbose comments
"""
import re
import os
from pathlib import Path

def clean_file(filepath):
    """Remove debug logging and verbose comments from a Python file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Remove logger.info with emojis (debug logs)
    content = re.sub(r'\n\s*logger\.info\(f?["\'].*?[📊🖊️✅📄📧⚠️❌➡️🔒ℹ️🚀👋💰🖼️📝].*?["\']\)\s*\n', '\n', content, flags=re.MULTILINE)
    
    # Remove standalone debug logger.info calls (keep warnings and errors)
    patterns_to_remove = [
        r'\n\s*logger\.info\(f?"[^"]*(?:DEBUG|Test|✓|Generated|Downloaded|Converted|Added|Applied|Processing|Final|Using)[^"]*"\)\s*\n',
        r'\n\s*logger\.info\(f?\'[^\']*(?:DEBUG|Test|✓|Generated|Downloaded|Converted|Added|Applied|Processing|Final|Using)[^\']*\'\)\s*\n',
    ]
    
    for pattern in patterns_to_remove:
        content = re.sub(pattern, '\n', content, flags=re.MULTILINE | re.DOTALL)
    
    # Remove multi-line debug comment blocks
    content = re.sub(r'\n\s*# DEBUG:.*?\n', '\n', content, flags=re.MULTILINE)
    content = re.sub(r'\n\s*# Log .*?\n', '\n', content, flags=re.MULTILINE)
    content = re.sub(r'\n\s*# CRITICAL DEBUG:.*?\n', '\n', content, flags=re.MULTILINE)
    
    # Remove excessive blank lines (more than 2 consecutive)
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    # Only write if content changed
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    """Clean all Python files in routes directory"""
    routes_dir = Path(__file__).parent / 'app' / 'routes'
    
    if not routes_dir.exists():
        print(f"Routes directory not found: {routes_dir}")
        return
    
    cleaned_files = []
    for py_file in routes_dir.glob('*.py'):
        if py_file.name == '__init__.py':
            continue
        
        if clean_file(py_file):
            cleaned_files.append(py_file.name)
            print(f"Cleaned: {py_file.name}")
    
    if cleaned_files:
        print(f"\nCleaned {len(cleaned_files)} files")
    else:
        print("No files needed cleaning")

if __name__ == '__main__':
    main()
