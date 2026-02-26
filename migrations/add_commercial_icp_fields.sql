-- Add commercial ICP fields to users table
-- These fields replace account_type and hear_about with business-focused data

-- Add company name field
ALTER TABLE users ADD COLUMN IF NOT EXISTS company_name VARCHAR(255);

-- Add employee count field (ranges: 1-9, 10-24, 25-74, 75+)
ALTER TABLE users ADD COLUMN IF NOT EXISTS employee_count VARCHAR(20);

-- Add primary service type field (Office, Medical, Retail, Industrial, Multi-site)
ALTER TABLE users ADD COLUMN IF NOT EXISTS primary_service_type VARCHAR(100);

-- Add contract type field (Mostly recurring, Mixed, Mostly one-time)
ALTER TABLE users ADD COLUMN IF NOT EXISTS contract_type VARCHAR(100);

-- Add indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_users_primary_service_type ON users(primary_service_type);
CREATE INDEX IF NOT EXISTS idx_users_contract_type ON users(contract_type);
