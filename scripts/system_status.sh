#!/usr/bin/env bash
# system_status.sh — the half of "is the chain running?" that the website
# cannot answer about itself.
#
# The page at #/system (GET /api/system/overview) reports what the running
# web process can see: captures, rounds, derived stats, its own database.
# Three things sit outside that process, and a status page that guesses at
# them is worse than one that stays quiet:
#
#   1. how far production has fallen behind main,
#   2. whether the Lua scripts on the game server match the repo,
#   3. the local service/port/ledger picture (delegated to health_check.sh).
#
# Read-only by construction: it only ever runs `git`, `ssh … sha256sum` and
# `ssh … git log`. It starts nothing, stops nothing and writes nothing outside
# its own temp dir. Every remote step degrades to a WARN when the host is
# unreachable, because "I could not look" must never print as "all good".
#
# Usage: scripts/system_status.sh [--skip-health] [--skip-remote]

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || exit 1

SKIP_HEALTH=0
SKIP_REMOTE=0
for arg in "$@"; do
    case "$arg" in
        --skip-health) SKIP_HEALTH=1 ;;
        --skip-remote) SKIP_REMOTE=1 ;;
        -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
        *) printf 'unknown argument: %s\n' "$arg" >&2; exit 2 ;;
    esac
done

OK_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

ok()   { printf 'OK    %s\n' "$1"; OK_COUNT=$((OK_COUNT + 1)); }
warn() { printf 'WARN  %s\n' "$1"; WARN_COUNT=$((WARN_COUNT + 1)); }
fail() { printf 'FAIL  %s\n' "$1"; FAIL_COUNT=$((FAIL_COUNT + 1)); }
section() { printf '\n-- %s --\n' "$1"; }

# Hosts are overridable: the game server moved once already, and hardcoding a
# host is how a check quietly starts testing the wrong machine.
PROD_SSH_HOST="${PROD_SSH_HOST:-slomix-vm}"
PROD_REPO_DIR="${PROD_REPO_DIR:-/opt/slomix}"
GAME_SSH_HOST="${GAME_SSH_HOST:-et@puran.hehe.si}"
GAME_SSH_PORT="${GAME_SSH_PORT:-48101}"
GAME_SSH_KEY="${GAME_SSH_KEY:-$HOME/.ssh/etlegacy_bot}"
GAME_LUA_DIR="${GAME_LUA_DIR:-etlegacy-v2.83.1-x86_64/legacy/luascripts}"
SSH_OPTS=(-o ConnectTimeout=10 -o BatchMode=yes)

# ---------------------------------------------------------------------------
# 1. Release drift: what is live vs what is on main.
# ---------------------------------------------------------------------------
section "release"

local_version="$(grep -m1 '^version = ' pyproject.toml | cut -d'"' -f2)"
# if/else, not `A && B || C`: with the short-circuit form a failing `ok` would
# ALSO run `warn`, reporting both outcomes for one check (Codacy SC2015).
if [ -n "$local_version" ]; then
    ok "repo version $local_version"
else
    warn "could not read version from pyproject.toml"
fi

# SC2029 below is intended: PROD_REPO_DIR / GAME_LUA_DIR are operator-set
# config values, and `ssh host cmd` joins its arguments into a single remote
# command string — expanding them here is the only way to pass them at all.
# shellcheck disable=SC2029
if git rev-parse --verify -q origin/main >/dev/null 2>&1; then
    main_sha="$(git rev-parse --short origin/main)"

    if [ "$SKIP_REMOTE" -eq 1 ]; then
        warn "production check skipped (--skip-remote)"
    elif prod_sha="$(ssh "${SSH_OPTS[@]}" "$PROD_SSH_HOST" \
            "cd '$PROD_REPO_DIR' 2>/dev/null && git rev-parse --short HEAD" 2>/dev/null)" \
        && [ -n "$prod_sha" ]; then
        if [ "$prod_sha" = "$main_sha" ]; then
            ok "production is on origin/main ($main_sha)"
        elif git merge-base --is-ancestor "$prod_sha" origin/main 2>/dev/null; then
            behind="$(git rev-list --count "$prod_sha..origin/main" 2>/dev/null || echo '?')"
            warn "production $prod_sha is $behind commit(s) behind origin/main ($main_sha)"
        else
            # Not an ancestor: either the commit is unknown here or production
            # carries something main does not. Both deserve a human.
            warn "production $prod_sha is not an ancestor of origin/main ($main_sha) — fetch or investigate"
        fi
    else
        warn "production unreachable over ssh ($PROD_SSH_HOST) — release drift unknown"
    fi
