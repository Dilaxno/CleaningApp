-- Add client limiting columns to users table
-- Run this SQL against your PostgreSQL database first

ALTER TABLE users ADD COLUMN IF NOT EXISTS clients_this_month INTEGER DEFAULT 0 NOT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS month_reset_date TIMESTAMP;

-- Initialize month_reset_date to first day of next month for existing users
UPDATE users 
SET month_reset_date = DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month'
WHERE month_reset_date IS NULL;

-- Verify columns were added
SELECT column_name, data_type, is_nullable, column_default 
FROM information_schema.columns 
WHERE table_name = 'users' 
AND column_name IN ('clients_this_month', 'month_reset_date');
