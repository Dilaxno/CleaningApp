-- Add scope_template JSON field to form_templates table
-- This stores the default scope of work structure (service areas and tasks) for each template

ALTER TABLE form_templates ADD COLUMN IF NOT EXISTS scope_template JSON;

COMMENT ON COLUMN form_templates.scope_template IS 'Default scope of work template with service areas and tasks for this form template';
