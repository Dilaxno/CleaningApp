-- Add pending_email field to users table for email change tracking
ALTER TABLE users 
ADD COLUMN pending_email VARCHAR(255) NULL;

COMMENT ON COLUMN users.pending_email IS 'Temporary storage for new email during email change process before verification';
