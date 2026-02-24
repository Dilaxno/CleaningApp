-- Migration: Provider-Led Scope of Work Workflow
-- Refactors post-quote workflow so provider creates scope, client reviews/approves
-- Includes versioning, status tracking, frequency per task, PDF generation, and email reminders

-- ============================================================
-- 1. CREATE SCOPE OF WORK PROPOSALS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS scope_proposals (
    id SERIAL PRIMARY KEY,
    public_id VARCHAR(36) UNIQUE NOT NULL DEFAULT gen_random_uuid()::text,
    
    -- Relationships
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    contract_id INTEGER REFERENCES contracts(id) ON DELETE SET NULL,
    
    -- Version tracking
    version VARCHAR(10) NOT NULL DEFAULT 'v1.0',
    parent_proposal_id INTEGER REFERENCES scope_proposals(id) ON DELETE SET NULL,
    
    -- Status workflow: draft → sent → viewed → approved / revision_requested / expired
    status VARCHAR(50) NOT NULL DEFAULT 'draft',
    
    -- Scope data
    scope_data JSON NOT NULL, -- {serviceAreas: [{id, name, tasks: [{id, label, frequency, notes}]}]}
    provider_notes TEXT,
    
    -- PDF storage
    pdf_key VARCHAR(500), -- R2 key for generated PDF
    pdf_hash VARCHAR(64), -- SHA-256 hash for integrity
    pdf_generated_at TIMESTAMP,
    
    -- Client review tracking
    review_token VARCHAR(64) UNIQUE, -- Secure token for client review link
    review_deadline TIMESTAMP,
    sent_at TIMESTAMP,
    viewed_at TIMESTAMP,
    client_ip VARCHAR(45),
    client_user_agent VARCHAR(500),
    
    -- Client response
    client_response VARCHAR(50), -- approved / revision_requested
    client_response_at TIMESTAMP,
    client_revision_notes TEXT,
    
    -- Email tracking
    email_sent BOOLEAN DEFAULT false,
    reminder_24h_sent BOOLEAN DEFAULT false,
    reminder_47h_sent BOOLEAN DEFAULT false,
    expiry_notification_sent BOOLEAN DEFAULT false,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Indexes
    CONSTRAINT valid_status CHECK (status IN ('draft', 'sent', 'viewed', 'approved', 'revision_requested', 'expired')),
    CONSTRAINT valid_client_response CHECK (client_response IS NULL OR client_response IN ('approved', 'revision_requested'))
);

CREATE INDEX IF NOT EXISTS idx_scope_proposals_user_id ON scope_proposals(user_id);
CREATE INDEX IF NOT EXISTS idx_scope_proposals_client_id ON scope_proposals(client_id);
CREATE INDEX IF NOT EXISTS idx_scope_proposals_contract_id ON scope_proposals(contract_id);
CREATE INDEX IF NOT EXISTS idx_scope_proposals_public_id ON scope_proposals(public_id);
CREATE INDEX IF NOT EXISTS idx_scope_proposals_review_token ON scope_proposals(review_token);
CREATE INDEX IF NOT EXISTS idx_scope_proposals_status ON scope_proposals(status);
CREATE INDEX IF NOT EXISTS idx_scope_proposals_review_deadline ON scope_proposals(review_deadline);

-- ============================================================
-- 2. CREATE SCOPE PROPOSAL AUDIT LOG
-- ============================================================
CREATE TABLE IF NOT EXISTS scope_proposal_audit_log (
    id SERIAL PRIMARY KEY,
    proposal_id INTEGER NOT NULL REFERENCES scope_proposals(id) ON DELETE CASCADE,
    
    -- Action tracking
    action VARCHAR(100) NOT NULL, -- created, sent, viewed, approved, revision_requested, expired, resent, updated
    actor_type VARCHAR(50) NOT NULL, -- provider / client / system
    actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    
    -- Details
    old_status VARCHAR(50),
    new_status VARCHAR(50),
    notes TEXT,
    audit_metadata JSON, -- Additional context (IP, user agent, etc.)
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scope_audit_proposal_id ON scope_proposal_audit_log(proposal_id);
CREATE INDEX IF NOT EXISTS idx_scope_audit_created_at ON scope_proposal_audit_log(created_at);

-- ============================================================
-- 3. CREATE EMAIL REMINDERS QUEUE
-- ============================================================
CREATE TABLE IF NOT EXISTS scope_email_reminders (
    id SERIAL PRIMARY KEY,
    proposal_id INTEGER NOT NULL REFERENCES scope_proposals(id) ON DELETE CASCADE,
    
    -- Reminder type
    reminder_type VARCHAR(50) NOT NULL, -- 24h_reminder / 47h_reminder / expiry_notification
    
    -- Scheduling
    scheduled_for TIMESTAMP NOT NULL,
    sent_at TIMESTAMP,
    
    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'pending', -- pending / sent / failed / cancelled
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT valid_reminder_type CHECK (reminder_type IN ('24h_reminder', '47h_reminder', 'expiry_notification')),
    CONSTRAINT valid_reminder_status CHECK (status IN ('pending', 'sent', 'failed', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_scope_reminders_proposal_id ON scope_email_reminders(proposal_id);
CREATE INDEX IF NOT EXISTS idx_scope_reminders_scheduled_for ON scope_email_reminders(scheduled_for);
CREATE INDEX IF NOT EXISTS idx_scope_reminders_status ON scope_email_reminders(status);

-- ============================================================
-- 4. UPDATE CLIENTS TABLE
-- ============================================================
-- Add scope proposal tracking to clients
ALTER TABLE clients 
ADD COLUMN IF NOT EXISTS active_scope_proposal_id INTEGER REFERENCES scope_proposals(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS scope_approval_status VARCHAR(50) DEFAULT 'pending';

CREATE INDEX IF NOT EXISTS idx_clients_active_scope_proposal ON clients(active_scope_proposal_id);

-- ============================================================
-- 5. UPDATE CONTRACTS TABLE
-- ============================================================
-- Link approved scope to contract
ALTER TABLE contracts
ADD COLUMN IF NOT EXISTS approved_scope_proposal_id INTEGER REFERENCES scope_proposals(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_contracts_approved_scope_proposal ON contracts(approved_scope_proposal_id);

-- ============================================================
-- 6. CREATE FUNCTION TO AUTO-EXPIRE PROPOSALS
-- ============================================================
CREATE OR REPLACE FUNCTION expire_overdue_scope_proposals()
RETURNS void AS $$
BEGIN
    -- Mark proposals as expired if deadline passed and not yet approved
    UPDATE scope_proposals
    SET status = 'expired',
        updated_at = NOW()
    WHERE status = 'sent'
      AND review_deadline < NOW()
      AND client_response IS NULL;
      
    -- Log the expiration
    INSERT INTO scope_proposal_audit_log (proposal_id, action, actor_type, old_status, new_status, notes)
    SELECT 
        id,
        'expired',
        'system',
        'sent',
        'expired',
        'Proposal expired due to deadline passing'
    FROM scope_proposals
    WHERE status = 'expired'
      AND updated_at >= NOW() - INTERVAL '1 minute';
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 7. VERIFICATION QUERIES
-- ============================================================
-- Verify tables were created
SELECT 
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public'
  AND table_name IN ('scope_proposals', 'scope_proposal_audit_log', 'scope_email_reminders')
ORDER BY table_name;

-- Verify indexes
SELECT 
    tablename,
    indexname
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN ('scope_proposals', 'scope_proposal_audit_log', 'scope_email_reminders')
ORDER BY tablename, indexname;
