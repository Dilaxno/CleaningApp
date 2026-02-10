-- Migration: Add revision request fields to contracts table
-- This enables providers to request changes before signing

ALTER TABLE contracts 
ADD COLUMN IF NOT EXISTS revision_requested BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS revision_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS revision_notes TEXT,
ADD COLUMN IF NOT EXISTS revision_requested_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS revision_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS custom_quote JSONB,
ADD COLUMN IF NOT EXISTS custom_scope JSONB;

-- Add index for quick lookup of contracts with pending revisions
CREATE INDEX IF NOT EXISTS idx_contracts_revision_requested ON contracts(revision_requested) WHERE revision_requested = TRUE;

-- Add comments
COMMENT ON COLUMN contracts.revision_requested IS 'True if provider requested changes before signing';
COMMENT ON COLUMN contracts.revision_type IS 'Type of revision: pricing, scope, or both';
COMMENT ON COLUMN contracts.revision_notes IS 'Provider notes explaining requested changes';
COMMENT ON COLUMN contracts.revision_count IS 'Number of revision rounds (prevents infinite loops)';
COMMENT ON COLUMN contracts.custom_quote IS 'Provider custom pricing override as JSON';
COMMENT ON COLUMN contracts.custom_scope IS 'Provider custom scope (inclusions/exclusions) as JSON';
