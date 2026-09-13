#!/usr/bin/env python3
"""slomix watchdog — an observer that alerts, never a supervisor that starts.

Scope (docs/design/24_WATCHDOG.md, slice 1, 2026-09-06): every check below is
read-only and touches no process. systemd already restarts the units; a
hand-started copy wins the port race and systemd then fails in a loop
(2026-08-05), so this script proposes commands and never runs them.

Nine checks, each a pure `check_*` over inputs the `collect_*` functions
gather, so the judgement is testable without a system:

  units        systemctl show: ActiveState, NRestarts, ActiveEnterTimestamp
  web          GET <WATCHDOG_WEB_URL>/health (503 on a DB failure)
  db           SELECT 1 + pg_stat_activity connection count
  rounds       newest counted round vs the bot's own monitoring cadence
  live         GET /api/live/status → newest_age_seconds (the puran tailer)
  collector    mtimes under ~/slomix-server-logs (cron every 10 min)
  lua          frame_health-<today>.log stalls in the last 30 minutes
  disk         df / and journald --disk-usage
  lua_webhook  lua_round_teams newest row vs rounds newest row

Levels: ok / warn / fail / unknown. `unknown` is a state ("no measurement",
e.g. no log file for today), never a pass.

State between runs lives in a JSON file (WATCHDOG_STATE_FILE): per key the
last level, the consecutive-failure count and the last alert time. Rules:
an alert on the transition into fail (web and lua_webhook only on the 2nd
consecutive), at most one alert per key per hour, one "recovered" on the
way back to ok, and one heartbeat line per day after 09:00 so a dead
watchdog is not invisible.

Outputs: the Discord webhook (WATCHDOG_WEBHOOK_URL; --dry-run prints), the
full report to WATCHDOG_LAST_FILE (which /api/diagnostics may expose later),
and the exit code: 0 (the run completed; findings are the payload), 1 only
with --strict and a failing check, 2 when the run itself broke.

Config comes from the ROOT .env via dotenv_values (never website/.env, which
overrides POSTGRES_USER to the least-privilege role — the admin-tool trap of
2026-09-03) with the process environment winning; WATCHDOG_DB_USER selects
the read role explicitly.

Usage: scripts/slomix_watchdog.py [--once] [--dry-run] [--json]
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

Level = str  # "ok" | "warn" | "fail" | "unknown"
LEVEL_ORDER = {"ok": 0, "unknown": 1, "warn": 2, "fail": 3}

# Keys that alert only on the SECOND consecutive failure: a single blip on a
# 2-second health probe or one late webhook row is noise, two in a row is not.
CONFIRM_TWICE = {"web", "lua_webhook"}
ALERT_DEDUP_S = 3600
HEARTBEAT_HOUR = 9
STATE_VERSION = 1


@dataclass
class Finding:
    key: str
    level: Level
    value: Any = None
    threshold: Any = None
    reason: str = ""
    suggest: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config(repo_root: Path = REPO, environ: dict | None = None) -> dict[str, str]:
    """Root .env first, process environment wins. Never website/.env."""
    environ = os.environ if environ is None else environ
    values: dict[str, str] = {}
    root_env = repo_root / ".env"
    if root_env.exists():
        try:
            from dotenv import dotenv_values
            values.update({k: v for k, v in (dotenv_values(root_env) or {}).items() if v is not None})
        except ImportError:
            # python-dotenv is in requirements.txt; without it the process
            # environment is the only source and the caller sees that in the
            # empty POSTGRES_* keys (the db check then reports a connect error).
            values.setdefault("WATCHDOG_CONFIG_NOTE", "python-dotenv missing: root .env not read")
    values.update({k: v for k, v in environ.items() if k.startswith(("WATCHDOG_", "POSTGRES_", "BOT_LOG_DIR", "MONITORING_"))})
    logs_dir = Path(values.get("BOT_LOG_DIR") or (repo_root / "logs"))
    values.setdefault("WATCHDOG_DB_USER", "etlegacy_user")
    values.setdefault("WATCHDOG_WEB_URL", "http://127.0.0.1:8000")
    values.setdefault("WATCHDOG_UNITS", "etlegacy-bot,etlegacy-web")
    values.setdefault("WATCHDOG_STATE_FILE", str(logs_dir / "watchdog_state.json"))
    values.setdefault("WATCHDOG_LAST_FILE", str(logs_dir / "watchdog_last.json"))
    values.setdefault("WATCHDOG_SERVER_LOGS_DIR", str(Path.home() / "slomix-server-logs"))
    values.setdefault("WATCHDOG_BOT_STREAKS_FILE", str(logs_dir / "bot_error_streaks.json"))
    return values


# ---------------------------------------------------------------------------
# Collectors — the only functions that touch the system. All read-only.
# ---------------------------------------------------------------------------

def collect_units(units: list[str]) -> dict[str, dict[str, str] | None]:
    """`systemctl show` needs no sudo. A unit that does not exist answers
    `ActiveState=inactive` too — LoadState tells them apart."""
    out: dict[str, dict[str, str] | None] = {}
    for unit in units:
        try:
            raw = subprocess.run(
                ["systemctl", "show", f"{unit}.service", "-p",
                 "LoadState,ActiveState,SubState,NRestarts,ActiveEnterTimestampMonotonic,ActiveEnterTimestamp"],
                capture_output=True, text=True, timeout=10, check=False,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            out[unit] = None
            continue
        props = dict(line.split("=", 1) for line in raw.splitlines() if "=" in line)
        out[unit] = props
    return out


def collect_http_json(url: str, timeout: float = 5.0) -> tuple[int | None, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310  # http(s) to our own host
            body = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body[:200]
    except urllib.error.HTTPError as e:
        return e.code, None
    except (urllib.error.URLError, OSError, ValueError):
        return None, None


async def collect_db(cfg: dict[str, str]) -> dict[str, Any]:
    """SELECT 1, connection count, newest counted round, newest Lua webhook
    row — the same gated round query diagnostics_router uses."""
    try:
        import asyncpg
    except ImportError:
        return {"error": "asyncpg not installed"}
    try:
        conn = await asyncio.wait_for(asyncpg.connect(
            host=cfg.get("POSTGRES_HOST", "localhost"), port=int(cfg.get("POSTGRES_PORT", "5432")),
            database=cfg.get("POSTGRES_DATABASE", "etlegacy"), user=cfg["WATCHDOG_DB_USER"],
            password=cfg.get("WATCHDOG_DB_PASSWORD") or cfg.get("POSTGRES_PASSWORD"),
        ), timeout=5)
    except Exception as e:  # noqa: BLE001 - the failure IS the measurement
        return {"error": f"connect: {type(e).__name__}"}
    try:
        one = await conn.fetchval("SELECT 1")
        conns = await conn.fetchval("SELECT COUNT(*) FROM pg_stat_activity WHERE datname = current_database()")
        max_conns = await conn.fetchval("SELECT setting::int FROM pg_settings WHERE name = 'max_connections'")
        newest_round = await conn.fetchval(
            "SELECT MAX(created_at) FROM rounds WHERE round_number IN (1, 2) "
            "AND is_bot_round IS DISTINCT FROM TRUE AND is_valid IS DISTINCT FROM FALSE"
        )
        newest_lua = await conn.fetchval("SELECT MAX(captured_at) FROM lua_round_teams")
        newest_server = await conn.fetchval("SELECT MAX(recorded_at) FROM server_status_history")
        newest_voice = await conn.fetchval("SELECT MAX(recorded_at) FROM voice_status_history")
        players_now = await conn.fetchval(
            "SELECT player_count FROM server_status_history ORDER BY recorded_at DESC LIMIT 1"
        )
        return {
            "select_one": one, "connections": conns, "max_connections": max_conns,
            "newest_round": _iso(newest_round), "newest_lua_round": _iso(newest_lua),
            "newest_server_status": _iso(newest_server), "newest_voice_status": _iso(newest_voice),
            "players_now": players_now,
        }
    except Exception as e:  # noqa: BLE001
        return {"error": f"query: {type(e).__name__}"}
    finally:
        await conn.close()


def collect_mtimes(paths: dict[str, Path]) -> dict[str, float | None]:
    return {k: (p.stat().st_mtime if p.exists() else None) for k, p in paths.items()}


def collect_frame_health(path: Path, window_s: int = 1800, now: float | None = None) -> dict[str, Any] | None:
    """Stalls in the last window, attributed with scripts/frame_health_report."""
    if not path.exists():
        return None
    try:
        import frame_health_report as fhr
    except ImportError:
        return {"error": "frame_health_report not importable"}
    now = time.time() if now is None else now
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-20000:]
    report = fhr.parse(lines)
    fhr.attribute(report)
    recent = [g for g in report.gaps if _wall_to_epoch(g.wall) >= now - window_s]
    stalls = [g for g in recent if g.gap >= 500]
    return {
        "gaps_in_window": len(recent),
        "stalls": len(stalls),
        "max_gap_ms": max((g.gap for g in recent), default=0),
        "lua_ms": sum(g.lua_ms for g in stalls),
        "players": max((g.players for g in recent), default=0),
    }


def collect_disk(path: str = "/") -> dict[str, Any]:
    usage = shutil.disk_usage(path)
    journal_bytes: int | None = None
    try:
        raw = subprocess.run(["journalctl", "--no-pager", "--disk-usage"], capture_output=True, text=True,
                             timeout=10, check=False).stdout
        journal_bytes = parse_journal_usage(raw)
    except (OSError, subprocess.SubprocessError):
        # journalctl missing or hanging: the journal size stays None, which
        # check_disk renders as "unknown" rather than as zero.
        journal_bytes = None
    # ⛔⛔ `used / total` IS NOT THE NUMBER A HUMAN SEES. `df` reports
    # `used / (used + available)`, and on ext4 roughly 5% of the filesystem is
    # reserved for root, so the two diverge. Measured on this box 2026-09-07:
    # shutil says 84.9%, df says 89.5% — 4.6 points apart, on the same disk at
    # the same second.
    #
    # That gap sits exactly where it hurts: the 85% warn threshold fires only
    # once df reads ~89.6%, and the 92% fail once df reads ~96.5%. An operator
    # who runs `df -h`, sees 90% and finds the watchdog reporting `ok` has to
    # decide which of the two is lying. Neither is — they answer different
    # questions — but a monitor is worth less than nothing when it disagrees
    # with the command the operator will actually type.
    #
    # `usage.free` is the space this user can really use, so used/(used+free)
    # matches df. `total_pct` keeps the old figure for anyone who wants it.
    denominator = usage.used + usage.free
    return {"used_pct": round(usage.used / denominator * 100, 1) if denominator else 0.0,
            "used_pct_of_total": round(usage.used / usage.total * 100, 1) if usage.total else 0.0,
            "free_gb": round(usage.free / 2**30, 2),
            "journal_bytes": journal_bytes}


def collect_bot_streaks(path: Path) -> dict[str, Any] | None:
    """The bot's own error-streak file (#923). Only liveness is read from it:
    `written_at`/`boot_time` and the streaks that are currently `alerted` —
    an absent key means never failed OR recovered OR expired, so history
    is not something this file can tell us."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"error": "unreadable"}
    if data.get("version") != STATE_VERSION:
        return {"error": f"version {data.get('version')!r} not understood"}
    return data


