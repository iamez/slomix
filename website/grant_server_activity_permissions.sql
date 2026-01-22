-- Grant SELECT permissions on server_status_history table to website_readonly user
-- Run this as PostgreSQL superuser: psql -U postgres -d et_stats -f grant_server_activity_permissions.sql

-- Grant SELECT on the server_status_history table
GRANT SELECT ON TABLE server_status_history TO website_readonly;

-- Grant SELECT on voice_status_history table (if it exists)
GRANT SELECT ON TABLE voice_status_history TO website_readonly;

-- Grant SELECT on voice_members table (if it exists)
GRANT SELECT ON TABLE voice_members TO website_readonly;

\echo ''
\echo '=================================================='
\echo 'Permissions granted successfully!'
\echo ''
\echo 'website_readonly can now SELECT from:'
\echo '  - server_status_history'
\echo '  - voice_status_history'
\echo '  - voice_members'
\echo '=================================================='
