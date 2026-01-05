-- Migration: Add notification preferences to users table
-- Description: Adds columns for user notification preferences

-- Add notification preference columns
ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_new_clients BOOLEAN DEFAULT TRUE NOT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_contract_signed BOOLEAN DEFAULT TRUE NOT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_schedule_confirmed BOOLEAN DEFAULT TRUE NOT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_payment_received BOOLEAN DEFAULT TRUE NOT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_reminders BOOLEAN DEFAULT TRUE NOT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_marketing BOOLEAN DEFAULT FALSE NOT NULL;

-- Add comments for documentation
COMMENT ON COLUMN users.notify_new_clients IS 'Email notification when new client submits form';
COMMENT ON COLUMN users.notify_contract_signed IS 'Email notification when contract is signed';
COMMENT ON COLUMN users.notify_schedule_confirmed IS 'Email notification when schedule is confirmed';
COMMENT ON COLUMN users.notify_payment_received IS 'Email notification when payment is received';
COMMENT ON COLUMN users.notify_reminders IS 'Email notification for upcoming appointments';
COMMENT ON COLUMN users.notify_marketing IS 'Marketing and product update emails';
