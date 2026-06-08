-- migrations/056_add_player_links_locale_twitch.sql
-- Optional identity enrichment columns on player_links for the player profile:
--   - discord_locale: captured best-effort from the Discord OAuth /users/@me
--     payload at link time (it's a LANGUAGE locale e.g. "sl"/"en-US", NOT a
--     verified country — the profile labels it accordingly).
--   - twitch_login: a Twitch handle (admin/manual for now). The profile shows a
--     twitch.tv link; live status via the Helix API stays dormant until
--     TWITCH_CLIENT_ID/TWITCH_CLIENT_SECRET env are set (separate follow-up).
--
-- IDEMPOTENT (035-style): ADD COLUMN IF NOT EXISTS, re-runnable with no effect.
-- Purely additive — existing rows get NULLs, all current behaviour unchanged.

BEGIN;

ALTER TABLE public.player_links
    ADD COLUMN IF NOT EXISTS discord_locale character varying(16);

ALTER TABLE public.player_links
    ADD COLUMN IF NOT EXISTS twitch_login   character varying(64);

COMMIT;
