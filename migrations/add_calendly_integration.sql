-- Migration: Add Calendly integration support
-- Description: Adds table for storing Calendly OAuth tokens and integration settings

CREATE TABLE IF NOT EXISTS calendly_integrations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    
    -- OAuth tokens
    access_token VARCHAR(500) NOT NULL,
    refresh_token VARCHAR(500) NOT NULL,
    token_expires_at TIMESTAMP NOT NULL,
    
    -- Calendly user info
    calendly_user_uri VARCHAR(500) NOT NULL,
    calendly_user_email VARCHAR(255),
    calendly_organization_uri VARCHAR(500),
    
    -- Selected event type for appointments
    default_event_type_uri VARCHAR(500),
    default_event_type_name VARCHAR(255),
    default_event_type_url VARCHAR(500),
    
    -- Settings
    auto_sync_enabled BOOLEAN DEFAULT TRUE,
    webhook_uuid VARCHAR(255),
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create index for faster user lookups
CREATE INDEX idx_calendly_user_id ON calendly_integrations(user_id);

-- Add comments for documentation
COMMENT ON TABLE calendly_integrations IS 'Stores Calendly OAuth tokens and integration settings for users';
COMMENT ON COLUMN calendly_integrations.access_token IS 'Calendly OAuth access token';
COMMENT ON COLUMN calendly_integrations.refresh_token IS 'Calendly OAuth refresh token';
COMMENT ON COLUMN calendly_integrations.token_expires_at IS 'When the access token expires';
COMMENT ON COLUMN calendly_integrations.calendly_user_uri IS 'Calendly user URI from API';
COMMENT ON COLUMN calendly_integrations.default_event_type_uri IS 'Selected event type for client scheduling';
COMMENT ON COLUMN calendly_integrations.webhook_uuid IS 'UUID of registered webhook subscription';
