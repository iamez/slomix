#!/usr/bin/env bash
# health_check.sh — nine checks the 2026-07-29 maintenance sweep did by hand
# (root disk 96%, journald 3.2GB, ufw open to Anywhere, Samba share exposing
# the whole 1.7TB volume — none of it reported by anything, someone had to go
# looking). Prints OK/WARN/FAIL per line, exits non-zero if any check FAILs.
#
# Usage: scripts/health_check.sh [--json]   (--json currently unused, reserved)
#
# Run from the repo root. Read-only: never stops/restarts a service, never
# writes outside /tmp. Some checks are best-effort on a box that isn't the
# canonical VM layout (systemd unit names, mount points) — a WARN with an
# explanation beats a hard assumption.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || exit 1

# Private temp directory for command output capture, not predictable
# /tmp/health_check_*.out paths: when this script runs with elevated
# privileges, another local user could pre-create a predictable path as a
# symlink, and the privileged `>` redirect would truncate whatever it points
# at before this script ever writes anything (Codex P1 review on #580).
# mktemp -d creates it 0700, owner-only, so no other local user can even
# traverse into it.
HEALTH_CHECK_TMPDIR="$(mktemp -d -t health_check.XXXXXXXXXX)"
trap 'rm -rf "$HEALTH_CHECK_TMPDIR"' EXIT

FAIL_COUNT=0
WARN_COUNT=0
OK_COUNT=0

ok()   { printf 'OK    %s\n' "$1"; OK_COUNT=$((OK_COUNT + 1)); }
warn() { printf 'WARN  %s\n' "$1"; WARN_COUNT=$((WARN_COUNT + 1)); }
fail() { printf 'FAIL  %s\n' "$1"; FAIL_COUNT=$((FAIL_COUNT + 1)); }

section() { printf '\n-- %s --\n' "$1"; }

# ===========================================================================
# 1. Services active
# ===========================================================================
section "1. Services"
# Dev boxes and the canonical VM use different unit names for the same two
# services (etlegacy-bot/etlegacy-web here vs slomix-bot/slomix-web per
# CLAUDE.md) — check both spellings, WARN (not FAIL) if neither systemd unit
# exists at all, since some hosts run these under `screen` instead.
# Check EVERY candidate before deciding, not just the first installed one:
# a host that migrated from etlegacy-bot to slomix-bot (or vice versa) can
# have BOTH units installed with only one actually active — breaking on the
# first installed candidate can report FAIL on a stale inactive alias while
# the real, active service goes unchecked (Codex review on #580).
check_service_pair() {
    local label="$1"; shift
    local candidates=("$@")
    local any_installed=0
    for name in "${candidates[@]}"; do
        if systemctl list-unit-files "${name}.service" 2>/dev/null | grep -q "${name}.service"; then
            any_installed=1
            if systemctl is-active --quiet "$name"; then
                ok "$label ($name) active"
                return
            fi
        fi
    done
    if [[ "$any_installed" -eq 1 ]]; then
        fail "$label: installed unit(s) found (${candidates[*]}) but none active"
    else
        warn "$label: no matching systemd unit found (checked: ${candidates[*]}) — may run under screen/manual process"
    fi
}
check_service_pair "bot" etlegacy-bot slomix-bot
check_service_pair "web" etlegacy-web slomix-web
# postgresql is versioned (postgresql@14-main in dev, @17-main in production
# per CLAUDE.md) — discover whichever cluster unit is actually active rather
# than hardcoding one version (Copilot review on #580).
if systemctl is-active --quiet postgresql 2>/dev/null; then
    ok "postgresql active"
else
    pg_unit="$(systemctl list-units --all --plain --no-legend 'postgresql@*-main.service' 2>/dev/null \
        | awk '{print $1}' | head -1)"
    if [[ -n "$pg_unit" ]] && systemctl is-active --quiet "$pg_unit" 2>/dev/null; then
        ok "$pg_unit active"
    elif [[ -n "$pg_unit" ]]; then
        fail "$pg_unit not active: $(systemctl is-active "$pg_unit" 2>&1)"
    else
        warn "postgresql: no matching systemd unit found (postgresql or postgresql@*-main)"
    fi
fi
for svc in redis-server tailscaled fail2ban smbd; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        ok "$svc active"
    else
        status="$(systemctl is-active "$svc" 2>&1)"
        if [[ "$status" == "unknown" || "$status" == "could not"* ]]; then
            warn "$svc: no matching systemd unit found"
        else
            fail "$svc not active: $status"
        fi
    fi
done

# ===========================================================================
# 2. Ports — expected listening, warn on unexpected 0.0.0.0 exposure
# ===========================================================================
section "2. Ports"
if ! command -v ss >/dev/null 2>&1; then
    warn "ss not available, skipping port check"
