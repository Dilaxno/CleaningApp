-- Add business_phone field to business_configs table
-- This field stores the business phone number for optional client assistance

ALTER TABLE business_configs ADD COLUMN business_phone VARCHAR(50);
