-- Add pending contract fields to clients table
-- These fields store contract template data until client completes signing and scheduling

ALTER TABLE clients ADD COLUMN pending_contract_title VARCHAR(255);
ALTER TABLE clients ADD COLUMN pending_contract_description TEXT;
ALTER TABLE clients ADD COLUMN pending_contract_type VARCHAR(100);
ALTER TABLE clients ADD COLUMN pending_contract_start_date TIMESTAMP;
ALTER TABLE clients ADD COLUMN pending_contract_end_date TIMESTAMP;
ALTER TABLE clients ADD COLUMN pending_contract_total_value DECIMAL(10,2);
ALTER TABLE clients ADD COLUMN pending_contract_payment_terms VARCHAR(255);
ALTER TABLE clients ADD COLUMN pending_contract_terms_conditions TEXT;