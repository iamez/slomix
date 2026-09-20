"""Delivery failures use isolated files and in-process collectors, never Discord."""
import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import slomix_watchdog as wd  # noqa: E402

NOW = wd.dt.datetime(2026, 9, 7, 3, 0).timestamp()


@pytest.fixture
def cycle(monkeypatch, tmp_path):
    cfg = wd.load_config(tmp_path, environ={"WATCHDOG_WEBHOOK_URL": "https://example.invalid/test"})
    findings = [wd.Finding("db", "fail", reason="synthetic outage")]
    deliveries = []
    outcome = [False]

    async def db(_):
        return {}

    monkeypatch.setattr(wd, "collect_db", db)
    monkeypatch.setattr(wd, "collect_units", lambda _: {})
    monkeypatch.setattr(wd, "collect_http_json", lambda _: (200, {}))
    monkeypatch.setattr(wd, "collect_mtimes", lambda _: {})
    monkeypatch.setattr(wd, "collect_frame_health", lambda *a, **kw: None)
    monkeypatch.setattr(wd, "collect_disk", lambda _: {})
    monkeypatch.setattr(wd, "collect_bot_streaks", lambda _: None)
    monkeypatch.setattr(wd, "check_units", lambda *a: findings.copy())
    for name in ("web", "db", "rounds", "live", "collector", "lua", "disk", "lua_webhook", "bot_streaks"):
        monkeypatch.setattr(wd, f"check_{name}", lambda *a, key=name: wd.Finding(f"stub:{key}", "ok"))

    def send(url, embeds):
        # Observation must already be durable, but delivery must not be.
        state = wd.load_state(Path(cfg["WATCHDOG_STATE_FILE"]))
        assert state["pending_alerts"]
        deliveries.append(embeds)
        return outcome[0]

    monkeypatch.setattr(wd, "send_webhook", send)

    def run(now=NOW, dry_run=False):
        return asyncio.run(wd.run(cfg, dry_run=dry_run, now=now))

    return cfg, findings, deliveries, outcome, run


def test_failed_alert_retries_without_resetting_observations(cycle):
    cfg, _, deliveries, outcome, run = cycle
    run()
    state = wd.load_state(Path(cfg["WATCHDOG_STATE_FILE"]))
    assert state["keys"]["db"]["consecutive_fail"] == 1
    assert state["keys"]["db"]["last_alert_at"] == 0
    assert state["pending_alerts"][0]["kind"] == "fail"
    outcome[0] = True
    run(NOW + 300)
    state = wd.load_state(Path(cfg["WATCHDOG_STATE_FILE"]))
    assert state["keys"]["db"]["consecutive_fail"] == 2
    assert state["keys"]["db"]["last_alert_at"] == NOW + 300
    assert state["pending_alerts"] == []
    run(NOW + 600)
    assert len(deliveries) == 2


def test_failed_recovery_retries_after_observed_level_already_ok(cycle):
    cfg, findings, deliveries, outcome, run = cycle
    outcome[0] = True
    run()
    findings[0].level = "ok"
    outcome[0] = False
    run(NOW + 300)
    state = wd.load_state(Path(cfg["WATCHDOG_STATE_FILE"]))
    assert state["keys"]["db"]["level"] == "ok"
    assert state["keys"]["db"]["last_alert_at"] == NOW
    outcome[0] = True
    run(NOW + 600)
    run(NOW + 900)
    assert len(deliveries) == 3
    assert deliveries[1][0]["title"].startswith("✔")
    assert deliveries[2][0]["title"].startswith("✔")
    assert wd.load_state(Path(cfg["WATCHDOG_STATE_FILE"]))["keys"]["db"]["last_alert_at"] == 0


def test_failed_heartbeat_retries_and_marks_only_success(cycle):
    cfg, findings, deliveries, outcome, run = cycle
    findings[0].level = "ok"
    morning = wd.dt.datetime(2026, 9, 7, 9, 5).timestamp()
    run(morning)
    assert "last_heartbeat_date" not in wd.load_state(Path(cfg["WATCHDOG_STATE_FILE"]))
    outcome[0] = True
    run(morning + 300)
    run(morning + 600)
    assert len(deliveries) == 2
    assert wd.load_state(Path(cfg["WATCHDOG_STATE_FILE"]))["last_heartbeat_date"] == "2026-09-07"


def test_missing_webhook_never_acknowledges(cycle):
    cfg, _, deliveries, _, run = cycle
    cfg.pop("WATCHDOG_WEBHOOK_URL")
    run()
    assert not deliveries
    assert wd.load_state(Path(cfg["WATCHDOG_STATE_FILE"]))["keys"]["db"]["last_alert_at"] == 0


