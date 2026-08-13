# Release config for v1.37.0 — uploads modernisation.
# ADDS migration 076 (uploads.poster_path) for client-captured clip poster
# thumbnails, on top of the 073/074/075 already applied in v1.35.0/v1.36.0. Also
# carries the uploads video-lifecycle fix + modern player and the Data Trust /
# hero-KILLS work from v1.36.1 (code-only). The full 045+ range is kept so
# straight upgrades from older tags still apply everything.
# shellcheck shell=bash
# shellcheck disable=SC2034
#
# Production can still upgrade from v1.25.0. The runner skips migrations
# already present in the ledger and refuses when a pending migration is
# omitted from --only, so keep the complete 045+ range here.
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
)
FLAGS=(
  "TRUSTED_HOSTS=www.slomix.fyi,slomix.fyi,localhost,127.0.0.1"
)
RELEASE_NOTES="Uploads modernisation. Video stops on navigate-away + a modern player (keyboard/PiP/speed/focus-trap). Gallery poster thumbnails: adds migration 076 (uploads.poster_path) for client-captured clip posters shown lazily on cards. .avi/.mkv stay download-only (future .mp4 transcode)."