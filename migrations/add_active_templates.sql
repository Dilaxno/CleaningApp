-- Add active_templates field to business_configs table
-- This field stores the list of template IDs that the business owner has selected to work with

ALTER TABLE business_configs 
ADD COLUMN active_templates JSON DEFAULT '[]';

-- Update existing records to have all templates active by default (backward compatibility)
UPDATE business_configs 
SET active_templates = '["office", "retail", "medical", "gym", "restaurant", "residential", "airbnb", "school", "warehouse", "post-construction", "move-in-out", "deep-clean", "outside-cleaning", "carpet-cleaning"]'
WHERE active_templates IS NULL OR JSON_LENGTH(active_templates) = 0;