# Release config for v1.38.0 — the "silent failures become sensors" release.
# NO new migrations: this tag is code-only (the 045..077 range is carried so
# straight upgrades from older tags still apply everything; the runner skips
# migrations already in the ledger).
#
# Ships: Lua 5.4 %d crash fix + garbage-origin guard (already hot-deployed to
# puran, this makes the repo the source of truth), the game-console sentinel
# (GAME_CONSOLE_LOG env, defaults to puran's etconsole.log), Lua CI gate,
# KIS coverage reconcile loop, Smart Stats restore, real session team scores,
# honest record book (accuracy/orphan-R2 gates + full-map records), the About
# rewrite, and the permanent data-plausibility audit.
#
# POST-DEPLOY (manual, once): the R2-cumulative data repair must be run on the
# production database — scripts/repair_inverted_r2_cumulative_rounds.py
# --heal-orphans --stamp-unhealable (dry-run first). It is evidence-gated and
# idempotent; see PR #758.
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
  # 071 ships with this tag (PR #645).
  # (copied from this one) ships it, and so the no-orphan-migration contract
  # test covers it. A checkout of the v1.30.1 TAG does not see this line.
  "071_add_round_id_coverage_indexes.sql"
  "072_repair_miscancelled_complete_rounds.sql"
  "073_player_identity_links.sql"
  "074_seed_ownator_sick_leave.sql"
  "075_canonical_guid_function.sql"
  "076_uploads_poster.sql"
  # 077 ships with this tag: player_aim_summary, the cached true-aim summary
  # (PR #746). Derived data only — safe to TRUNCATE, every row rebuilds itself
  # on the next profile read.
  "077_player_aim_summary.sql"
)
FLAGS=(
  "TRUSTED_HOSTS=www.slomix.fyi,slomix.fyi,localhost,127.0.0.1"
)
RELEASE_NOTES="Silent failures become sensors. Lua 5.4 %d/garbage-origin crash fixes (proximity data loss closed), game-console sentinel alerting Lua errors to Discord, Lua parse+semantics CI gate, KIS coverage reconcile loop (heals never-scored sessions), Smart Stats restored to its pre-redesign look with fixes kept, session lists show real BOX team scores, record book gains accuracy/orphan-R2 honesty gates plus full-map records, About rewritten as a project presentation, and a permanent data-plausibility audit (Data Trust pillar B). Code-only: no new migrations. Post-deploy: run the R2-cumulative repair script against prod (see config header)."
