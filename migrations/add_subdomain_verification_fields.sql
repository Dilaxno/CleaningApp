-- Migration: Add subdomain verification fields for automated email domains
-- Allows users to connect their own subdomains for sending automated emails

-- Add subdomain verification columns
ALTER TABLE business_configs ADD COLUMN IF NOT EXISTS email_subdomain VARCHAR(255);
ALTER TABLE business_configs ADD COLUMN IF NOT EXISTS subdomain_verification_status VARCHAR(50);
ALTER TABLE business_configs ADD COLUMN IF NOT EXISTS subdomain_dns_records JSON;
ALTER TABLE business_configs ADD COLUMN IF NOT EXISTS subdomain_verified_at TIMESTAMP;
ALTER TABLE business_configs ADD COLUMN IF NOT EXISTS subdomain_last_check_at TIMESTAMP;
ALTER TABLE business_configs ADD COLUMN IF NOT EXISTS subdomain_verification_token VARCHAR(255);

-- Add comments for documentation
COMMENT ON COLUMN business_configs.email_subdomain IS 'Custom subdomain for automated emails (e.g., mail.preclean.com)';
COMMENT ON COLUMN business_configs.subdomain_verification_status IS 'Verification status: pending, verified, failed';
COMMENT ON COLUMN business_configs.subdomain_dns_records IS 'Required DNS records for subdomain verification (CNAME, TXT, MX)';
COMMENT ON COLUMN business_configs.subdomain_verified_at IS 'Timestamp when subdomain was successfully verified';
COMMENT ON COLUMN business_configs.subdomain_last_check_at IS 'Last DNS verification check timestamp';
COMMENT ON COLUMN business_configs.subdomain_verification_token IS 'Unique verification token for TXT record';

-- Create index for faster subdomain lookups
CREATE INDEX IF NOT EXISTS idx_business_configs_email_subdomain ON business_configs(email_subdomain);
CREATE INDEX IF NOT EXISTS idx_business_configs_subdomain_status ON business_configs(subdomain_verification_status);