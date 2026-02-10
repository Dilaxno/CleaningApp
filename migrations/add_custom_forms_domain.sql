-- Add custom forms domain/subdomain for white-labeled public form links
--
-- Example desired hostname:
--   forms.cleaningco.com
-- DNS setup (customer):
--   Type: CNAME
--   Name: forms
--   Value: api.cleanenroll.com
--
ALTER TABLE business_configs ADD COLUMN IF NOT EXISTS custom_forms_domain VARCHAR(255);

COMMENT ON COLUMN business_configs.custom_forms_domain IS 'Optional hostname used for public form links (e.g., forms.cleaningco.com)';
