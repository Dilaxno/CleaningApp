-- Add accepted frequencies and payment methods columns to business_configs table
-- Migration: add_accepted_frequencies_payment_methods
-- Date: 2026-02-08

-- Add accepted_frequencies column with default values
ALTER TABLE business_configs
ADD COLUMN IF NOT EXISTS accepted_frequencies JSONB DEFAULT '["one-time", "weekly", "bi-weekly", "monthly"]'::jsonb;

-- Add accepted_payment_methods column (empty by default, user must select)
ALTER TABLE business_configs
ADD COLUMN IF NOT EXISTS accepted_payment_methods JSONB DEFAULT '[]'::jsonb;

-- Update existing rows to have default values if NULL
UPDATE business_configs
SET accepted_frequencies = '["one-time", "weekly", "bi-weekly", "monthly"]'::jsonb
WHERE accepted_frequencies IS NULL;

UPDATE business_configs
SET accepted_payment_methods = '[]'::jsonb
WHERE accepted_payment_methods IS NULL;

-- Add comments for documentation
COMMENT ON COLUMN business_configs.accepted_frequencies IS 'Array of accepted cleaning frequencies (one-time, weekly, bi-weekly, monthly, custom)';
COMMENT ON COLUMN business_configs.accepted_payment_methods IS 'Array of accepted payment methods (cash, check, card, venmo, paypal, zelle, bank-transfer, square)';
