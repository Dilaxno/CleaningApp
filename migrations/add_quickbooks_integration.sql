-- QuickBooks Integration Tables
-- Add tables for QuickBooks OAuth and sync tracking

-- QuickBooks Integration table
CREATE TABLE IF NOT EXISTS quickbooks_integrations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    token_expires_at TIMESTAMP NOT NULL,
    realm_id VARCHAR(255) NOT NULL,
    company_name VARCHAR(255),
    auto_sync_enabled BOOLEAN DEFAULT TRUE,
    sync_invoices BOOLEAN DEFAULT TRUE,
    sync_payments BOOLEAN DEFAULT TRUE,
    sync_customers BOOLEAN DEFAULT TRUE,
    last_invoice_sync TIMESTAMP,
    last_payment_sync TIMESTAMP,
    last_customer_sync TIMESTAMP,
    environment VARCHAR(50) DEFAULT 'production',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- QuickBooks Sync Log table
CREATE TABLE IF NOT EXISTS quickbooks_sync_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    integration_id INTEGER NOT NULL,
    sync_type VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id INTEGER NOT NULL,
    quickbooks_id VARCHAR(255),
    status VARCHAR(50) NOT NULL,
    error_message TEXT,
    sync_data JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (integration_id) REFERENCES quickbooks_integrations(id) ON DELETE CASCADE
);

-- Indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_quickbooks_integrations_user_id ON quickbooks_integrations(user_id);
CREATE INDEX IF NOT EXISTS idx_quickbooks_sync_logs_user_id ON quickbooks_sync_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_quickbooks_sync_logs_integration_id ON quickbooks_sync_logs(integration_id);
CREATE INDEX IF NOT EXISTS idx_quickbooks_sync_logs_entity ON quickbooks_sync_logs(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_quickbooks_sync_logs_status ON quickbooks_sync_logs(status);
