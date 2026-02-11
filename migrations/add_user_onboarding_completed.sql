-- Add onboarding_completed column to users table
-- This field is synchronized with business_configs.onboarding_complete
-- to ensure onboarding status persists across devices and browsers

ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN DEFAULT FALSE;

-- Synchronize existing users: set onboarding_completed = TRUE if they have a business_config with onboarding_complete = TRUE
UPDATE users u
SET onboarding_completed = TRUE
FROM business_configs bc
WHERE u.id = bc.user_id
  AND bc.onboarding_complete = TRUE;

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_onboarding_completed ON users(onboarding_completed);