# ---------------------------------------------------------------------------
# Checks — pure judgement over collected inputs.
# ---------------------------------------------------------------------------

def check_units(props: dict[str, dict[str, str] | None], previous: dict[str, Any] | None,
                units: list[str]) -> list[Finding]:
    out: list[Finding] = []
    prev = (previous or {}).get("units", {})
    for unit in units:
        p = props.get(unit)
        if p is None:
            out.append(Finding(f"unit:{unit}", "unknown", reason="systemctl could not be asked"))
            continue
        if p.get("LoadState") != "loaded":
            out.append(Finding(f"unit:{unit}", "unknown", value=p.get("LoadState"),
                               reason="unit is not installed on this host — 'inactive' would have lied",
                               suggest="systemctl list-units --all 'etlegacy-*' 'slomix-*'"))
            continue
        active = p.get("ActiveState")
        restarts = int(p.get("NRestarts") or 0)
        entered = p.get("ActiveEnterTimestamp") or ""
        if active != "active":
            out.append(Finding(f"unit:{unit}", "fail", value=active, threshold="active",
                               reason=f"{unit} is {active}/{p.get('SubState')}",
                               suggest=f"sudo systemctl status {unit}  # then the owner decides"))
            continue
        before = prev.get(unit, {})
        if before and (restarts > int(before.get("restarts", 0)) or entered != before.get("entered", entered)):
            out.append(Finding(f"unit:{unit}", "warn", value={"restarts": restarts, "entered": entered},
                               reason=f"{unit} restarted since the last check (NRestarts {before.get('restarts')} → {restarts})",
                               suggest=f"journalctl --no-pager -u {unit} -n 200"))
            continue
        out.append(Finding(f"unit:{unit}", "ok", value={"restarts": restarts, "entered": entered}))
    return out


