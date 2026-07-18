# Release config for v1.26.0 — Codex audit remediation wave (PRs #508-#514).
# shellcheck shell=bash
# shellcheck disable=SC2034
#
# Migrations shipped by this release:
#   061 — prediction shadow program v2 columns (match_predictions)
#   062 — proximity_processed_files capability columns (tracker_version,
#         round_key, capabilities JSONB)
#
# Flags:
#   TRUSTED_HOSTS — REQUIRED by the AUD-005 host gate under the production
#   posture (SESSION_HTTPS_ONLY=true): the web app refuses to start without it.
#   HOSTNAME-ONLY entries (no scheme, no port) — the gate parses the Host
#   header as hostname[:port] and compares hostnames.
MIGRATIONS=(
  "061_prediction_shadow_v2.sql"
  "062_proximity_processed_files_capabilities.sql"
)
FLAGS=(
  "TRUSTED_HOSTS=www.slomix.fyi,slomix.fyi,localhost,127.0.0.1"
)
RELEASE_NOTES="Codex audit remediation: migration-ledger enforcement, host/path security (TRUSTED_HOSTS required), prediction shadow program, prox quality contract, ET Performance v3 shadow, CI hardening."
