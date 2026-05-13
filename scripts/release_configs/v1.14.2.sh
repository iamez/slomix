# Release config for v1.14.2 — Audit bundle (PRs #245 + #247 + #251)
#
# Already deployed 2026-05-13. Kept as historical reference + template
# for future releases.
#
# Sourced by scripts/deploy_release.sh — defines:
#   MIGRATIONS=()    filenames under migrations/ to psql-apply in order
#   FLAGS=()         KV pairs to set/replace in /opt/slomix/.env (sudo'd)
#   RELEASE_NOTES    free-form description shown in deploy header

MIGRATIONS=(
  "052_composite_indexes_proximity.sql"
  "053_add_weapon_stats_mv.sql"
  "054_add_storytelling_kis_shadow_audit.sql"
)

FLAGS=(
  "USE_WEAPON_STATS_MV=true"
  "WEAPON_STATS_MV_REFRESH_SECONDS=300"
  # KIS_SHADOW_MODE_ENABLED intentionally NOT enabled on prod — see PR #251
)

RELEASE_NOTES="Audit bundle: A8 weapon_stats_mv + A5 KIS shadow (PRs #245/#247/#251)"
