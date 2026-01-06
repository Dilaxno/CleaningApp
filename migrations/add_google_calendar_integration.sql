-- Add google_calendar_integrations table
CREATE TABLE IF NOT EXISTS google_calendar_integrations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    
    -- OAuth tokens
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    token_expires_at TIMESTAMP NOT NULL,
    
    -- Google user info
    google_user_email VARCHAR(255),
    google_calendar_id VARCHAR(500),
    
    -- Settings
    auto_sync_enabled BOOLEAN DEFAULT TRUE,
    default_appointment_duration INTEGER DEFAULT 60,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_google_calendar_user_id ON google_calendar_integrations(user_id);
