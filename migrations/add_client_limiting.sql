-- Migration: Add client limiting fields to users table
-- Run this if you need to manually add the columns

-- Add clients_this_month column with default 0
ALTER TABLE users ADD COLUMN IF NOT EXISTS clients_this_month INTEGER DEFAULT 0 NOT NULL;

-- Add month_reset_date column
ALTER TABLE users ADD COLUMN IF NOT EXISTS month_reset_date TIMESTAMP;

-- Initialize month_reset_date to first day of next month for all users
-- You can adjust the date calculation based on current date
UPDATE users 
SET month_reset_date = DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month')
WHERE month_reset_date IS NULL;

-- Initialize clients_this_month to 0 for any NULL values
UPDATE users 
SET clients_this_month = 0 
WHERE clients_this_month IS NULL;
