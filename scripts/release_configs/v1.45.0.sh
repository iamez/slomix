# Release config for v1.45.0 — the time-fields repair, end to end.
#
# ONE NEW MIGRATION: 081 (time_dead_reconstructed flag on
# player_comprehensive_stats). Column only, no data movement in the
# migration itself; the rewrite it marks is done by
# scripts/repair_dead_time_reconstruction.py, run by hand with a verified
# backup manifest.
#
# Why the flag exists: pre-2026-03-24 rows carry a dead time the game
# server's Lua inflated ~2.2x (it re-added the running limbo time on every
# 5s tick). The repair derives the value from the engine's own alive%
# instead, keeps the old number in time_dead_minutes_original, and stamps
# the row so a consumer can ASK whether a number is a measurement rather
# than infer it from a date range.
#
# Ships (v1.44.0..v1.45.0), the short version — CHANGELOG.md carries the
# full list:
#   #885  the live import path writes time_played_percent again (it never
#         had: the column was in the mixin path only, so every row since
#         2026-04 read zero and alive_pct_drift could not fire)
#   #886  backfill for the zeros, from the archived capture files
#   #892  four plausibility rules for the time fields, incl. the one that
#         asks whether a field was WRITTEN (zero is in range)
#   #893  the dead-time smoke tests get assertions — they had none, and
#         printed "FAIL" while passing
#   #895  the aggregate rule class: a monthly statistic that MOVED, which
#         no per-row predicate can see
#   #900  arming replaces three acknowledgements — mute the past, not the
#         rule
#   this tag: migration 081 and the reconstruction itself
#
# Deploy note: prod remains FROZEN on v1.39.0 by the owner's decision
# (2026-08-28) — this config exists so the contract holds and the dev/VM
# upgrade path is ready, not as a deploy instruction.
#
# ⚠️ 080 and ownership: carried from v1.44.0 — the migration runner may
# connect as website_app, which does not own combat_engagement. Apply that
# one statement as etlegacy_user, then ANALYZE combat_engagement once.
#
# ⚠️ 079 and website_app: carried verbatim — the v1.39.0 production host's
# ledger predates 079; proximity_reaction_metric is owned by website_app,
# so apply the statement from 079's header as website_app.

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
  # 080 ships with this tag: the GIN index behind the player-profile
  # backbone (3.5 s warm -> 9 ms, measured; see the migration header).
  "080_combat_engagement_attackers_gin.sql"
  # 081 ships with this tag: the flag that marks a reconstructed dead time.
  # Adding a nullable column, no default, no rewrite of existing rows.
  "081_time_dead_reconstructed_flag.sql"
)
FLAGS=(
  "TRUSTED_HOSTS=www.slomix.fyi,slomix.fyi,localhost,127.0.0.1"
)
RELEASE_NOTES="The time-fields repair, end to end: the live import writes the engine's alive% again after five months of zeros, the archived capture files fill the gap, and the plausibility audit gains four per-row rules plus a new aggregate class that can see a monthly statistic move. One schema change: 081, the flag that marks a dead time as reconstructed rather than measured."
