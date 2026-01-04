-- Add trial tracking table for free contract generation feature
-- Tracks users by session ID and IP address to limit to 1 free contract

CREATE TABLE IF NOT EXISTS trial_contracts (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    client_name VARCHAR(255) NOT NULL,
    client_email VARCHAR(255),
    business_name VARCHAR(255),
    property_type VARCHAR(100),
    square_footage INTEGER,
    cleaning_frequency VARCHAR(100),
    contract_data JSONB,
    pdf_key VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, ip_address)
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_trial_session_ip ON trial_contracts(session_id, ip_address);
CREATE INDEX IF NOT EXISTS idx_trial_created_at ON trial_contracts(created_at);

-- Add comment
COMMENT ON TABLE trial_contracts IS 'Tracks free trial contract generations limited to 1 per session/IP combination';
