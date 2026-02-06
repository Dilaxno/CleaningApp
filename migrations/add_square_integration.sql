-- Add Square integration fields to business_configs table
ALTER TABLE business_configs
ADD COLUMN square_access_token TEXT,
ADD COLUMN square_refresh_token TEXT,
ADD COLUMN square_merchant_id VARCHAR(255),
ADD COLUMN square_token_expires_at TIMESTAMP,
ADD COLUMN square_connected_at TIMESTAMP,
ADD COLUMN square_location_id VARCHAR(255),
ADD COLUMN square_auto_invoice BOOLEAN DEFAULT FALSE,
ADD COLUMN square_auto_subscription BOOLEAN DEFAULT FALSE;

-- Add Square payment tracking to contracts table
ALTER TABLE contracts
ADD COLUMN square_invoice_id VARCHAR(255),
ADD COLUMN square_subscription_id VARCHAR(255),
ADD COLUMN square_payment_status VARCHAR(50),
ADD COLUMN square_invoice_url TEXT;

-- Create Square webhooks log table for debugging
CREATE TABLE IF NOT EXISTS square_webhook_logs (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(255) NOT NULL,
    event_id VARCHAR(255) UNIQUE NOT NULL,
    merchant_id VARCHAR(255),
    payload JSONB NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_square_webhook_event_id ON square_webhook_logs(event_id);
CREATE INDEX idx_square_webhook_merchant_id ON square_webhook_logs(merchant_id);
