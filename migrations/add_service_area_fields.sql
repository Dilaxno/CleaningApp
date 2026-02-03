-- Add service area configuration fields to business_configs table
-- This allows business owners to define their service areas during onboarding

ALTER TABLE business_configs 
ADD COLUMN service_area_enabled BOOLEAN DEFAULT FALSE NOT NULL,
ADD COLUMN service_area_type VARCHAR(20),
ADD COLUMN service_area_center_lat FLOAT,
ADD COLUMN service_area_center_lon FLOAT,
ADD COLUMN service_area_radius_miles FLOAT,
ADD COLUMN service_area_zipcodes JSON,
ADD COLUMN service_area_states JSON,
ADD COLUMN service_area_counties JSON,
ADD COLUMN service_area_neighborhoods JSON;

-- Add comments for documentation
COMMENT ON COLUMN business_configs.service_area_enabled IS 'Whether service area restrictions are enabled';
COMMENT ON COLUMN business_configs.service_area_type IS 'Type of service area: radius, zipcode, or custom';
COMMENT ON COLUMN business_configs.service_area_center_lat IS 'Center point latitude for radius-based service area';
COMMENT ON COLUMN business_configs.service_area_center_lon IS 'Center point longitude for radius-based service area';
COMMENT ON COLUMN business_configs.service_area_radius_miles IS 'Service radius in miles from center point';
COMMENT ON COLUMN business_configs.service_area_zipcodes IS 'JSON array of allowed ZIP codes';
COMMENT ON COLUMN business_configs.service_area_states IS 'JSON array of allowed states (2-letter codes)';
COMMENT ON COLUMN business_configs.service_area_counties IS 'JSON array of allowed counties in state:county format';
COMMENT ON COLUMN business_configs.service_area_neighborhoods IS 'JSON array of allowed neighborhood names';