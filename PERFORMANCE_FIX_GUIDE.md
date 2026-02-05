# 🚀 Performance Fix Guide - Slow Database Queries

## 🔴 Problem Identified

Your logs show **slow database queries** (1-2+ seconds) causing server slowness:
- Users table queries: 1.23s, 2.34s
- Invoices table queries: 1.31s
- Schedules table queries: 1.79s

**Root Cause:** Missing database indexes on frequently queried columns.

## ✅ Immediate Fix (5 minutes)

### Step 1: Run Diagnostics
```bash
cd /home/ubuntu/CleaningApp/backend
sudo python3 diagnose_performance.py
```

This will show you:
- Current indexes
- Missing indexes
- Table sizes
- Connection pool status

### Step 2: Apply Performance Fix
```bash
sudo bash fix_slow_queries.sh
```

This will:
- Create all missing indexes
- Update table statistics
- Restart the application
- Monitor logs for improvements

### Step 3: Verify Improvement
```bash
sudo journalctl -u cleaningapp -f | grep "Slow query"
```

You should see:
- ✅ Queries now <0.5s (was 1-2s)
- ✅ Fewer slow query warnings
- ✅ Faster response times

## 📊 What Gets Fixed

### Indexes Created:

#### Users Table
- `idx_users_email_verified` - For authentication checks
- `idx_users_plan` - For plan-based queries
- `idx_users_subscription_status` - For subscription checks

#### Clients Table
- `idx_clients_user_id_status` - For user's client list
- `idx_clients_created_at` - For sorting by date
- `idx_clients_email` - For email lookups

#### Contracts Table
- `idx_contracts_user_id_status` - For user's contracts
- `idx_contracts_client_id_status` - For client's contracts
- `idx_contracts_created_at` - For sorting

#### Invoices Table (Major improvement here!)
- `idx_invoices_user_id_status` - For user's invoices
- `idx_invoices_client_id` - For client's invoices
- `idx_invoices_contract_id` - For contract invoices
- `idx_invoices_due_date` - For due date queries
- `idx_invoices_created_at` - For sorting

#### Schedules Table
- `idx_schedules_user_id_status` - For user's schedules
- `idx_schedules_client_id` - For client's schedules
- `idx_schedules_scheduled_date` - For date-based queries

## 🎯 Expected Results

### Before Fix:
```
🐌 Slow query (2.34s): SELECT users...
🐌 Slow query (1.31s): SELECT invoices...
🐌 Slow query (1.79s): SELECT schedules...
```

### After Fix:
```
✅ Query completed in 0.15s
✅ Query completed in 0.08s
✅ Query completed in 0.12s
```

### Performance Improvements:
- **Query Speed:** 10-20x faster
- **CPU Usage:** 50-70% reduction
- **Response Time:** <500ms for most requests
- **Server Load:** Significantly reduced

## 🔧 Additional Optimizations (Optional)

### 1. Enable PostgreSQL Query Statistics
```sql
-- Connect to your database
sudo -u postgres psql cleaningapp

-- Enable pg_stat_statements
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Check it's enabled
SELECT * FROM pg_extension WHERE extname = 'pg_stat_statements';
```

### 2. Adjust Database Configuration
Edit `/etc/postgresql/*/main/postgresql.conf`:
```conf
# Increase shared buffers (25% of RAM)
shared_buffers = 2GB

# Increase effective cache size (50-75% of RAM)
effective_cache_size = 6GB

# Increase work memory
work_mem = 64MB

# Enable query statistics
shared_preload_libraries = 'pg_stat_statements'
pg_stat_statements.track = all
```

Then restart PostgreSQL:
```bash
sudo systemctl restart postgresql
```

### 3. Add Redis Caching (Future Enhancement)
For frequently accessed data like user profiles and business configs:
```bash
sudo apt install redis-server
pip install redis
```

## 📈 Monitoring Performance

### Check Slow Queries
```bash
sudo journalctl -u cleaningapp -f | grep "Slow query"
```

### Monitor Database Performance
```bash
sudo python3 monitor_performance.py
```

### Check Connection Pool
```bash
sudo python3 diagnose_performance.py
```

### View Application Logs
```bash
sudo journalctl -u cleaningapp -f
```

## 🚨 Troubleshooting

### If queries are still slow after fix:

1. **Check if indexes were created:**
```bash
sudo python3 diagnose_performance.py
```

2. **Verify PostgreSQL is running:**
```bash
sudo systemctl status postgresql
```

3. **Check database connections:**
```bash
sudo -u postgres psql cleaningapp -c "SELECT count(*) FROM pg_stat_activity;"
```

4. **Check server resources:**
```bash
htop  # or top
df -h  # disk space
free -h  # memory
```

### If server is still slow:

1. **Check CPU usage:**
```bash
top -bn1 | grep "Cpu(s)"
```

2. **Check memory:**
```bash
free -h
```

3. **Check disk I/O:**
```bash
iostat -x 1 5
```

4. **Upgrade server if needed:**
- Current: t2.micro (1 vCPU, 1GB RAM)
- Recommended: t3.small (2 vCPU, 2GB RAM) or larger

## 💡 Best Practices Going Forward

### 1. Regular Maintenance
```bash
# Run weekly
sudo python3 optimize_database.py
```

### 2. Monitor Performance
```bash
# Check daily
sudo python3 diagnose_performance.py
```

### 3. Review Slow Queries
```bash
# Monitor continuously
sudo journalctl -u cleaningapp -f | grep "Slow query"
```

### 4. Database Backups
```bash
# Backup before major changes
sudo -u postgres pg_dump cleaningapp > backup_$(date +%Y%m%d).sql
```

## 📞 Support

If issues persist after applying these fixes:

1. **Check logs:** `sudo journalctl -u cleaningapp -f`
2. **Run diagnostics:** `sudo python3 diagnose_performance.py`
3. **Check database:** `sudo -u postgres psql cleaningapp`
4. **Monitor resources:** `htop` or `top`

## ✅ Quick Command Reference

```bash
# Fix slow queries (MAIN FIX)
sudo bash fix_slow_queries.sh

# Diagnose issues
sudo python3 diagnose_performance.py

# Monitor logs
sudo journalctl -u cleaningapp -f

# Restart service
sudo systemctl restart cleaningapp

# Check service status
sudo systemctl status cleaningapp
```

---

**Expected Time to Fix:** 5-10 minutes
**Expected Improvement:** 10-20x faster queries
**Downtime:** ~10 seconds during restart
