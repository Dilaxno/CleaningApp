# Manual SQL Migration Instructions

This directory contains SQL migration scripts that can be run manually if you prefer not to use Alembic.

## Current Migration: Add Form Embedding Feature

**File**: `add_form_embedding_enabled.sql`  
**Purpose**: Adds `form_embedding_enabled` column to `business_configs` table  
**Date**: 2026-01-24

---

## Prerequisites

Before running the migration, ensure you have:

1. ✅ Database credentials (username, password, host, database name)
2. ✅ Backup of your database (always backup before migrations!)
3. ✅ Access to a database client (psql, pgAdmin, MySQL Workbench, etc.)
4. ✅ Verified your database is PostgreSQL (this script is PostgreSQL-compatible)

---

## How to Run the Migration

### Option 1: Using psql (PostgreSQL Command Line)

```bash
# Navigate to the migrations directory
cd backend/migrations

# Connect to your database and run the script
psql -h <host> -U <username> -d <database_name> -f add_form_embedding_enabled.sql

# Example:
# psql -h localhost -U postgres -d cleanenroll_db -f add_form_embedding_enabled.sql
```

### Option 2: Using pgAdmin (GUI)

1. Open pgAdmin
2. Connect to your database server
3. Select your database (e.g., `cleanenroll_db`)
4. Click **Tools** → **Query Tool**
5. Open the file `add_form_embedding_enabled.sql`
6. Click **Execute/Run** (F5)
7. Verify "Query returned successfully" message

### Option 3: Using DBeaver (GUI)

1. Open DBeaver
2. Connect to your CleanEnroll database
3. Right-click on your database → **SQL Editor** → **Open SQL Script**
4. Select `add_form_embedding_enabled.sql`
5. Click **Execute SQL Statement** (Ctrl+Enter)
6. Check the results panel for success

### Option 4: Copy-Paste Method

1. Open your preferred database client
2. Open `add_form_embedding_enabled.sql` in a text editor
3. Copy the entire contents
4. Paste into your database client's query window
5. Execute the query

---

## Verification

After running the migration, verify it was successful:

```sql
-- Check if column exists
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'business_configs'
  AND column_name = 'form_embedding_enabled';

-- Expected result:
-- column_name              | data_type | is_nullable | column_default
-- form_embedding_enabled   | boolean   | NO          | false

-- Check existing data
SELECT id, business_name, form_embedding_enabled
FROM business_configs
LIMIT 5;

-- All existing rows should have form_embedding_enabled = false
```

---

## Rollback Instructions

If you need to undo this migration:

```sql
-- This will remove the form_embedding_enabled column
ALTER TABLE business_configs DROP COLUMN form_embedding_enabled;
```

**⚠️ Warning**: Rollback will permanently delete all data in the `form_embedding_enabled` column!

---

## Troubleshooting

### Issue: "column already exists"

**Error**: `column "form_embedding_enabled" of relation "business_configs" already exists`

**Solution**: The migration has already been run. No action needed.

```sql
-- Verify column exists
\d business_configs
```

---

### Issue: "permission denied"

**Error**: `ERROR: permission denied for table business_configs`

**Solution**: Ensure you're connected with a user that has ALTER TABLE privileges.

```sql
-- Grant permissions (run as superuser)
GRANT ALL PRIVILEGES ON TABLE business_configs TO your_username;
```

---

### Issue: "table business_configs does not exist"

**Error**: `ERROR: relation "business_configs" does not exist`

**Solution**: 
1. Verify you're connected to the correct database
2. Check if the table name is different in your setup
3. Run initial migrations first

```sql
-- List all tables
\dt

-- Or in standard SQL:
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public';
```

---

### Issue: "syntax error" (MySQL/MariaDB)

**Error**: MySQL syntax errors

**Solution**: The script is PostgreSQL-specific. For MySQL, modify the script:

```sql
-- MySQL version
ALTER TABLE business_configs
ADD COLUMN form_embedding_enabled BOOLEAN DEFAULT FALSE NOT NULL;

UPDATE business_configs
SET form_embedding_enabled = FALSE
WHERE form_embedding_enabled IS NULL;
```

---

## Database-Specific Notes

### PostgreSQL ✅
- Script works as-is
- No modifications needed

### MySQL/MariaDB
- Replace `BOOLEAN` with `TINYINT(1)` if needed
- Use `DEFAULT FALSE NOT NULL` in single ALTER statement

### SQLite
- Use `INTEGER` instead of `BOOLEAN` (0 for false, 1 for true)
- Cannot use `ALTER COLUMN` for constraints
- May need to recreate table

---

## What This Migration Does

1. **Adds a new column** `form_embedding_enabled` to `business_configs` table
2. **Sets default value** to `FALSE` for all existing businesses
3. **Makes column non-nullable** to ensure data integrity
4. **Purpose**: Tracks whether business owners want iframe embedding on their website

---

## Post-Migration Steps

After successful migration:

1. ✅ Restart your backend server
2. ✅ Test the onboarding flow in the frontend
3. ✅ Verify Step 9 appears in onboarding
4. ✅ Test both embedding options (Full Automation vs Manual)
5. ✅ Update any database backup schedules

---

## Need Help?

- **Check logs**: Look for error messages in your database client
- **Review schema**: Use `\d business_configs` (PostgreSQL) to see table structure
- **Backup first**: Always create a backup before running migrations
- **Contact support**: If issues persist, contact your database administrator

---

## Migration History

| Date       | File                              | Description                    | Status |
|------------|-----------------------------------|--------------------------------|--------|
| 2026-01-24 | add_form_embedding_enabled.sql    | Add form embedding preference  | ✅ New  |

---

## Example: Complete Migration Process

```bash
# 1. Backup database
pg_dump -h localhost -U postgres cleanenroll_db > backup_$(date +%Y%m%d).sql

# 2. Navigate to migrations directory
cd backend/migrations

# 3. Run migration
psql -h localhost -U postgres -d cleanenroll_db -f add_form_embedding_enabled.sql

# 4. Verify
psql -h localhost -U postgres -d cleanenroll_db -c "SELECT column_name FROM information_schema.columns WHERE table_name = 'business_configs' AND column_name = 'form_embedding_enabled';"

# 5. Restart backend
cd ..
python -m uvicorn app.main:app --reload
```

---

**✅ Migration Complete!**

Your database is now ready to support the form embedding feature. Business owners can now choose to embed CleanEnroll forms directly on their websites during onboarding.