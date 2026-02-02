-- Add form templates tables
CREATE TABLE form_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id VARCHAR(100) NOT NULL UNIQUE,
    user_id INTEGER,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    image VARCHAR(500),
    color VARCHAR(7),
    is_system_template BOOLEAN NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    template_data JSON NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE INDEX ix_form_templates_template_id ON form_templates (template_id);
CREATE INDEX ix_form_templates_user_id ON form_templates (user_id);

CREATE TABLE user_template_customizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    template_id INTEGER NOT NULL,
    customized_data JSON NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (template_id) REFERENCES form_templates (id)
);

CREATE INDEX ix_user_template_customizations_user_id ON user_template_customizations (user_id);
CREATE INDEX ix_user_template_customizations_template_id ON user_template_customizations (template_id);