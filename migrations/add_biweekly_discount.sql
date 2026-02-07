-- Add bi-weekly discount field to business_configs table
-- This allows businesses to set a separate discount rate for bi-weekly cleaning frequency

ALTER TABLE business_configs ADD COLUMN discount_biweekly FLOAT;

-- Update existing records: copy discount_weekly to discount_biweekly as a starting point
-- Business owners can then customize the bi-weekly rate separately
UPDATE business_configs SET discount_biweekly = discount_weekly WHERE discount_weekly IS NOT NULL;
