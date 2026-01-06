-- Fix Calendly token column sizes
-- Change access_token and refresh_token from VARCHAR(500) to TEXT
-- This allows storing longer OAuth tokens from Calendly

ALTER TABLE calendly_integrations 
  ALTER COLUMN access_token TYPE TEXT,
  ALTER COLUMN refresh_token TYPE TEXT;
