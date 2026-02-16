-- Migration: Drop Calendly Integration Table
-- Date: 2026-02-16
-- Description: Remove Calendly integration support - drop calendly_integrations table

-- Drop the calendly_integrations table
DROP TABLE IF EXISTS calendly_integrations CASCADE;

-- Note: This migration removes all Calendly integration data
-- Make sure to backup the table before running if you need to preserve any data