def test_failed_heartbeat_retries_across_midnight_until_ack(cycle):
    cfg, findings, deliveries, outcome, run = cycle
    findings[0].level = "ok"
    late = wd.dt.datetime(2026, 9, 7, 23, 58).timestamp()
    run(late)
    outcome[0] = True
    run(late + 300)  # 00:03: still owe yesterday's heartbeat.
    assert len(deliveries) == 2
    state = wd.load_state(Path(cfg["WATCHDOG_STATE_FILE"]))
    assert state["last_heartbeat_date"] == "2026-09-07"
    assert state["pending_alerts"] == []
    run(late + 600)
    assert len(deliveries) == 2
    run(wd.dt.datetime(2026, 9, 8, 9, 5).timestamp())
    assert len(deliveries) == 3
    assert wd.load_state(Path(cfg["WATCHDOG_STATE_FILE"]))["last_heartbeat_date"] == "2026-09-08"


def test_new_daily_heartbeat_supersedes_undelivered_previous_day(cycle):
    cfg, findings, deliveries, _, run = cycle
    findings[0].level = "ok"
    run(wd.dt.datetime(2026, 9, 7, 23, 58).timestamp())
    run(wd.dt.datetime(2026, 9, 8, 9, 5).timestamp())
    pending = wd.load_state(Path(cfg["WATCHDOG_STATE_FILE"]))["pending_alerts"]
    assert len(pending) == 1
    assert pending[0]["date"] == "2026-09-08"
    assert [len(batch) for batch in deliveries] == [1, 1]


def test_failed_warning_retries(cycle):
    cfg, findings, deliveries, outcome, run = cycle
    findings[0].level = "warn"
    run()
    outcome[0] = True
    run(NOW + 300)
    run(NOW + 4000)
    assert len(deliveries) == 2
    assert wd.load_state(Path(cfg["WATCHDOG_STATE_FILE"]))["keys"]["db"]["notified_level"] == "warn"


def test_unacknowledged_failure_resolving_does_not_send_false_recovery(cycle):
    cfg, findings, deliveries, _, run = cycle
    run()
    findings[0].level = "ok"
    run(NOW + 300)
    assert len(deliveries) == 1
    assert wd.load_state(Path(cfg["WATCHDOG_STATE_FILE"]))["pending_alerts"] == []


@pytest.mark.parametrize("existing", [False, True])
def test_dry_run_neither_writes_nor_sends(cycle, monkeypatch, existing):
    cfg, _, deliveries, _, run = cycle
    paths = [Path(cfg[k]) for k in ("WATCHDOG_STATE_FILE", "WATCHDOG_LAST_FILE")]
    if existing:
        for path in paths:
            wd.save_json(path, {"version": 1, "keys": {}})
    before = [(p.read_bytes(), p.stat().st_mtime_ns) if p.exists() else None for p in paths]

    def forbidden(*a, **kw):
        pytest.fail("dry-run attempted a filesystem write")

    monkeypatch.setattr(wd, "save_json", forbidden)
    run(dry_run=True)
    assert deliveries == []
    assert [(p.read_bytes(), p.stat().st_mtime_ns) if p.exists() else None for p in paths] == before
    if not existing:
        assert not paths[0].parent.exists()


def test_batches_acknowledge_only_successfully_delivered_entries(cycle):
    cfg, findings, deliveries, outcome, run = cycle
    findings[:] = [wd.Finding(f"test:{i}", "fail") for i in range(12)]
    outcome[0] = True
    run()
    assert [len(batch) for batch in deliveries] == [10, 2]
    state = json.loads(Path(cfg["WATCHDOG_STATE_FILE"]).read_text())
    assert state["pending_alerts"] == []
    assert all(state["keys"][f"test:{i}"]["last_alert_at"] == NOW for i in range(12))


def test_second_batch_failure_does_not_repeat_successful_first_batch(cycle, monkeypatch):
    cfg, findings, _, _, run = cycle
    findings[:] = [wd.Finding(f"test:{i}", "fail") for i in range(12)]
    calls = []

    def send(url, embeds):
        calls.append(embeds)
        return len(calls) != 2

    monkeypatch.setattr(wd, "send_webhook", send)
    run()
    state = wd.load_state(Path(cfg["WATCHDOG_STATE_FILE"]))
    assert [a["key"] for a in state["pending_alerts"]] == ["test:10", "test:11"]
    run(NOW + 300)
    assert [len(batch) for batch in calls] == [10, 2, 2]
    assert wd.load_state(Path(cfg["WATCHDOG_STATE_FILE"]))["pending_alerts"] == []
