-- Add three-category time estimation system
-- Replaces single cleaning_time_per_sqft with job-size-specific estimates

-- Add new three-category time estimation fields to business_configs table
ALTER TABLE business_configs ADD COLUMN time_small_job REAL;
ALTER TABLE business_configs ADD COLUMN time_medium_job REAL;
ALTER TABLE business_configs ADD COLUMN time_large_job REAL;

-- Add comments for documentation
COMMENT ON COLUMN business_configs.time_small_job IS 'Hours for jobs under 1,000 sqft (apartments, small offices, condos)';
COMMENT ON COLUMN business_configs.time_medium_job IS 'Hours for jobs 1,500-2,500 sqft (medium homes, larger offices)';
COMMENT ON COLUMN business_configs.time_large_job IS 'Hours for jobs 2,500+ sqft (large homes, commercial spaces)';