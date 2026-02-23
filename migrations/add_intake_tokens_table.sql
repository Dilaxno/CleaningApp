-- Migration: Add intake_tokens table for secure pre-intake form data transfer
-- This table stores temporary tokens that securely pass client information
-- from the pre-intake iframe form to the full intake form

CREATE TABLE IF NOT EXISTS intake_tokens (
    id SERIAL PRIMARY KEY,
    token VARCHAR(255) UNIQUE NOT NULL,
    business_id VARCHAR(255) NOT NULL,
    template_id VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(50) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_intake_tokens_token ON intake_tokens(token);
CREATE INDEX IF NOT EXISTS idx_intake_tokens_business_id ON intake_tokens(business_id);
CREATE INDEX IF NOT EXISTS idx_intake_tokens_expires_at ON intake_tokens(expires_at);

-- Add comment
COMMENT ON TABLE intake_tokens IS 'Secure tokens for transferring pre-intake form data to full intake forms';
