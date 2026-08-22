"""The W6 trace probe must stay dormant in the repository.

This is the capture half of the W6 evidence: it asks the running engine the same
trace question the offline tracer answers, so the two can be compared segment by
segment. It is also the only code in the tracker that deliberately hitches a
frame — 250 traces per batch — so it must never run anywhere but a local test
server, and never by default.

⚠️ The lesson this guard encodes is `shot_fired`'s: that flag was true on the
live server and false in the repository, so the next deploy silently switched
the capture off and gunfire rows stopped dead (2026-08-11). A default that
disagrees with intent is a deploy away from doing damage in either direction —
so the intent is pinned here rather than left in a comment.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

TRACKER = (
    Path(__file__).resolve().parents[2] / "proximity" / "lua" / "proximity_tracker.lua"
)


def _source() -> str:
    return TRACKER.read_text(encoding="utf-8")


def test_trace_fixture_ships_disabled() -> None:
    block = re.search(r"trace_fixture = \{(.*?)\n    \}", _source(), re.S)
    assert block, "trace_fixture config block not found"
    assert re.search(r"\benabled\s*=\s*false\b", block.group(1)), (
        "the W6 probe must ship disabled: it batches 250 traces per frame and "
        "belongs on a local test server only"
    )


#: The runtime entry points, by the names the tracker actually uses.
#:
#: ⚠️ This list was `("w6Load", "w6RunBatch")`. `w6RunBatch` does not exist —
#: the batch function is `w6Step` — and `w6Load` is called as
#: `w6.segments = w6Load(...)`, which a start-of-line pattern never matched. So
#: the test iterated over an empty set and asserted nothing, while passing. That
#: is the failure this repository's own CI comments warn about: a guard that
#: skips looks identical to a guard that holds.
PROBE_ENTRY_POINTS = ("w6Load", "w6Step", "runTraceProbe")


@pytest.mark.parametrize("marker", PROBE_ENTRY_POINTS)
def test_the_entry_point_exists_before_anything_is_asserted_about_it(marker: str) -> None:
    """First prove there is something to guard.

    Without this, renaming a function turns its guard into a no-op that still
    reports green — which is exactly what happened to `w6RunBatch`.
    """
    # Bare name, not `name(`: `runTraceProbe` is handed to `pcall` as a value,
    # so a call-shaped pattern misses it — the same class of near-miss that let
    # the previous version of this file assert nothing.
    uses = [
        m for m in re.finditer(rf"\b{marker}\b", _source())
        if not _source()[:m.start()].rstrip().endswith("local function")
    ]
    assert uses, f"{marker} is never used; the guard below would assert nothing"


@pytest.mark.parametrize("marker", PROBE_ENTRY_POINTS)
def test_every_probe_entry_point_is_gated(marker: str) -> None:
    """A single ungated call site is enough to hitch a production frame."""
    source = _source()
    # Call sites only — skip the definition, which is `local function w6Step(`.
    calls = [
        m for m in re.finditer(rf"\b{marker}\b", source)
        if not source[:m.start()].rstrip().endswith("local function")
    ]
    assert calls, f"{marker}: no call sites found"
    for match in calls:
        preceding = source[max(0, match.start() - 900):match.start()]
        assert "config.trace_fixture" in preceding or "trace_probe" in preceding, (
            f"{marker} is called without a nearby trace_fixture / probe gate"
        )


def test_the_probe_says_where_it_may_run() -> None:
    """Prose, deliberately: the next person to read this needs the constraint
    where the code is, not only in a research document."""
    assert _source().count("Local test server only") >= 2


# --- the probe must prove its premise before the capture runs ---------------


def test_capture_waits_for_the_probe_to_validate_not_merely_to_run() -> None:
    """⭐ "the probe ran" and "the probe proved its preconditions" differ.

    W6's whole verdict rests on `entNum = -2` excluding entity clipping. If it
    does not, every fixture segment measures something other than the world and
    the 99.92% is about nothing. The capture gate must therefore test the
    validated flag, not the config flag and not "the probe finished".
    """
    source = _source()
    gate = re.search(
        r"if config\.trace_fixture and config\.trace_fixture\.enabled"
        r"(.*?)then\s*\n\s*if w6\.segments == nil",
        source, re.S,
    )
    assert gate, "the fixture capture gate was not found"
    assert "trace_probe_validated" in gate.group(1), (
        "the capture runs on the config flag alone; it must require the probe's "
        "verdict"
    )


def test_the_premise_is_only_validated_by_a_discriminating_entity() -> None:
    """Client pairs agreeing proves nothing — with no entity on the segment, -2
    and -1 must agree either way. Only `ent_differ > 0` discriminates."""
    assert re.search(r"trace_probe_validated\s*=\s*\(ent_differ > 0\)", _source())


@pytest.mark.parametrize("control", ["DOWN", "TINY"])
def test_a_wrong_control_stops_the_probe(control: str) -> None:
    """Their results used to be printed and dropped. A probe that answers a
    known question wrong cannot be trusted with an unknown one."""
    source = _source()
    body = source[source.index("local function runTraceProbe"):]
    body = body[: body.index("\nfunction et_RunFrame")]
    assert f'traceProbeOne("{control}"' in body
    assert "REFUSED" in body, "no control refusal path"
    # The refusal must come before the entity sweep, or the probe does the
    # expensive work anyway and reports a verdict it should not have reached.
    assert body.index("REFUSED") < body.index("ent_tested")


# --- a truncated fixture must not load at all -------------------------------

LUA = shutil.which("lua5.4") or shutil.which("lua")

_W6LOAD_HARNESS = """
local src = io.open(%r):read('a')
local block = src:match('(local function w6Load.-\\nend)')
assert(block, 'w6Load not found')
local payload = %s
local et = {
  FS_READ = 0,
  trap_FS_FOpenFile = function() return 7, #payload end,
  trap_FS_Read = function() return payload end,
  trap_FS_FCloseFile = function() end,
  G_Print = function(s) io.stderr:write(s) end,
}
local chunk = assert(load('local et = ... \\n' .. block .. '\\nreturn w6Load'))
local w6Load = chunk(et)
local segs = w6Load('test')
if segs == nil then print('NIL') else print(#segs) end
"""


def _run_w6load(payload: str) -> str:
    script = _W6LOAD_HARNESS % (str(TRACKER), "[==[" + payload + "]==]")
    result = subprocess.run(
        [LUA, "-"], input=script, capture_output=True, text=True, timeout=30, check=True
    )
    return result.stdout.strip()


@pytest.mark.skipif(not LUA, reason="no lua interpreter on this host")
def test_a_complete_fixture_loads_every_segment() -> None:
    payload = (
        "# header\n"
        "0 blocked 0 0 0 100 0 0 blocked 0\n"
        "1 clear 0 0 0 100 0 0 clear 0\n"
        "2 control_down 0 0 56 0 0 -9944 blocked 0\n"
    )
    assert _run_w6load(payload) == "3"


@pytest.mark.skipif(not LUA, reason="no lua interpreter on this host")
def test_a_truncated_line_refuses_the_whole_fixture() -> None:
    """⛔ It used to SKIP the bad line and keep going — the exact opposite of
    the comment above it, which says a truncated file must not quietly become a
    shorter measurement. The load returned a shorter table, the capture wrote
    fewer rows, and the shortfall had to be caught two layers later."""
    payload = (
        "# header\n"
        "0 blocked 0 0 0 100 0 0 blocked 0\n"
        "1 clear 0 0 0 100 0\n"           # cut mid-line, as a truncation does
    )
    assert _run_w6load(payload) == "NIL"


@pytest.mark.skipif(not LUA, reason="no lua interpreter on this host")
def test_a_non_numeric_coordinate_refuses_the_fixture() -> None:
    payload = "# header\n0 blocked 0 0 0 1e0 nan-ish 0 blocked 0\n"
    assert _run_w6load(payload) == "NIL"
