-- Migration: Add Two-Factor Authentication fields to users table
-- Date: 2026-01-05
-- Description: Adds TOTP, SMS, recovery email, and backup codes support

-- Add 2FA columns to users table
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS totp_secret VARCHAR(100),
ADD COLUMN IF NOT EXISTS totp_enabled BOOLEAN DEFAULT FALSE NOT NULL,
ADD COLUMN IF NOT EXISTS phone_number VARCHAR(50),
ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN DEFAULT FALSE NOT NULL,
ADD COLUMN IF NOT EXISTS phone_2fa_enabled BOOLEAN DEFAULT FALSE NOT NULL,
ADD COLUMN IF NOT EXISTS recovery_email VARCHAR(255),
ADD COLUMN IF NOT EXISTS recovery_email_verified BOOLEAN DEFAULT FALSE NOT NULL,
ADD COLUMN IF NOT EXISTS backup_codes JSON;

-- Create index for phone lookup
CREATE INDEX IF NOT EXISTS idx_users_phone_number ON users(phone_number) WHERE phone_number IS NOT NULL;

-- Create index for recovery email lookup  
CREATE INDEX IF NOT EXISTS idx_users_recovery_email ON users(recovery_email) WHERE recovery_email IS NOT NULL;

-- Add comment
COMMENT ON COLUMN users.totp_secret IS 'TOTP secret for authenticator app 2FA';
COMMENT ON COLUMN users.totp_enabled IS 'Whether TOTP 2FA is enabled';
COMMENT ON COLUMN users.phone_number IS 'Phone number for SMS 2FA';
COMMENT ON COLUMN users.phone_verified IS 'Whether phone number is verified';
COMMENT ON COLUMN users.phone_2fa_enabled IS 'Whether SMS 2FA is enabled';
COMMENT ON COLUMN users.recovery_email IS 'Secondary email for account recovery';
COMMENT ON COLUMN users.recovery_email_verified IS 'Whether recovery email is verified';
COMMENT ON COLUMN users.backup_codes IS 'Encrypted backup codes for 2FA recovery';