def check_web(status: int | None, body: Any) -> Finding:
    if status == 200 and isinstance(body, dict) and body.get("status") == "ok":
        return Finding("web", "ok", value=200)
    if status is None:
        return Finding("web", "fail", value=None, threshold=200, reason="/health did not answer",
                       suggest="ss -ltnp | grep :8000 ; sudo systemctl status etlegacy-web")
    return Finding("web", "fail", value=status, threshold=200,
                   reason=f"/health answered {status}: {body!r}"[:200],
                   suggest="the website's own DB probe failed — see the db check")


def check_db(db: dict[str, Any]) -> Finding:
    if "error" in db:
        return Finding("db", "fail", value=db["error"], reason=f"database probe failed: {db['error']}",
                       suggest="pg_isready -h localhost -p 5432 ; sudo systemctl status postgresql")
    conns, maxc = db.get("connections") or 0, db.get("max_connections") or 0
    if maxc and conns >= 0.9 * maxc:
        return Finding("db", "warn", value=conns, threshold=int(0.9 * maxc),
                       reason=f"{conns} of {maxc} connections in use")
    return Finding("db", "ok", value={"connections": conns, "max": maxc})


def check_rounds(db: dict[str, Any], now: float, server_interval_s: int = 300) -> Finding:
    """A round file that never became a row. Gated on activity: the bot's
    MonitoringService writes server_status_history every `server_interval_s`
    (MONITORING_SERVER_INTERVAL_SECONDS, default 300) with no gate of its own,
    so a stale MAX(recorded_at) means the bot is down OR its monitor loop is
    failing every tick (it survives its own exceptions and sleeps 60 s) — the
    finding says both, never "the event loop is dead". No row at all means the
    service was never started (MONITORING_ENABLED), which is unknown, not a
    failure. A database that cannot be asked is `unknown` upstream."""
    if "error" in db:
        return Finding("rounds", "unknown", reason="no database — the bot's liveness cannot be read from it")
    if not db.get("newest_server_status"):
        return Finding("rounds", "unknown",
                       reason="server_status_history has no rows — MonitoringService never wrote here (MONITORING_ENABLED?)",
                       suggest="grep -n MONITORING_ENABLED .env ; journalctl --no-pager -u etlegacy-bot -n 50")
    threshold = max(900, 3 * int(server_interval_s))
    server_age = _age(db.get("newest_server_status"), now)
    if server_age is None or server_age > threshold:
        return Finding("rounds", "fail", value=server_age, threshold=threshold,
                       reason=f"server_status_history last written {_fmt_age(server_age)} ago (monitor interval {server_interval_s} s): "
                              "the bot is down, or its monitor loop is failing on every tick (UDP status or DB write)",
                       suggest="sudo systemctl status etlegacy-bot ; journalctl --no-pager -u etlegacy-bot -n 100 | grep -i monitor")
    players = db.get("players_now") or 0
    round_age = _age(db.get("newest_round"), now)
    if players >= 2 and (round_age is None or round_age > 2 * 3600):
        return Finding("rounds", "warn", value=round_age, threshold=7200,
                       reason=f"{players} players on the server and no counted round for {_fmt_age(round_age)}",
                       suggest="the round files may be waiting on puran — check the SSH monitor alerts")
    return Finding("rounds", "ok", value={"newest_round_age_s": round_age, "players_now": players})


