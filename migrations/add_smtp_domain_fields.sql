-- Add custom SMTP domain fields to business_configs table
ALTER TABLE business_configs ADD COLUMN IF NOT EXISTS smtp_email VARCHAR(255);
ALTER TABLE business_configs ADD COLUMN IF NOT EXISTS smtp_domain VARCHAR(255);
ALTER TABLE business_configs ADD COLUMN IF NOT EXISTS resend_domain_id VARCHAR(255);
ALTER TABLE business_configs ADD COLUMN IF NOT EXISTS smtp_status VARCHAR(50);
ALTER TABLE business_configs ADD COLUMN IF NOT EXISTS smtp_dns_records JSON;
ALTER TABLE business_configs ADD COLUMN IF NOT EXISTS smtp_verified_records INTEGER DEFAULT 0;

-- Add comments for documentation
COMMENT ON COLUMN business_configs.smtp_email IS 'Custom email address for sending (e.g., bookings@preclean.com)';
COMMENT ON COLUMN business_configs.smtp_domain IS 'Domain extracted from smtp_email (e.g., preclean.com)';
COMMENT ON COLUMN business_configs.resend_domain_id IS 'Resend API domain ID for verification';
COMMENT ON COLUMN business_configs.smtp_status IS 'Domain verification status: pending, verified, failed';
COMMENT ON COLUMN business_configs.smtp_dns_records IS 'DNS records user needs to configure (MX, SPF, DKIM)';
COMMENT ON COLUMN business_configs.smtp_verified_records IS 'Count of verified DNS records (0-3)';
