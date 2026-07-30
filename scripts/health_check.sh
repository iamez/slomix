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
# This process and every ancestor up to PID 1, one per line. Used to keep
# `pgrep -f` from matching the command line of whatever invoked this script.
_ancestor_pids() {
    local pid=$$
    while [[ -n "$pid" && "$pid" != "0" ]]; do
        printf '%s\n' "$pid"
        [[ "$pid" == "1" ]] && break
        pid="$(awk '{print $4}' "/proc/$pid/stat" 2>/dev/null)"
    done
}

# check_service_pair <label> <process-pattern|-> <unit-name>...
#   process-pattern: pgrep -f pattern to fall back on when no systemd unit
#   exists, or "-" for none.
check_service_pair() {
    local label="$1"; shift
    local proc_pattern="$1"; shift
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
        return
    fi
    # No systemd unit: this project explicitly supports hosts running the bot
    # under `screen` (CLAUDE.md), and nothing else in this script probes the bot
    # process — so a plain WARN here reported identically whether the bot was
    # running fine or had crashed hours ago, on exactly the hosts where nothing
    # would restart it (Codex review on #580). Fall back to looking for the
    # actual process before giving up.
    if [[ "$proc_pattern" != "-" ]] && command -v pgrep >/dev/null 2>&1; then
        # Exclude this script AND its whole ancestor chain. `pgrep -f` matches
        # full command lines, so if the pattern appears anywhere in the chain
        # that invoked us — a wrapper script, a CI step, an interactive
        # `bash -c` that happens to contain it — pgrep reports a hit and every
        # service looks alive regardless. Verified while testing this: a
        # deliberately-bogus pattern kept matching, and excluding just $$ and
        # $PPID wasn't enough because the real match was a grandparent.
        local matches
        matches="$(pgrep -f "$proc_pattern" 2>/dev/null | grep -vxF -f <(_ancestor_pids) || true)"
        if [[ -n "$matches" ]]; then
            ok "$label: no systemd unit, but a matching process is running (pgrep -f '$proc_pattern' -> $(echo "$matches" | tr '\n' ' '))"
        else
            fail "$label: no systemd unit AND no process matching '$proc_pattern' — not running anywhere"
        fi
        return
    fi
    warn "$label: no matching systemd unit found (checked: ${candidates[*]}) — may run under screen/manual process"
}
check_service_pair "bot" "bot.ultimate_bot" etlegacy-bot slomix-bot
check_service_pair "web" "uvicorn.*backend.main" etlegacy-web slomix-web
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
# cloudflared carries ALL public traffic to www.slomix.fyi on the canonical VM
# (slomix_vm_setup.sh installs /etc/systemd/system/cloudflared.service and
# `systemctl enable cloudflared.service`, lines 1035/1064) — if the tunnel is
# down the whole site is unreachable from outside even with slomix-web healthy,
# which is exactly the blind spot a health check exists to close (Codex P1
# review on #580).
#
# Existence is tested with `list-unit-files`, not by pattern-matching
# `is-active` output: on this box `systemctl is-active cloudflared` prints
# "inactive" for a unit whose file doesn't exist at all, so the old
# "unknown"/"could not" match silently misclassified a not-installed service
# as installed-but-down and FAILed on it. Not-installed WARNs (some hosts run
# these differently, or not at all); installed-but-not-running FAILs — except
# a unit that's installed yet deliberately `disabled`, which is a dev-box
# posture rather than an outage, so that WARNs too.
for svc in redis-server tailscaled fail2ban smbd cloudflared; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        ok "$svc active"
    elif ! systemctl list-unit-files "${svc}.service" 2>/dev/null | grep -q "${svc}.service"; then
        warn "$svc: no matching systemd unit found (not installed on this host)"
    elif [[ "$(systemctl is-enabled "$svc" 2>/dev/null)" == "disabled" ]]; then
        warn "$svc installed but disabled (intentionally off on this host?): $(systemctl is-active "$svc" 2>&1)"
    else
        fail "$svc not active: $(systemctl is-active "$svc" 2>&1)"
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
    # Match ONLY the Local Address:Port column ($4 with -H: State, Recv-Q,
    # Send-Q, Local, Peer[, Process]). Every `ss -ltn` row carries a literal
    # "0.0.0.0:*" in the *Peer* column, so grepping the whole line reported
    # every correctly-loopback-bound listener (e.g. "127.0.0.1:5432") as
    # exposed to all interfaces — a false positive on essentially every row,
    # which is worse than no check because it buries the real ones (Codex
    # review on #580).
    EXPOSED="$(echo "$LISTENING" | awk '$4 ~ /^(0\.0\.0\.0|\*|\[::\]):/ {print}' || true)"
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
    # Collect per-base results first, then judge. Reporting a FAIL the moment
    # any candidate answers badly punished the normal dev/manual layout: only
    # one of :8000/:7000 is Slomix, and an unrelated app on the other port
    # commonly answers 404 for these paths, so a perfectly healthy host scored
    # FAILs from a service that isn't even ours (Codex review on #580, second
    # round). A base only counts as Slomix once it answers 200/304 on at least
    # one path; bases that never do are reported as "not this box's" instead.
    declare -A base_ok=() base_bad=()
    for base in "http://127.0.0.1:8000" "http://127.0.0.1:7000"; do
        for path in /health /api/status; do
            # curl's -w already prints "000" on connection failure regardless
            # of curl's own exit code, so no `|| echo` fallback here — one
            # would double up into "000000" when curl also exits non-zero.
            code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "${base}${path}" 2>/dev/null)"
            code="${code:0:3}"
            if [[ "$code" =~ ^(200|304)$ ]]; then
                ok "${base}${path} -> $code"
                base_ok["$base"]=1
            elif [[ "$code" == "000" || -z "$code" ]]; then
                : # nothing listening here — silent skip
            else
                base_bad["$base"]="${base_bad[$base]:-}${base_bad[$base]:+, }${path} -> $code"
            fi
        done
    done
    for base in "${!base_bad[@]}"; do
        if [[ -n "${base_ok[$base]:-}" ]]; then
            # This base IS Slomix (it served one path) but failed another —
            # a real problem worth failing on.
            fail "${base}: ${base_bad[$base]}"
        else
            # Answered, but never successfully on any Slomix path — some other
            # application on that port, not our outage to report.
            warn "${base}: responded but no Slomix endpoint served (${base_bad[$base]}) — probably an unrelated app on this port"
        fi
    done
    if [[ ${#base_ok[@]} -eq 0 ]]; then
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
# The web service's log directory is configurable: logging_config.py resolves
# WEB_LOG_DIR and only falls back to <repo>/logs. A deployment that sets it
# elsewhere (e.g. /var/log/slomix) would have this check pass on an empty or
# stale repo-local logs/ while the directory that actually matters — the one
# whose 0640-vs-0660 permissions have twice taken the bot down — goes
# unexamined (Codex review on #580). Scan both, de-duplicated.
LOG_DIRS=(logs)
WEB_LOG_DIR_RESOLVED="${WEB_LOG_DIR:-}"
if [[ -z "$WEB_LOG_DIR_RESOLVED" && -f website/.env ]]; then
    # Not sourced: .env may contain arbitrary shell. Read the one key we need.
    WEB_LOG_DIR_RESOLVED="$(grep -E '^\s*WEB_LOG_DIR=' website/.env 2>/dev/null \
        | tail -1 | cut -d= -f2- | tr -d '"'"'"' ' || true)"
fi
if [[ -n "$WEB_LOG_DIR_RESOLVED" ]]; then
    # Compare canonical paths so an absolute WEB_LOG_DIR pointing at the repo's
    # own logs/ isn't scanned (and reported) twice.
    repo_logs_real="$(readlink -f logs 2>/dev/null || echo logs)"
    web_logs_real="$(readlink -f "$WEB_LOG_DIR_RESOLVED" 2>/dev/null || echo "$WEB_LOG_DIR_RESOLVED")"
    if [[ "$web_logs_real" != "$repo_logs_real" ]]; then
        if [[ -d "$WEB_LOG_DIR_RESOLVED" ]]; then
            LOG_DIRS+=("$WEB_LOG_DIR_RESOLVED")
        else
            warn "WEB_LOG_DIR is set to '$WEB_LOG_DIR_RESOLVED' but that directory doesn't exist"
        fi
    fi
fi

for LOG_DIR_SCAN in "${LOG_DIRS[@]}"; do
if [[ -d "$LOG_DIR_SCAN" ]]; then
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
    done < <(find "$LOG_DIR_SCAN" -maxdepth 1 -type f -name '*.log' -print0 2>/dev/null)
    LOG_COUNT=$(find "$LOG_DIR_SCAN" -maxdepth 1 -type f -name '*.log' 2>/dev/null | wc -l)
    LOG_SIZE=$(du -sh "$LOG_DIR_SCAN" 2>/dev/null | cut -f1)
    ok "$LOG_DIR_SCAN has $LOG_COUNT *.log files, $LOG_SIZE total"
    if [[ "$STALE_FOUND" -eq 1 ]]; then
        warn "$LOG_DIR_SCAN: at least one *.log file hasn't been written to in 7+ days (may be fine if that service is idle)"
    fi
else
    warn "$LOG_DIR_SCAN directory not found"
fi
done

# ===========================================================================
# 6. ERROR/CRITICAL counts, last 24h
# ===========================================================================
section "6. Error rate (24h)"
# Scan EVERY resolved log directory, same set section 5 built. With WEB_LOG_DIR
# pointing outside the repository, counting only the repo-local errors.log meant
# a website drowning in errors was reported healthy off the bot's log alone
# (Codex review on #580, second round).
ERROR_LOG_FILES=()
for _dir in "${LOG_DIRS[@]}"; do
    for _f in "$_dir"/errors.log "$_dir"/errors.log.*; do
        [[ -f "$_f" ]] && ERROR_LOG_FILES+=("$_f")
    done
done
if [[ ${#ERROR_LOG_FILES[@]} -gt 0 ]]; then
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
        for f in "${ERROR_LOG_FILES[@]}"; do
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
        SCOPE="${#ERROR_LOG_FILES[@]} file(s) across: ${LOG_DIRS[*]}"
        if [[ "$COUNT" -gt 100 ]]; then
            fail "$COUNT ERROR/CRITICAL lines in the last 24h (threshold 100) — $SCOPE"
        elif [[ "$COUNT" -gt 20 ]]; then
            warn "$COUNT ERROR/CRITICAL lines in the last 24h (threshold 20) — $SCOPE"
        else
            ok "$COUNT ERROR/CRITICAL lines in the last 24h — $SCOPE"
        fi
    else
        warn "could not compute 24h cutoff (date command mismatch), skipping error-rate check"
    fi
else
    warn "no errors.log found in any resolved log directory (${LOG_DIRS[*]})"
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
    # The router is mounted with prefix="/api" (main.py: include_router(
    # diagnostics_router.router, prefix="/api")), so the served path is
    # /api/diagnostics/round-linkage — the unprefixed spelling in CLAUDE.md
    # 404s. Probe the real one first, keep the bare path as a fallback in case
    # a host mounts it differently (Codex review on #580).
    #
    # 200 is NOT achievable here: the route depends on require_admin_user
    # (diagnostics_router.py:527), so an anonymous probe gets 401 no matter how
    # healthy the API is — expecting 200 made this branch permanently
    # unsatisfiable. 401/403 is therefore the SUCCESS signal for "the endpoint
    # exists and the app is serving it"; the anomaly data itself simply can't be
    # read without a session, so this degrades to a reachability check and says
    # so rather than pretending to have checked thresholds (Codex review on
    # #580, second round).
    linkage_status=""
    for base in "http://127.0.0.1:8000" "http://127.0.0.1:7000"; do
        for route in "/api/diagnostics/round-linkage" "/diagnostics/round-linkage"; do
            code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "${base}${route}" 2>/dev/null)"
            code="${code:0:3}"
            case "$code" in
                401|403)
                    warn "round-linkage: endpoint reachable at ${base}${route} (HTTP $code — admin-only, thresholds NOT checked; install scripts/check_round_linkage_anomalies.py for the real check)"
                    linkage_status="reachable"
                    break 2
                    ;;
                200)
                    ok "GET ${base}${route} -> 200"
                    linkage_status="ok"
                    break 2
                    ;;
                5??)
                    fail "round-linkage: ${base}${route} -> $code"
                    linkage_status="error"
                    break 2
                    ;;
            esac
        done
    done
    if [[ -z "$linkage_status" ]]; then
        fail "round-linkage: no API base answered /api/diagnostics/round-linkage (tried :8000 and :7000)"
    fi
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
