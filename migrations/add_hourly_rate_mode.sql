-- Add hourly_rate_mode field to business_config table
-- This field determines how hourly pricing is calculated:
-- 'per_cleaner': Total = Hourly Rate × Number of Cleaners × Job Duration
-- 'general': Total = Hourly Rate × Job Duration (cleaner count doesn't multiply)

ALTER TABLE business_config
ADD COLUMN IF NOT EXISTS hourly_rate_mode VARCHAR(20) DEFAULT 'per_cleaner';

-- Add comment to explain the field
COMMENT ON COLUMN business_config.hourly_rate_mode IS 'Hourly pricing mode: per_cleaner (rate × cleaners × hours) or general (rate × hours only)';
