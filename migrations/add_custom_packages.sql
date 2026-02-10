-- Add custom packages support to business_configs table
-- This migration adds a JSON column to store custom packages configuration

ALTER TABLE business_configs 
ADD COLUMN custom_packages JSON DEFAULT NULL;

-- Add comment for documentation
COMMENT ON COLUMN business_configs.custom_packages IS 'Custom packages configuration: [{"id": "uuid", "name": "Package Name", "description": "...", "included": ["..."], "duration": 120, "priceType": "flat|range|quote", "price": 150, "priceMin": 100, "priceMax": 200}]';