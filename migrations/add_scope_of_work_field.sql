-- Add scope_of_work JSON field to contracts table
-- This stores the structured scope of work data selected by the client

ALTER TABLE contracts ADD COLUMN IF NOT EXISTS scope_of_work JSON;

-- Add exhibit_a_pdf_key to store the Exhibit A PDF separately
ALTER TABLE contracts ADD COLUMN IF NOT EXISTS exhibit_a_pdf_key VARCHAR(500);

COMMENT ON COLUMN contracts.scope_of_work IS 'Structured scope of work data with selected tasks, consumables responsibility, and special notes';
COMMENT ON COLUMN contracts.exhibit_a_pdf_key IS 'R2 storage key for the Exhibit A - Detailed Scope of Work PDF attachment';
