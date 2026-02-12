-- Add payment confirmation tracking fields to contracts table
-- These fields enable frontend redirect flow after Square webhook confirms payment

ALTER TABLE contracts 
ADD COLUMN IF NOT EXISTS payment_confirmation_pending BOOLEAN DEFAULT FALSE;

ALTER TABLE contracts 
ADD COLUMN IF NOT EXISTS payment_confirmed_at TIMESTAMP;

-- Add comments for documentation
COMMENT ON COLUMN contracts.payment_confirmation_pending IS 'Flag to trigger frontend redirect to payment confirmation page';
COMMENT ON COLUMN contracts.payment_confirmed_at IS 'Timestamp when payment was confirmed via Square webhook';
