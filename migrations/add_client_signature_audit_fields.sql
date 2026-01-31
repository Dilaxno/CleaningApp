-- Add client signature audit trail fields to contracts table
-- These fields track when and from where clients sign contracts

-- Check if columns exist before adding (safe to re-run)
DO $$ 
BEGIN
    -- Add client_signature_ip if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'contracts' AND column_name = 'client_signature_ip'
    ) THEN
        ALTER TABLE contracts ADD COLUMN client_signature_ip VARCHAR(45);
    END IF;

    -- Add client_signature_user_agent if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'contracts' AND column_name = 'client_signature_user_agent'
    ) THEN
        ALTER TABLE contracts ADD COLUMN client_signature_user_agent VARCHAR(500);
    END IF;

    -- Add client_signature_timestamp if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'contracts' AND column_name = 'client_signature_timestamp'
    ) THEN
        ALTER TABLE contracts ADD COLUMN client_signature_timestamp TIMESTAMP;
    END IF;
END $$;
