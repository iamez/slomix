-- ============================================================================
-- Migration 006 DOWN: Discord Account Linking + Promotion Campaign Scheduler
-- ============================================================================
-- Revert in reverse dependency order.
-- ============================================================================

DROP TABLE IF EXISTS availability_promotion_send_logs;
DROP TABLE IF EXISTS availability_promotion_jobs;
DROP TABLE IF EXISTS availability_promotion_campaigns;
DROP TABLE IF EXISTS subscription_preferences;
DROP TABLE IF EXISTS account_link_audit_log;
DROP TABLE IF EXISTS user_player_links;
DROP TABLE IF EXISTS discord_accounts;
DROP TABLE IF EXISTS website_users;
