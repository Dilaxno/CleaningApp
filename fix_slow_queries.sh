#!/bin/bash

# Immediate Fix for Slow Database Queries
# This script will optimize your database and improve performance

echo "🚀 CleaningApp - Immediate Performance Fix"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}❌ Please run with sudo: sudo bash fix_slow_queries.sh${NC}"
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "app/main.py" ]; then
    echo -e "${RED}❌ Error: Please run this script from the backend directory${NC}"
    exit 1
fi

echo -e "${YELLOW}📊 Step 1: Creating database indexes...${NC}"
python3 optimize_database.py
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Database indexes created successfully${NC}"
else
    echo -e "${RED}❌ Failed to create indexes${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}🔄 Step 2: Restarting application...${NC}"
systemctl restart cleaningapp
sleep 3

echo ""
echo -e "${YELLOW}📋 Step 3: Checking service status...${NC}"
systemctl status cleaningapp --no-pager -l | head -20

echo ""
echo -e "${GREEN}✅ Performance fix applied!${NC}"
echo ""
echo -e "${YELLOW}📊 Monitoring logs for 10 seconds...${NC}"
echo "Press Ctrl+C to stop"
echo ""
timeout 10 journalctl -u cleaningapp -f || true

echo ""
echo -e "${GREEN}🎉 Done! Your database should now be much faster.${NC}"
echo ""
echo -e "${YELLOW}📈 What was fixed:${NC}"
echo "  • Added indexes on users table (email_verified, plan, subscription_status)"
echo "  • Added indexes on clients table (user_id, status, created_at, email)"
echo "  • Added indexes on contracts table (user_id, client_id, status, created_at)"
echo "  • Added indexes on invoices table (user_id, client_id, contract_id, status, due_date)"
echo "  • Added indexes on schedules table (user_id, client_id, status, scheduled_date)"
echo "  • Updated table statistics for query optimizer"
echo ""
echo -e "${YELLOW}🔍 To monitor performance:${NC}"
echo "  sudo journalctl -u cleaningapp -f | grep 'Slow query'"
echo ""
echo -e "${YELLOW}💡 Expected results:${NC}"
echo "  • Queries should now be <0.5s (was 1-2s)"
echo "  • Reduced CPU usage"
echo "  • Faster page loads"
