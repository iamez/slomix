# Release config for v1.28.0 — data-correctness audit remediation (PRs #546-#557).
# shellcheck shell=bash
# shellcheck disable=SC2034
#
# ─── WHY THIS CONFIG LISTS SO MANY MIGRATIONS ────────────────────────────────
#
# Production (slomix_vm) is still on v1.25.0. Two intervening releases never
# reached it:
#   * v1.26.0 shipped 060/061/062 and has a config, but was never deployed;
#   * v1.27.0 shipped 063 and NEVER HAD A CONFIG AT ALL.
# So a v1.25.0 -> v1.28.0 deploy must carry the whole delta, not just this
# release's own migrations.
#
# The runner is `apply_migrations.py --only <files>`, and its preflight
# REFUSES to run while any migration OUTSIDE the named set is un-applied.
# That makes an incomplete list worse than a long one: the deploy would abort
# after services stop. Every migration below is idempotent, and the runner
# skips those the target ledger already records, so listing the full range is
# safe and makes the deploy independent of prod's exact ledger state — which
# is known to have drifted (see 06_DEPLOY_OPS in the audit package).
#
# 045 is included deliberately. It was PENDING forever because `voice_members`
# is owned by `postgres` and `etlegacy_user` cannot DROP it — which, given the
# --only preflight above, silently blocked EVERY future targeted deploy. It
# now uses an ownership-tolerant DO block: it drops what the current role can
# drop and leaves anything else in place with a NOTICE instead of failing.
#
# 046-051 were applied to dev by hand and appear in no release config at all,
# so no target has ever received them through the deploy path. They are listed
# here for the same --only reason: if prod's ledger is missing any of them, an
# unlisted pending migration aborts the whole run.
#
#   PRE-DEPLOY RECONCILIATION (do this before the deploy, not during it):
#   050 creates its UNIQUE index without IF NOT EXISTS, so if the object is
#   already present on the target but has no ledger row — the exact drift this
#   audit found — the migration step fails and takes the transaction with it.
#   Do NOT edit the migration to fix this: it is already applied elsewhere and
#   editing it puts every target into checksum drift, which the startup guard
#   (#545) and `--validate` both fail on. Reconcile instead:
#
#     python scripts/apply_migrations.py --status        # what is really there
#     # for each migration whose objects already exist on the target:
#     python scripts/apply_migrations.py --mark 050_round_canonical_id_unique.sql
#     python scripts/apply_migrations.py --validate      # must exit 0
#
#   Then run the deploy, which will skip everything already marked.
#
# ─── SCHEMA THIS RELEASE'S CODE REQUIRES ─────────────────────────────────────
#
#   063 — storytelling_kill_impact.gaming_session_id column
#   064 — backfill of that column (87% of rows were NULL; the panels that
#         filter on it returned empty for every historical session)
#   065 — round identity + UNIQUE for proximity_revive /
#         proximity_weapon_accuracy, plus the dedup
#
# Deploying this release's CODE without 063-065 breaks the KIS gsid path and
# the parser's ON CONFLICT targets. Deploying the migrations without the code
# is harmless (all additive).
#
# ─── ORDER OF OPERATIONS (do not reorder) ────────────────────────────────────
#
#   1. backup (deploy_release.sh step 2/8 does this)
#   2. migrations  — this list
#   3. code + flags
#   4. restart services
#   5. THEN, and only then, the historical KIS recompute:
#        python scripts/backfill_kis_recompute.py            # dry-run first
#        python scripts/backfill_kis_recompute.py --apply \
#          --i-have-a-backup --expect-db <host:port/dbname> \
#          --residue-file /tmp/kis_residue.json
#      It must run AFTER the code, because it recomputes against the CURRENT
#      formula (kis-v5) and the CURRENT objective zones. Running it first
#      would rescore history with the formula being replaced.
#   6. verify: apply_migrations.py --validate, then check the version mix is
#      single-generation:
#        SELECT formula_version, COUNT(*) FROM storytelling_kill_impact
#        GROUP BY 1;
#
# ─── FLAGS ───────────────────────────────────────────────────────────────────
#
#   TRUSTED_HOSTS — REQUIRED. website/backend/main.py resolves it AT IMPORT
#   under the production posture (SESSION_HTTPS_ONLY=true) and raises without
#   it, so the web service will not start at all. Hostname-only entries (no
#   scheme, no port): the gate parses the Host header as hostname[:port] and
#   compares hostnames.
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
)
FLAGS=(
  "TRUSTED_HOSTS=www.slomix.fyi,slomix.fyi,localhost,127.0.0.1"
)
RELEASE_NOTES="Data-correctness audit remediation: KIS gsid backfill and scoped cache invalidation, KIS v5 (push multiplier retired after it measured at the round-winner baseline), Power Rating v2 (inverted dodge term and signal-free return-fire term removed), proximity serving-layer sweep with an explicit attribution contract, revive/weapon-accuracy round identity and dedup, objective zones for et_brewdog, and narrative baseline scoping."