def check_live(status: int | None, body: Any, players_now: int) -> Finding:
    if status is None:
        # The website itself is down: that is the `web` finding's alert, not
        # a second one wearing the tailer's name.
        return Finding("live", "unknown", reason="the website did not answer — see web")
    if status != 200 or not isinstance(body, dict):
        return Finding("live", "fail", value=status, threshold=200, reason=f"/api/live/status answered {status}")
    age = body.get("newest_age_seconds")
    if players_now >= 1 and (age is None or age > 600):
        return Finding("live", "warn", value=age, threshold=600,
                       reason=f"players on the server but the live feed's newest event is {_fmt_age(age)} old — the puran tailer may be down",
                       suggest="ssh puran 'pgrep -c -f \"[l]iveview_tailer\"'  # owner")
    return Finding("live", "ok", value={"newest_age_s": age, "buffered": body.get("buffered")})


def check_collector(mtimes: dict[str, float | None], now: float, players_now: int) -> Finding:
    """The 10-minute cron that pulls etconsole/frame_health from puran. Its
    collector.log holds failures too — a fresh mtime on a day-file is the
    proof of a successful pull."""
    day = mtimes.get("frame_health_today")
    console = mtimes.get("etconsole_today")
    newest = max((t for t in (day, console) if t is not None), default=None)
    if newest is None:
        if players_now >= 1:
            return Finding("collector", "fail", reason="no log file for today while the server has players",
                           suggest="tail ~/slomix-server-logs/collector.log")
        return Finding("collector", "unknown", reason="no log file for today yet (no players to log)")
    age = now - newest
    if age > 1800 and players_now >= 1:
        return Finding("collector", "fail", value=int(age), threshold=1800,
                       reason=f"newest pulled log is {_fmt_age(age)} old with players on the server",
                       suggest="tail ~/slomix-server-logs/collector.log  # SSH banner timeouts and stale paths land here")
    if age > 6 * 3600:
        return Finding("collector", "warn", value=int(age), threshold=6 * 3600,
                       reason=f"newest pulled log is {_fmt_age(age)} old")
    return Finding("collector", "ok", value=int(age))


