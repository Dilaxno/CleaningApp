-- Add Google Calendar integration fields to schedules table
ALTER TABLE schedules ADD COLUMN IF NOT EXISTS google_calendar_event_id VARCHAR(500);
ALTER TABLE schedules ADD COLUMN IF NOT EXISTS location VARCHAR(500);

-- Create index for google_calendar_event_id
CREATE INDEX IF NOT EXISTS idx_schedules_google_calendar_event_id ON schedules(google_calendar_event_id);
