-- Migration: Cleanup Calendly References from Schedules Table
-- Date: 2026-02-26
-- Description: Remove Calendly-related columns from schedules table since Calendly integration was removed

-- Remove Calendly fields from schedules table
ALTER TABLE schedules DROP COLUMN IF EXISTS calendly_event_uri CASCADE;
ALTER TABLE schedules DROP COLUMN IF EXISTS calendly_event_id CASCADE;
ALTER TABLE schedules DROP COLUMN IF EXISTS calendly_invitee_uri CASCADE;
ALTER TABLE schedules DROP COLUMN IF EXISTS calendly_booking_method CASCADE;

-- Note: This completes the Calendly integration removal
-- The calendly_integrations table was already dropped in drop_calendly_integrations.sql
-- The endpoint /public/calendly-status/{firebase_uid} is kept for backward compatibility but returns False