else
    LISTENING="$(ss -Hltnp 2>/dev/null || ss -Hltn 2>/dev/null)"
    check_port_open() {
        local port="$1" label="$2"
        if echo "$LISTENING" | grep -q ":${port} "; then
            ok "port $port ($label) listening"
        else
            warn "port $port ($label) not listening"
        fi
    }
    check_port_open 5432 postgres
    check_port_open 6379 redis
    # Website binds 7000 on the canonical VM (slomix_vm_setup.sh), but dev
    # boxes commonly run uvicorn on 8000 directly — check both, don't fail
    # on whichever one isn't this box's convention.
    if echo "$LISTENING" | grep -qE ":(7000|8000) "; then
        ok "website port (7000 or 8000) listening"
    else
        warn "website port: neither 7000 nor 8000 listening"
    fi

    # Every listener bound to all interfaces (0.0.0.0/::), including the
    # website's own port, is surfaced as a WARN for a human to eyeball —
    # this project's own history includes ufw rules accidentally left open
    # to Anywhere, and the website itself binding 0.0.0.0 instead of
    # 127.0.0.1 would be exactly the kind of thing worth catching here, not
    # excluding (Copilot review on #580: the comment previously implied an
    # exclusion the code never implemented).
    EXPOSED="$(echo "$LISTENING" | grep -E '0\.0\.0\.0:|(\*|\[::\]):' || true)"
    if [[ -n "$EXPOSED" ]]; then
        while IFS= read -r line; do
            [[ -z "$line" ]] && continue
            warn "bound to all interfaces: $line"
        done <<< "$EXPOSED"
    else
        ok "nothing unexpected bound to 0.0.0.0/::"
    fi
fi

# ===========================================================================
# 3. Connectivity — postgres, redis, puran, /api/* probe
# ===========================================================================
section "3. Connectivity"
if command -v pg_isready >/dev/null 2>&1; then
    if pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1; then
        ok "postgres reachable (127.0.0.1:5432)"
    else
        fail "postgres not reachable (127.0.0.1:5432)"
    fi
else
    warn "pg_isready not available, skipping postgres connectivity check"
fi

if command -v redis-cli >/dev/null 2>&1; then
    if redis-cli -h 127.0.0.1 -p 6379 ping 2>/dev/null | grep -q PONG; then
        ok "redis reachable (127.0.0.1:6379)"
    else
        fail "redis not reachable (127.0.0.1:6379)"
    fi
else
    warn "redis-cli not available, skipping redis connectivity check"
fi

if command -v nc >/dev/null 2>&1; then
    if nc -z -w3 puran.hehe.si 48101 2>/dev/null; then
        ok "puran.hehe.si:48101 reachable"
    else
        warn "puran.hehe.si:48101 not reachable (game server may be offline, or network path blocked)"
    fi
else
    warn "nc not available, skipping puran connectivity check"
fi

if command -v curl >/dev/null 2>&1; then
    # If NEITHER base answers at all (both 000), that's a full API outage,
    # not "wrong port for this box" — must FAIL, not silently skip (Codex
    # review on #580: a screen/manual-process setup, or a systemd unit that
    # stays active but stops listening, would otherwise report nothing
    # wrong here at all).
    any_base_answered=0
    for path in /health /api/status; do
        for base in "http://127.0.0.1:8000" "http://127.0.0.1:7000"; do
            # curl's -w already prints "000" on connection failure regardless
            # of curl's own exit code, so no `|| echo` fallback here — one
            # would double up into "000000" when curl also exits non-zero.
            code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "${base}${path}" 2>/dev/null)"
            code="${code:0:3}"
            if [[ "$code" =~ ^(200|304)$ ]]; then
                ok "${base}${path} -> $code"
                any_base_answered=1
            elif [[ "$code" == "000" || -z "$code" ]]; then
                : # this base isn't the one running on this box — silent skip
            else
                fail "${base}${path} -> $code"
                any_base_answered=1
            fi
        done
    done
    if [[ "$any_base_answered" -eq 0 ]]; then
        fail "no response from either API base (127.0.0.1:8000 or :7000) on /health or /api/status — full outage or wrong ports"
    fi
else
    warn "curl not available, skipping API probe"
fi

# ===========================================================================
# 4. Disk — every mount, not just one. 85% warn, 92% fail.
# ===========================================================================
section "4. Disk"
DISK_WARN_PCT="${HEALTH_CHECK_DISK_WARN_PCT:-85}"
DISK_FAIL_PCT="${HEALTH_CHECK_DISK_FAIL_PCT:-92}"
while read -r line; do
    pct="$(echo "$line" | awk '{print $5}' | tr -d '%')"
    mount="$(echo "$line" | awk '{print $6}')"
    [[ -z "$pct" ]] && continue
    if [[ "$pct" -ge "$DISK_FAIL_PCT" ]]; then
        fail "disk $mount at ${pct}% (>= ${DISK_FAIL_PCT}%)"
    elif [[ "$pct" -ge "$DISK_WARN_PCT" ]]; then
        warn "disk $mount at ${pct}% (>= ${DISK_WARN_PCT}%)"
    else
        ok "disk $mount at ${pct}%"
    fi
