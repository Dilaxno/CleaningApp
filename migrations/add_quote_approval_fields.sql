-- Migration: Add quote approval workflow fields to clients table
-- Date: 2026-02-15
-- Description: Adds fields to support the new quote approval workflow where
--              clients approve automated quotes and providers review before final approval

-- Add quote status field
ALTER TABLE clients ADD COLUMN IF NOT EXISTS quote_status VARCHAR(50) DEFAULT 'pending_review';
COMMENT ON COLUMN clients.quote_status IS 'Status of quote approval: pending_review, approved, adjusted, rejected';

-- Add quote approval tracking fields
ALTER TABLE clients ADD COLUMN IF NOT EXISTS quote_approved_at TIMESTAMP;
COMMENT ON COLUMN clients.quote_approved_at IS 'When the provider approved/adjusted the quote';

ALTER TABLE clients ADD COLUMN IF NOT EXISTS quote_approved_by VARCHAR(255);
COMMENT ON COLUMN clients.quote_approved_by IS 'User ID or email of who approved the quote';

-- Add quote amount tracking
ALTER TABLE clients ADD COLUMN IF NOT EXISTS original_quote_amount DECIMAL(10, 2);
COMMENT ON COLUMN clients.original_quote_amount IS 'Original automated quote amount';

ALTER TABLE clients ADD COLUMN IF NOT EXISTS adjusted_quote_amount DECIMAL(10, 2);
COMMENT ON COLUMN clients.adjusted_quote_amount IS 'Adjusted quote amount if provider made changes';

ALTER TABLE clients ADD COLUMN IF NOT EXISTS quote_adjustment_notes TEXT;
COMMENT ON COLUMN clients.quote_adjustment_notes IS 'Provider notes explaining quote adjustments';

-- Add client quote submission timestamp
ALTER TABLE clients ADD COLUMN IF NOT EXISTS quote_submitted_at TIMESTAMP;
COMMENT ON COLUMN clients.quote_submitted_at IS 'When the client submitted/approved the automated quote';

-- Create index for efficient querying of pending reviews
CREATE INDEX IF NOT EXISTS idx_clients_quote_status ON clients(quote_status);
CREATE INDEX IF NOT EXISTS idx_clients_user_quote_status ON clients(user_id, quote_status);

-- Create quote history table for audit trail
CREATE TABLE IF NOT EXISTS quote_history (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    action VARCHAR(50) NOT NULL,
    amount DECIMAL(10, 2),
    notes TEXT,
    created_by VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT quote_history_action_check CHECK (action IN ('submitted', 'approved', 'adjusted', 'rejected'))
);

CREATE INDEX IF NOT EXISTS idx_quote_history_client_id ON quote_history(client_id);
CREATE INDEX IF NOT EXISTS idx_quote_history_created_at ON quote_history(created_at);

COMMENT ON TABLE quote_history IS 'Audit trail for quote approval workflow actions';
COMMENT ON COLUMN quote_history.action IS 'Type of action: submitted, approved, adjusted, rejected';
COMMENT ON COLUMN quote_history.amount IS 'Quote amount at time of action';
COMMENT ON COLUMN quote_history.notes IS 'Additional notes or explanation for the action';
COMMENT ON COLUMN quote_history.created_by IS 'User ID or identifier of who performed the action';
