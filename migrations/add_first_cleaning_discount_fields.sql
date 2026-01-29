-- Adds first cleaning discount fields to business_configs
-- This discount can be configured as percent or fixed amount and is applied only to the first cleaning session.

ALTER TABLE business_configs
  ADD COLUMN IF NOT EXISTS first_cleaning_discount_type VARCHAR(20);

ALTER TABLE business_configs
  ADD COLUMN IF NOT EXISTS first_cleaning_discount_value DOUBLE PRECISION;
