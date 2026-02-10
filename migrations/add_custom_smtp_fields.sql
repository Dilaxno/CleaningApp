-- Migration: Add custom SMTP fields to business_configs table
-- Replaces Resend-based domain verification with standard SMTP credentials

-- Add new SMTP credential columns
ALTER TABLE business_configs ADD COLUMN IF NOT EXISTS smtp_host VARCHAR(255);
ALTER TABLE business_configs ADD COLUMN IF NOT EXISTS smtp_port INTEGER DEFAULT 587;
ALTER TABLE business_configs ADD COLUMN IF NOT EXISTS smtp_username VARCHAR(255);
ALTER TABLE business_configs ADD COLUMN IF NOT EXISTS smtp_password VARCHAR(500);  -- Encrypted
ALTER TABLE business_configs ADD COLUMN IF NOT EXISTS smtp_use_tls BOOLEAN DEFAULT TRUE;
ALTER TABLE business_configs ADD COLUMN IF NOT EXISTS smtp_last_test_at TIMESTAMP;
ALTER TABLE business_configs ADD COLUMN IF NOT EXISTS smtp_last_test_success BOOLEAN;
ALTER TABLE business_configs ADD COLUMN IF NOT EXISTS smtp_error_message VARCHAR(500);

-- Update smtp_status to support new statuses: live, testing, failed, null
-- Existing values: pending, verified, failed -> will map to: testing, live, failed

-- Add comments for documentation
COMMENT ON COLUMN business_configs.smtp_host IS 'SMTP server hostname (e.g., smtp.gmail.com)';
COMMENT ON COLUMN business_configs.smtp_port IS 'SMTP server port (typically 587 for TLS, 465 for SSL)';
COMMENT ON COLUMN business_configs.smtp_username IS 'SMTP authentication username';
COMMENT ON COLUMN business_configs.smtp_password IS 'SMTP authentication password (encrypted)';
COMMENT ON COLUMN business_configs.smtp_use_tls IS 'Whether to use STARTTLS';
COMMENT ON COLUMN business_configs.smtp_last_test_at IS 'Last connection test timestamp';
COMMENT ON COLUMN business_configs.smtp_last_test_success IS 'Result of last connection test';
COMMENT ON COLUMN business_configs.smtp_error_message IS 'Error message from last failed test';
COMMENT ON COLUMN business_configs.smtp_email IS 'From email address (e.g., bookings@preclean.com)';
COMMENT ON COLUMN business_configs.smtp_status IS 'Status: live, testing, failed, or null';
