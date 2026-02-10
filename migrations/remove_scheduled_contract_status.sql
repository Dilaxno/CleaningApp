-- Migration: Remove 'scheduled' status from contract workflow
-- Description: Updates contract status workflow to remove 'scheduled' status
-- New workflow: new → signed → active → completed/cancelled

-- Update existing 'scheduled' contracts to 'signed' status
-- This ensures contracts that were scheduled but not yet active remain in signed state
UPDATE contracts 
SET status = 'signed' 
WHERE status = 'scheduled';

-- Drop the old constraint if it exists
DO $ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'contracts_status_check'
    ) THEN
        ALTER TABLE contracts DROP CONSTRAINT contracts_status_check;
    END IF;
END $;

-- Add new check constraint for valid statuses (without 'scheduled')
ALTER TABLE contracts 
ADD CONSTRAINT contracts_status_check 
CHECK (status IN ('new', 'signed', 'active', 'cancelled', 'completed'));

-- Update the column comment to reflect new workflow
COMMENT ON COLUMN contracts.status IS 'Contract lifecycle status: new (initial/sent to client) → signed (both parties signed) → active (service started) → completed/cancelled';

-- Update the contract status summary view to reflect new workflow
DROP VIEW IF EXISTS contract_status_summary;
CREATE OR REPLACE VIEW contract_status_summary AS
SELECT 
    user_id,
    status,
    COUNT(*) as count,
    SUM(total_value) as total_value,
    MIN(created_at) as earliest_contract,
    MAX(created_at) as latest_contract
FROM contracts
WHERE status IN ('new', 'signed', 'active', 'cancelled', 'completed')
GROUP BY user_id, status;

COMMENT ON VIEW contract_status_summary IS 'Summary of contracts by user and status for analytics (updated workflow without scheduled)';