-- Add Twilio Integration Tables
-- Stores Twilio credentials and SMS logs for automated notifications

-- Twilio Integration table
CREATE TABLE IF NOT EXISTS twilio_integrations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE,
    account_sid TEXT NOT NULL,
    auth_token TEXT NOT NULL,
    messaging_service_sid TEXT,
    phone_number VARCHAR(20),
    sms_enabled BOOLEAN DEFAULT TRUE,
    send_estimate_approval BOOLEAN DEFAULT TRUE,
    send_schedule_confirmation BOOLEAN DEFAULT TRUE,
    send_contract_signed BOOLEAN DEFAULT TRUE,
    send_job_reminder BOOLEAN DEFAULT TRUE,
    send_job_completion BOOLEAN DEFAULT TRUE,
    send_payment_confirmation BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    last_test_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Twilio SMS Logs table
CREATE TABLE IF NOT EXISTS twilio_sms_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    integration_id INTEGER NOT NULL,
    to_phone VARCHAR(20) NOT NULL,
    message_body TEXT NOT NULL,
    message_type VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50),
    entity_id INTEGER,
    twilio_message_sid VARCHAR(255),
    status VARCHAR(50) NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (integration_id) REFERENCES twilio_integrations(id) ON DELETE CASCADE
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_twilio_integrations_user_id ON twilio_integrations(user_id);
CREATE INDEX IF NOT EXISTS idx_twilio_sms_logs_user_id ON twilio_sms_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_twilio_sms_logs_integration_id ON twilio_sms_logs(integration_id);
CREATE INDEX IF NOT EXISTS idx_twilio_sms_logs_created_at ON twilio_sms_logs(created_at);
