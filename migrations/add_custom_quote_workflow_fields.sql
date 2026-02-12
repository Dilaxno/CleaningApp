-- Custom Quote Workflow - Database Schema Updates
-- Adds fields to support complete custom quote workflow

-- CustomQuoteRequest table updates
ALTER TABLE custom_quote_requests 
ADD COLUMN IF NOT EXISTS client_notes TEXT;

ALTER TABLE custom_quote_requests 
ADD COLUMN IF NOT EXISTS provider_viewed_at TIMESTAMP;

-- Contract table updates
ALTER TABLE contracts 
ADD COLUMN IF NOT EXISTS custom_quote_request_id INTEGER REFERENCES custom_quote_requests(id);

ALTER TABLE contracts 
ADD COLUMN IF NOT EXISTS invoice_auto_sent BOOLEAN DEFAULT FALSE;

ALTER TABLE contracts 
ADD COLUMN IF NOT EXISTS invoice_auto_sent_at TIMESTAMP;

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_contracts_custom_quote_request_id 
ON contracts(custom_quote_request_id);

CREATE INDEX IF NOT EXISTS idx_custom_quote_requests_status 
ON custom_quote_requests(status);

CREATE INDEX IF NOT EXISTS idx_custom_quote_requests_user_id_status 
ON custom_quote_requests(user_id, status);

-- Add comments
COMMENT ON COLUMN custom_quote_requests.client_notes IS 'Client-provided notes describing their specific needs';
COMMENT ON COLUMN custom_quote_requests.provider_viewed_at IS 'Timestamp when provider first viewed the request';
COMMENT ON COLUMN contracts.custom_quote_request_id IS 'Link to custom quote request if contract was created from custom quote';
COMMENT ON COLUMN contracts.invoice_auto_sent IS 'Whether Square invoice was automatically sent after both parties signed';
COMMENT ON COLUMN contracts.invoice_auto_sent_at IS 'Timestamp when invoice was automatically sent';
