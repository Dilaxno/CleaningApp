# CleanEnroll Backend Cleanup Script (PowerShell)
# Run this script to automatically clean and organize your codebase

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "CleanEnroll Backend Cleanup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if we're in the backend directory
if (-not (Test-Path "app")) {
    Write-Host "Error: Please run this script from the backend directory" -ForegroundColor Red
    exit 1
}

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Python not found. Please install Python first." -ForegroundColor Red
    exit 1
}

# Function to run command and check result
function Run-Step {
    param(
        [string]$Description,
        [string]$Command
    )
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host "Step: $Description" -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host "Command: $Command" -ForegroundColor Gray
    Write-Host ""
    
    Invoke-Expression $Command
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ $Description completed successfully" -ForegroundColor Green
        return $true
    } else {
        Write-Host "⚠ $Description completed with warnings" -ForegroundColor Yellow
        return $false
    }
}

# Create backup
Write-Host "Creating backup..." -ForegroundColor Cyan
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupBranch = "backup-before-cleanup-$timestamp"

try {
    git checkout -b $backupBranch 2>&1 | Out-Null
    git checkout - 2>&1 | Out-Null
    Write-Host "✓ Backup branch created: $backupBranch" -ForegroundColor Green
} catch {
    Write-Host "⚠ Could not create backup branch (not a git repo?)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Starting cleanup process..." -ForegroundColor Cyan
Write-Host ""

# Step 1: Format code with Black
Run-Step -Description "Format code with Black" -Command "python -m black app/ --line-length 100"

# Step 2: Fix linting issues with Ruff
Run-Step -Description "Fix linting issues with Ruff" -Command "python -m ruff check app/ --fix"

# Step 3: Find dead code with Vulture
Run-Step -Description "Find dead code with Vulture" -Command "python -m vulture app/ --min-confidence 60 > vulture_report.txt"

# Step 4: Security scan with Bandit
Run-Step -Description "Security scan with Bandit" -Command "python -m bandit -r app/ -f txt -o bandit_report.txt"

# Step 5: Type check with MyPy
Run-Step -Description "Type check with MyPy" -Command "python -m mypy app/ --ignore-missing-imports > mypy_report.txt 2>&1"

# Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Cleanup Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Reports generated:" -ForegroundColor Yellow
Write-Host "  • vulture_report.txt  - Dead code and unused imports" -ForegroundColor White
Write-Host "  • bandit_report.txt   - Security vulnerabilities" -ForegroundColor White
Write-Host "  • mypy_report.txt     - Type errors" -ForegroundColor White
Write-Host ""

Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Review the reports above" -ForegroundColor White
Write-Host "  2. Fix any critical security issues from bandit_report.txt" -ForegroundColor White
Write-Host "  3. Remove dead code identified in vulture_report.txt" -ForegroundColor White
Write-Host "  4. Add type hints for errors in mypy_report.txt" -ForegroundColor White
Write-Host "  5. Test your application: python run.py" -ForegroundColor White
Write-Host "  6. Commit changes: git add . && git commit -m 'refactor: code cleanup'" -ForegroundColor White
Write-Host ""

Write-Host "Backup branch: $backupBranch" -ForegroundColor Cyan
Write-Host "To restore: git checkout $backupBranch" -ForegroundColor Cyan
Write-Host ""

# Open reports in default text editor (optional)
$openReports = Read-Host "Open reports in notepad? (y/n)"
if ($openReports -eq "y") {
    if (Test-Path "vulture_report.txt") { notepad vulture_report.txt }
    if (Test-Path "bandit_report.txt") { notepad bandit_report.txt }
    if (Test-Path "mypy_report.txt") { notepad mypy_report.txt }
}

Write-Host "Done! 🎉" -ForegroundColor Green
