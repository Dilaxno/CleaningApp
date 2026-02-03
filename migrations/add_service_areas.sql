-- Add service area configuration to business_configs table
ALTER TABLE business_configs 
ADD COLUMN service_areas JSON DEFAULT '[]';

-- Add comment for documentation
COMMENT ON COLUMN business_configs.service_areas IS 'JSON array of service areas with states, counties, and neighborhoods. Format: [{"type": "state", "value": "CA", "name": "California"}, {"type": "county", "value": "Los Angeles County", "state": "CA"}, {"type": "neighborhood", "value": "Beverly Hills", "state": "CA", "county": "Los Angeles County"}]';