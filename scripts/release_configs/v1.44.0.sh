# Release config for v1.44.0 — phase 5's proximity telemetry page and the
# frame-health watcher for the game-server lag investigation.
#
# ONE NEW MIGRATION: 080 (GIN jsonb_path_ops on combat_engagement.attackers).
# The player-profile backbone spent 3.4 s of its 3.5 s warm latency in a
# jsonb EXISTS scan; the kill count is a containment test, and this index
# answers it in 9 ms. Predicate equivalence was proven on live data before
# the query rewrite (two active guids, row-identical counts).
#
# Ships (v1.43.0..v1.44.0), the short version — CHANGELOG.md carries the
# full list:
#   #861-#873  phase 5, the proximity page in six slices: scope discipline
#              (fail-closed, the first paint is never the unbounded window),
#              ten leaderboard tabs, instruments/competitive/objective
#              panels, round canvases (wave ledger, heatmap, journeys), the
#              engagement record with its two-form drill-down
#   #874/#876  tracker v6.12: the frame-health watcher whose gap/self pair
#              splits "our lua" from "host contention", proven live with an
#              induced stall; the etconsole collector
#   player profile (this tag): class-B routes profile/radar plus the
#              scored-family panels, the zero-form rendered as absence
#
# ⚠️ 080 and ownership: the migration runner may connect as website_app,
# which does not own combat_engagement — CREATE INDEX then fails with
# "must be owner". Apply the one statement as etlegacy_user (the owner) or
# superuser, then ANALYZE combat_engagement once (see the migration's
# header; done on dev 2026-09-02). The ledger records it either way.
#
# ⚠️ 079 and website_app: carried verbatim from v1.43.0 — the v1.39.0
# production host's ledger predates 079; proximity_reaction_metric is owned
# by website_app, so apply the statement from 079's header as website_app.
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
  # 080 ships with this tag: the GIN index behind the player-profile
  # backbone (3.5 s warm -> 9 ms, measured; see the migration header).
  "080_combat_engagement_attackers_gin.sql"
)
FLAGS=(
  "TRUSTED_HOSTS=www.slomix.fyi,slomix.fyi,localhost,127.0.0.1"
)
RELEASE_NOTES="Phase 5: the proximity telemetry page lands in six slices with fail-closed scoping and recorded-wire fixtures, plus the player profile. Tracker v6.12 adds the frame-health watcher that attributes server stalls to lua or host, proven live. One schema change: 080, the GIN index that takes the profile backbone from 3.5 s to 9 ms."
