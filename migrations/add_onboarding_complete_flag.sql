-- Add onboarding_complete column to business_configs table
ALTER TABLE business_configs ADD COLUMN IF NOT EXISTS onboarding_complete BOOLEAN DEFAULT FALSE;

-- Update existing records to set onboarding_complete based on whether they have a business_name
UPDATE business_configs SET onboarding_complete = TRUE WHERE business_name IS NOT NULL AND business_name != '';
