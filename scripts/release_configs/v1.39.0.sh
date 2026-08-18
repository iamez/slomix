# Release config for v1.39.0 — the 2026-08-18 mega-day: round-duration truth,
# live-page overhaul, supastats automation, PWC transparency.
# NO new migrations (code-only): carries the 045..077 range so straight
# upgrades from older tags still apply everything; the ledger skips applied ones.
#
# Ships (all merged 2026-08-18/19):
#   #769 PWC/MVP transparency (waa_bayes in payload, public formula endpoint)
#   #770 round durations from measurement (actual_time is the stopwatch
#        TARGET; demo-verified 213/213 within 2 s) + daily audit invariant
#   #771 supastats: reactions, map-points row, noise gate, !supacheck unblock
#   #772 live page: feed truth (newest-first paging, retention), one status
#        card, reducer hysteresis/linger, dev mirror (LIVE_UPSTREAM_URL)
#   #773 liveview tailer hardening (vps_scripts — deployed to the game
#        server separately on 2026-08-19; nothing to do on the web VM)
#   #774 timing debug queue/edit + stale-round guard
#   #775 player card endpoint + FUT-style card on the profile
#   #776 live ladder (per-player live K/D/DPM, alive dots, momentum timeline,
#        post-round flash box)
#
# POST-DEPLOY: none required. LIVE_UPSTREAM_URL and SUPASTATS_* stay
# dev-only by design — do NOT set them on prod.
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
RELEASE_NOTES="Round durations now come from measurement (demo-verified to the second) with a daily divergence invariant; the Live page gets a ground-up fix (feed truth, one status card) plus the Live Ladder, momentum timeline, post-round flash box and FUT-style player cards; supastats screenshots are auto-checked with channel reactions; Smart Stats MVP selection is fully transparent. Code-only: no new migrations."
