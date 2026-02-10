-- Add scheduled time fields to clients table for Calendly integration
ALTER TABLE clients 
ADD COLUMN scheduled_start_time TIMESTAMP NULL,
ADD COLUMN scheduled_end_time TIMESTAMP NULL,
ADD COLUMN calendly_event_id VARCHAR(255) NULL,
ADD COLUMN scheduling_status VARCHAR(50) DEFAULT 'pending';

-- scheduling_status values:
-- 'pending' - No schedule selected yet
-- 'client_selected' - Client selected time via Calendly, awaiting provider confirmation
-- 'provider_requested_change' - Provider requested different time
-- 'confirmed' - Both parties confirmed the schedule

COMMENT ON COLUMN clients.scheduled_start_time IS 'Client preferred first cleaning start time from Calendly';
COMMENT ON COLUMN clients.scheduled_end_time IS 'Client preferred first cleaning end time from Calendly';
COMMENT ON COLUMN clients.calendly_event_id IS 'Calendly event ID for tracking';
COMMENT ON COLUMN clients.scheduling_status IS 'Status of scheduling: pending, client_selected, provider_requested_change, confirmed';
