"""Formula registry integrity (owner answer B6).

The registry's job is to never lie: unique names, valid statuses, live
versions imported from the owning modules (not hand-copied), and module
paths that actually exist for everything that ships.
"""
from __future__ import annotations

from pathlib import Path

from website.backend.services.formula_registry import get_formula, get_registry

REPO = Path(__file__).resolve().parents[2]


def test_names_unique_and_statuses_valid():
    reg = get_registry()
    names = [e["name"] for e in reg]
    assert len(names) == len(set(names))
    assert {e["status"] for e in reg} <= {"live", "shadow", "research", "proposed"}
    for e in reg:
        for key in ("name", "version", "status", "module", "surface", "summary"):
            assert e.get(key), f"{e.get('name')} missing {key}"


def test_live_and_research_modules_exist():
    for e in get_registry():
        if e["status"] == "proposed":
            continue
        path = e["module"].split(" ")[0]  # strip annotations like "(composite)"
        assert (REPO / path).exists(), f"{e['name']}: {path} does not exist"


def test_live_versions_track_source_constants():
    from website.backend.services.prox_scoring import (
        FORMULA_VERSION as PROX_VERSION,
    )
    from website.backend.services.s_effort_service import (
        FORMULA_VERSION as SE_VERSION,
    )
    assert get_formula("s_effort")["version"] == SE_VERSION
    assert get_formula("adjusted_lifetime")["version"] == SE_VERSION
    assert get_formula("prox_score_web")["version"] == PROX_VERSION


def test_lookup_miss_returns_none():
    assert get_formula("no-such-formula") is None


def test_prediction_status_follows_publish_flag(monkeypatch):
    """The prediction_engine registry entry reports live/shadow from the actual
    PREDICTION_PUBLISH_ENABLED flag, not a hard-coded 'shadow' (Codex #511)."""
    monkeypatch.setenv("PREDICTION_PUBLISH_ENABLED", "false")
    assert get_formula("prediction_engine")["status"] == "shadow"
    monkeypatch.setenv("PREDICTION_PUBLISH_ENABLED", "true")
    entry = get_formula("prediction_engine")
    assert entry["status"] == "live"
    assert "published" in entry["surface"].lower()
