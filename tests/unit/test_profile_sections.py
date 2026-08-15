"""The `sections` parameter on /api/players/{id}/profile.

Two heavy sections (aim, advanced) cost 11–17 s on a cold cache while the other
twelve together cost ~500 ms, so the page asks for `core` first and fills the
rest in afterwards. These tests pin the parts of that contract that are easy to
break by accident: the alias meanings, the back-compatible default, and the
registry staying in step with the declared section list.
"""
from __future__ import annotations

import inspect
import re

import pytest
from fastapi import HTTPException

from website.backend.routers import players_profile_router as P
from website.backend.routers.players_profile_router import (
    _HEAVY_SECTIONS,
    _PROFILE_SECTIONS,
    _parse_sections,
    get_player_profile,
)


def test_default_is_every_section():
    """No parameter must mean exactly what it meant before it existed."""
    assert _parse_sections(None, _PROFILE_SECTIONS) == _PROFILE_SECTIONS


def test_core_is_everything_except_the_heavy_two():
    core = _parse_sections("core", _PROFILE_SECTIONS)

    assert core == _PROFILE_SECTIONS - _HEAVY_SECTIONS
    assert "aim" not in core and "advanced" not in core
    # …and it is not a stub: the cheap sections are all still there.
    assert {"weapons", "maps", "relationships", "skill"} <= core


def test_heavy_sections_can_be_fetched_on_their_own():
    assert _parse_sections("aim,advanced", _PROFILE_SECTIONS) == _HEAVY_SECTIONS


def test_all_alias_and_whitespace_and_case():
    assert _parse_sections("all", _PROFILE_SECTIONS) == _PROFILE_SECTIONS
    assert _parse_sections(" AIM , advanced ,", _PROFILE_SECTIONS) == _HEAVY_SECTIONS


def test_core_plus_a_heavy_section_composes():
    got = _parse_sections("core,aim", _PROFILE_SECTIONS)

    assert got == _PROFILE_SECTIONS - {"advanced"}


def test_unknown_section_is_a_400_not_a_silent_empty_profile():
    """Silently dropping a typo would serve a half-empty profile that looks like
    missing data, and the caller would have no way to tell."""
    with pytest.raises(HTTPException) as exc:
        _parse_sections("aim,weapns", _PROFILE_SECTIONS)

    assert exc.value.status_code == 400
    assert "weapns" in exc.value.detail


def test_empty_selection_is_rejected():
    for value in ("", "  ", ",,"):
        with pytest.raises(HTTPException) as exc:
            _parse_sections(value, _PROFILE_SECTIONS)
        assert exc.value.status_code == 400


def test_registry_and_declared_sections_cannot_drift():
    """`_PROFILE_SECTIONS` is what the parameter validates against, while the
    `fetchers` dict inside the handler is what actually runs. If a new section is
    added to one and not the other, the endpoint either 400s on a section it can
    serve or schedules one it never returns."""
    source = inspect.getsource(get_player_profile)
    body = source.split("fetchers = {", 1)[1].split("}", 1)[0]
    registry = set(re.findall(r'"([a-z_]+)":\s*lambda', body))

    assert registry == set(_PROFILE_SECTIONS)


def test_heavy_sections_are_real_sections():
    assert _HEAVY_SECTIONS <= _PROFILE_SECTIONS


# ── handler level ──────────────────────────────────────────────────────────
#
# The parser tests above pin the vocabulary; these pin what the endpoint does
# with it — which sections actually run, what the payload carries, and that the
# 400/404 boundaries did not move.


@pytest.fixture
def stub_profile(monkeypatch):
    """Replace every section fetcher with a recorder, so a call to the handler
    reports exactly which sections were scheduled."""
    called: list[str] = []

    def _stub(name):
        async def _fetch(*_args, **_kwargs):
            called.append(name)
            return {"available": True, "section": name}
        return _fetch

    for name in _PROFILE_SECTIONS:
        attr = "_fetch_aim_summary" if name == "aim" else f"_fetch_{name}"
        monkeypatch.setattr(P, attr, _stub(name))

    async def _lifetime(*_a, **_k):
        called.append("lifetime")
        return {"available": True}

    async def _resolve(_db, identifier):
        return None if identifier == "nobody" else "D8423F90"

    async def _guid32(*_a, **_k):
        called.append("guid32")
        return "D8423F90" + "0" * 24

    monkeypatch.setattr(P, "_fetch_lifetime", _lifetime)
    monkeypatch.setattr(P, "resolve_player_guid", _resolve)
    monkeypatch.setattr(P, "_resolve_guid32", _guid32)
    return called


async def test_core_runs_only_the_cheap_sections(stub_profile):
    payload = await P.get_player_profile("vid", sections="core", db=object())

    ran = set(stub_profile) - {"lifetime", "guid32"}
    assert ran == _PROFILE_SECTIONS - _HEAVY_SECTIONS
    # Not requested → absent, so a caller can tell "not asked for" from "no data".
    assert "aim" not in payload and "advanced" not in payload
    assert payload["weapons"] == {"available": True, "section": "weapons"}
    assert payload["sections"] == sorted(_PROFILE_SECTIONS - _HEAVY_SECTIONS)


async def test_heavy_only_request_skips_the_twelve_cheap_ones(stub_profile):
    payload = await P.get_player_profile("vid", sections="aim,advanced", db=object())

    assert set(stub_profile) - {"lifetime"} == _HEAVY_SECTIONS
    assert set(payload) - {"guid", "generated_at", "sections", "lifetime"} == _HEAVY_SECTIONS
    # guid32 is only needed by relationships; it must not be resolved here.
    assert "guid32" not in stub_profile


async def test_no_parameter_still_returns_the_whole_profile(stub_profile):
    payload = await P.get_player_profile("vid", db=object())

    assert set(stub_profile) - {"lifetime", "guid32"} == _PROFILE_SECTIONS
    assert set(payload) - {"guid", "generated_at", "sections", "lifetime"} == _PROFILE_SECTIONS


async def test_relationships_gets_its_guid32(stub_profile):
    await P.get_player_profile("vid", sections="relationships", db=object())

    assert "guid32" in stub_profile


async def test_unknown_section_is_400_even_for_a_player_that_does_not_exist(stub_profile):
    """The parameter is validated before the lookup: a typo must not come back as
    404 'player not found', which would send the caller hunting the wrong bug."""
    with pytest.raises(HTTPException) as exc:
        await P.get_player_profile("nobody", sections="weapns", db=object())

    assert exc.value.status_code == 400
    assert stub_profile == []      # nothing was scheduled, no lookup happened


async def test_missing_player_is_still_404(stub_profile):
    with pytest.raises(HTTPException) as exc:
        await P.get_player_profile("nobody", sections="core", db=object())

    assert exc.value.status_code == 404


async def test_a_failing_section_does_not_sink_the_others(stub_profile, monkeypatch):
    async def _boom(*_a, **_k):
        raise RuntimeError("proximity table went away")

    monkeypatch.setattr(P, "_fetch_weapons", _boom)

    payload = await P.get_player_profile("vid", sections="core", db=object())

    assert payload["weapons"] == {"available": False, "reason": "error"}
    assert payload["maps"]["available"] is True
