-- ============================================================================
-- Migration 008: Website app grants for Availability/Promotions/Planning
-- ============================================================================
-- Ensures website_app can read/write availability + planning tables and that
-- future tables/sequences created by etlegacy_user inherit compatible grants.
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'website_app') THEN
        RAISE NOTICE 'Role website_app does not exist; skipping grant migration.';
        RETURN;
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public TO website_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
    availability_entries,
    availability_user_settings,
    availability_channel_links,
    availability_subscriptions,
    notifications_ledger,
    website_users,
    discord_accounts,
    player_links,
    user_player_links,
    account_link_audit_log,
    subscription_preferences,
    availability_promotion_campaigns,
    availability_promotion_jobs,
    availability_promotion_send_logs,
    planning_sessions,
    planning_team_names,
    planning_votes,
    planning_teams,
    planning_team_members
TO website_app;

GRANT USAGE, SELECT, UPDATE ON SEQUENCE
    availability_entries_id_seq,
    availability_channel_links_id_seq,
    availability_subscriptions_id_seq,
    notifications_ledger_id_seq,
    discord_accounts_id_seq,
    player_links_id_seq,
    account_link_audit_log_id_seq,
    availability_promotion_campaigns_id_seq,
    availability_promotion_jobs_id_seq,
    availability_promotion_send_logs_id_seq,
    planning_sessions_id_seq,
    planning_team_names_id_seq,
    planning_votes_id_seq,
    planning_teams_id_seq,
    planning_team_members_id_seq
TO website_app;

ALTER DEFAULT PRIVILEGES FOR ROLE etlegacy_user IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO website_app;

ALTER DEFAULT PRIVILEGES FOR ROLE etlegacy_user IN SCHEMA public
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO website_app;
