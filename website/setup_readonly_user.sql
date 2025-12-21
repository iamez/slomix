-- ET:Legacy Stats Website - PostgreSQL Read-Only User Setup
-- Run this script as a PostgreSQL superuser to create a secure read-only user for the website
-- 
-- Usage: psql -U postgres -d et_stats -f setup_readonly_user.sql

-- Drop user if exists (comment out if you want to preserve existing user)
-- DROP USER IF EXISTS website_readonly;

-- Create the read-only user
CREATE USER website_readonly WITH PASSWORD 'WebsiteReadOnly2024!';

-- Grant connect permission to the database
GRANT CONNECT ON DATABASE et_stats TO website_readonly;

-- Grant usage on the public schema
GRANT USAGE ON SCHEMA public TO website_readonly;

-- Grant SELECT on all existing tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO website_readonly;

-- Grant SELECT on all existing sequences (for auto-increment columns)
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO website_readonly;

-- Set default privileges for future tables (so new tables are also readable)
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO website_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO website_readonly;

-- Verify the grants
\echo 'Verifying grants for website_readonly user...'
SELECT 
    grantor, 
    grantee, 
    table_schema, 
    table_name, 
    privilege_type
FROM information_schema.table_privileges 
WHERE grantee = 'website_readonly'
LIMIT 20;

\echo ''
\echo '=================================================='
\echo 'Read-only user "website_readonly" created successfully!'
\echo ''
\echo 'Update your website/.env with:'
\echo '  POSTGRES_USER=website_readonly'
\echo '  POSTGRES_PASSWORD=change_this_password'
\echo '=================================================='
