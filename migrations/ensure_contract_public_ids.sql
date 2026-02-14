-- Ensure all contracts have a public_id
-- This migration adds public_id to any contracts that don't have one

UPDATE contracts 
SET public_id = gen_random_uuid()::text
WHERE public_id IS NULL;

-- Make public_id NOT NULL after populating
ALTER TABLE contracts 
ALTER COLUMN public_id SET NOT NULL;

-- Add comment
COMMENT ON COLUMN contracts.public_id IS 'Secure public UUID for contract references (prevents enumeration attacks)';
