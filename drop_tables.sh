#!/bin/bash
# Drop all PostgreSQL tables to recreate with correct schema

sudo -u postgres psql -d etlegacy <<EOF
DROP TABLE IF EXISTS weapon_comprehensive_stats CASCADE;
DROP TABLE IF EXISTS player_comprehensive_stats CASCADE;
DROP TABLE IF EXISTS processed_files CASCADE;
DROP TABLE IF EXISTS session_teams CASCADE;
DROP TABLE IF EXISTS player_links CASCADE;
DROP TABLE IF EXISTS player_aliases CASCADE;
DROP TABLE IF EXISTS rounds CASCADE;
EOF

echo "✅ All tables dropped successfully!"
