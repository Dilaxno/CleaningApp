#!/usr/bin/env python3
"""
Automated cleanup script for CleanEnroll backend
Runs formatters, linters, and generates reports
"""
import subprocess
import sys
from pathlib import Path

def run_command(cmd, description):
    """Run a command and report results"""
    print(f"\n{'='*60}")
    print(f"🔧 {description}")
    print(f"{'='*60}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Main cleanup workflow"""
    print("🚀 Starting CleanEnroll Backend Cleanup")
    print("="*60)
    
    # Change to backend directory
    backend_dir = Path(__file__).parent
    print(f"📁 Working directory: {backend_dir}")
    
    steps = [
        # Step 1: Format code
        ("black app/ --line-length 100", "Formatting code with Black"),
        
        # Step 2: Auto-fix linting issues
        ("ruff check app/ --fix", "Auto-fixing linting issues with Ruff"),
        
        # Step 3: Find unused code
        ("vulture app/ --min-confidence 60 > vulture_report.txt", "Finding dead code with Vulture"),
        
        # Step 4: Security scan
        ("bandit -r app/ -f txt -o bandit_report.txt", "Running security scan with Bandit"),
        
        # Step 5: Type checking
        ("mypy app/ --ignore-missing-imports > mypy_report.txt", "Type checking with MyPy"),
    ]
    
    results = []
    for cmd, desc in steps:
        success = run_command(cmd, desc)
        results.append((desc, success))
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 CLEANUP SUMMARY")
    print(f"{'='*60}")
    for desc, success in results:
        status = "✅" if success else "⚠️"
        print(f"{status} {desc}")
    
    print(f"\n{'='*60}")
    print("📄 Reports generated:")
    print("  - vulture_report.txt (dead code)")
    print("  - bandit_report.txt (security issues)")
    print("  - mypy_report.txt (type errors)")
    print(f"{'='*60}")
    
    print("\n✅ Cleanup complete! Review reports and fix remaining issues.")

if __name__ == "__main__":
    main()
