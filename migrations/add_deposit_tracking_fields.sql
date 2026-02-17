-- Add deposit tracking fields to contracts table
-- This supports the 50% deposit payment structure

ALTER TABLE contracts
ADD COLUMN IF NOT EXISTS deposit_amount DECIMAL(10, 2),
ADD COLUMN IF NOT EXISTS deposit_paid BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS deposit_paid_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS remaining_balance DECIMAL(10, 2),
ADD COLUMN IF NOT EXISTS balance_invoice_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS balance_invoice_url TEXT,
ADD COLUMN IF NOT EXISTS balance_paid BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS balance_paid_at TIMESTAMP;

-- Add comments for clarity
COMMENT ON COLUMN contracts.deposit_amount IS '50% deposit amount charged upfront';
COMMENT ON COLUMN contracts.deposit_paid IS 'Whether the 50% deposit has been paid';
COMMENT ON COLUMN contracts.deposit_paid_at IS 'When the deposit was paid';
COMMENT ON COLUMN contracts.remaining_balance IS 'Remaining 50% balance due after job completion';
COMMENT ON COLUMN contracts.balance_invoice_id IS 'Square invoice ID for the remaining balance';
COMMENT ON COLUMN contracts.balance_invoice_url IS 'Payment URL for the remaining balance invoice';
COMMENT ON COLUMN contracts.balance_paid IS 'Whether the remaining balance has been paid';
COMMENT ON COLUMN contracts.balance_paid_at IS 'When the remaining balance was paid';
