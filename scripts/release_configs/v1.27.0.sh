# Release config for v1.27.0 — startup migration-drift guard (#545) and the
# KIS gaming-session scoping that #543 depends on.
# shellcheck shell=bash
# shellcheck disable=SC2034
#
# This config was written after the fact (2026-07-26). v1.27.0 was tagged and
# released with NO config file, which is how migration 063 came to ship in a
# release that no deploy path could apply: deploy_release.sh sources
# scripts/release_configs/<TAG>.sh, and a missing file means the tag deploys
# code with an empty migration set. Production never took this release, so
# nothing was mis-deployed — but anyone checking out the v1.27.0 tag needs
# this list to be correct, and the CI contract test
# (tests/unit/test_release_config_contract.py) now fails the build if the
# current version has no config.
#
# In practice you almost certainly want v1.28.0.sh instead: production is on
# v1.25.0, and the v1.28.0 config carries the whole 045-065 delta plus the
# code that reads it.
#
# 063 adds storytelling_kill_impact.gaming_session_id. This release's code
# filters on that column, but does NOT backfill it — the backfill is 064, in
# v1.28.0. Deploying v1.27.0 on its own therefore leaves the columns's
# historical rows NULL and the panels that filter on it empty for older
# sessions. That is the known state of this release, not a config error.
MIGRATIONS=(
  "063_kis_gaming_session_id.sql"
)
FLAGS=(
  "TRUSTED_HOSTS=www.slomix.fyi,slomix.fyi,localhost,127.0.0.1"
)
RELEASE_NOTES="Startup migration-drift guard (prevents silent schema drift); KIS leaderboard and archetypes span the full gaming session."
