-- Migration: Update contract status workflow
-- Description: Implements comprehensive status workflow for contract lifecycle management

-- Add new status values and update existing ones
-- Status workflow: new → signed → scheduled → active → completed/cancelled

-- First, let's update existing statuses to the new workflow
UPDATE contracts 
SET status = 'new' 
WHERE status IN ('draft', 'sent');

UPDATE contracts 
SET status = 'signed' 
WHERE status = 'pending_provider_signature' 
   OR (status = 'signed' AND client_signature IS NOT NULL AND provider_signature IS NOT NULL);

-- Contracts that are currently active but haven't started yet should be scheduled
UPDATE contracts 
SET status = 'scheduled' 
WHERE status = 'active' 
  AND start_date > NOW();

-- Contracts that are active and have started
UPDATE contracts 
SET status = 'active' 
WHERE status = 'active' 
  AND start_date <= NOW() 
  AND (end_date IS NULL OR end_date > NOW());

-- Contracts that have ended
UPDATE contracts 
SET status = 'completed' 
WHERE status = 'completed' 
  OR (status = 'active' AND end_date IS NOT NULL AND end_date <= NOW());

-- Add check constraint for valid statuses (PostgreSQL)
-- Note: This is optional but helps maintain data integrity
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'contracts_status_check'
    ) THEN
        ALTER TABLE contracts 
        ADD CONSTRAINT contracts_status_check 
        CHECK (status IN ('new', 'signed', 'scheduled', 'active', 'cancelled', 'completed'));
    END IF;
END $$;

-- Add index for status-based queries (improves performance)
CREATE INDEX IF NOT EXISTS idx_contracts_status ON contracts(status);
CREATE INDEX IF NOT EXISTS idx_contracts_status_dates ON contracts(status, start_date, end_date);

-- Add comments for documentation
COMMENT ON COLUMN contracts.status IS 'Contract lifecycle status: new (initial lead) → signed (both parties signed) → scheduled (time slot confirmed) → active (service started) → completed/cancelled';

-- Create a view for contract status analytics (optional)
CREATE OR REPLACE VIEW contract_status_summary AS
SELECT 
    user_id,
    status,
    COUNT(*) as count,
    SUM(total_value) as total_value,
    MIN(created_at) as earliest_contract,
    MAX(created_at) as latest_contract
FROM contracts
GROUP BY user_id, status;

COMMENT ON VIEW contract_status_summary IS 'Summary of contracts by user and status for analytics';
