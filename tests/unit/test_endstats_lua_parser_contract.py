"""endstats.lua writes the file; endstats_parser.py reads it. Hold them together.

The repo's copy of `vps_scripts/endstats.lua` drifted away from the one actually
running on the game server and nobody could tell, because the two are never
compared: the Lua is deployed by hand and the parser only ever sees output from
the deployed copy. By 2026-08-20 the repo copy had lost the block that writes
`VS_HEADER` lines — the marker `endstats_parser.py` uses to attribute a
head-to-head block to a player — so deploying the repo copy would have silently
turned every VS record anonymous. The parser would not have errored; it would
have kept parsing and stored nothing.

These tests state the producer/consumer contract in the repo, where CI can see
it. They cannot reach the game server, so they cannot detect a hand-edit made
there — that is what `scripts/deploy_release.sh` and a checksum comparison are
for. What they do catch is the repo copy losing something the parser needs.
"""
from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LUA = _REPO_ROOT / "vps_scripts" / "endstats.lua"
_PARSER = _REPO_ROOT / "bot" / "endstats_parser.py"


def _lua() -> str:
    return _LUA.read_text(encoding="utf-8")


def _known_awards() -> set[str]:
    src = _PARSER.read_text(encoding="utf-8")
    block = re.search(r"KNOWN_AWARDS\s*=\s*[\{\[](.*?)[\}\]]", src, re.S)
    assert block, "KNOWN_AWARDS not found — the parser was restructured"
    return set(re.findall(r"[\"']([^\"']+)[\"']", block.group(1)))


def test_endstats_lua_is_present_and_substantial():
    """Guards every check below from passing against a missing or stub file."""
    assert _LUA.is_file(), f"{_LUA} is gone"
    assert len(_lua()) > 40_000, "endstats.lua is far smaller than expected"


def test_vs_header_is_written():
    """Without this line every VS block is attributed to nobody."""
    lua = _lua()
    assert 'VS_HEADER\\t' in lua or '"VS_HEADER"' in lua or "VS_HEADER" in lua, (
        "endstats.lua no longer writes VS_HEADER, but bot/endstats_parser.py "
        "still keys head-to-head attribution on it (see its parse loop). "
        "Deploying this copy would store VS rows with no subject."
    )
    # and it must carry both fields the parser reads: name then GUID.
    # Anchored on the string literal, not the word — the comment above the
    # block also says VS_HEADER, and matching that made this test pass while
    # checking nothing.
    hdr = [ln for ln in lua.split("\n") if '"VS_HEADER\\t' in ln]
    assert hdr, "VS_HEADER appears only in a comment, not in a written line"
    assert any("p_name" in ln and "p_guid" in ln for ln in hdr), (
        "the VS_HEADER line does not carry both name and GUID: " + "; ".join(hdr)
    )


def test_every_award_the_lua_emits_is_known_to_the_parser():
    """An unknown award name is dropped silently, not reported."""
    emitted: set[str] = set()
    for table in re.findall(r"^\w*_names\s*=\s*\{(.*?)\}\s*$", _lua(), re.M | re.S):
        emitted |= set(re.findall(r'\[\d+\]\s*=\s*"([^"]+)"', table))
    assert emitted, "no award-name table found — endstats.lua was restructured"

    unknown = sorted(emitted - _known_awards())
    assert not unknown, (
        "endstats.lua emits award names bot/endstats_parser.py does not know:\n  "
        + "\n  ".join(unknown)
        + "\n\nThe parser skips what it does not recognise, so these awards "
        "would vanish without an error. Add them to KNOWN_AWARDS."
    )


def test_stats_path_uses_a_forward_slash():
    """The server is Linux; a backslash makes one filename, not a directory."""
    bad = [
        line.strip()
        for line in _lua().split("\n")
        if "gamestats\\\\" in line
    ]
    assert not bad, (
        "endstats.lua builds its output path with a backslash:\n  "
        + "\n  ".join(bad)
        + "\nOn the game server that writes a single file literally named "
        "'gamestats\\...' instead of one inside gamestats/."
    )
