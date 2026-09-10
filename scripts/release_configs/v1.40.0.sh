# Release config for v1.40.0 — match totals from one place, uploads out of the
# work tree.
# ONE new migration (078): carries the 045..078 range so straight upgrades from
# older tags still apply everything; the ledger skips applied ones.
#
# Ships:
#   #779 data-plausibility audit measures round DURATION (shared/round_time)
#        instead of the stopwatch target; playtime repair tooling for the
#        ms/clock-fallback rows (both databases already repaired by hand)
#   #781 UPLOAD_STORAGE_ROOT no longer depends on the systemd WorkingDirectory;
#        production should point it outside the git tree
#   (this PR) player_match_stats view + retirement of the round_number = 0
#        player rows: the importer stops writing them, the six per-match record
#        queries read the view, ~270 lines of dead reader code removed
#
# POST-DEPLOY (owner, optional but recommended — see PR #781):
#   install -d -o slomix_web -g slomix -m 2750 /var/lib/slomix/uploads
#   rsync -a --remove-source-files /opt/slomix/website/data/uploads/ /var/lib/slomix/uploads/
#   set UPLOAD_STORAGE_ROOT=/var/lib/slomix/uploads in /opt/slomix/.env, restart web
# Until that move, nothing changes: the default names the same directory.
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
  # 078 ships with this tag: the player_match_stats VIEW (PR for the R0
  # retirement). Derived only — it holds no rows of its own, so applying it on
  # a host that already has it is a no-op CREATE OR REPLACE.
  "078_player_match_stats_view.sql"
)
FLAGS=(
  "TRUSTED_HOSTS=www.slomix.fyi,slomix.fyi,localhost,127.0.0.1"
)
RELEASE_NOTES="Match totals get a single, trustworthy home: the new player_match_stats view sums a match's two halves, replacing six hand-rolled aggregates behind the Hall of Fame and retiring the 2025 \"map summary\" rows that never worked. Community uploads move out of the git work tree, so a deploy checkout can no longer collide with user data. Plus the data-plausibility audit now measures round duration instead of reading the stopwatch target."
