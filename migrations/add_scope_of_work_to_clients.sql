-- Add scope_of_work JSON field to clients table
-- This stores the structured scope of work data selected by the client during form submission

ALTER TABLE clients ADD COLUMN IF NOT EXISTS scope_of_work JSON;

COMMENT ON COLUMN clients.scope_of_work IS 'Structured scope of work data with selected tasks, consumables responsibility, and special notes from scope builder';
