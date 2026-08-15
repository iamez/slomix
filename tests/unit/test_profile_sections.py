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