def check_lua(fh: dict[str, Any] | None) -> Finding:
    if fh is None:
        return Finding("lua", "unknown", reason="no frame_health log for today")
    if "error" in fh:
        return Finding("lua", "unknown", reason=fh["error"])
    if fh["stalls"] > 2 and fh["players"] > 0:
        return Finding("lua", "warn", value=fh["stalls"], threshold=2,
                       reason=f"{fh['stalls']} frame stalls ≥ 500 ms in 30 min (max {fh['max_gap_ms']} ms, our Lua {fh['lua_ms']} ms of it)",
                       suggest="venv/bin/python scripts/frame_health_report.py ~/slomix-server-logs/frame_health-$(date +%F).log")
    return Finding("lua", "ok", value=fh)


def check_disk(d: dict[str, Any]) -> Finding:
    if d["used_pct"] >= 92:
        return Finding("disk", "fail", value=d["used_pct"], threshold=92, reason=f"root disk {d['used_pct']} % full",
                       suggest="sudo journalctl --vacuum-size=500M ; du -sh /home/samba/share/*/logs")
    if d["used_pct"] >= 85 or (d.get("journal_bytes") or 0) > 2**30:
        return Finding("disk", "warn", value=d, threshold={"used_pct": 85, "journal_bytes": 2**30},
                       reason=f"root disk {d['used_pct']} %, journald {_fmt_bytes(d.get('journal_bytes'))}")
    return Finding("disk", "ok", value=d)


