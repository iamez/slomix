"""Contract tests for /diagnostics/storytelling-completeness.

PR #169 changed this endpoint in two ways:
- Removed the unauthenticated auto-trigger of compute_session_kis()
  (was a DoS-shaped write surface).
- Added kis_computed: bool to the response so the UI can decide
  whether to render an "open Smart Stats to compute" hint instead
  of guessing from kis_rows == 0.

Pin both behaviours so a future "improvement" doesn't silently
re-introduce the write side-effect.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from website.backend.routers.diagnostics_router import get_storytelling_completeness


class _ComplianceFakeDb:
    """Scripted DB. Captures all queries to assert no compute path runs."""

    def __init__(self, *, kills_total=100, kis_rows=100, rounds_total=10,
                 rounds_correlated=10, kills_with_round=100, distinct_rounds=10):
        self.kills_row = (kills_total, kills_with_round, distinct_rounds, 5)
        self.kis_row = (kis_rows, 5, 1234.56)
        self.rounds_row = (rounds_total, rounds_correlated)
        self.queries: list[str] = []

    async def fetch_one(self, query, params=None):
        q = str(query)
        self.queries.append(q)
        if "FROM proximity_kill_outcome" in q and "kills_total" in q:
            return self.kills_row
        if "FROM storytelling_kill_impact" in q:
            return self.kis_row
        if "FROM proximity_kill_outcome pko" in q and "rounds_correlated" in q:
            return self.rounds_row
        return None

    async def fetch_all(self, query, params=None):
        return []

    async def execute(self, *args, **kwargs):
        # If anything tries to write, capture it so the test can fail loud
        self.queries.append(f"EXECUTE: {args[0] if args else ''}")
        return "EXECUTE 0"


@pytest.mark.asyncio
async def test_endpoint_does_not_trigger_compute_session_kis():
    """Regression for PR #169: endpoint must be strictly read-only.

    If a future change re-introduces auto-compute, the storytelling
    schema's DELETE+INSERT into storytelling_kill_impact would surface
    in `executed` queries — assert it does not.
    """
    db = _ComplianceFakeDb(kills_total=100, kis_rows=80)
    result = await get_storytelling_completeness("2026-04-21", db)

    # No DELETE / INSERT should have been issued
    write_traces = [q for q in db.queries if "EXECUTE" in q or "DELETE FROM storytelling" in q]
    assert write_traces == [], f"unexpected write side-effects: {write_traces}"
    assert result["kis_computed"] is True


@pytest.mark.asyncio
async def test_endpoint_reports_kis_not_computed_when_rows_zero():
    """When KIS hasn't been computed for the date, kis_computed=False
    AND a non-warning info message guides the user."""
    db = _ComplianceFakeDb(kills_total=100, kis_rows=0)
    result = await get_storytelling_completeness("2026-04-21", db)

    assert result["kis_computed"] is False
    info_warnings = [w for w in result["warnings"] if w["level"] == "info"]
    assert any("Smart Stats še ni izračunan" in w["message"] for w in info_warnings)
    # The "samo X/Y kills imajo KIS" warning must NOT fire when nothing
    # has been computed at all — otherwise it's noise on top of the info hint
    completeness_warnings = [
        w for w in result["warnings"]
        if w["level"] == "warning" and "kills ima KIS izračun" in w["message"]
    ]
    assert completeness_warnings == []


@pytest.mark.asyncio
async def test_endpoint_emits_completeness_warning_when_partially_computed():
    """KIS computed but covers <95% of kills → warning fires."""
    db = _ComplianceFakeDb(kills_total=100, kis_rows=50)
    result = await get_storytelling_completeness("2026-04-21", db)

    assert result["kis_computed"] is True
    completeness_warnings = [
        w for w in result["warnings"]
        if "ima KIS izračun" in w["message"]
    ]
    assert len(completeness_warnings) == 1


@pytest.mark.asyncio
async def test_endpoint_rejects_invalid_session_date():
    db = _ComplianceFakeDb()
    with pytest.raises(HTTPException) as exc:
        await get_storytelling_completeness("not-a-date", db)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_endpoint_returns_known_issues_panel_always():
    """Sistemska opozorila so vedno prikazana — ne glede na popolnost."""
    db = _ComplianceFakeDb(kills_total=0)
    result = await get_storytelling_completeness("2026-04-21", db)
    assert "known_issues" in result
    keys = {ki["key"] for ki in result["known_issues"]}
    assert {"time_played_per_player", "headshot_pct", "distance_mult_hardcoded"} <= keys
