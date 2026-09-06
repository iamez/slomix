"""scripts/slomix_watchdog.py — the judgement is pure, so it is tested
without a system: synthetic inputs, a state dict, a clock.

Controls that must fail are here as tests of the negative: a unit that
vanished from the register is `unknown`, not `ok`; a second failure inside
the dedup hour is silent; a recovery is announced exactly once.
"""
from __future__ import annotations

import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import slomix_watchdog as wd  # noqa: E402

# A local 03:00, so the daily heartbeat (after 09:00 local) stays out of the
# policy tests that are not about it.
NOW = wd.dt.datetime(2026, 9, 6, 3, 0).timestamp()


def _units_ok():
    return {
        "etlegacy-bot": {"LoadState": "loaded", "ActiveState": "active", "SubState": "running",
                         "NRestarts": "0", "ActiveEnterTimestamp": "Sat 2026-09-06 10:00:00 CEST"},
        "etlegacy-web": {"LoadState": "loaded", "ActiveState": "active", "SubState": "running",
                         "NRestarts": "2", "ActiveEnterTimestamp": "Sat 2026-09-06 10:00:00 CEST"},
    }


# ---- units ------------------------------------------------------------------

def test_a_unit_that_is_not_installed_is_unknown_not_inactive():
    props = _units_ok()
    props["slomix-bot"] = {"LoadState": "not-found", "ActiveState": "inactive", "NRestarts": "0"}
    out = {f.key: f for f in wd.check_units(props, None, ["etlegacy-bot", "etlegacy-web", "slomix-bot"])}
    assert out["unit:slomix-bot"].level == "unknown"
    assert "not installed" in out["unit:slomix-bot"].reason
    assert out["unit:etlegacy-bot"].level == "ok"


def test_control_a_unit_missing_from_systemctl_is_unknown_not_ok():
    """The mutation kept as a test: a unit systemctl could not be asked about
    must not pass."""
    out = wd.check_units({"etlegacy-bot": None}, None, ["etlegacy-bot"])
    assert out[0].level == "unknown"


def test_a_restart_since_the_last_run_is_a_warning_with_the_journal_command():
    props = _units_ok()
    props["etlegacy-web"]["NRestarts"] = "3"
    previous = {"units": {"etlegacy-web": {"restarts": 2, "entered": "Sat 2026-09-06 10:00:00 CEST"}}}
    out = {f.key: f for f in wd.check_units(props, previous, ["etlegacy-web"])}
    assert out["unit:etlegacy-web"].level == "warn"
    assert "journalctl" in out["unit:etlegacy-web"].suggest


def test_an_inactive_unit_fails_and_suggests_status_not_restart():
    props = _units_ok()
    props["etlegacy-bot"]["ActiveState"] = "failed"
    out = wd.check_units(props, None, ["etlegacy-bot"])[0]
    assert out.level == "fail"
    assert "restart" not in out.suggest


# ---- web / db / rounds / live / collector / lua / disk / webhook -------------

def test_web_needs_200_and_status_ok():
    assert wd.check_web(200, {"status": "ok", "database": "ok"}).level == "ok"
    assert wd.check_web(503, None).level == "fail"
    assert wd.check_web(None, None).level == "fail"
    assert wd.check_web(200, "<html>").level == "fail"


def test_db_connection_pressure_is_a_warning():
    assert wd.check_db({"error": "connect: OSError"}).level == "fail"
    assert wd.check_db({"connections": 95, "max_connections": 100}).level == "warn"
    assert wd.check_db({"connections": 5, "max_connections": 100}).level == "ok"


def test_rounds_fail_when_the_bots_monitor_stopped_writing():
    db = {"newest_server_status": wd.dt.datetime.fromtimestamp(NOW - 3600, wd.dt.timezone.utc).isoformat(),
          "players_now": 0, "newest_round": None}
    f = wd.check_rounds(db, NOW)
    assert f.level == "fail" and "300 s monitor" in f.reason


def test_rounds_warn_only_when_players_are_on_and_no_round_lands():
    fresh = wd.dt.datetime.fromtimestamp(NOW - 60, wd.dt.timezone.utc).isoformat()
    old = wd.dt.datetime.fromtimestamp(NOW - 3 * 3600, wd.dt.timezone.utc).isoformat()
    assert wd.check_rounds({"newest_server_status": fresh, "players_now": 6, "newest_round": old}, NOW).level == "warn"
    assert wd.check_rounds({"newest_server_status": fresh, "players_now": 0, "newest_round": old}, NOW).level == "ok"


