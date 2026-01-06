-- Add meetings_required field to business_configs table
ALTER TABLE business_configs ADD COLUMN IF NOT EXISTS meetings_required BOOLEAN DEFAULT FALSE;

-- Set default to false for existing records
UPDATE business_configs SET meetings_required = FALSE WHERE meetings_required IS NULL;