def check_lua_webhook(db: dict[str, Any], now: float) -> Finding:
    if "error" in db:
        return Finding("lua_webhook", "unknown", reason="no database")
    round_age = _age(db.get("newest_round"), now)
    lua_age = _age(db.get("newest_lua_round"), now)
    if round_age is not None and round_age < 6 * 3600 and (lua_age is None or lua_age > round_age + 1800):
        return Finding("lua_webhook", "fail", value={"round_age_s": round_age, "lua_age_s": lua_age},
                       reason="rounds are being imported but the Lua webhook has not written lua_round_teams for them",
                       suggest="check /tmp/slomix_pending_webhooks/ on puran and the bot's control channel  # owner")
    return Finding("lua_webhook", "ok", value={"round_age_s": round_age, "lua_age_s": lua_age})


def check_bot_streaks(data: dict[str, Any] | None, now: float) -> Finding:
    if data is None:
        return Finding("bot_streaks", "unknown", reason="the bot has not written logs/bot_error_streaks.json on this host")
    if "error" in data:
        return Finding("bot_streaks", "unknown", reason=f"streak file {data['error']}")
    written_age = _age(data.get("written_at"), now)
    alerted = sorted(k for k, v in (data.get("streaks") or {}).items() if isinstance(v, dict) and v.get("alerted"))
    if alerted:
        return Finding("bot_streaks", "warn", value=alerted, reason=f"the bot is currently alerting on: {', '.join(alerted)}")
    return Finding("bot_streaks", "ok", value={"written_age_s": written_age, "boot_time": data.get("boot_time")})


# ---------------------------------------------------------------------------
# Policy — what to say, given findings and the state of the last run.
# ---------------------------------------------------------------------------

