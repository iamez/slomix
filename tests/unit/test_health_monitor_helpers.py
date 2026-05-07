"""Tests for HealthMonitor pure helpers + init thresholds.

The health monitor is the operator-facing alarm for bot internals
(memory, errors, SSH/DB hiccups). A regression silently:

- _analyze_health_data thresholds drift → alerts fire on noise OR
  miss real outages.
- init thresholds default to wrong values when config missing →
  bot ships with wrong sensitivity.

`_analyze_health_data` is the only pure helper (other methods are
all DB/Discord-bound). Pin every threshold + the issue-format.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from bot.services.automation.health_monitor import HealthMonitor


def _make_monitor(config=None):
    """Build a HealthMonitor without spinning up Discord/DB."""
    bot = MagicMock()
    metrics = MagicMock()
    return HealthMonitor(bot=bot, admin_channel_id=42, metrics_logger=metrics, config=config)


# ---------------------------------------------------------------------------
# __init__ — threshold defaults from config (with fallback)
# ---------------------------------------------------------------------------


def test_init_uses_config_thresholds_when_provided():
    cfg = MagicMock()
    cfg.health_alert_cooldown = 600
    cfg.health_error_threshold = 20
    cfg.health_ssh_error_threshold = 8
    cfg.health_db_error_threshold = 12
    m = _make_monitor(config=cfg)
    assert m.alert_cooldown == 600
    assert m.error_threshold == 20
    assert m.ssh_error_threshold == 8
    assert m.db_error_threshold == 12


def test_init_uses_default_thresholds_when_config_none():
    """No config → safe defaults: 300s cooldown, error≤10, ssh≤5, db≤5.
    Pin so a deploy with missing config doesn't ship with wrong
    sensitivity (e.g., alert on every error)."""
    m = _make_monitor(config=None)
    assert m.alert_cooldown == 300
    assert m.error_threshold == 10
    assert m.ssh_error_threshold == 5
    assert m.db_error_threshold == 5


def test_init_starts_in_idle_state():
    """Monitoring not started yet, no last alert/check."""
    m = _make_monitor()
    assert m.is_monitoring is False
    assert m.last_alert_time is None
    assert m.last_check_time is None


def test_init_records_start_time():
    """start_time is set at construction → uptime calc reference."""
    m = _make_monitor()
    assert m.start_time is not None


def test_init_stores_dependencies():
    bot = MagicMock()
    metrics = MagicMock()
    m = HealthMonitor(bot=bot, admin_channel_id=42, metrics_logger=metrics)
    assert m.bot is bot
    assert m.metrics is metrics
    assert m.admin_channel_id == 42


# ---------------------------------------------------------------------------
# _analyze_health_data — issue detection
# ---------------------------------------------------------------------------


def test_analyze_returns_empty_list_when_all_healthy():
    """Healthy: error_count=0, no SSH/DB/Discord errors, low memory.
    Pin so a regression that ALWAYS reports "high error count" is loud."""
    m = _make_monitor()
    out = m._analyze_health_data({
        "error_count": 0,
        "ssh_errors": 0,
        "db_errors": 0,
        "discord_post_errors": 0,
        "ssh_status": "monitoring",
        "memory_mb": 100,
    })
    assert out == []


def test_analyze_flags_high_error_count():
    """error_count > error_threshold (default 10) → issue."""
    m = _make_monitor()
    out = m._analyze_health_data({
        "error_count": 15,
        "ssh_errors": 0,
        "db_errors": 0,
        "discord_post_errors": 0,
        "memory_mb": 100,
    })
    assert any("error count" in s.lower() for s in out)


def test_analyze_does_not_flag_at_threshold_boundary():
    """error_count == error_threshold (10) → NO issue (uses strict >).
    Pin the strict-> so flapping at threshold doesn't oscillate
    alerts on/off."""
    m = _make_monitor()
    out = m._analyze_health_data({
        "error_count": 10,  # exactly at threshold
        "ssh_errors": 0,
        "db_errors": 0,
        "discord_post_errors": 0,
        "memory_mb": 100,
    })
    assert out == []


def test_analyze_flags_ssh_errors():
    m = _make_monitor()
    out = m._analyze_health_data({
        "error_count": 0,
        "ssh_errors": 6,  # > default 5
        "db_errors": 0,
        "discord_post_errors": 0,
        "memory_mb": 100,
    })
    assert any("SSH" in s for s in out)


def test_analyze_flags_db_errors():
    m = _make_monitor()
    out = m._analyze_health_data({
        "error_count": 0,
        "ssh_errors": 0,
        "db_errors": 6,  # > default 5
        "discord_post_errors": 0,
        "memory_mb": 100,
    })
    assert any("Database" in s for s in out)


def test_analyze_flags_any_discord_errors():
    """Discord post errors threshold is 0 (any error → issue). Pin
    the strict-zero policy: failing to post stats is operator-visible."""
    m = _make_monitor()
    out = m._analyze_health_data({
        "error_count": 0,
        "ssh_errors": 0,
        "db_errors": 0,
        "discord_post_errors": 1,  # ANY is an issue
        "memory_mb": 100,
    })
    assert any("Discord" in s for s in out)


def test_analyze_flags_ssh_persistent_errors_at_extreme_count():
    """ssh_status='monitoring' AND ssh_errors > 10 → 'persistent errors'
    second issue (in addition to the regular SSH error count)."""
    m = _make_monitor()
    out = m._analyze_health_data({
        "error_count": 0,
        "ssh_errors": 12,  # both > 5 (regular) AND > 10 (persistent)
        "db_errors": 0,
        "discord_post_errors": 0,
        "ssh_status": "monitoring",
        "memory_mb": 100,
    })
    # Two SSH-related issues should fire
    assert any("SSH" in s for s in out)
    assert any("persistent" in s.lower() for s in out)


def test_analyze_does_not_flag_persistent_when_ssh_status_not_monitoring():
    """ssh_status != 'monitoring' (e.g., 'disabled') → no persistent
    issue even with high ssh_errors. Pin so the SSH-disabled bot
    doesn't false-alert."""
    m = _make_monitor()
    out = m._analyze_health_data({
        "error_count": 0,
        "ssh_errors": 20,
        "db_errors": 0,
        "discord_post_errors": 0,
        "ssh_status": "disabled",
        "memory_mb": 100,
    })
    assert not any("persistent" in s.lower() for s in out)


