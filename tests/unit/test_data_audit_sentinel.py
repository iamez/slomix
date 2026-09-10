"""The daily data-plausibility sentinel must exist, be wired, and summarize
the audit's --json output correctly (Data Trust pillar B made permanent)."""
from __future__ import annotations

import inspect

from bot.services.monitor_tasks_mixin import (
    _MonitorTasksMixin,  # noqa: SLF001 - the mixin IS the unit under test
)


def _mixin_src() -> str:
    return inspect.getsource(_MonitorTasksMixin)


def test_sentinel_loop_exists_and_is_daily():
    loop = _MonitorTasksMixin.data_plausibility_sentinel
    assert loop.hours == 24.0 and loop.minutes == 0.0 and loop.seconds == 0.0


def test_bot_starts_the_sentinel():
    import bot.ultimate_bot as ub
    assert "data_plausibility_sentinel.start()" in inspect.getsource(ub)


def test_summary_is_none_when_clean():
    payload = [{"name": "a", "live": 0}, {"name": "b", "live": 0}]
    assert _MonitorTasksMixin._summarize_audit_payload(payload) is None  # noqa: SLF001
    assert _MonitorTasksMixin._summarize_audit_payload({"rules": payload}) is None  # noqa: SLF001


def test_summary_lists_firing_rules():
    payload = [{"name": "pcs_kills_rate", "live": 3}, {"name": "ok", "live": 0}]
    body = _MonitorTasksMixin._summarize_audit_payload(payload)  # noqa: SLF001
    assert body and "pcs_kills_rate" in body and "3" in body


def test_summary_reports_shape_drift_instead_of_swallowing_it():
    assert _MonitorTasksMixin._summarize_audit_payload({"weird": True}) is not None  # noqa: SLF001
