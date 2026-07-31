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

# ---------------------------------------------------------------------------
# Configuration lookup.
#
# Most of this script's early revisions hardcoded what the deployment makes
# configurable — port 7000/8000, postgres on 127.0.0.1:5432, redis on
# 127.0.0.1:6379 — so any supported non-default layout produced confident
# FAILs about services that were perfectly healthy somewhere else, which is
# worse than no check at all (Codex review on #580).
#
# Environment wins over the file, matching load_dotenv(override=False). The
# file is READ, never sourced: .env may contain arbitrary shell.
# ---------------------------------------------------------------------------
cfg() {
    local key="$1" default="${2:-}" val="" f
    val="${!key:-}"
    if [[ -z "$val" ]]; then
        for f in .env website/.env; do
            [[ -f "$f" ]] || continue
            val="$(sed -n "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*//p" "$f" 2>/dev/null \
                   | tail -1 | sed -e 's/[[:space:]]*#.*$//' -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'\$/\1/")"
            [[ -n "$val" ]] && break
        done
    fi
    printf '%s' "${val:-$default}"
}

# Resolved once here because sections 2 and 3 both branch on it.
DB_TYPE="$(cfg DATABASE_TYPE postgresql)"

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
    # Check EVERY cluster, not `head -1`. An upgraded host keeps the old
    # cluster's unit around (postgresql@14-main alongside an active
    # postgresql@17-main), and taking the first match could pin the stale one
    # and FAIL permanently while the live cluster served every query — the
    # connectivity probe below would even pass, making the two contradict each
    # other (Codex review on #580).
    pg_active=""
    pg_inactive=()
    while read -r pg_unit; do
        [[ -n "$pg_unit" ]] || continue
        if systemctl is-active --quiet "$pg_unit" 2>/dev/null; then
            pg_active="${pg_active:+$pg_active, }$pg_unit"
        else
            pg_inactive+=("$pg_unit")
        fi
    done < <(systemctl list-units --all --plain --no-legend 'postgresql@*-main.service' 2>/dev/null | awk '{print $1}')

    if [[ -n "$pg_active" ]]; then
        ok "postgresql cluster active: $pg_active"
        # Idle clusters on an upgraded box are normal, not a fault.
        [[ ${#pg_inactive[@]} -gt 0 ]] && ok "postgresql inactive cluster(s) ignored: ${pg_inactive[*]}"
    elif [[ ${#pg_inactive[@]} -gt 0 ]]; then
        fail "no active postgresql cluster (found but not running: ${pg_inactive[*]})"
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
        # For cloudflared, `active` is necessary but nowhere near sufficient:
        # the process stays up with revoked credentials, a lost edge
        # connection, or a broken ingress rule, while every other probe in
        # this script is local and therefore still green. The public site can
        # be completely unavailable and nothing here would say so (Codex P1
        # review on #580). Probe the public hostname when one is configured.
        if [[ "$svc" == "cloudflared" ]]; then
            PUBLIC_URL="$(cfg HEALTH_CHECK_PUBLIC_URL)"
            if [[ -z "$PUBLIC_URL" ]]; then
                warn "cloudflared active but no HEALTH_CHECK_PUBLIC_URL configured — tunnel is NOT verified end-to-end, only the process is running"
            elif ! command -v curl >/dev/null 2>&1; then
                warn "cloudflared active but curl unavailable — cannot verify public reachability"
            else
                pub_code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 "${PUBLIC_URL%/}/api/status" 2>/dev/null)"
                if [[ "${pub_code:0:3}" =~ ^(200|304)$ ]]; then
                    ok "cloudflared tunnel serving publicly (${PUBLIC_URL%/}/api/status -> $pub_code)"
                else
                    fail "cloudflared is active but the public site is NOT reachable (${PUBLIC_URL%/}/api/status -> ${pub_code:-000}) — tunnel up, traffic not flowing"
                fi
            fi
        fi
    elif ! systemctl list-unit-files "${svc}.service" 2>/dev/null | grep -q "${svc}.service"; then
        warn "$svc: no matching systemd unit found (not installed on this host)"
    elif [[ "$(systemctl is-enabled "$svc" 2>/dev/null)" == "disabled" ]]; then
        # "disabled" is only benign where the service was never set up. For
        # cloudflared specifically, /etc/cloudflared holds the tunnel
        # credentials slomix_vm_setup.sh puts there (CF_CRED_DIR, line 330) —
        # if that exists, this box IS a configured tunnel host and a disabled
        # unit means the public site is unreachable while every local check
        # stays green. That has to FAIL, not warn (Codex P1 review on #580).
        if [[ "$svc" == "cloudflared" && -d /etc/cloudflared ]]; then
            fail "cloudflared is configured (/etc/cloudflared present) but DISABLED — public site unreachable"
        else
            warn "$svc installed but disabled (intentionally off on this host?): $(systemctl is-active "$svc" 2>&1)"
        fi
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
    # Only expect a local postgres listener when postgres is actually local.
    # A configured remote POSTGRES_HOST has nothing listening here by design.
    PG_HOST_CFG="$(cfg POSTGRES_HOST 127.0.0.1)"
    if [[ "$DB_TYPE" == "sqlite" ]]; then
        ok "DATABASE_TYPE=sqlite — no local postgres listener expected"
    elif [[ "$PG_HOST_CFG" =~ ^(127\.0\.0\.1|localhost|::1)$ ]]; then
        check_port_open "$(cfg POSTGRES_PORT 5432)" postgres
    else
        ok "postgres configured remotely ($PG_HOST_CFG) — no local listener expected"
    fi
    if [[ "$(cfg CACHE_BACKEND redis)" == "redis" && -z "$(cfg REDIS_URL)" ]]; then
        check_port_open 6379 redis
    else
        ok "redis not configured as a local default backend — skipping local listener check"
    fi
    # Website binds 7000 on the canonical VM (slomix_vm_setup.sh) and dev boxes
    # commonly run uvicorn on 8000, but both are overridable (WEBSITE_PORT in
    # prod_up.sh, DEV_WEBSITE_PORT in dev_up.sh) — a host serving happily on
    # 9000 previously warned that nothing was listening (Codex review on #580).
    WEB_PORT_CANDIDATES="$(cfg WEBSITE_PORT) $(cfg DEV_WEBSITE_PORT) $(cfg WEBSITE_PUBLIC_PORT) 7000 8000"
    WEB_PORT_RE="$(printf '%s' "$WEB_PORT_CANDIDATES" | tr ' ' '\n' | grep -E '^[0-9]+$' | sort -u | paste -sd'|')"
    if echo "$LISTENING" | grep -qE ":(${WEB_PORT_RE}) "; then
        ok "website port listening (candidates: ${WEB_PORT_RE//|/, })"
    else
        warn "website port: none of ${WEB_PORT_RE//|/, } listening"
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
# Probe the backend the app is CONFIGURED to use. A remote POSTGRES_HOST, a
# non-default port, or the SQLite mode scripts/dev_up.sh selects all made the
# old hardcoded 127.0.0.1:5432 probe record a hard failure against a socket
# nothing was supposed to be listening on (Codex review on #580).
if [[ "$DB_TYPE" == "sqlite" ]]; then
    ok "DATABASE_TYPE=sqlite — skipping postgres probe (not this deployment's backend)"
elif command -v pg_isready >/dev/null 2>&1; then
    PG_HOST="$(cfg POSTGRES_HOST 127.0.0.1)"
    PG_PORT="$(cfg POSTGRES_PORT 5432)"
    if pg_isready -h "$PG_HOST" -p "$PG_PORT" >/dev/null 2>&1; then
        ok "postgres reachable ($PG_HOST:$PG_PORT)"
    else
        fail "postgres not reachable ($PG_HOST:$PG_PORT)"
    fi
else
    warn "pg_isready not available, skipping postgres connectivity check"
fi

# Same for the cache. CACHE_BACKEND=memory is a supported dev posture, and a
# remote or password-protected instance is configured through REDIS_URL
# (website/backend/services/http_cache_backend.py) — contacting unauthenticated
# localhost in either case tests something the application never uses.
CACHE_BACKEND="$(cfg CACHE_BACKEND redis)"
REDIS_URL="$(cfg REDIS_URL)"
if [[ "$CACHE_BACKEND" != "redis" ]]; then
    ok "CACHE_BACKEND=$CACHE_BACKEND — skipping redis probe (not this deployment's cache)"
elif ! command -v redis-cli >/dev/null 2>&1; then
    warn "redis-cli not available, skipping redis connectivity check"
elif [[ -n "$REDIS_URL" ]]; then
    # redis-cli -u handles host, port, db and password in one flag.
    if redis-cli -u "$REDIS_URL" ping 2>/dev/null | grep -q PONG; then
        ok "redis reachable (REDIS_URL)"
    else
        fail "redis not reachable (REDIS_URL as configured)"
    fi
else
    if redis-cli -h 127.0.0.1 -p 6379 ping 2>/dev/null | grep -q PONG; then
        ok "redis reachable (127.0.0.1:6379, default)"
    else
        fail "redis not reachable (127.0.0.1:6379, default)"
    fi
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
    # Candidate bases: whatever the deployment CONFIGURES first, then the two
    # conventional defaults. prod_up.sh honours WEBSITE_PORT and dev_up.sh
    # DEV_WEBSITE_PORT, so a service healthy on e.g. 9000 previously made both
    # hardcoded candidates return 000 and the check declared a full outage
    # (Codex review on #580).
    declare -a API_BASES=()
    for p in "$(cfg WEBSITE_PORT)" "$(cfg DEV_WEBSITE_PORT)" "$(cfg WEBSITE_PUBLIC_PORT)"; do
        [[ -n "$p" ]] && API_BASES+=("http://127.0.0.1:${p}")
    done
    API_BASES+=("http://127.0.0.1:8000" "http://127.0.0.1:7000")
    # De-duplicate, preserving the configured-first order.
    declare -A seen_base=()
    declare -a API_BASES_UNIQ=()
    for base in "${API_BASES[@]}"; do
        [[ -n "${seen_base[$base]:-}" ]] && continue
        seen_base["$base"]=1
        API_BASES_UNIQ+=("$base")
    done

    declare -A base_ok=() base_bad=()
    for base in "${API_BASES_UNIQ[@]}"; do
        # /api/status FIRST and as the sole identity test. /health is a
        # near-universal route name, so an unrelated app on a candidate port
        # answering 200 there was enough to mark that base as Slomix — after
        # which its 404 on /api/status counted as our failure, even with the
        # real Slomix base fully healthy (Codex review on #580). Only the
        # Slomix-specific path may promote a base.
        for path in /api/status /health; do
            # curl's -w already prints "000" on connection failure regardless
            # of curl's own exit code, so no `|| echo` fallback here — one
            # would double up into "000000" when curl also exits non-zero.
            code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "${base}${path}" 2>/dev/null)"
            code="${code:0:3}"
            if [[ "$code" =~ ^(200|304)$ ]]; then
                ok "${base}${path} -> $code"
                # Only /api/status establishes that this base is Slomix. A 200
                # on the generic /health proves someone is listening, not who.
                [[ "$path" == "/api/status" ]] && base_ok["$base"]=1
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
        fail "no Slomix API base answered /api/status (tried: ${API_BASES_UNIQ[*]}) — full outage, or set WEBSITE_PORT/DEV_WEBSITE_PORT if this host uses another port"
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
# Deliberately NOT including bot/logs. It was suggested on review, but
# bot/logging_config.py:13 is `Path(__file__).parent.parent / "logs"` — from
# bot/logging_config.py that resolves to <repo>/logs, not bot/logs. Verified on
# this box: the running bot holds fds on logs/{bot,commands,database,errors,
# webhook}.log and none in bot/logs, whose newest file is from 2025-11-28.
# bot/logs is a leftover from an older layout; scanning it would permanently
# WARN about 9-month-old permissions and stale mtimes.
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
    # Rotated files are scanned too. RotatingFileHandler rolls errors.log to
    # errors.log.1 and logrotate compresses to errors.log.1.gz — neither
    # matches '*.log', so an old rotation could sit world-readable or
    # group-writable indefinitely without one warning, in the very check that
    # exists because log permissions have twice taken the bot down (Codex
    # review on #580).
    while IFS= read -r -d '' f; do
        perms="$(stat -c '%a' "$f" 2>/dev/null || stat -f '%Lp' "$f" 2>/dev/null)"
        # client_errors.log is deliberately owner-only (0600, single writer -
        # see website/backend/logging_config.py's OwnerOnlyRotatingFileHandler);
        # every other *.log file needs group-write (0660) for bot/web
        # cross-process access. Reject ANY other mode, not just the one
        # specific 0640 value previously seen - 0644/0666 would silently
        # pass the old check despite exposing logs or permitting unintended
        # writes (Codex P2 review on #580).
        #
        # Strip the rotation suffix before deciding which mode applies:
        # client_errors.log.1 is the same owner-only file and must not be held
        # to the 0660 rule just because its name gained a number.
        base_name="$(basename "$f")"
        base_name="${base_name%.gz}"
        base_name="$(printf '%s' "$base_name" | sed -E 's/\.[0-9]+$//')"
        if [[ "$base_name" == "client_errors.log" ]]; then
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
        # Staleness applies to ACTIVE logs only. A rotated errors.log.3 is
        # supposed to be old, so including rotations here would WARN forever
        # on every healthy host.
        if [[ "$f" == *.log ]]; then
            age_secs=$(( $(date +%s) - $(stat -c '%Y' "$f" 2>/dev/null || stat -f '%m' "$f" 2>/dev/null || echo 0) ))
            if [[ "$age_secs" -gt $((7 * 86400)) ]]; then
                STALE_FOUND=1
            fi
        fi
    done < <(find "$LOG_DIR_SCAN" -maxdepth 1 -type f \( -name '*.log' -o -name '*.log.*' \) -print0 2>/dev/null)
    LOG_COUNT=$(find "$LOG_DIR_SCAN" -maxdepth 1 -type f \( -name '*.log' -o -name '*.log.*' \) 2>/dev/null | wc -l)
    LOG_SIZE=$(du -sh "$LOG_DIR_SCAN" 2>/dev/null | cut -f1)
    ok "$LOG_DIR_SCAN has $LOG_COUNT log files (incl. rotations), $LOG_SIZE total"
    if [[ "$STALE_FOUND" -eq 1 ]]; then
        warn "$LOG_DIR_SCAN: at least one active *.log file hasn't been written to in 7+ days (may be fine if that service is idle)"
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
# --validate is NOT read-only: cmd_validate() calls ensure_tracking_table()
# (apply_migrations.py:511), which runs CREATE TABLE IF NOT EXISTS
# schema_migrations and takes the runner advisory lock. Pointed at a fresh or
# misconfigured database this health check would therefore CREATE a table —
# breaking the "read-only" promise in this script's own header (Codex review on
# #580). Confirm the ledger already exists, read-only, before invoking it.
ledger_exists() {
    local py="$1"
    # Reuse apply_migrations.py's own get_connection(): it resolves the same
    # POSTGRES_*/DB_* env names AND load_dotenv()s the repo .env, so this check
    # talks to exactly the database --validate would. Importing the module is
    # side-effect free (it only defines functions and loads env at import).
    "$py" - <<'PYEOF' 2>/dev/null
import asyncio, pathlib, sys
sys.path.insert(0, str(pathlib.Path("scripts").resolve()))
try:
    from apply_migrations import get_connection
except Exception:
    sys.exit(2)
async def main():
    try:
        conn = await get_connection()
    except Exception:
        sys.exit(3)
    try:
        found = await conn.fetchval("SELECT to_regclass('public.schema_migrations') IS NOT NULL")
    finally:
        await conn.close()
    sys.exit(0 if found else 1)
asyncio.run(main())
PYEOF
}
if [[ -f scripts/apply_migrations.py ]]; then
    PYTHON_BIN="$(find_python "${HEALTH_CHECK_PYTHON:-}")"
    OUT="$HEALTH_CHECK_TMPDIR/migrations.out"
    # Save and restore the CALLER's errexit state rather than forcing `set -e`.
    # This script runs under `set -uo pipefail` with errexit OFF by design, so
    # the old unconditional `set -e` switched it ON for everything that
    # followed — after which the very next `code="$(curl ...)"` that failed to
    # connect (exit 7) terminated the whole health check mid-run, before the
    # remaining sections could report (Codex review on #580).
    _prev_errexit="$(set +o | grep -E ' -o errexit$' || echo 'set +o errexit')"
    set +e; ledger_exists "$PYTHON_BIN"; LEDGER_RC=$?; eval "$_prev_errexit"
    if [[ "$LEDGER_RC" -eq 1 ]]; then
        # NOT a warning. schema_migrations absent on a database that already
        # holds application tables means migration state is unknown and the
        # only drift check in this script is silently skipped — the health
        # check would exit 0 while the schema could be arbitrarily behind
        # (Codex P1 review on #580). An genuinely empty database is the one
        # benign case, so distinguish it rather than blanket-failing.
        if "$PYTHON_BIN" - <<'PYEOF' 2>/dev/null
import asyncio, pathlib, sys
sys.path.insert(0, str(pathlib.Path("scripts").resolve()))
from apply_migrations import get_connection
async def main():
    conn = await get_connection()
    try:
        n = await conn.fetchval(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'"
        )
    finally:
        await conn.close()
    # 0 tables -> fresh database, nothing to be behind on.
    sys.exit(0 if n == 0 else 1)
asyncio.run(main())
PYEOF
        then
            warn "schema_migrations absent, but the database has no tables — fresh install, nothing to validate"
        else
            fail "schema_migrations absent on a database that already has tables — migration state is UNKNOWN and drift cannot be checked; run scripts/apply_migrations.py"
        fi
    elif [[ "$LEDGER_RC" -gt 1 ]]; then
        warn "could not check for schema_migrations (no asyncpg or DB unreachable) — skipping --validate"
    elif "$PYTHON_BIN" scripts/apply_migrations.py --validate >"$OUT" 2>&1; then
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
