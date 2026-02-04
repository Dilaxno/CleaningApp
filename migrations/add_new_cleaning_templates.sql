-- Migration to add new cleaning templates: outside-cleaning and carpet-cleaning
-- Run this after adding the new templates to the codebase

-- Update existing business configs that have all 12 previous templates
-- to include the new templates as well
UPDATE business_configs 
SET active_templates = '["office", "retail", "medical", "gym", "restaurant", "residential", "airbnb", "school", "warehouse", "post-construction", "move-in-out", "deep-clean", "outside-cleaning", "carpet-cleaning"]'
WHERE json_array_length(active_templates) = 12
AND json_extract(active_templates, '$') LIKE '%"office"%'
AND json_extract(active_templates, '$') LIKE '%"deep-clean"%'
AND json_extract(active_templates, '$') NOT LIKE '%"outside-cleaning"%'
AND json_extract(active_templates, '$') NOT LIKE '%"carpet-cleaning"%';

-- Update any configs that are empty or null (backward compatibility)
UPDATE business_configs 
SET active_templates = '["office", "retail", "medical", "gym", "restaurant", "residential", "airbnb", "school", "warehouse", "post-construction", "move-in-out", "deep-clean", "outside-cleaning", "carpet-cleaning"]'
WHERE active_templates IS NULL 
OR active_templates = '[]' 
OR json_array_length(active_templates) = 0;