def decide(findings: list[Finding], state: dict[str, Any], now: float,
           heartbeat_hour: int = HEARTBEAT_HOUR) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Returns (alerts, new_state). Pure: nothing is sent here."""
    keys = state.setdefault("keys", {})
    alerts: list[dict[str, Any]] = []
    for f in findings:
        k = keys.setdefault(f.key, {"level": "ok", "consecutive_fail": 0, "last_alert_at": 0.0})
        was = k.get("level", "ok")
        if f.level == "fail":
            k["consecutive_fail"] = int(k.get("consecutive_fail", 0)) + 1
        else:
            k["consecutive_fail"] = 0
        needed = 2 if f.key in CONFIRM_TWICE else 1
        if f.level == "fail" and k["consecutive_fail"] >= needed and now - float(k.get("last_alert_at", 0)) >= ALERT_DEDUP_S:
            alerts.append({"kind": "fail", "key": f.key, "reason": f.reason, "suggest": f.suggest, "value": f.value})
            k["last_alert_at"] = now
        elif f.level == "warn" and was in ("ok", "unknown") and now - float(k.get("last_alert_at", 0)) >= ALERT_DEDUP_S:
            alerts.append({"kind": "warn", "key": f.key, "reason": f.reason, "suggest": f.suggest, "value": f.value})
            k["last_alert_at"] = now
        elif f.level == "ok" and was in ("fail", "warn") and float(k.get("last_alert_at", 0)) > 0:
            alerts.append({"kind": "recovered", "key": f.key, "reason": f"{f.key} is back to ok"})
            k["last_alert_at"] = 0.0
        k["level"] = f.level
        k["last_seen_at"] = now
    local = dt.datetime.fromtimestamp(now, tz=dt.timezone.utc).astimezone()
    today = local.date().isoformat()
    hour = local.hour
    if state.get("last_heartbeat_date") != today and hour >= heartbeat_hour:
        worst = max((LEVEL_ORDER[f.level] for f in findings), default=0)
        summary = ", ".join(f"{f.key}={f.level}" for f in findings if f.level != "ok") or "all ok"
        alerts.append({"kind": "heartbeat", "key": "heartbeat",
                       "reason": f"daily heartbeat: {summary}", "value": worst})
        state["last_heartbeat_date"] = today
    # Units the register no longer measures do not linger with a stale level.
    live_keys = {f.key for f in findings}
    for stale in [k for k in keys if k not in live_keys]:
        keys.pop(stale, None)
    state["version"] = STATE_VERSION
    state["last_run_at"] = now
    return alerts, state


# ---------------------------------------------------------------------------
# State and outputs
# ---------------------------------------------------------------------------

def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": STATE_VERSION, "keys": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": STATE_VERSION, "keys": {}}
    if data.get("version") != STATE_VERSION:
        return {"version": STATE_VERSION, "keys": {}}
    return data


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)


COLOURS = {"fail": 0xE0443A, "warn": 0xD6A85B, "recovered": 0x4CAF7A, "heartbeat": 0x5B7BD6}


def format_alert(a: dict[str, Any], host: str) -> dict[str, Any]:
    title = {"fail": "✖", "warn": "▲", "recovered": "✔", "heartbeat": "♥"}[a["kind"]] + f" {a['key']} · {host}"
    desc = a["reason"]
    if a.get("suggest"):
        desc += f"\n`{a['suggest']}`"
    return {"title": title[:256], "description": desc[:2000], "color": COLOURS[a["kind"]],
            "footer": {"text": "slomix watchdog · observer, never a supervisor"}}


def send_webhook(url: str, embeds: list[dict[str, Any]], timeout: float = 10.0) -> bool:
    payload = json.dumps({"username": "slomix watchdog", "embeds": embeds[:10]}).encode("utf-8")
    if not url.startswith("https://"):
        return False
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")  # noqa: S310
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310  # operator-configured https webhook
            return resp.status in (200, 204)
    except (urllib.error.URLError, OSError):
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iso(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, (dt.datetime, dt.date)):
        return v.isoformat()
    return str(v)


def _age(iso: str | None, now: float) -> float | None:
    if not iso:
        return None
    try:
        t = dt.datetime.fromisoformat(str(iso))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return max(0.0, now - t.timestamp())


def _fmt_age(seconds: float | None) -> str:
    if seconds is None:
        return "ever"
    if seconds < 90:
        return f"{int(seconds)} s"
    if seconds < 5400:
        return f"{int(seconds // 60)} min"
    return f"{seconds / 3600:.1f} h"


def _fmt_bytes(n: int | None) -> str:
    if n is None:
        return "unknown"
    return f"{n / 2**20:.0f} MB" if n < 2**30 else f"{n / 2**30:.1f} GB"


def parse_journal_usage(raw: str) -> int | None:
    """`Archived and active journals take up 1.2G in the file system.`"""
    import re
    m = re.search(r"take up ([0-9.]+)([KMGT])", raw)
    if not m:
        return None
    n, unit = float(m.group(1)), m.group(2)
    return int(n * {"K": 2**10, "M": 2**20, "G": 2**30, "T": 2**40}[unit])


def _wall_to_epoch(wall: int) -> float:
    return wall / 1000.0 if wall > 10**11 else float(wall)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

async def run(cfg: dict[str, str], *, dry_run: bool, now: float | None = None) -> tuple[list[Finding], list[dict[str, Any]]]:
    now = time.time() if now is None else now
    units = [u.strip() for u in cfg["WATCHDOG_UNITS"].split(",") if u.strip()]
    state_path = Path(cfg["WATCHDOG_STATE_FILE"])
    state = load_state(state_path)
    today = dt.datetime.fromtimestamp(now, tz=dt.timezone.utc).astimezone().date().isoformat()
    logs = Path(cfg["WATCHDOG_SERVER_LOGS_DIR"]).expanduser()

    db = await collect_db(cfg)
    players_now = int(db.get("players_now") or 0)
    web_status, web_body = collect_http_json(cfg["WATCHDOG_WEB_URL"].rstrip("/") + "/health")
    live_status, live_body = collect_http_json(cfg["WATCHDOG_WEB_URL"].rstrip("/") + "/api/live/status")
    mtimes = collect_mtimes({
        "frame_health_today": logs / f"frame_health-{today}.log",
        "etconsole_today": logs / f"etconsole-{today}.log",
        "collector_log": logs / "collector.log",
    })
    fh = collect_frame_health(logs / f"frame_health-{today}.log", now=now)
    disk = collect_disk("/")
    streaks = collect_bot_streaks(Path(cfg["WATCHDOG_BOT_STREAKS_FILE"]))
    unit_props = collect_units(units)

    findings: list[Finding] = []
    findings += check_units(unit_props, state.get("snapshot"), units)
    findings.append(check_web(web_status, web_body))
    findings.append(check_db(db))
    findings.append(check_rounds(db, now, int(cfg.get("MONITORING_SERVER_INTERVAL_SECONDS") or 300)))
    findings.append(check_live(live_status, live_body, players_now))
    findings.append(check_collector(mtimes, now, players_now))
    findings.append(check_lua(fh))
    findings.append(check_disk(disk))
    findings.append(check_lua_webhook(db, now))
    findings.append(check_bot_streaks(streaks, now))

    alerts, state = decide(findings, state, now)
    state["snapshot"] = {"units": {u: {"restarts": int((p or {}).get("NRestarts") or 0),
                                        "entered": (p or {}).get("ActiveEnterTimestamp", "")}
                                   for u, p in unit_props.items()}}
    host = os.uname().nodename
    report = {"version": STATE_VERSION, "ran_at": dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat(),
              "host": host, "players_now": players_now, "findings": [f.as_dict() for f in findings],
              "alerts": alerts, "dry_run": dry_run}
    if not dry_run:
        save_json(state_path, state)
    save_json(Path(cfg["WATCHDOG_LAST_FILE"]), report)
    if alerts:
        url = cfg.get("WATCHDOG_WEBHOOK_URL")
        embeds = [format_alert(a, host) for a in alerts]
        if dry_run or not url:
            for e in embeds:
                print(f"[alert{' (dry-run)' if dry_run else ' (no WATCHDOG_WEBHOOK_URL)'}] {e['title']}\n  {e['description']}")
        else:
            ok = send_webhook(url, embeds)
            if not ok:
                print("webhook POST failed", file=sys.stderr)
    return findings, alerts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--once", action="store_true", help="run one cycle (the only mode; the timer repeats it)")
    ap.add_argument("--dry-run", action="store_true", help="measure and print; do not send or persist state")
    ap.add_argument("--json", action="store_true", help="print the full report as JSON")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 when any check fails (for a human at a shell); under the timer the "
                         "findings are the payload and a failing CHECK is not a failing RUN")
    args = ap.parse_args(argv)
    cfg = load_config()
    try:
        findings, alerts = asyncio.run(run(cfg, dry_run=args.dry_run))
    except Exception as e:  # noqa: BLE001 - the run itself broke; say so, exit 2
        print(f"watchdog run failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"findings": [f.as_dict() for f in findings], "alerts": alerts}, indent=2, default=str))
    else:
        width = max(len(f.key) for f in findings)
        for f in findings:
            extra = f.reason or (json.dumps(f.value, default=str) if f.value is not None else "")
            print(f"{f.level:<8} {f.key:<{width}}  {extra[:140]}")
        print(f"alerts: {len(alerts)}")
    # Exit 2 above means the watchdog itself broke. A failing check is a
    # finding, not a broken watchdog: under systemd a non-zero oneshot shows
    # up as a "failed" unit on every tick with a down service, which buries
    # the one signal that matters (the run at 02:41 on 2026-09-07 ran one
    # second after the web restart, saw /health closed, and systemd reported
    # the WATCHDOG failed). --strict keeps the old behaviour for shells.
    if args.strict and any(f.level == "fail" for f in findings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
