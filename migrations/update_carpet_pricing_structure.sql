-- Update carpet pricing structure from per sq ft to size-based pricing
-- This migration adds new columns for carpet size pricing and keeps the old column for backward compatibility

-- Add new carpet pricing columns
ALTER TABLE business_configs 
ADD COLUMN IF NOT EXISTS addon_carpet_small DECIMAL(10,2) DEFAULT NULL,
ADD COLUMN IF NOT EXISTS addon_carpet_medium DECIMAL(10,2) DEFAULT NULL,
ADD COLUMN IF NOT EXISTS addon_carpet_large DECIMAL(10,2) DEFAULT NULL;

-- Add comment explaining the new structure
COMMENT ON COLUMN business_configs.addon_carpet_small IS 'Price for small carpet cleaning (e.g., bedroom, small area rug)';
COMMENT ON COLUMN business_configs.addon_carpet_medium IS 'Price for medium carpet cleaning (e.g., living room, office space)';
COMMENT ON COLUMN business_configs.addon_carpet_large IS 'Price for large carpet cleaning (e.g., large living room, conference room)';

-- Keep the old addon_carpets column for backward compatibility during transition
COMMENT ON COLUMN business_configs.addon_carpets IS 'Legacy per sq ft pricing - deprecated in favor of size-based pricing';