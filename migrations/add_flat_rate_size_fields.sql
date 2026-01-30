-- Add flat rate size-based pricing fields
-- These columns are referenced by the BusinessConfig model and quote calculation logic.
-- Safe to run multiple times.

ALTER TABLE business_configs
  ADD COLUMN IF NOT EXISTS flat_rate_small DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS flat_rate_medium DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS flat_rate_large DOUBLE PRECISION;
