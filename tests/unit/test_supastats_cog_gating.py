"""Supastats cog QA (2026-08-18): small non-sheet images must not DM.

On 2026-08-18 superboyy's meme pastes (1-9 KB) produced 8 noise DMs, while
the real sheet (26 KB) produced the one report that mattered. Auto-triggered
detection failures below SMALL_IMAGE_BYTES are now logged, not DMed; an
explicit !supacheck still always reports back.
"""
# ruff: noqa: SLF001 — the DM gating lives in private cog methods; testing it
# through Discord's public surface would need a full gateway session.
from __future__ import annotations

from types import SimpleNamespace

import pytest

import bot.cogs.supastats_cog as supastats_cog
from bot.cogs.supastats_cog import PNG_MAGIC, SMALL_IMAGE_BYTES, SupastatsCog
from bot.services.supastats_image_reader import UnsupportedScreenshot


def _cog_with_captured_dms(monkeypatch):
    bot = SimpleNamespace(config=SimpleNamespace(
        supastats_check_enabled=True,
        supastats_channel_id=1,
        supastats_author_ids=[42],
        owner_user_id=7,
    ))
    cog = SupastatsCog.__new__(SupastatsCog)
    cog.bot = bot
    cog.config = bot.config
    cog._handled = []
    dms: list[list[str]] = []

    async def fake_dm(lines):
        dms.append(list(lines))
    cog._dm = fake_dm

    def raise_unsupported(data):
        raise UnsupportedScreenshot("separator strip not found — not a supastats sheet")
    monkeypatch.setattr(supastats_cog, "read_supastats_image", raise_unsupported)
    return cog, dms


def _message():
    async def add_reaction(emoji):
        pass
    return SimpleNamespace(
        author=SimpleNamespace(display_name="superboyy"),
        channel=SimpleNamespace(name="slomix", id=1),
        add_reaction=add_reaction,
    )


def _attachment(size: int):
    async def read():
        return PNG_MAGIC + b"\x00" * 64
    return SimpleNamespace(filename="slika.png", size=size, read=read)


@pytest.mark.asyncio
async def test_auto_small_non_sheet_is_silent(monkeypatch):
    cog, dms = _cog_with_captured_dms(monkeypatch)
    await cog._run_check(_message(), _attachment(5 * 1024), source="auto")
    assert dms == []  # meme paste: log only, no DM


@pytest.mark.asyncio
async def test_auto_large_non_sheet_still_dms(monkeypatch):
    # A big image that fails detection may be a real sheet at a different
    # zoom — the owner must see it.
    cog, dms = _cog_with_captured_dms(monkeypatch)
    await cog._run_check(_message(), _attachment(SMALL_IMAGE_BYTES + 1), source="auto")
    assert len(dms) == 1
    assert any("cannot read this screenshot" in line for line in dms[0])


@pytest.mark.asyncio
async def test_manual_supacheck_always_reports(monkeypatch):
    cog, dms = _cog_with_captured_dms(monkeypatch)
    await cog._run_check(_message(), _attachment(5 * 1024), source="manual")
    assert len(dms) == 1
    assert any("cannot read this screenshot" in line for line in dms[0])


# ── reactions on the sheet post (2026-08-18) ─────────────────────────

def _reacting_message():
    reactions: list[str] = []

    async def add_reaction(emoji):
        reactions.append(emoji)
    msg = SimpleNamespace(
        author=SimpleNamespace(display_name="superboyy"),
        channel=SimpleNamespace(name="slomix", id=1),
        add_reaction=add_reaction,
    )
    return msg, reactions


@pytest.mark.asyncio
async def test_small_non_sheet_gets_no_reaction(monkeypatch):
    cog, _ = _cog_with_captured_dms(monkeypatch)
    msg, reactions = _reacting_message()
    await cog._run_check(msg, _attachment(5 * 1024), source="auto")
    assert reactions == []


@pytest.mark.asyncio
async def test_large_non_sheet_gets_cross(monkeypatch):
    cog, _ = _cog_with_captured_dms(monkeypatch)
    msg, reactions = _reacting_message()
    await cog._run_check(msg, _attachment(SMALL_IMAGE_BYTES + 1), source="auto")
    assert reactions == ["❌"]


async def _run_success_path(monkeypatch, report_text):
    cog, dms = _cog_with_captured_dms(monkeypatch)
    fake_sheet = SimpleNamespace(map_count=8, kills=[1] * 6,
                                 kills_checksum_ok=True, map_points=None)
    monkeypatch.setattr(supastats_cog, "read_supastats_image",
                        lambda data: fake_sheet)

    async def fake_compare(sheet, date_override):
        return report_text
    cog._compare = fake_compare
    msg, reactions = _reacting_message()
    await cog._run_check(msg, _attachment(26 * 1024), source="auto")
    return reactions, dms


@pytest.mark.asyncio
async def test_matching_sheet_gets_checkmark(monkeypatch):
    reactions, dms = await _run_success_path(
        monkeypatch, "✅ everything comparable matches")
    assert reactions == ["✅"]
    assert len(dms) == 1


@pytest.mark.asyncio
async def test_mismatching_sheet_gets_warning(monkeypatch):
    reactions, _ = await _run_success_path(
        monkeypatch, "kills differ: squaze map 3 sheet=41 ours=38")
    assert reactions == ["⚠️"]
