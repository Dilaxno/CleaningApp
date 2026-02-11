-- Migration: Add custom_quote_requests table
-- Description: Enables clients to request custom quotes by uploading video walkthroughs
-- Date: 2026-02-11

CREATE TABLE IF NOT EXISTS custom_quote_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT UNIQUE NOT NULL,
    user_id INTEGER NOT NULL,
    client_id INTEGER NOT NULL,
    
    -- Video details
    video_r2_key TEXT NOT NULL,
    video_filename TEXT NOT NULL,
    video_size_bytes INTEGER NOT NULL,
    video_duration_seconds REAL,
    video_mime_type TEXT NOT NULL,
    
    -- Request status
    status TEXT DEFAULT 'pending' NOT NULL,
    
    -- Custom quote from provider
    custom_quote_amount REAL,
    custom_quote_currency TEXT DEFAULT 'USD',
    custom_quote_description TEXT,
    custom_quote_line_items TEXT,
    custom_quote_notes TEXT,
    quoted_at TEXT,
    
    -- Client response
    client_response TEXT,
    client_response_notes TEXT,
    responded_at TEXT,
    
    -- Link to generated contract after approval
    contract_id INTEGER,
    
    -- Metadata
    client_ip TEXT,
    client_user_agent TEXT,
    expires_at TEXT,
    
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE SET NULL
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_custom_quote_requests_public_id ON custom_quote_requests(public_id);
CREATE INDEX IF NOT EXISTS idx_custom_quote_requests_user_id ON custom_quote_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_custom_quote_requests_client_id ON custom_quote_requests(client_id);
CREATE INDEX IF NOT EXISTS idx_custom_quote_requests_status ON custom_quote_requests(status);
CREATE INDEX IF NOT EXISTS idx_custom_quote_requests_created_at ON custom_quote_requests(created_at);
