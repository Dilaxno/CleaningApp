-- Clean Square Integration Table
-- This creates the square_integrations table for storing OAuth tokens

-- Drop existing table if it exists (clean slate)
DROP TABLE IF EXISTS square_integrations CASCADE;

-- Create square_integrations table
CREATE TABLE square_integrations (
    user_id VARCHAR PRIMARY KEY,
    merchant_id VARCHAR NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key to users table using firebase_uid
    CONSTRAINT fk_square_user FOREIGN KEY (user_id) REFERENCES users(firebase_uid) ON DELETE CASCADE
);

-- Create index for faster lookups
CREATE INDEX idx_square_user_id ON square_integrations(user_id);
CREATE INDEX idx_square_active ON square_integrations(is_active);

-- Add comment
COMMENT ON TABLE square_integrations IS 'Stores Square OAuth tokens and merchant information for payment processing';
