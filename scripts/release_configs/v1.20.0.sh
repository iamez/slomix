# Release config for v1.20.0 — deep-audit remediation + go-live + Faza C.
#
# Sourced by scripts/deploy_release.sh — defines:
#   MIGRATIONS=()    filenames under migrations/ to psql-apply in order
#   FLAGS=()         KV pairs to set/replace in /opt/slomix/.env (sudo'd)
#   RELEASE_NOTES    free-form description shown in deploy header
#
# NOTE: prod (slomix_vm) is at ~v1.18.0 (edd3f0f) + manual patches, so this jumps
# two minor versions. All migrations below are idempotent (IF NOT EXISTS), so
# re-applying an already-applied one is a safe no-op. The deploy also does a
# pre-migration DB backup (step 2/8) and has a rollback trap.
#
# ⚠️ WEBSITE MIGRATIONS ARE NOT APPLIED BY THIS SCRIPT — it only runs root
# migrations/ (psql -f migrations/$MIG). Verified 2026-07-02 (read-only prod
# query): prod has website/migrations 001-006 but is MISSING 007-011
# (planning_rooms, mvp_votes, weekly_challenges, season_awards, parimutuel_markets,
# team_a_guids). The v1.20.0 code uses those tables, so apply them to the prod DB
# manually as a separate step (backup first; mind multi-owner — 008 grants to
# website_app, some tables website_app-owned). See docs/GO_LIVE_CHECKLIST.
#
# shellcheck shell=bash
# shellcheck disable=SC2034

MIGRATIONS=(
  "055_add_proximity_shot_fired.sql"
  "056_add_player_links_locale_twitch.sql"
  "057_add_rounds_is_valid.sql"
  "058_add_proximity_v7_tables.sql"
  "059_add_rounds_start_unix_index.sql"
)

# No env-flag changes required. New opt-in features stay OFF by default:
#   - Betting auto-lifecycle: leave BETS_LIFECYCLE_SECONDS unset (=0). To enable
#     later, FIRST apply website/migrations/011_add_market_rosters.sql (roster
#     columns; not in the root migrations/ path above), then set
#     BETS_LIFECYCLE_SECONDS=120 (+ optional BETS_LIVE_WITHIN_SECONDS=5400).
FLAGS=()

RELEASE_NOTES="v1.20.0: deep-audit Wave1+2 remediation, CI security gate, betting auto-lifecycle (off by default), schema drift-guard, micro-perf. Consolidates prod's manual patches (aim-lock endpoint + JS cache-bust) into canonical main."
