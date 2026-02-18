-- Migration: Add Visit Management System
-- Description: Creates visits table for tracking individual service visits within contracts

CREATE TABLE IF NOT EXISTS visits (
    id SERIAL PRIMARY KEY,
    public_id VARCHAR(36) UNIQUE NOT NULL,
    user_id INTEGER NOT NULL,
    client_id INTEGER NOT NULL,
    contract_id INTEGER NOT NULL,
    invoice_id INTEGER,
    visit_number INTEGER NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    scheduled_date TIMESTAMP NOT NULL,
    scheduled_start_time VARCHAR(10),
    scheduled_end_time VARCHAR(10),
    duration_minutes INTEGER,
    actual_start_time TIMESTAMP,
    actual_end_time TIMESTAMP,
    status VARCHAR(50) NOT NULL DEFAULT 'scheduled',
    visit_amount FLOAT,
    currency VARCHAR(10) DEFAULT 'USD',
    payment_method VARCHAR(50),
    payment_status VARCHAR(50),
    payment_captured_at TIMESTAMP,
    square_invoice_id VARCHAR(255),
    square_invoice_url TEXT,
    square_payment_id VARCHAR(255),
    provider_notes TEXT,
    client_notes TEXT,
    completion_notes TEXT,
    started_by VARCHAR(255),
    started_at TIMESTAMP,
    completed_by VARCHAR(255),
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE CASCADE,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE SET NULL
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_visits_public_id ON visits(public_id);
CREATE INDEX IF NOT EXISTS idx_visits_user_id ON visits(user_id);
CREATE INDEX IF NOT EXISTS idx_visits_client_id ON visits(client_id);
CREATE INDEX IF NOT EXISTS idx_visits_contract_id ON visits(contract_id);
CREATE INDEX IF NOT EXISTS idx_visits_status ON visits(status);
CREATE INDEX IF NOT EXISTS idx_visits_scheduled_date ON visits(scheduled_date);
