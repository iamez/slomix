"""Human-thread narrative slot (TOK H Steber B, Val H2).

The story behind the numbers: when a roster player is on an active sick-leave
identity link (a fresh guid taken on purpose so an injury/off-form run doesn't
stain the career record — the carniee/ownator case), the session recap names it.

These lock the two ways that slot breaks quietly:
  1. a lead template grows a placeholder the caller doesn't fill (KeyError at
     render, blanking the whole recap), and
  2. the picker stops selecting the strongest alt, or reacts to a non-alt /
     inactive link (attribution on someone it shouldn't touch).
The GUID-width normalisation (32-char KIS board vs 8-char identity key) is the
subtle one — it silently matched nothing until fixed, so it gets its own case.
"""

from __future__ import annotations

import types

import pytest

from website.backend.services.storytelling.narrative import (
    _HUMAN_INJURY_LEADS,
    _HUMAN_SEPARATE_LEADS,
    _NarrativeMixin,
)


@pytest.mark.parametrize("template", [*_HUMAN_INJURY_LEADS, *_HUMAN_SEPARATE_LEADS])
def test_lead_templates_take_exactly_subject_and_stat(template):
    """Every lead renders from {subject}+{stat} alone, with no leftover braces."""
    rendered = template.format(subject="SUBJ", stat="STAT")
    assert "SUBJ" in rendered and "STAT" in rendered
    assert "{" not in rendered and "}" not in rendered


def _thread_fn(links: dict):
    """Return _collect_human_thread bound to a stub self, with
    fetch_identity_links stubbed to yield `links` — no DB, no network."""
    runner = types.SimpleNamespace(db=object())

    async def _fake_fetch(_db, _guids):
        return links

    # _collect_human_thread does `from ...api_helpers import fetch_identity_links`
    # at call time; patch the source module attribute it resolves.
    import website.backend.routers.api_helpers as helpers
    helpers.fetch_identity_links = _fake_fetch  # type: ignore[assignment]
    return _NarrativeMixin._collect_human_thread.__get__(runner)  # noqa: SLF001


@pytest.mark.asyncio
async def test_picks_strongest_active_injury_alt():
    # KIS board is KIS-descending; the alt is #2 (32-char proximity guid).
    board = [
        {"guid": "AAAAAAAA1111111111111111", "name": "topdog"},
        {"guid": "EF561EAA92BE11A8E562A904A262C4C6", "name": "ownator"},
    ]
    links = {  # keyed by 8-char UPPER, as the DB stores it
        "EF561EAA": {
            "role": "alt", "link_type": "sick_leave", "reason": "injury",
            "active": True, "primary_name": "ownator",
        }
    }
    thread = await _thread_fn(links)(board, seed=0)
    assert "injury" in thread.lower()
    assert "#2 by Kill-Impact" in thread  # anchored on the alt's KIS rank


@pytest.mark.asyncio
async def test_rename_names_primary_but_same_handle_does_not():
    board = [{"guid": "EF561EAA92BE11A8E562A904A262C4C6", "name": "ownator"}]
    same = {"EF561EAA": {"role": "alt", "reason": "injury", "active": True,
                         "primary_name": "ownator"}}
    diff = {"EF561EAA": {"role": "alt", "reason": "injury", "active": True,
                         "primary_name": "carniee"}}
    assert "is carniee" in await _thread_fn(diff)(board, 0)
    assert "is ownator" not in await _thread_fn(same)(board, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("links", [
    {},  # nobody on a link
    {"EF561EAA": {"role": "primary", "alts": []}},        # a primary, not an alt
    {"EF561EAA": {"role": "alt", "reason": "injury", "active": False,
                  "primary_name": "x"}},                   # sick leave ended
])
async def test_no_thread_when_no_active_alt(links):
    board = [{"guid": "EF561EAA92BE11A8E562A904A262C4C6", "name": "ownator"}]
    assert await _thread_fn(links)(board, 0) == ""


@pytest.mark.asyncio
async def test_empty_board_returns_empty():
    assert await _thread_fn({})([], 0) == ""
