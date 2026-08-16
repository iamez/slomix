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
                 rounds_correlated=10, kills_with_round=100, distinct_rounds=10,
                 comparable_link_rows=None, exact_link_rows=None):
        self.kills_row = (kills_total, kills_with_round, distinct_rounds, 5)
        self.kis_row = (kis_rows, 5, 1234.56)
        self.rounds_row = (rounds_total, rounds_correlated)
        # Default: every comparable row is an exact link (healthy) unless a
        # test overrides it to exercise the wrong-round-linkage path.
        comparable = kills_with_round if comparable_link_rows is None else comparable_link_rows
        exact = comparable if exact_link_rows is None else exact_link_rows
        self.wrong_link_row = (comparable, exact)
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
        if "comparable_rows" in q and "exact_rows" in q:
            return self.wrong_link_row
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
async def test_endpoint_flags_wrong_round_linkage_distinct_from_missing_link():
    """Codex §18 / L1 methodology: a non-NULL round_id only proves a kill
    points at SOME round, not the CORRECT one. 100/100 kills have a
    round_id (linkage_ratio healthy), but 5 of those point at the WRONG
    round (round_start_unix mismatch) — must surface as its own warning
    and degrade status, not be hidden by a healthy linkage_ratio."""
    db = _ComplianceFakeDb(
        kills_total=100, kis_rows=100, kills_with_round=100,
        comparable_link_rows=100, exact_link_rows=95,
    )
    result = await get_storytelling_completeness("2026-04-21", db)

    assert result["wrong_round_kills"] == 5
    assert result["status"] == "degraded"
    wrong_link_warnings = [
        w for w in result["warnings"] if "NAPAČNO rundo" in w["message"]
    ]
    assert len(wrong_link_warnings) == 1


@pytest.mark.asyncio
async def test_endpoint_wrong_link_query_excludes_zero_round_start_unix():
    """Both proximity_kill_outcome.round_start_unix and rounds.round_start_unix
    default to 0 (not NULL) for legacy/unset rows — an IS NOT NULL-only check
    would count a 0-vs-0 pair as a "comparable, exact" match, when neither
    side ever recorded a real timestamp. The query must require > 0 on both
    sides (Copilot review on #525)."""
    db = _ComplianceFakeDb()
    await get_storytelling_completeness("2026-04-21", db)

    wrong_link_queries = [q for q in db.queries if "comparable_rows" in q and "exact_rows" in q]
    assert len(wrong_link_queries) == 1
    q = wrong_link_queries[0]
    assert "pko.round_start_unix > 0" in q
    assert "r.round_start_unix > 0" in q


@pytest.mark.asyncio
async def test_endpoint_status_ok_when_fully_healthy():
    db = _ComplianceFakeDb(kills_total=100, kis_rows=100, kills_with_round=100)
    result = await get_storytelling_completeness("2026-04-21", db)

    assert result["status"] == "ok"
    assert result["wrong_round_kills"] == 0
    assert result["unlinked_kills"] == 0


@pytest.mark.asyncio
async def test_endpoint_status_no_data_when_no_kills():
    db = _ComplianceFakeDb(kills_total=0, kis_rows=0, kills_with_round=0)
    result = await get_storytelling_completeness("2026-04-21", db)

    assert result["status"] == "no_data"


@pytest.mark.asyncio
async def test_endpoint_returns_known_issues_panel_always():
    """Sistemska opozorila so vedno prikazana — ne glede na popolnost."""
    db = _ComplianceFakeDb(kills_total=0)
    result = await get_storytelling_completeness("2026-04-21", db)
    assert "known_issues" in result
    keys = {ki["key"] for ki in result["known_issues"]}
    assert {"time_played_per_player", "headshot_pct", "distance_mult_hardcoded"} <= keys


# ---------------------------------------------------------------------------
# Session scope (2026-08-17)
#
# The Smart Stats page used this endpoint's ratio to qualify a SESSION-scoped
# number ("Total KIS (N% scored)") while asking it a DATE-wide question. One
# calendar date can hold several gaming sessions — 2026-03-25 held four — so on
# those dates the label described a different population than the number it sat
# on. The endpoint now answers per session when asked.
# ---------------------------------------------------------------------------

class _ScopeStub:
    dates = ("2026-03-25",)

    def round_key_arrays(self):
        return ([1_700_000_000], ["supply"], [1])

    def round_key_filter_sql(self, first_param, alias=""):
        prefix = f"{alias}." if alias else ""
        return f"ROUNDKEY({prefix}round_start_unix, ${first_param})"


@pytest.mark.asyncio
async def test_a_session_id_scopes_every_query_to_that_session(monkeypatch):
    from website.backend.routers import diagnostics_router as mod

    async def _fake_resolve(db, *, gaming_session_id=None, session_date=None):
        assert gaming_session_id == 138
        return _ScopeStub()

    monkeypatch.setattr(mod, "resolve_gaming_session_scope", _fake_resolve)
    db = _ComplianceFakeDb(kills_total=100, kis_rows=40, kills_with_round=100)

    result = await get_storytelling_completeness(None, db, 138)

    assert result["scope"] == "gaming_session"
    assert result["gaming_session_id"] == 138
    assert result["session_date"] == "2026-03-25"
    # Every counting query must carry the round-key filter. A query left on the
    # bare date would silently re-introduce the day-wide answer for one of the
    # four numbers while the others were session-scoped.
    counting = [q for q in db.queries if "session_date" in q]
    assert counting, "no scoped query ran"
    for q in counting:
        assert "ROUNDKEY(" in q, q
        assert "session_date = ANY($1)" in q, q


@pytest.mark.asyncio
async def test_the_date_path_is_untouched():
    """The legacy caller (system overview, direct links) still gets the day."""
    db = _ComplianceFakeDb(kills_total=10, kis_rows=10, kills_with_round=10)

    result = await get_storytelling_completeness("2026-04-21", db)

    assert result["scope"] == "date"
    assert result["gaming_session_id"] is None
    assert all("ROUNDKEY(" not in q for q in db.queries)


@pytest.mark.asyncio
async def test_asking_about_nothing_is_refused():
    """Neither parameter used to mean "the string 'None'" reaching strptime."""
    db = _ComplianceFakeDb()

    with pytest.raises(HTTPException) as exc:
        await get_storytelling_completeness(None, db, None)

    assert exc.value.status_code == 422
