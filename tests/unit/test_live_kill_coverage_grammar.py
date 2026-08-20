"""The canary and the parser must agree on what a usable K line is.

`scripts/check_live_kill_coverage.py` compares the engine's kills against the
live stream's K lines. It ran on the server, so it duplicates the parser's
grammar rather than importing `vps_scripts/liveview_parser.py` — the website
package is not deployed there.

Duplication that nothing checks is how the canary would drift into counting
records the pipeline discards: a malformed line would stand in for a genuinely
missing kill and the check would answer OK, which is the one thing it must
never do (CodeRabbit review, #785). So both sides see the same lines here, and
this fails when they disagree.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


canary = _load(_REPO_ROOT / "scripts" / "check_live_kill_coverage.py", "_canary")
parser = _load(_REPO_ROOT / "vps_scripts" / "liveview_parser.py", "_liveview_parser")

# Real shapes plus the ways a truncated write mangles them. Left as bytes for
# the canary (it reads the log in binary — the logs carry NUL bytes) and
# decoded for the parser.
LINES = [
    b"K 1755600000000 3 6 8 100,200,30 110,210,30 78 412",   # ordinary
    b"K 1755600000001 -1 6 8 0,0,0 0,0,0 100 0",             # world kill
    b"K 1755600000002 3 -1 8 0,0,0 0,0,0 100 0",
    b"K 1755600000003 3 6 8 100,200,30 110,210,30 78",       # one field short
    b"K 1755600000004 3 6",                                   # truncated
    b"K notanumber 3 6 8 0,0,0 0,0,0 100 0",                  # bad timestamp
    b"K 1755600000005 x 6 8 0,0,0 0,0,0 100 0",               # bad killer slot
    b"K 1755600000006 3 y 8 0,0,0 0,0,0 100 0",               # bad victim slot
    b"K",                                                     # bare marker
    b"K ",
    b"A 1755600000007 3 120 40 2 1",                          # not a kill at all
    b"M 1755600000008 3:10,20,30",
    b"I 1755600000009 map supply",
    b"",
]


def test_the_two_grammars_agree_line_for_line():
    disagreements = []
    for raw in LINES:
        mine = canary.is_usable_live_kill(raw)
        event = parser.parse_line(raw.decode("utf-8", "replace"))
        theirs = event is not None and event.type == "LIVE_KILL"
        if mine != theirs:
            disagreements.append((raw, mine, theirs))
    assert not disagreements, "canary vs parser:\n" + "\n".join(
        f"  {raw!r}: canary={m}, parser={t}" for raw, m, t in disagreements
    )


def test_the_sample_covers_both_answers():
    """A sample that is all-accept or all-reject would agree vacuously."""
    verdicts = {canary.is_usable_live_kill(raw) for raw in LINES}
    assert verdicts == {True, False}


@pytest.mark.parametrize("bad", [
    b"K 1755600000003 3 6 8 100,200,30 110,210,30 78",
    b"K notanumber 3 6 8 0,0,0 0,0,0 100 0",
    b"K 1755600000005 x 6 8 0,0,0 0,0,0 100 0",
])
def test_malformed_kills_are_not_counted(bad: bytes):
    """These are the lines that would mask a missing kill."""
    assert not canary.is_usable_live_kill(bad)