def test_live_feed_age_matters_only_with_players():
    assert wd.check_live(200, {"newest_age_seconds": 900}, players_now=0).level == "ok"
    assert wd.check_live(200, {"newest_age_seconds": 900}, players_now=3).level == "warn"
    assert wd.check_live(200, {"newest_age_seconds": None}, players_now=3).level == "warn"
    assert wd.check_live(None, None, players_now=0).level == "unknown"  # the web finding owns that alert
    assert wd.check_live(500, None, players_now=0).level == "fail"


def test_collector_without_todays_file_is_unknown_when_nobody_plays_and_fail_when_they_do():
    assert wd.check_collector({"frame_health_today": None, "etconsole_today": None}, NOW, 0).level == "unknown"
    assert wd.check_collector({"frame_health_today": None, "etconsole_today": None}, NOW, 2).level == "fail"
    assert wd.check_collector({"frame_health_today": NOW - 100, "etconsole_today": None}, NOW, 2).level == "ok"
    assert wd.check_collector({"frame_health_today": NOW - 3600, "etconsole_today": None}, NOW, 2).level == "fail"


def test_lua_stalls_threshold_and_missing_log():
    assert wd.check_lua(None).level == "unknown"
    assert wd.check_lua({"stalls": 2, "players": 4, "max_gap_ms": 700, "lua_ms": 10}).level == "ok"
    assert wd.check_lua({"stalls": 3, "players": 4, "max_gap_ms": 700, "lua_ms": 10}).level == "warn"
    assert wd.check_lua({"stalls": 9, "players": 0, "max_gap_ms": 700, "lua_ms": 10}).level == "ok"


def test_disk_thresholds():
    assert wd.check_disk({"used_pct": 50.0, "free_gb": 10, "journal_bytes": 10}).level == "ok"
    assert wd.check_disk({"used_pct": 86.0, "free_gb": 3, "journal_bytes": 10}).level == "warn"
    assert wd.check_disk({"used_pct": 50.0, "free_gb": 10, "journal_bytes": 3 * 2**30}).level == "warn"
    assert wd.check_disk({"used_pct": 93.0, "free_gb": 1, "journal_bytes": 10}).level == "fail"


def test_lua_webhook_fails_only_when_rounds_land_without_lua_rows():
    r = wd.dt.datetime.fromtimestamp(NOW - 600, wd.dt.timezone.utc).isoformat()
    assert wd.check_lua_webhook({"newest_round": r, "newest_lua_round": r}, NOW).level == "ok"
    assert wd.check_lua_webhook({"newest_round": r, "newest_lua_round": None}, NOW).level == "fail"
    old = wd.dt.datetime.fromtimestamp(NOW - 10 * 3600, wd.dt.timezone.utc).isoformat()
    assert wd.check_lua_webhook({"newest_round": old, "newest_lua_round": None}, NOW).level == "ok"


def test_bot_streak_file_is_read_for_liveness_and_current_alerts_only():
    assert wd.check_bot_streaks(None, NOW).level == "unknown"
    assert wd.check_bot_streaks({"error": "version 2 not understood"}, NOW).level == "unknown"
    data = {"version": 1, "written_at": "2026-09-06T10:00:00+00:00", "boot_time": "x",
            "streaks": {"ssh_monitor": {"count": 3, "alerted": True}, "proximity": {"count": 1, "alerted": False}}}
    f = wd.check_bot_streaks(data, NOW)
    assert f.level == "warn" and f.value == ["ssh_monitor"]


# ---- policy -----------------------------------------------------------------

def _f(key, level, reason="r"):
    return wd.Finding(key, level, reason=reason)


def test_fail_alerts_once_then_is_silent_for_an_hour_then_recovers_once():
    state = {"version": 1, "keys": {}}
    a1, state = wd.decide([_f("db", "fail")], state, NOW)
    assert [a["kind"] for a in a1] == ["fail"]
    a2, state = wd.decide([_f("db", "fail")], state, NOW + 600)
    assert a2 == []  # dedup
    a3, state = wd.decide([_f("db", "fail")], state, NOW + 3700)
    assert [a["kind"] for a in a3] == ["fail"]  # an hour later, once more
    a4, state = wd.decide([_f("db", "ok")], state, NOW + 4000)
    assert [a["kind"] for a in a4] == ["recovered"]
    a5, state = wd.decide([_f("db", "ok")], state, NOW + 4300)
    assert a5 == []  # recovery is announced exactly once


