-- Add contract term length and auto-renewal fields to business_configs table
-- These fields support commercial cleaning MSA workflows

-- Add contract_term_length field (6 months, 12 months, or month-to-month)
ALTER TABLE business_configs
ADD COLUMN IF NOT EXISTS contract_term_length VARCHAR(20);

-- Add auto_renewal field (whether contract automatically renews)
ALTER TABLE business_configs
ADD COLUMN IF NOT EXISTS auto_renewal BOOLEAN DEFAULT TRUE;

-- Set default values for existing records
UPDATE business_configs
SET contract_term_length = '12'
WHERE contract_term_length IS NULL;

UPDATE business_configs
SET auto_renewal = TRUE
WHERE auto_renewal IS NULL;

-- Add comments for documentation
COMMENT ON COLUMN business_configs.contract_term_length IS 'Contract term length: 6, 12, or month-to-month';
COMMENT ON COLUMN business_configs.auto_renewal IS 'Whether the contract automatically renews at term end';
