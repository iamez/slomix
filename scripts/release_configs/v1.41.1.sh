# Release config for v1.41.1 — the season counts its days again.
#
# ⚠️ DRAFT FOR THE NEXT TAG. v1.41.0 is tagged but not yet deployed; this
# config exists so migration 079 is named by a release the moment it lands
# on main (the no-orphan-migration contract), and so a v1.41.1 deploy — the
# next tag release-please will cut from fix commits — has its config ready.
# If feature commits land before tagging and the version becomes v1.42.0,
# RENAME this file to match the tag; deploy_release.sh resolves the config
# strictly by tag name.
#
# ⛔ REGENERATE THE NOTES AT TAG TIME against `git log v1.41.0..main` —
# a list written from "what is here now" misses everything that arrives
# after, every time (see v1.41.0.sh, which learned this twice).
#
# Ships (v1.41.0..main, as of 2026-08-26):
#   #815  season summary: active_days no longer silently null (a pasted
#         player filter on a table with no players), and the relinker's
#         five-minute sweep drops from 10-22 s to ~0.1 s (migration 079 —
#         mismatch-leg indexes for all 29 detection tables; only
#         proximity_shot_fired had one).
#
# MIGRATIONS carries the same 045..078 range as v1.41.0 plus 079: a straight
# upgrade from an older tag still applies everything and the ledger skips
# what is already applied.
#
# ⚠️ 079 and website_app: proximity_reaction_metric is owned by website_app,
# so the migration file deliberately skips it. After the runner finishes,
# apply the one statement from the migration's header as website_app (or
# superuser). Fresh deploys are unaffected — tools/schema_postgresql.sql
# now carries all 30 indexes and is loaded with superuser rights.
#
# shellcheck shell=bash
# shellcheck disable=SC2034
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
RELEASE_NOTES="Maintenance release. The season summary counts its active days again (its query carried a player filter on a table with no players and failed silently inside a 200), and the background round-relinker sweep drops from tens of seconds to near-instant thanks to the mismatch-leg indexes it always needed. No behavioral changes to pages beyond the season card being truthful."
