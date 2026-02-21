-- Add field to track if user skipped SMS setup during onboarding
ALTER TABLE users ADD COLUMN IF NOT EXISTS sms_onboarding_skipped BOOLEAN DEFAULT FALSE;

-- Add comment
COMMENT ON COLUMN users.sms_onboarding_skipped IS 'Tracks if user skipped SMS setup during onboarding';
