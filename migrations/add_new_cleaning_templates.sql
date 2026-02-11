-- Migration to add new cleaning templates: outside-cleaning and carpet-cleaning
-- Run this after adding the new templates to the codebase
-- PostgreSQL version

-- Update existing business configs that have all 12 previous templates
-- to include the new templates as well
UPDATE business_configs 
SET active_templates = '["office", "retail", "medical", "gym", "restaurant", "residential", "airbnb", "school", "warehouse", "post-construction", "move-in-out", "deep-clean", "outside-cleaning", "carpet-cleaning"]'::jsonb
WHERE jsonb_array_length(active_templates) = 12
AND active_templates @> '"office"'::jsonb
AND active_templates @> '"deep-clean"'::jsonb
AND NOT active_templates @> '"outside-cleaning"'::jsonb
AND NOT active_templates @> '"carpet-cleaning"'::jsonb;

-- Update any configs that are empty or null (backward compatibility)
UPDATE business_configs 
SET active_templates = '["office", "retail", "medical", "gym", "restaurant", "residential", "airbnb", "school", "warehouse", "post-construction", "move-in-out", "deep-clean", "outside-cleaning", "carpet-cleaning"]'::jsonb
WHERE active_templates IS NULL 
OR active_templates = '[]'::jsonb
OR jsonb_array_length(active_templates) = 0;