# Release config for v1.27.0 — startup migration-drift guard (#545) and the
# KIS gaming-session scoping that #543 depends on.
# shellcheck shell=bash
# shellcheck disable=SC2034
#
# ─── WRITTEN AFTER THE FACT ──────────────────────────────────────────────────
#
# v1.27.0 was tagged and released with NO config file, which is how migration
# 063 came to ship in a release that no deploy path could apply:
# deploy_release.sh sources scripts/release_configs/<TAG>.sh, and a missing
# file means the tag deploys code with an EMPTY migration set. Production
# never took this release, so nothing was mis-deployed — but checking out the
# v1.27.0 tag has to produce a config that actually works, and CI now fails
# the build when the current version has no config (see
# tests/unit/test_release_config_contract.py).
#
# ─── YOU ALMOST CERTAINLY WANT v1.28.0.sh INSTEAD ────────────────────────────
#
# Production is on v1.25.0. This release's code reads
# storytelling_kill_impact.gaming_session_id (063) but does NOT backfill it —
# the backfill is 064, in v1.28.0. Deploying v1.27.0 on its own therefore
# leaves the column ~87% NULL and every panel that filters on it empty for
# historical sessions. That is the known state of this release, not a config
# error. v1.28.0 carries 063 AND 064 together.
#
# ─── WHY THE LIST IS NOT JUST 063 ────────────────────────────────────────────
#
# `apply_migrations.py --only` refuses to run while ANY migration outside the
# named set is un-applied. A single-entry config would therefore abort on both
# realistic targets: one upgraded through the committed configs has never
# received 045-051 (no config ever shipped them), and the documented v1.25.0
# production target also still has 060-062 pending. So this lists the whole
# range that exists at this tag. All are idempotent and the runner skips what
# the ledger already records.
#
# 045 needs the same pre-deploy reconciliation documented at length in
# v1.28.0.sh: it DROPs a postgres-owned table, fails as etlegacy_user and sits
# PENDING, and must NOT be edited (a changed file puts targets that already
# recorded it into checksum drift that `--mark` cannot repair). Check with
# `--status`, then either apply it as postgres or `--mark` it. Note that 066,
# which retries that cleanup with an ownership-tolerant block, does not exist
# at this tag.
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
)
FLAGS=(
  "TRUSTED_HOSTS=www.slomix.fyi,slomix.fyi,localhost,127.0.0.1"
)
RELEASE_NOTES="Startup migration-drift guard (prevents silent schema drift); KIS leaderboard and archetypes span the full gaming session."