def test_analyze_flags_high_memory_above_500mb():
    """>500 MB memory → issue. Pin so a memory-leak regression is loud."""
    m = _make_monitor()
    out = m._analyze_health_data({
        "error_count": 0,
        "ssh_errors": 0,
        "db_errors": 0,
        "discord_post_errors": 0,
        "memory_mb": 600,
    })
    assert any("memory" in s.lower() for s in out)


def test_analyze_does_not_flag_at_500mb_boundary():
    """500 MB exactly → NO issue (uses strict >)."""
    m = _make_monitor()
    out = m._analyze_health_data({
        "error_count": 0,
        "ssh_errors": 0,
        "db_errors": 0,
        "discord_post_errors": 0,
        "memory_mb": 500,
    })
    assert out == []


def test_analyze_collects_multiple_issues():
    """Multiple thresholds breached simultaneously → all reported."""
    m = _make_monitor()
    out = m._analyze_health_data({
        "error_count": 50,
        "ssh_errors": 10,
        "db_errors": 8,
        "discord_post_errors": 3,
        "memory_mb": 700,
    })
    # error_count + ssh_errors + db_errors + discord + memory = 5 issues minimum
    assert len(out) >= 5


def test_analyze_uses_custom_thresholds_from_config():
    """If config provides higher thresholds, healthy state extends
    accordingly. Pin so a tunable deployment can suppress noise."""
    cfg = MagicMock()
    cfg.health_alert_cooldown = 300
    cfg.health_error_threshold = 100  # very lenient
    cfg.health_ssh_error_threshold = 100
    cfg.health_db_error_threshold = 100
    m = _make_monitor(config=cfg)
    out = m._analyze_health_data({
        "error_count": 50,  # would breach default (10) but not custom (100)
        "ssh_errors": 50,
        "db_errors": 50,
        "discord_post_errors": 0,
        "memory_mb": 100,
    })
    assert out == []


def test_analyze_handles_missing_optional_keys():
    """Optional fields (ssh_errors, db_errors, etc.) absent → use
    .get() default of 0 → no issue. Pin fail-safe so health checks
    don't crash on partial telemetry."""
    m = _make_monitor()
    out = m._analyze_health_data({"error_count": 0})  # only mandatory key
    assert out == []


def test_analyze_includes_count_in_issue_message():
    """Issue strings include the actual breach number for operator
    triage (NOT just "high errors")."""
    m = _make_monitor()
    out = m._analyze_health_data({
        "error_count": 42,
        "ssh_errors": 0,
        "db_errors": 0,
        "discord_post_errors": 0,
        "memory_mb": 100,
    })
    assert any("42" in s for s in out)
