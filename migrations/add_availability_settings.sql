-- Add availability settings to business_configs table
ALTER TABLE business_configs ADD COLUMN IF NOT EXISTS working_days JSON;
ALTER TABLE business_configs ADD COLUMN IF NOT EXISTS working_hours JSON;
ALTER TABLE business_configs ADD COLUMN IF NOT EXISTS break_times JSON;

-- Set default working days (Monday-Friday) for existing records
UPDATE business_configs 
SET working_days = '["monday", "tuesday", "wednesday", "thursday", "friday"]'::json
WHERE working_days IS NULL;

-- Set default working hours (9 AM - 5 PM) for existing records
UPDATE business_configs 
SET working_hours = '{"start": "09:00", "end": "17:00"}'::json
WHERE working_hours IS NULL;