else
    warn "no origin/main ref locally — run git fetch first"
fi

open_release_pr="$(git log --oneline -1 origin/main 2>/dev/null | head -1)"
[ -n "$open_release_pr" ] && printf '      main tip: %s\n' "$open_release_pr"

# ---------------------------------------------------------------------------
# 2. Lua drift: the repo is only the truth if the game server runs the same
#    bytes. Compared by sha256, never copied in either direction — the live
#    copy has been ahead of the repo before (2026-08-07).
# ---------------------------------------------------------------------------
section "lua (game server)"

# repo path -> filename on the game server
LUA_PAIRS=(
    "vps_scripts/c0rnp0rn8.lua:c0rnp0rn8.lua"
    "vps_scripts/stats_discord_webhook.lua:stats_discord_webhook.lua"
    "vps_scripts/live_events.lua:live_events.lua"
    "proximity/lua/proximity_tracker.lua:proximity_tracker.lua"
)

# shellcheck disable=SC2029  # see the note above: client-side expansion is intended
if [ "$SKIP_REMOTE" -eq 1 ]; then
    warn "lua comparison skipped (--skip-remote)"
elif remote_sums="$(ssh "${SSH_OPTS[@]}" -i "$GAME_SSH_KEY" -p "$GAME_SSH_PORT" \
        "$GAME_SSH_HOST" "sha256sum '$GAME_LUA_DIR'/*.lua" 2>/dev/null)" \
    && [ -n "$remote_sums" ]; then
    for pair in "${LUA_PAIRS[@]}"; do
        repo_path="${pair%%:*}"
        remote_name="${pair##*:}"
        if [ ! -f "$repo_path" ]; then
            warn "$remote_name: not in the repo at $repo_path"
            continue
        fi
        repo_sum="$(sha256sum "$repo_path" | cut -d' ' -f1)"
        remote_sum="$(printf '%s\n' "$remote_sums" | awk -v f="$remote_name" '$2 ~ f"$" {print $1; exit}')"
        if [ -z "$remote_sum" ]; then
            warn "$remote_name: not present on the game server"
        elif [ "$repo_sum" = "$remote_sum" ]; then
            ok "$remote_name matches the repo"
        else
            warn "$remote_name DIFFERS from the repo (needs a three-way merge + full map load)"
        fi
    done
else
    warn "game server unreachable over ssh ($GAME_SSH_HOST) — lua drift unknown"
fi

# ---------------------------------------------------------------------------
# 3. Local host picture — delegated, never duplicated.
# ---------------------------------------------------------------------------
section "local host"

if [ "$SKIP_HEALTH" -eq 1 ]; then
    warn "health_check.sh skipped (--skip-health)"
elif [ -x scripts/health_check.sh ]; then
    health_out="$(scripts/health_check.sh 2>&1)"
    health_rc=$?
    printf '%s\n' "$health_out" | grep -E '^(FAIL|WARN)' || true
    health_fails="$(printf '%s\n' "$health_out" | grep -c '^FAIL' || true)"
    health_warns="$(printf '%s\n' "$health_out" | grep -c '^WARN' || true)"
    if [ "$health_rc" -eq 0 ] && [ "$health_fails" -eq 0 ]; then
        ok "health_check.sh clean ($health_warns warning(s))"
    else
        fail "health_check.sh reported $health_fails failure(s), $health_warns warning(s)"
    fi
else
    warn "scripts/health_check.sh not executable here"
fi

# ---------------------------------------------------------------------------
# 4. Pointer to the in-process half, so the two are never read in isolation.
# ---------------------------------------------------------------------------
section "pipeline"

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000}"
if overview="$(curl -fsS --max-time 15 "$API_BASE_URL/api/system/overview" 2>/dev/null)"; then
    # No f-strings and no backslashes on purpose: this program lives inside a
    # single-quoted shell string, where a backslash-escaped quote would reach
    # Python as a literal backslash and fail to parse.
    printf '%s' "$overview" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print("      overall: " + str(d.get("overall")))
for s in d.get("stages") or []:
    print("      [%-7s] %-14s %s" % (s.get("state", "?"), s.get("label", s.get("key")), s.get("summary", "")))
' || warn "overview response could not be parsed"
    ok "pipeline overview read from $API_BASE_URL"
else
    warn "pipeline overview unreachable at $API_BASE_URL — start the web service or set API_BASE_URL"
fi

printf '\n-- summary --\nOK %d   WARN %d   FAIL %d\n' "$OK_COUNT" "$WARN_COUNT" "$FAIL_COUNT"
[ "$FAIL_COUNT" -eq 0 ] || exit 1
exit 0
