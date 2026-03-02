#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"

cd "$ROOT"

printf "\n=== Slomix System Smoke Tests ===\n"

# 1) Pipeline parse + scoring (no DB writes)
"$PYTHON" scripts/smoke_pipeline.py

# 2) Endstats parse (if sample file exists)
if [[ -f "2026-01-12-224606-te_escape2-round-2-endstats.txt" ]]; then
  printf "\n=== Endstats Parser Smoke ===\n"
  "$PYTHON" bot/endstats_parser.py "2026-01-12-224606-te_escape2-round-2-endstats.txt" || true
else
  printf "\n=== Endstats Parser Smoke: SKIPPED (sample file missing) ===\n"
fi

# 3) Security and robustness tests
printf "\n=== Webhook Security Tests ===\n"
"$PYTHON" test_webhook_id_validation.py
"$PYTHON" test_webhook_security.py
"$PYTHON" test_rate_limiting.py

printf "\n=== Parser Robustness Tests ===\n"
"$PYTHON" test_parser_robustness.py

# 4) Optional DB-only checks (read-only)
if [[ "${SMOKE_DB:-0}" == "1" ]]; then
  printf "\n=== DB Consistency Smoke (read-only) ===\n"
  "$PYTHON" scripts/smoke_team_consistency.py
else
  printf "\n=== DB Consistency Smoke: SKIPPED (set SMOKE_DB=1 to enable) ===\n"
fi

printf "\n=== DONE ===\n"
