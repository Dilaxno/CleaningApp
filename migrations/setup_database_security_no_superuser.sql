-- ============================================================================
-- PostgreSQL Security Setup for CleanEnroll (No Superuser Required)
-- ============================================================================
-- This migration implements database security features that don't require
-- superuser privileges:
-- - pgcrypto extension (if available)
-- - Row-Level Security (RLS) policies
-- - Security functions
-- - Monitoring views
-- - Performance indexes
--
-- Note: pgaudit and SSL configuration require superuser access
-- ============================================================================

-- ============================================================================
-- STEP 1: Install pgcrypto Extension (if available)
-- ============================================================================

-- Try to enable pgcrypto for encryption functions
-- This may fail if you don't have CREATE EXTENSION privilege
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS pgcrypto;
    RAISE NOTICE '✓ pgcrypto extension installed';
EXCEPTION
    WHEN insufficient_privilege THEN
        RAISE NOTICE '✗ pgcrypto requires superuser - skipping';
    WHEN OTHERS THEN
        RAISE NOTICE '✗ pgcrypto installation failed: %', SQLERRM;
END
$$;

-- ============================================================================
-- STEP 2: Create Security Functions
-- ============================================================================

-- Function to set current user context for RLS
CREATE OR REPLACE FUNCTION set_current_user_id(user_id INTEGER)
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_user_id', user_id::TEXT, FALSE);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get current user context
CREATE OR REPLACE FUNCTION get_current_user_id()
RETURNS INTEGER AS $$
BEGIN
    RETURN NULLIF(current_setting('app.current_user_id', TRUE), '')::INTEGER;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to hash sensitive data (for PII protection)
-- Uses built-in digest function if pgcrypto is available
CREATE OR REPLACE FUNCTION hash_pii(data TEXT)
RETURNS TEXT AS $$
BEGIN
    -- Try to use pgcrypto's digest function
    BEGIN
        RETURN encode(digest(data, 'sha256'), 'hex');
    EXCEPTION
        WHEN undefined_function THEN
            -- Fallback to md5 if pgcrypto not available
            RETURN md5(data);
    END;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================================
-- STEP 3: Enable Row-Level Security (RLS)
-- ============================================================================

-- Enable RLS on users table
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own data
DROP POLICY IF EXISTS user_isolation_policy ON users;
CREATE POLICY user_isolation_policy ON users
    USING (id = NULLIF(current_setting('app.current_user_id', TRUE), '')::INTEGER);

-- Enable RLS on clients table
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own clients
DROP POLICY IF EXISTS client_isolation_policy ON clients;
CREATE POLICY client_isolation_policy ON clients
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::INTEGER);

-- Enable RLS on contracts table
ALTER TABLE contracts ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own contracts
DROP POLICY IF EXISTS contract_isolation_policy ON contracts;
CREATE POLICY contract_isolation_policy ON contracts
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::INTEGER);

-- Enable RLS on schedules table
ALTER TABLE schedules ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own schedules
DROP POLICY IF EXISTS schedule_isolation_policy ON schedules;
CREATE POLICY schedule_isolation_policy ON schedules
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::INTEGER);

-- Enable RLS on business_configs table
ALTER TABLE business_configs ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own business config
DROP POLICY IF EXISTS business_config_isolation_policy ON business_configs;
CREATE POLICY business_config_isolation_policy ON business_configs
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::INTEGER);

-- Enable RLS on invoices table (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'invoices') THEN
        ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
        
        DROP POLICY IF EXISTS invoice_isolation_policy ON invoices;
        CREATE POLICY invoice_isolation_policy ON invoices
            USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::INTEGER);
        
        RAISE NOTICE '✓ RLS enabled on invoices table';
    END IF;
END
$$;

-- Enable RLS on visits table (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'visits') THEN
        ALTER TABLE visits ENABLE ROW LEVEL SECURITY;
        
        DROP POLICY IF EXISTS visit_isolation_policy ON visits;
        CREATE POLICY visit_isolation_policy ON visits
            USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::INTEGER);
        
        RAISE NOTICE '✓ RLS enabled on visits table';
    END IF;
END
$$;

-- Enable RLS on form_templates table (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'form_templates') THEN
        ALTER TABLE form_templates ENABLE ROW LEVEL SECURITY;
        
        DROP POLICY IF EXISTS form_template_isolation_policy ON form_templates;
        CREATE POLICY form_template_isolation_policy ON form_templates
            USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::INTEGER);
        
        RAISE NOTICE '✓ RLS enabled on form_templates table';
    END IF;
END
$$;

-- Enable RLS on quote_history table (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'quote_history') THEN
        ALTER TABLE quote_history ENABLE ROW LEVEL SECURITY;
        
        DROP POLICY IF EXISTS quote_history_isolation_policy ON quote_history;
        CREATE POLICY quote_history_isolation_policy ON quote_history
            USING (
                client_id IN (
                    SELECT id FROM clients 
                    WHERE user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::INTEGER
                )
            );
        
        RAISE NOTICE '✓ RLS enabled on quote_history table';
    END IF;
END
$$;

-- Enable RLS on scheduling_proposals table (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'scheduling_proposals') THEN
        ALTER TABLE scheduling_proposals ENABLE ROW LEVEL SECURITY;
        
        DROP POLICY IF EXISTS scheduling_proposal_isolation_policy ON scheduling_proposals;
        CREATE POLICY scheduling_proposal_isolation_policy ON scheduling_proposals
            USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::INTEGER);
        
        RAISE NOTICE '✓ RLS enabled on scheduling_proposals table';
    END IF;
