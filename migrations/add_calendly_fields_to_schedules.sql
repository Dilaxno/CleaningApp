-- Migration: Add Calendly integration fields to schedules table
-- Date: 2026-01-05

ALTER TABLE schedules 
ADD COLUMN IF NOT EXISTS calendly_event_uri VARCHAR(500),
ADD COLUMN IF NOT EXISTS calendly_event_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS calendly_invitee_uri VARCHAR(500),
ADD COLUMN IF NOT EXISTS calendly_booking_method VARCHAR(50);

-- Create index for faster lookups by Calendly event URI
CREATE INDEX IF NOT EXISTS idx_schedules_calendly_event_uri ON schedules(calendly_event_uri);

-- Add comment for documentation
COMMENT ON COLUMN schedules.calendly_event_uri IS 'Unique Calendly event URI for syncing';
COMMENT ON COLUMN schedules.calendly_event_id IS 'Calendly event UUID';
COMMENT ON COLUMN schedules.calendly_invitee_uri IS 'Calendly invitee URI for tracking';
COMMENT ON COLUMN schedules.calendly_booking_method IS 'How booking was created: client_selected, provider_created, synced';
