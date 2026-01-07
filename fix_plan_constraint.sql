-- Fix plan column constraint and set default for existing users
ALTER TABLE users ALTER COLUMN plan DROP NOT NULL;
UPDATE users SET plan = 'free' WHERE plan IS NULL;
