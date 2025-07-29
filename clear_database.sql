-- Disable foreign key checks temporarily
SET session_replication_role = 'replica';

-- Clear all tables that might reference users
DELETE FROM code_submissions;
DELETE FROM code_reviews;
DELETE FROM code_files;
DELETE FROM code_sessions;

-- Clear users table
DELETE FROM users;

-- Re-enable foreign key checks
SET session_replication_role = 'origin';

-- Confirmation message
SELECT 'All user data has been cleared successfully.' AS message; 