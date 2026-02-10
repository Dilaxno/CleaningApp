-- Add Square invoice tracking fields to contracts table
-- These fields track Square payment status and invoice links

ALTER TABLE contracts ADD COLUMN IF NOT EXISTS square_invoice_id VARCHAR(255);
ALTER TABLE contracts ADD COLUMN IF NOT EXISTS square_invoice_url TEXT;
ALTER TABLE contracts ADD COLUMN IF NOT EXISTS square_payment_status VARCHAR(50);
ALTER TABLE contracts ADD COLUMN IF NOT EXISTS square_invoice_created_at TIMESTAMP;

-- Create indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_contracts_square_invoice_id ON contracts(square_invoice_id);
CREATE INDEX IF NOT EXISTS idx_contracts_square_payment_status ON contracts(square_payment_status);

-- Add comments
COMMENT ON COLUMN contracts.square_invoice_id IS 'Square invoice ID for payment tracking';
COMMENT ON COLUMN contracts.square_invoice_url IS 'Public Square invoice URL for client payment';
COMMENT ON COLUMN contracts.square_payment_status IS 'Square payment status: pending, paid, failed, cancelled';
COMMENT ON COLUMN contracts.square_invoice_created_at IS 'When the Square invoice was created';
