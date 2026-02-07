-- Add Square subscription fields to contracts table
ALTER TABLE contracts ADD COLUMN IF NOT EXISTS square_subscription_id VARCHAR(255);
ALTER TABLE contracts ADD COLUMN IF NOT EXISTS square_subscription_status VARCHAR(50);
ALTER TABLE contracts ADD COLUMN IF NOT EXISTS square_subscription_created_at TIMESTAMP;
ALTER TABLE contracts ADD COLUMN IF NOT EXISTS provider_signed_at TIMESTAMP;
ALTER TABLE contracts ADD COLUMN IF NOT EXISTS both_parties_signed_at TIMESTAMP;
ALTER TABLE contracts ADD COLUMN IF NOT EXISTS invoice_auto_generated BOOLEAN DEFAULT FALSE;
ALTER TABLE contracts ADD COLUMN IF NOT EXISTS frequency VARCHAR(50);

-- Add Square subscription fields to clients table
ALTER TABLE clients ADD COLUMN IF NOT EXISTS square_subscription_id VARCHAR(255);
ALTER TABLE clients ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(50);
ALTER TABLE clients ADD COLUMN IF NOT EXISTS subscription_frequency VARCHAR(50);

-- Add indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_contracts_square_subscription_id ON contracts(square_subscription_id);
CREATE INDEX IF NOT EXISTS idx_clients_square_subscription_id ON clients(square_subscription_id);
CREATE INDEX IF NOT EXISTS idx_contracts_provider_signed_at ON contracts(provider_signed_at);
CREATE INDEX IF NOT EXISTS idx_contracts_both_parties_signed_at ON contracts(both_parties_signed_at);
