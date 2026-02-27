-- ================================================================
-- User Permission System Migration
-- ================================================================
-- Created: 2025-12-14
-- Purpose: Add user ID-based permission whitelist with 3-tier system
-- Security: Replaces channel-based auth with user ID verification
-- ================================================================

-- User permissions table
CREATE TABLE IF NOT EXISTS user_permissions (
    id SERIAL PRIMARY KEY,
    discord_id BIGINT NOT NULL UNIQUE,
    username VARCHAR(255),
    tier VARCHAR(50) NOT NULL CHECK (tier IN ('root', 'admin', 'moderator')),
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    added_by BIGINT,
    reason TEXT
);

-- Create indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_user_permissions_discord_id ON user_permissions(discord_id);
CREATE INDEX IF NOT EXISTS idx_user_permissions_tier ON user_permissions(tier);

-- Audit log for permission changes
CREATE TABLE IF NOT EXISTS permission_audit_log (
    id SERIAL PRIMARY KEY,
    target_discord_id BIGINT NOT NULL,
    action VARCHAR(50) NOT NULL CHECK (action IN ('add', 'remove', 'promote', 'demote')),
    old_tier VARCHAR(50),
    new_tier VARCHAR(50),
    changed_by BIGINT NOT NULL,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_target ON permission_audit_log(target_discord_id);
CREATE INDEX IF NOT EXISTS idx_audit_changed_by ON permission_audit_log(changed_by);

-- Insert root user (seareal) automatically
INSERT INTO user_permissions (discord_id, username, tier, added_by, reason)
VALUES (231165917604741121, 'seareal', 'root', 231165917604741121, 'System initialization - Bot root user')
ON CONFLICT (discord_id) DO NOTHING;

-- Verify tables created
SELECT 'Tables created successfully!' AS status;
SELECT * FROM user_permissions WHERE tier='root';
