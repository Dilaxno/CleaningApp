-- Add approval workflow fields to schedules table
ALTER TABLE schedules 
ADD COLUMN approval_status VARCHAR(50) DEFAULT 'pending',
ADD COLUMN proposed_date TIMESTAMP NULL,
ADD COLUMN proposed_start_time VARCHAR(10) NULL,
ADD COLUMN proposed_end_time VARCHAR(10) NULL;

-- Update existing schedules to be accepted by default (backward compatibility)
UPDATE schedules SET approval_status = 'accepted' WHERE approval_status IS NULL;

-- Add index for faster queries on approval_status
CREATE INDEX idx_schedules_approval_status ON schedules(approval_status);
