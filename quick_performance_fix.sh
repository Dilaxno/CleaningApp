#!/bin/bash

# Quick Performance Fix Script for CleaningApp
# Run this script to apply immediate performance improvements

echo "🚀 CleaningApp Performance Quick Fix"
echo "===================================="

# Check if we're in the right directory
if [ ! -f "app/main.py" ]; then
    echo "❌ Error: Please run this script from the backend directory"
    exit 1
fi

# Make scripts executable
chmod +x optimize_database.py
chmod +x monitor_performance.py

echo "📊 Step 1: Running database optimization..."
python3 optimize_database.py

echo ""
echo "🔍 Step 2: Running performance monitoring..."
python3 monitor_performance.py

echo ""
echo "🔄 Step 3: Restarting application service..."
sudo systemctl restart cleaningapp

echo ""
echo "📋 Step 4: Checking service status..."
sudo systemctl status cleaningapp --no-pager -l

echo ""
echo "📊 Step 5: Monitoring logs for 30 seconds..."
echo "Press Ctrl+C to stop monitoring"
timeout 30 sudo journalctl -u cleaningapp -f || true

echo ""
echo "✅ Performance optimization completed!"
echo ""
echo "🔧 Additional recommendations:"
echo "1. Monitor logs with: sudo journalctl -u cleaningapp -f"
echo "2. Check slow queries with: python3 monitor_performance.py"
echo "3. Enable pg_stat_statements in PostgreSQL for better monitoring"
echo "4. Consider adding Redis caching for frequently accessed data"
echo ""
echo "📈 Expected improvements:"
echo "- Reduced authentication token errors"
echo "- Faster invoice queries (6.45s → <1s)"
echo "- Better database index utilization"
echo "- Improved connection pooling"