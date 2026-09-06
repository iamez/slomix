"""`GET /api/diagnostics` gained a response_model on 2026-09-06 (#911's
degraded states carried over to the About panel). The model must not
drop or invent a key on either recording the SPA is tested against:

- `api_diagnostics.json` is RECORDED from the live backend (healthy);
- `api_diagnostics_degraded.json` is CONSTRUCTED from the handler's
  branches (a permission-denied table, an empty time block, a monitoring
  table that failed, a pool without stats) and says so in `_note`.

The route serialises with `response_model_exclude_unset`, so a key the
handler never wrote (a failed table's `row_count`) stays absent — the
About panel reads absence as "no count", never as zero — while a null the
handler DID write (`last_recorded_at`) is kept.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from website.backend.routers.diagnostics_router import DiagnosticsReport

FIXTURES = (
    pathlib.Path(__file__).resolve().parents[2]
    / "website" / "frontend" / "src" / "app" / "pages" / "__fixtures__"
)


def _load(name: str) -> dict:
    data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    data.pop("_note", None)
    return data


@pytest.mark.parametrize("name", ["api_diagnostics.json", "api_diagnostics_degraded.json"])
def test_the_model_round_trips_both_recordings_without_loss(name):
    payload = _load(name)
    out = DiagnosticsReport.model_validate(payload).model_dump(mode="json", exclude_unset=True)
    assert out == payload, {
        "missing": sorted(set(payload) - set(out)),
        "invented": sorted(set(out) - set(payload)),
    }


def test_a_failed_table_keeps_no_row_count_key_and_a_real_zero_keeps_it():
    payload = _load("api_diagnostics_degraded.json")
    out = DiagnosticsReport.model_validate(payload).model_dump(mode="json", exclude_unset=True)
    by_name = {t["name"]: t for t in out["tables"]}
    assert "row_count" not in by_name["player_comprehensive_stats"]
    assert by_name["player_comprehensive_stats"]["error"].startswith("permission denied")
    assert by_name["gaming_sessions"]["row_count"] == 0


def test_a_failed_monitoring_table_keeps_its_error_next_to_its_zero():
    """The shape the About panel must read `error` before `count` on."""
    payload = _load("api_diagnostics_degraded.json")
    out = DiagnosticsReport.model_validate(payload).model_dump(mode="json", exclude_unset=True)
    assert out["monitoring"]["voice"] == {"count": 0, "last_recorded_at": None, "error": "query failed"}
    assert out["time"] == {}
    assert out["pool"] == {"connected": False, "reason": "adapter has no pool_stats"}


def test_control_exclude_none_would_have_dropped_the_written_null():
    """Why the route uses exclude_unset and not exclude_none: the guard in
    test_response_models_drop_nothing pins exclude_none to one route, and
    here it would erase a null the handler meant."""
    payload = _load("api_diagnostics_degraded.json")
    out = DiagnosticsReport.model_validate(payload).model_dump(mode="json", exclude_none=True)
    assert "last_recorded_at" not in out["monitoring"]["voice"]


def test_watchdog_summary_reads_the_last_report_or_says_it_never_ran(tmp_path):
    from website.backend.routers.diagnostics_router import read_watchdog_last
    assert read_watchdog_last(str(tmp_path / "missing.json")) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert read_watchdog_last(str(bad)) == {"error": "unreadable"}
    good = tmp_path / "watchdog_last.json"
    good.write_text(json.dumps({
        "version": 1, "ran_at": "2026-09-06T18:00:00+00:00", "host": "samba", "dry_run": False,
        "findings": [{"key": "web", "level": "ok"}, {"key": "collector", "level": "fail"}],
        "alerts": [{"kind": "fail", "key": "collector"}],
    }), encoding="utf-8")
    import datetime as dt
    ran = dt.datetime(2026, 9, 6, 18, 0, tzinfo=dt.timezone.utc).timestamp()
    out = read_watchdog_last(str(good), now=ran + 240)
    assert out["levels"] == {"web": "ok", "collector": "fail"}
    assert out["alerts"] == 1 and out["host"] == "samba" and out["dry_run"] is False
    assert out["age_seconds"] == 240.0


def test_the_model_carries_the_watchdog_key_without_touching_status():
    payload = _load("api_diagnostics.json")
    payload["watchdog"] = {"ran_at": "2026-09-06T18:00:00+00:00", "age_seconds": 12.0, "levels": {"web": "ok"}, "alerts": 0}
    out = DiagnosticsReport.model_validate(payload).model_dump(mode="json", exclude_unset=True)
    assert out["watchdog"]["levels"] == {"web": "ok"}
    assert out["status"] == payload["status"]
