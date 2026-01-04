-- Migration: Add provider_signature column to contracts table
-- This stores the provider's actual signature image (base64) on the contract

ALTER TABLE contracts 
ADD COLUMN IF NOT EXISTS provider_signature TEXT;

-- Add comment for documentation
COMMENT ON COLUMN contracts.provider_signature IS 'Base64 encoded provider signature image';
