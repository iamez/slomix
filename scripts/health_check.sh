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
cd "$REPO_ROOT"

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
check_service_pair() {
    local label="$1"; shift
    local candidates=("$@")
    local found=0
    for name in "${candidates[@]}"; do
        if systemctl list-unit-files "${name}.service" >/dev/null 2>&1 \
            && systemctl list-unit-files "${name}.service" 2>/dev/null | grep -q "${name}.service"; then
            found=1
            if systemctl is-active --quiet "$name"; then
                ok "$label ($name) active"
            else
                fail "$label ($name) not active: $(systemctl is-active "$name" 2>&1)"
            fi
            break
        fi
    done
    if [[ "$found" -eq 0 ]]; then
        warn "$label: no matching systemd unit found (checked: ${candidates[*]}) — may run under screen/manual process"
    fi
}
check_service_pair "bot" etlegacy-bot slomix-bot
check_service_pair "web" etlegacy-web slomix-web
for svc in postgresql redis-server tailscaled fail2ban smbd; do
    # postgresql on this project is often versioned (postgresql@14-main) —
    # try the bare name first, then the most common versioned form.
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        ok "$svc active"
    elif systemctl is-active --quiet "postgresql@14-main" 2>/dev/null && [[ "$svc" == "postgresql" ]]; then
        ok "postgresql@14-main active"
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

    # Anything bound to 0.0.0.0/:: other than the website's own port is worth
    # a second look — this project's own history includes ufw rules
    # accidentally left open to Anywhere.
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
    for path in /health /api/status; do
        for base in "http://127.0.0.1:8000" "http://127.0.0.1:7000"; do
            # curl's -w already prints "000" on connection failure regardless
            # of curl's own exit code, so no `|| echo` fallback here — one
            # would double up into "000000" when curl also exits non-zero.
            code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "${base}${path}" 2>/dev/null)"
            code="${code:0:3}"
            if [[ "$code" =~ ^(200|304)$ ]]; then
                ok "${base}${path} -> $code"
            elif [[ "$code" == "000" || -z "$code" ]]; then
                : # this base isn't the one running on this box — silent skip
            else
                fail "${base}${path} -> $code"
            fi
        done
    done
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
        if [[ "$perms" == "640" ]]; then
            warn "log permission 0640 (should be 0660, blocks the other service's OS user): $f"
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
        COUNT=$(awk -v cutoff="$CUTOFF" '$0 >= cutoff' logs/errors.log 2>/dev/null | grep -cE '\| (ERROR|CRITICAL) *\|' || true)
        COUNT="${COUNT:-0}"
        if [[ "$COUNT" -gt 100 ]]; then
            fail "$COUNT ERROR/CRITICAL lines in errors.log in the last 24h (threshold 100)"
        elif [[ "$COUNT" -gt 20 ]]; then
            warn "$COUNT ERROR/CRITICAL lines in errors.log in the last 24h (threshold 20)"
        else
            ok "$COUNT ERROR/CRITICAL lines in errors.log in the last 24h"
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
section "7. Migrations"
if [[ -f scripts/apply_migrations.py ]]; then
    PYTHON_BIN="${HEALTH_CHECK_PYTHON:-venv/bin/python}"
    [[ -x "$PYTHON_BIN" ]] || PYTHON_BIN="python3"
    if "$PYTHON_BIN" scripts/apply_migrations.py --validate >/tmp/health_check_migrations.out 2>&1; then
        ok "apply_migrations.py --validate: clean"
    else
        fail "apply_migrations.py --validate: $(tail -3 /tmp/health_check_migrations.out | tr '\n' ' ')"
    fi
    rm -f /tmp/health_check_migrations.out
else
    warn "scripts/apply_migrations.py not found, skipping"
fi

# ===========================================================================
# 8. Environment drift, both venvs
# ===========================================================================
section "8. Environment drift"
if [[ -f scripts/check_env.py ]]; then
    if [[ -x venv/bin/python ]]; then
        if venv/bin/python scripts/check_env.py --requirements requirements.txt >/tmp/health_check_env_bot.out 2>&1; then
            ok "check_env.py clean for venv/ (bot)"
        else
            warn "check_env.py drift in venv/ (bot): $(tail -3 /tmp/health_check_env_bot.out | tr '\n' ' ')"
        fi
        rm -f /tmp/health_check_env_bot.out
    else
        warn "venv/bin/python not found, skipping bot venv check"
    fi
    if [[ -x website/venv/bin/python ]]; then
        if website/venv/bin/python scripts/check_env.py --requirements website/requirements.txt >/tmp/health_check_env_web.out 2>&1; then
            ok "check_env.py clean for website/venv/ (web)"
        else
            warn "check_env.py drift in website/venv/ (web): $(tail -3 /tmp/health_check_env_web.out | tr '\n' ' ')"
        fi
        rm -f /tmp/health_check_env_web.out
    else
        warn "website/venv/bin/python not found, skipping web venv check"
    fi
else
    warn "scripts/check_env.py not found, skipping (see docs/TASKS_FOR_SONNET_2026-07-29.md M4)"
fi

# ===========================================================================
# 9. Round-linkage anomalies / orphan counts
# ===========================================================================
section "9. Round linkage"
if [[ -f scripts/check_round_linkage_anomalies.py ]]; then
    PYTHON_BIN="${HEALTH_CHECK_PYTHON:-venv/bin/python}"
    [[ -x "$PYTHON_BIN" ]] || PYTHON_BIN="python3"
    if "$PYTHON_BIN" scripts/check_round_linkage_anomalies.py >/tmp/health_check_linkage.out 2>&1; then
        ok "round-linkage anomalies within thresholds"
    else
        fail "round-linkage anomalies over threshold: $(tail -5 /tmp/health_check_linkage.out | tr '\n' ' ')"
    fi
    rm -f /tmp/health_check_linkage.out
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
