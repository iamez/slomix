#!/bin/bash
# =============================================================================
# verify_post_deploy.sh — post-deploy smoke for the website.
#
# Run AFTER deploy_release.sh (and after migration 011, if applied) to confirm
# the modern React build shipped and the key API endpoints respond. Read-only.
#
# Usage:
#   BASE_URL=https://www.slomix.fyi ./scripts/verify_post_deploy.sh
#   ./scripts/verify_post_deploy.sh                 # defaults to localhost:7000
# =============================================================================
set -uo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:7000}"
fail=0
ok()   { echo "  ✅ $*"; }
bad()  { echo "  ❌ $*"; fail=1; }

echo "== verify_post_deploy against $BASE_URL =="

# 1) Modern React build is present (the #407 deploy-build / 'Offline' fix).
echo "[1] modern build assets"
for f in /static/modern/route-host.js /static/modern/route-host.css; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL$f" || echo 000)
  [ "$code" = "200" ] && ok "$f ($code)" || bad "$f ($code) — React routes would show 'Offline'"
done

# 2) Key API endpoints respond 200 with status ok.
echo "[2] API endpoints"
check_json() { # url, label
  local body; body=$(curl -s "$BASE_URL$1" || echo '')
  if echo "$body" | grep -q '"status"\s*:\s*"ok"' 2>/dev/null || echo "$body" | grep -q '"status":"ok"'; then
    ok "$2"
  else
    bad "$2 — $(echo "$body" | head -c 120)"
  fi
}
check_json "/api/stats/tonight" "Tonight live hub"
check_json "/api/bets/market/current" "betting market/current"
check_json "/api/proximity/prox-scores?range_days=30" "prox-scores (global)"
check_json "/api/sessions" "sessions list"
check_json "/api/skill/leaderboard" "skill leaderboard"

# 3) prox-scores scope actually filters (pick a real session_date if any).
echo "[3] prox-scores scope honored"
sd=$(curl -s "$BASE_URL/api/sessions" | grep -oE '"session_date":"[0-9-]+"' | head -1 | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}')
if [ -n "$sd" ]; then
  g=$(curl -s "$BASE_URL/api/proximity/prox-scores?range_days=3650" | grep -oE '"player_count":[0-9]+' | grep -oE '[0-9]+')
  s=$(curl -s "$BASE_URL/api/proximity/prox-scores?session_date=$sd" | grep -oE '"scoped":(true|false)')
  [ "$s" = '"scoped":true' ] && ok "scope echoed (session_date=$sd, global players=$g)" || bad "scope not echoed for $sd"
else
  echo "  (no session_date found to test scope — skip)"
fi

echo "== $([ $fail = 0 ] && echo 'ALL GREEN ✅' || echo 'FAILURES ❌ — investigate above') =="
exit $fail
