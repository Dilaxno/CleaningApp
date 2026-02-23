-- Add onboarding_step and oauth_states fields to users table
-- This allows preserving onboarding progress during OAuth flows

-- Add onboarding_step column (tracks current step 1-14)
ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_step INTEGER DEFAULT 1 NOT NULL;

-- Add oauth_states column (stores OAuth connection states as JSON)
ALTER TABLE users ADD COLUMN IF NOT EXISTS oauth_states JSONB DEFAULT '{}'::jsonb;

-- Update existing users to have default values
UPDATE users SET onboarding_step = 1 WHERE onboarding_step IS NULL;
UPDATE users SET oauth_states = '{}'::jsonb WHERE oauth_states IS NULL;

-- Add comment for documentation
COMMENT ON COLUMN users.onboarding_step IS 'Current onboarding step (1-14) for preserving progress during OAuth flows';
COMMENT ON COLUMN users.oauth_states IS 'OAuth connection states (JSON) for tracking provider connections during onboarding';
