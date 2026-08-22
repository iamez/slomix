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
from pathlib import Path

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


def test_every_probe_entry_point_is_gated() -> None:
    """A single ungated call site is enough to hitch a production frame."""
    source = _source()
    for marker in ("w6Load", "w6RunBatch"):
        for match in re.finditer(rf"^\s*{marker}\(", source, re.M):
            line_start = source.rfind("\n", 0, match.start())
            preceding = source[max(0, line_start - 600):match.start()]
            assert "config.trace_fixture" in preceding, (
                f"{marker} is called without a nearby trace_fixture gate"
            )


def test_the_probe_says_where_it_may_run() -> None:
    """Prose, deliberately: the next person to read this needs the constraint
    where the code is, not only in a research document."""
    assert _source().count("Local test server only") >= 2
