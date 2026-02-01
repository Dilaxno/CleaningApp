-- Add custom templates table for template customization feature
CREATE TABLE IF NOT EXISTS custom_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    base_template_id VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description VARCHAR(1000),
    template_config JSON NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_custom_templates_user_id ON custom_templates(user_id);
CREATE INDEX IF NOT EXISTS idx_custom_templates_base_template ON custom_templates(base_template_id);
CREATE INDEX IF NOT EXISTS idx_custom_templates_active ON custom_templates(is_active);