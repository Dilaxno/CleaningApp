#!/bin/bash
# CleanEnroll Backend Cleanup Script (Bash)
# Run this script to automatically clean and organize your codebase

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}========================================"
echo -e "CleanEnroll Backend Cleanup"
echo -e "========================================${NC}"
echo ""

# Check if we're in the backend directory
if [ ! -d "app" ]; then
    echo -e "${RED}Error: Please run this script from the backend directory${NC}"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python not found. Please install Python first.${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo -e "${GREEN}✓ Python found: $PYTHON_VERSION${NC}"

# Function to run command and check result
run_step() {
    local description=$1
    local command=$2
    
    echo ""
    echo -e "${YELLOW}========================================"
    echo -e "Step: $description"
    echo -e "========================================${NC}"
    echo -e "${NC}Command: $command${NC}"
    echo ""
    
    if eval "$command"; then
        echo -e "${GREEN}✓ $description completed successfully${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠ $description completed with warnings${NC}"
        return 1
    fi
}

# Create backup
echo -e "${CYAN}Creating backup...${NC}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_BRANCH="backup-before-cleanup-$TIMESTAMP"

if git rev-parse --git-dir > /dev/null 2>&1; then
    git checkout -b "$BACKUP_BRANCH" 2>&1 > /dev/null || true
    git checkout - 2>&1 > /dev/null || true
    echo -e "${GREEN}✓ Backup branch created: $BACKUP_BRANCH${NC}"
else
    echo -e "${YELLOW}⚠ Could not create backup branch (not a git repo?)${NC}"
fi

echo ""
echo -e "${CYAN}Starting cleanup process...${NC}"
echo ""

# Step 1: Format code with Black
run_step "Format code with Black" "python3 -m black app/ --line-length 100"

# Step 2: Fix linting issues with Ruff
run_step "Fix linting issues with Ruff" "python3 -m ruff check app/ --fix"

# Step 3: Find dead code with Vulture
run_step "Find dead code with Vulture" "python3 -m vulture app/ --min-confidence 60 > vulture_report.txt"

# Step 4: Security scan with Bandit
run_step "Security scan with Bandit" "python3 -m bandit -r app/ -f txt -o bandit_report.txt"

# Step 5: Type check with MyPy
run_step "Type check with MyPy" "python3 -m mypy app/ --ignore-missing-imports > mypy_report.txt 2>&1"

# Summary
echo ""
echo -e "${CYAN}========================================"
echo -e "Cleanup Complete!"
echo -e "========================================${NC}"
echo ""

echo -e "${YELLOW}Reports generated:${NC}"
echo -e "  • vulture_report.txt  - Dead code and unused imports"
echo -e "  • bandit_report.txt   - Security vulnerabilities"
echo -e "  • mypy_report.txt     - Type errors"
echo ""

echo -e "${YELLOW}Next steps:${NC}"
echo -e "  1. Review the reports above"
echo -e "  2. Fix any critical security issues from bandit_report.txt"
echo -e "  3. Remove dead code identified in vulture_report.txt"
echo -e "  4. Add type hints for errors in mypy_report.txt"
echo -e "  5. Test your application: python3 run.py"
echo -e "  6. Commit changes: git add . && git commit -m 'refactor: code cleanup'"
echo ""

echo -e "${CYAN}Backup branch: $BACKUP_BRANCH${NC}"
echo -e "${CYAN}To restore: git checkout $BACKUP_BRANCH${NC}"
echo ""

echo -e "${GREEN}Done! 🎉${NC}"