END
$$;

-- Enable RLS on integration_requests table (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'integration_requests') THEN
        ALTER TABLE integration_requests ENABLE ROW LEVEL SECURITY;
        
        DROP POLICY IF EXISTS integration_request_isolation_policy ON integration_requests;
        CREATE POLICY integration_request_isolation_policy ON integration_requests
            USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::INTEGER);
        
        RAISE NOTICE '✓ RLS enabled on integration_requests table';
    END IF;
END
$$;

-- ============================================================================
-- STEP 4: Create Security Views for Monitoring
-- ============================================================================

-- View to monitor active connections
CREATE OR REPLACE VIEW security_active_connections AS
SELECT 
    pid,
    usename,
    application_name,
    client_addr,
    backend_start,
    state,
    query_start,
    LEFT(query, 100) as query_preview
FROM pg_stat_activity
WHERE datname = current_database()
ORDER BY backend_start DESC;

-- View to monitor table sizes
CREATE OR REPLACE VIEW security_table_sizes AS
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
    pg_total_relation_size(schemaname||'.'||tablename) AS size_bytes
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- View to monitor RLS policies
CREATE OR REPLACE VIEW security_rls_policies AS
SELECT 
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd,
    qual,
    with_check
FROM pg_policies
WHERE schemaname = 'public'
ORDER BY tablename, policyname;

-- View to check RLS status on all tables
CREATE OR REPLACE VIEW security_rls_status AS
SELECT 
    schemaname,
    tablename,
    rowsecurity as rls_enabled,
    (SELECT COUNT(*) FROM pg_policies p 
     WHERE p.schemaname = t.schemaname 
     AND p.tablename = t.tablename) as policy_count
FROM pg_tables t
WHERE schemaname = 'public'
ORDER BY tablename;

-- ============================================================================
-- STEP 5: Create Indexes for Security and Performance
-- ============================================================================

-- Index on users.firebase_uid for authentication lookups
CREATE INDEX IF NOT EXISTS idx_users_firebase_uid ON users(firebase_uid);

-- Index on users.email for login lookups
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Index on clients.user_id for RLS performance
CREATE INDEX IF NOT EXISTS idx_clients_user_id ON clients(user_id);

-- Index on clients.public_id for public access
CREATE INDEX IF NOT EXISTS idx_clients_public_id ON clients(public_id);

-- Index on contracts.user_id for RLS performance
CREATE INDEX IF NOT EXISTS idx_contracts_user_id ON contracts(user_id);

-- Index on contracts.client_id for joins
CREATE INDEX IF NOT EXISTS idx_contracts_client_id ON contracts(client_id);

-- Index on contracts.public_id for public access
CREATE INDEX IF NOT EXISTS idx_contracts_public_id ON contracts(public_id);

-- Index on schedules.user_id for RLS performance
CREATE INDEX IF NOT EXISTS idx_schedules_user_id ON schedules(user_id);

-- Index on schedules.client_id for joins
CREATE INDEX IF NOT EXISTS idx_schedules_client_id ON schedules(client_id);

-- Index on schedules.scheduled_date for date queries
CREATE INDEX IF NOT EXISTS idx_schedules_scheduled_date ON schedules(scheduled_date);

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify RLS is enabled
SELECT 
    '✓ RLS Status' as check_name,
    COUNT(*) as tables_with_rls
FROM pg_tables
WHERE schemaname = 'public' AND rowsecurity = true;

-- Verify policies exist
SELECT 
    '✓ RLS Policies' as check_name,
    COUNT(*) as total_policies
FROM pg_policies
WHERE schemaname = 'public';

-- Verify functions exist
SELECT 
    '✓ Security Functions' as check_name,
    COUNT(*) as function_count
FROM pg_proc 
WHERE proname IN ('set_current_user_id', 'get_current_user_id', 'hash_pii');

-- Verify views exist
SELECT 
    '✓ Security Views' as check_name,
    COUNT(*) as view_count
FROM pg_views 
WHERE schemaname = 'public' 
AND viewname LIKE 'security_%';

-- Show RLS status for all tables
SELECT * FROM security_rls_status;

-- ============================================================================
-- SUCCESS MESSAGE
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '============================================================================';
    RAISE NOTICE '✓ PostgreSQL Security Setup Complete!';
    RAISE NOTICE '============================================================================';
    RAISE NOTICE '';
    RAISE NOTICE 'Enabled Features:';
    RAISE NOTICE '  ✓ Row-Level Security (RLS) on all user tables';
    RAISE NOTICE '  ✓ Security functions (set_current_user_id, get_current_user_id, hash_pii)';
    RAISE NOTICE '  ✓ Security monitoring views';
    RAISE NOTICE '  ✓ Performance indexes';
    RAISE NOTICE '';
    RAISE NOTICE 'Next Steps:';
    RAISE NOTICE '  1. Update application code to set RLS context';
    RAISE NOTICE '  2. Test with different user contexts';
    RAISE NOTICE '  3. Monitor using security views';
    RAISE NOTICE '';
    RAISE NOTICE 'Features Requiring Superuser (Optional):';
    RAISE NOTICE '  - pgaudit extension (audit logging)';
    RAISE NOTICE '  - SSL configuration';
    RAISE NOTICE '  - Read-only and backup roles';
    RAISE NOTICE '';
    RAISE NOTICE '============================================================================';
END
$$;
