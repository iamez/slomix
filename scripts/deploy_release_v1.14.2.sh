#!/usr/bin/env bash
# deploy_release_v1.14.2.sh — DEPRECATED thin wrapper.
#
# This script previously contained the full deploy logic. As of 2026-05-13 it
# is a one-line wrapper around scripts/deploy_release.sh, which is now the
# generic release runner. Per-release knobs (migrations to apply, .env flags)
# live in scripts/release_configs/v1.14.2.sh.
#
# Kept so existing bookmarks / runbook references / `git log` mentions of this
# filename still work. New releases should call scripts/deploy_release.sh
# directly:
#
#   SUDO_PASS=<pass> ./scripts/deploy_release.sh v1.14.3
#
# See scripts/release_configs/README.md for the new workflow.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/deploy_release.sh" v1.14.2 "$@"