done < <(df -hP --local 2>/dev/null | tail -n +2)

# ===========================================================================
# 5. Logs — permissions, executable bit, age
# ===========================================================================
section "5. Logs"
if [[ -d logs ]]; then
    STALE_FOUND=0
    while IFS= read -r -d '' f; do
        perms="$(stat -c '%a' "$f" 2>/dev/null || stat -f '%Lp' "$f" 2>/dev/null)"
        # client_errors.log is deliberately owner-only (0600, single writer -
        # see website/backend/logging_config.py's OwnerOnlyRotatingFileHandler);
        # every other *.log file needs group-write (0660) for bot/web
        # cross-process access. Reject ANY other mode, not just the one
        # specific 0640 value previously seen - 0644/0666 would silently
        # pass the old check despite exposing logs or permitting unintended
        # writes (Codex P2 review on #580).
        if [[ "$(basename "$f")" == "client_errors.log" ]]; then
            expected="600"
        else
            expected="660"
        fi
        if [[ "$perms" != "$expected" ]]; then
            warn "log permission 0$perms (expected 0$expected): $f"
        fi
        if [[ -x "$f" ]]; then
            warn "log has executable bit set (likely accidental): $f"
        fi
        age_secs=$(( $(date +%s) - $(stat -c '%Y' "$f" 2>/dev/null || stat -f '%m' "$f" 2>/dev/null || echo 0) ))
        if [[ "$age_secs" -gt $((7 * 86400)) ]]; then
            STALE_FOUND=1
        fi
    done < <(find logs -maxdepth 1 -type f -name '*.log' -print0 2>/dev/null)
    LOG_COUNT=$(find logs -maxdepth 1 -type f -name '*.log' 2>/dev/null | wc -l)
    LOG_SIZE=$(du -sh logs 2>/dev/null | cut -f1)
    ok "logs/ has $LOG_COUNT *.log files, $LOG_SIZE total"
    if [[ "$STALE_FOUND" -eq 1 ]]; then
        warn "at least one *.log file hasn't been written to in 7+ days (may be fine if that service is idle)"
    fi
else
    warn "logs/ directory not found"
fi

# ===========================================================================
# 6. ERROR/CRITICAL counts, last 24h
# ===========================================================================
section "6. Error rate (24h)"
if [[ -f logs/errors.log ]]; then
    CUTOFF="$(date -d '24 hours ago' '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date -v-24H '+%Y-%m-%d %H:%M:%S' 2>/dev/null)"
    if [[ -n "$CUTOFF" ]]; then
        # Rotated backups too (errors.log.1 .. .N, RotatingFileHandler on both
        # bot and website) — right after a high-volume error burst triggers
        # rotation, most/all of the last 24h can be in .1 while the fresh
        # active file looks empty (Codex review on #580). Both the
        # pipe-delimited plain-text format (StandardFormatter/DetailedFormatter,
        # default) and the JSON format (LOG_FORMAT_JSON=true) are supported —
        # JSON records have no "| ERROR |" substring at all.
        COUNT=0
        for f in logs/errors.log logs/errors.log.*; do
            [[ -f "$f" ]] || continue
            plain=$(awk -v cutoff="$CUTOFF" '$0 >= cutoff' "$f" 2>/dev/null | grep -cE '\| (ERROR|CRITICAL) *\|' || true)
            # NOTE: the JSON count below is whole-file, not 24h-scoped — JSON
            # records start with "{", not a sortable timestamp, so the same
            # awk cutoff trick doesn't apply without a JSON-aware timestamp
            # parser (jq). Acceptable for now: LOG_FORMAT_JSON is off by
            # default, and an inflated (whole-file) count only ever produces
            # a false WARN/FAIL, never a false OK.
            json=$(grep -cE '"level"[[:space:]]*:[[:space:]]*"(ERROR|CRITICAL)"' "$f" 2>/dev/null || true)
            COUNT=$((COUNT + ${plain:-0} + ${json:-0}))
        done
        if [[ "$COUNT" -gt 100 ]]; then
            fail "$COUNT ERROR/CRITICAL lines in errors.log(+rotations) in the last 24h (threshold 100)"
        elif [[ "$COUNT" -gt 20 ]]; then
            warn "$COUNT ERROR/CRITICAL lines in errors.log(+rotations) in the last 24h (threshold 20)"
        else
            ok "$COUNT ERROR/CRITICAL lines in errors.log(+rotations) in the last 24h"
        fi
    else
        warn "could not compute 24h cutoff (date command mismatch), skipping error-rate check"
    fi
