# Release config for v1.43.0 — the new site's phases 1-4, and the API that
# says what it means.
#
# NO NEW MIGRATIONS. 079 is still the highest in migrations/, so this carries
# the same 045..079 range as v1.41.1 — a straight upgrade from an older tag
# still applies everything and the ledger skips what is already applied.
#
# Ships (v1.41.1..v1.43.0), the short version — CHANGELOG.md carries the
# full list:
#   #818-#840  phase 3/4 of the standalone app: player page, layout
#              primitives, workshop, per-round numbers, smart stats, session
#              detail and lineups, the rating with its arithmetic, theme
#              tokens that reach the browser, the ratchet counting the right
#              tree
#   #830  response models for 45 operations, measured before typed; Discord
#         snowflakes travel as strings (an 18-digit int loses its last digit
#         in every JS client); record queries refuse NULL rows structurally
#   #841-#846  nullable map names; the eight storytelling endpoints; the app
#              can say it crashed; rivalries head-to-head; the absence
#              vocabulary (Absent/Meta + the grey-note ratchet at 43);
#              adjusted-lifetime on the skill page
#   #848  four live endpoint bugs (a 500 on limit=-5, an ignored period,
#         two contracts for one handler, zeros nobody measured) and the
#         in-band status vocabulary that keeps them fixed
#
# ⚠️ 079 and website_app: proximity_reaction_metric is owned by website_app,
# so the migration file deliberately skips it. After the runner finishes,
# apply the one statement from the migration's header as website_app (or
# superuser). Fresh deploys are unaffected — tools/schema_postgresql.sql
# now carries all 30 indexes and is loaded with superuser rights.
# (Carried verbatim from v1.41.1: the v1.39.0 production host's ledger
# predates 079, so THIS is the config whose operator will actually need it —
# the first draft dropped the note while an inline comment still pointed at
# it, which the review caught.)
#
# Deploy note: prod remains FROZEN on v1.39.0 by the owner's decision
# (2026-08-28) — this config exists so the contract holds and the dev/VM
# upgrade path is ready, not as a deploy instruction.

# shellcheck shell=bash
# shellcheck disable=SC2034  # sourced by deploy_release.sh; nothing here runs
MIGRATIONS=(
  "045_drop_orphan_monitoring_tables.sql"
  "046_fix_proximity_round_id_exact_match.sql"
  "047_orphan_recovery_null_round_id.sql"
  "048_orphan_recovery_drift_tolerance.sql"
  "049_add_round_canonical_id.sql"
  "050_round_canonical_id_unique.sql"
  "051_add_audit_indexes.sql"
  "052_composite_indexes_proximity.sql"
  "053_add_weapon_stats_mv.sql"
  "054_add_storytelling_kis_shadow_audit.sql"
  "055_add_proximity_shot_fired.sql"
  "056_add_player_links_locale_twitch.sql"
  "057_add_rounds_is_valid.sql"
  "058_add_proximity_v7_tables.sql"
  "059_add_rounds_start_unix_index.sql"
  "060_add_kis_formula_version.sql"
  "061_prediction_shadow_v2.sql"
  "062_proximity_processed_files_capabilities.sql"
  "063_kis_gaming_session_id.sql"
  "064_backfill_kis_gaming_session_id.sql"
  "065_dedup_revive_weapon_accuracy.sql"
  "066_drop_orphan_monitoring_tables_tolerant.sql"
  "067_repair_lua_round_links.sql"
  "068_add_relinker_unlinked_indexes.sql"
  "069_add_shot_fired_relinker_index.sql"
  "070_uploads_expires_at.sql"
  "071_add_round_id_coverage_indexes.sql"
  "072_repair_miscancelled_complete_rounds.sql"
  "073_player_identity_links.sql"
  "074_seed_ownator_sick_leave.sql"
  "075_canonical_guid_function.sql"
  "076_uploads_poster.sql"
  "077_player_aim_summary.sql"
  "078_player_match_stats_view.sql"
  # 079 ships with this tag (PR #815): mismatch-leg indexes for the
  # relinker sweep. Indexes only — no data movement, IF NOT EXISTS, safe
  # to reapply. See the website_app note in the header.
  "079_mismatch_recent_indexes.sql"
)
FLAGS=(
  "TRUSTED_HOSTS=www.slomix.fyi,slomix.fyi,localhost,127.0.0.1"
)
RELEASE_NOTES="The new site reaches feature parity on phases 1-4: session detail, smart stats, the rating with its arithmetic, rivalries with the duel view, the eight storytelling endpoints, and the response models that promise only what the API measures. No schema changes — 045..079 unchanged from v1.41.1."