def test_web_and_lua_webhook_need_two_consecutive_failures():
    state = {"version": 1, "keys": {}}
    a1, state = wd.decide([_f("web", "fail")], state, NOW)
    assert a1 == []
    a2, state = wd.decide([_f("web", "fail")], state, NOW + 300)
    assert [a["kind"] for a in a2] == ["fail"]
    # an ok in between resets the count
    state = {"version": 1, "keys": {}}
    wd.decide([_f("web", "fail")], state, NOW)
    wd.decide([_f("web", "ok")], state, NOW + 300)
    a3, _ = wd.decide([_f("web", "fail")], state, NOW + 600)
    assert a3 == []


def test_control_without_dedup_the_second_run_alerts_again(monkeypatch):
    """The mutation kept as a test: with the dedup window removed, the same
    failure alerts on every run — the noise the window exists to stop."""
    monkeypatch.setattr(wd, "ALERT_DEDUP_S", 0)
    state = {"version": 1, "keys": {}}
    wd.decide([_f("db", "fail")], state, NOW)
    a2, _ = wd.decide([_f("db", "fail")], state, NOW + 60)
    assert [a["kind"] for a in a2] == ["fail"]


def test_warn_alerts_on_the_transition_only():
    state = {"version": 1, "keys": {}}
    a1, state = wd.decide([_f("disk", "warn")], state, NOW)
    assert [a["kind"] for a in a1] == ["warn"]
    a2, state = wd.decide([_f("disk", "warn")], state, NOW + 600)
    assert a2 == []


def test_heartbeat_once_a_day_after_the_hour():
    state = {"version": 1, "keys": {}}
    morning = wd.dt.datetime(2026, 9, 7, 9, 5).timestamp()
    a1, state = wd.decide([_f("db", "ok")], state, morning)
    assert [a["kind"] for a in a1] == ["heartbeat"]
    a2, state = wd.decide([_f("db", "ok")], state, morning + 3600)
    assert a2 == []
    early = wd.dt.datetime(2026, 9, 8, 7, 0).timestamp()
    a3, state = wd.decide([_f("db", "ok")], state, early)
    assert a3 == []


def test_stale_keys_leave_the_state():
    state = {"version": 1, "keys": {"unit:gone": {"level": "fail", "consecutive_fail": 5, "last_alert_at": NOW}}}
    _, state = wd.decide([_f("db", "ok")], state, NOW)
    assert "unit:gone" not in state["keys"]


# ---- state file and config ---------------------------------------------------

def test_state_round_trips_and_an_unknown_version_starts_empty(tmp_path):
    p = tmp_path / "state.json"
    wd.save_json(p, {"version": 1, "keys": {"db": {"level": "fail"}}})
    assert wd.load_state(p)["keys"]["db"]["level"] == "fail"
    p.write_text(json.dumps({"version": 99, "keys": {"db": {"level": "fail"}}}))
    assert wd.load_state(p) == {"version": 1, "keys": {}}


def test_config_reads_the_root_env_and_the_environment_wins(tmp_path):
    (tmp_path / ".env").write_text("POSTGRES_USER=website_app\nPOSTGRES_PASSWORD=x\nWATCHDOG_WEB_URL=http://a\n")
    cfg = wd.load_config(tmp_path, environ={"WATCHDOG_WEB_URL": "http://b"})
    assert cfg["WATCHDOG_WEB_URL"] == "http://b"
    assert cfg["WATCHDOG_DB_USER"] == "etlegacy_user"  # never the website role
    assert cfg["WATCHDOG_STATE_FILE"].endswith("logs/watchdog_state.json")


def test_journal_usage_parses_the_human_line():
    assert wd.parse_journal_usage("Archived and active journals take up 1.2G in the file system.") == int(1.2 * 2**30)
    assert wd.parse_journal_usage("garbage") is None


def test_alert_formatting_names_the_host_and_keeps_the_command():
    e = wd.format_alert({"kind": "fail", "key": "web", "reason": "down", "suggest": "ss -ltnp"}, "samba")
    assert e["title"].startswith("✖ web · samba")
    assert "`ss -ltnp`" in e["description"]
