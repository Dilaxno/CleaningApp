-- Add photo proof fields to visits table
-- Photos are required for visit completion (min 2, max 10)

ALTER TABLE visits ADD COLUMN IF NOT EXISTS photo_proof_urls TEXT[];
ALTER TABLE visits ADD COLUMN IF NOT EXISTS photo_count INTEGER DEFAULT 0;
ALTER TABLE visits ADD COLUMN IF NOT EXISTS photos_uploaded_at TIMESTAMP;

-- Add index for filtering by photo completion
CREATE INDEX IF NOT EXISTS idx_visits_photo_count ON visits(photo_count);

-- Add comment
COMMENT ON COLUMN visits.photo_proof_urls IS 'Array of R2 URLs for service completion photos (min 2, max 10 required)';
COMMENT ON COLUMN visits.photo_count IS 'Number of photos uploaded for validation';