else
    warn "logs/errors.log not found"
fi

# ===========================================================================
# 7. Migration validation
# ===========================================================================
# Canonical VM (slomix_vm_setup.sh) provisions venv-bot/venv-web at the repo
# root; dev boxes commonly use venv/ + website/venv instead. Check the
# canonical names FIRST — falling back to a bare `venv` on a canonical VM
# silently picks a dependency-less system interpreter and produces false
# FAILs on both this section and the next (Codex P1 review on #580).
find_python() {
    local override="$1" candidate
    if [[ -n "$override" && -x "$override" ]]; then
        echo "$override"; return
    fi
    for candidate in venv-bot/bin/python venv/bin/python; do
        if [[ -x "$candidate" ]]; then echo "$candidate"; return; fi
    done
    echo "python3"
}

section "7. Migrations"
if [[ -f scripts/apply_migrations.py ]]; then
    PYTHON_BIN="$(find_python "${HEALTH_CHECK_PYTHON:-}")"
    OUT="$HEALTH_CHECK_TMPDIR/migrations.out"
    if "$PYTHON_BIN" scripts/apply_migrations.py --validate >"$OUT" 2>&1; then
        ok "apply_migrations.py --validate: clean"
    else
        fail "apply_migrations.py --validate: $(tail -3 "$OUT" | tr '\n' ' ')"
    fi
else
    warn "scripts/apply_migrations.py not found, skipping"
fi

# ===========================================================================
# 8. Environment drift, both venvs
# ===========================================================================
section "8. Environment drift"
if [[ -f scripts/check_env.py ]]; then
    BOT_PY="$(find_python "" )"
    if [[ -x "venv-bot/bin/python" || -x "venv/bin/python" ]]; then
        OUT="$HEALTH_CHECK_TMPDIR/env_bot.out"
        if "$BOT_PY" scripts/check_env.py --requirements requirements.txt >"$OUT" 2>&1; then
            ok "check_env.py clean for $BOT_PY (bot)"
        else
            warn "check_env.py drift for $BOT_PY (bot): $(tail -3 "$OUT" | tr '\n' ' ')"
        fi
    else
        warn "no bot venv found (checked venv-bot/, venv/), skipping bot env check"
    fi
    WEB_PY=""
    for candidate in venv-web/bin/python website/venv/bin/python; do
        if [[ -x "$candidate" ]]; then WEB_PY="$candidate"; break; fi
    done
    if [[ -n "$WEB_PY" ]]; then
        OUT="$HEALTH_CHECK_TMPDIR/env_web.out"
        if "$WEB_PY" scripts/check_env.py --requirements website/requirements.txt >"$OUT" 2>&1; then
            ok "check_env.py clean for $WEB_PY (web)"
        else
            warn "check_env.py drift for $WEB_PY (web): $(tail -3 "$OUT" | tr '\n' ' ')"
        fi
    else
        warn "no web venv found (checked venv-web/, website/venv/), skipping web env check"
    fi
else
    warn "scripts/check_env.py not found, skipping"
fi

# ===========================================================================
# 9. Round-linkage anomalies / orphan counts
# ===========================================================================
section "9. Round linkage"
if [[ -f scripts/check_round_linkage_anomalies.py ]]; then
    PYTHON_BIN="$(find_python "${HEALTH_CHECK_PYTHON:-}")"
    OUT="$HEALTH_CHECK_TMPDIR/linkage.out"
    # --fail-on-breach: without it the script exits 0 even when its own
    # result contains threshold breaches, so this check would report OK on a
    # database that's actually over threshold (Codex P1 review on #580).
    if "$PYTHON_BIN" scripts/check_round_linkage_anomalies.py --fail-on-breach >"$OUT" 2>&1; then
        ok "round-linkage anomalies within thresholds"
    else
        fail "round-linkage anomalies over threshold: $(tail -5 "$OUT" | tr '\n' ' ')"
    fi
elif command -v curl >/dev/null 2>&1; then
    for base in "http://127.0.0.1:8000" "http://127.0.0.1:7000"; do
        code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "${base}/diagnostics/round-linkage" 2>/dev/null)"
        code="${code:0:3}"
        if [[ "$code" == "200" ]]; then
            ok "GET ${base}/diagnostics/round-linkage -> 200"
            break
        fi
    done
else
    warn "scripts/check_round_linkage_anomalies.py not found and curl unavailable, skipping"
fi

# ===========================================================================
# Summary
# ===========================================================================
section "Summary"
printf 'OK=%d WARN=%d FAIL=%d\n' "$OK_COUNT" "$WARN_COUNT" "$FAIL_COUNT"
if [[ "$FAIL_COUNT" -gt 0 ]]; then
    exit 1
fi
exit 0
