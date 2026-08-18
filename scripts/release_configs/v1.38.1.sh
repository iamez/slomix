# Release config for v1.38.1 — data-honesty patch on top of 1.38.0.
# NO new migrations (code + one idempotent data backfill script): carries the
# 045..077 range so straight upgrades from older tags still apply everything;
# the runner skips migrations already in the ledger.
#
# Ships: historical bot-round flag backfill tooling (#762 — the SQL was
# already applied to prod by hand on 2026-08-18), one joint validity gate for
# Hall of Fame / season leaders / recent matches (#764), and the stale-roster
# guard for box scoring plus scripts/rescore_session_results.py (#765).
#
# POST-DEPLOY (manual, once): re-score the poisoned 2026-08-11 session on the
# production database —
#   venv-bot/bin/python scripts/rescore_session_results.py 2026-08-11 --gsid 144
# (prints before/after as its own evidence; prod row currently 0:0 with
# OMNIBOT rosters, same incident as dev).
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
RELEASE_NOTES="Data-honesty patch. Historical bot-dominated rounds are flagged (is_bot_round/is_valid backfill), the Hall of Fame, season leaders and homepage recent matches apply the same validity gate as the record book (no more bot rows or double-counted cumulative rows in aggregates), and the box scorer gains a stale-roster guard so a leftover roster can never swallow a session's score again — with scripts/rescore_session_results.py as the one-command repair. Code-only: no new migrations. Post-deploy: re-score the 2026-08-11 session (see config header)."
