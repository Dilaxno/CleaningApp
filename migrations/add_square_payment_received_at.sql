-- Add square_payment_received_at field to contracts table
-- This tracks when payment was actually received from Square

ALTER TABLE contracts 
ADD COLUMN IF NOT EXISTS square_payment_received_at TIMESTAMP NULL;

-- Add comment
COMMENT ON COLUMN contracts.square_payment_received_at IS 'Timestamp when payment was received from Square';
