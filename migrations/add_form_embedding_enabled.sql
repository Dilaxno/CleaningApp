-- Migration: Add form_embedding_enabled column to business_configs table
-- Date: 2026-01-24
-- Description: Adds a boolean field to track whether business owners want iframe embedding

-- ============================================================================
-- UPGRADE - Add form_embedding_enabled column
-- ============================================================================

-- Step 1: Add column as nullable
ALTER TABLE business_configs
ADD COLUMN form_embedding_enabled BOOLEAN;

-- Step 2: Set default value for existing rows (FALSE for all existing businesses)
UPDATE business_configs
SET form_embedding_enabled = FALSE
WHERE form_embedding_enabled IS NULL;

-- Step 3: Make column non-nullable with default
ALTER TABLE business_configs
ALTER COLUMN form_embedding_enabled SET NOT NULL;

ALTER TABLE business_configs
ALTER COLUMN form_embedding_enabled SET DEFAULT FALSE;

-- Verification query (optional - run to verify)
-- SELECT id, business_name, form_embedding_enabled FROM business_configs LIMIT 5;

-- ============================================================================
-- ROLLBACK - Remove form_embedding_enabled column (if needed)
-- ============================================================================
-- Uncomment and run the following line to rollback this migration:
-- ALTER TABLE business_configs DROP COLUMN form_embedding_enabled;

-- ============================================================================
-- Migration completed successfully
-- ============================================================================
