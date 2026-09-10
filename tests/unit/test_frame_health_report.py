"""scripts/frame_health_report.py — the attribution reader for the v6.13
frame-health log. A synthetic corpus with known sums; the attribution
window is the load-bearing rule and has a control that must fail."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import frame_health_report as fhr  # noqa: E402

CORPUS = """FH init wall=1000 version=6.13 mod=team-lock
FH init wall=1001 version=6.13 mod=proximity_tracker
FH watcher wall=1025 version=6.13
FM wall=5000 mod=stats_discord_webhook self=800 top=sweep:790
FM wall=5010 mod=proximity_tracker self=200 top=sample:150
FH wall=5020 gap=1200 self=200 gs=0 players=6 lt=400000 paused=0
FH wall=9000 gap=3000 self=0 gs=0 players=6 lt=400000 paused=1
FM wall=20000 mod=c0rnp0rn8 self=100 top=store_stats:90
FH wall=60000 gap=600 self=0 gs=2 players=0 lt=1000 paused=0
""".splitlines()


def test_sums_and_attribution_windows():
    r = fhr.parse(CORPUS)
    fhr.attribute(r)
    assert len(r.gaps) == 3 and len(r.fm) == 3 and len(r.inits) == 2
    first = r.gaps[0]
    # Both FM lines fall inside (5020-1200, 5020] and attach to the first gap.
    assert first.modules == {"stats_discord_webhook": 800, "proximity_tracker": 200}
    assert first.tops["stats_discord_webhook"] == "sweep:790"
    # The tracker's self on the gap line and its FM line are the same frame: not summed twice.
    assert first.lua_ms == 1000 and first.residual_ms == 200
    # The paused stall had no module inside it: all residual.
    second = r.gaps[1]
    assert second.paused and second.lua_ms == 0 and second.residual_ms == 3000
    # The c0rnp0rn8 line at wall=20000 belongs to no gap (nothing was slow then).
    assert all("c0rnp0rn8" not in g.modules for g in r.gaps)


def test_render_says_who_owned_the_stalls():
    out = fhr.render(fhr.parse(CORPUS), burst_gap_ms=30000, min_gap=100)
    assert "our Lua: 1000 ms" in out
    assert "residual (engine/host): 3800 ms" in out
    assert "stalls while paused: 1" in out
    assert "on an empty server: 1" in out
    assert "stats_discord_webhook/sweep×1" in out
    assert "modules that proved their write path: proximity_tracker, team-lock" in out


def test_the_window_is_half_open_on_the_right_edge_control():
    # Control that must fail: an FM line ONE ms after the gap's wall is the
    # NEXT frame, not the slow one. If the window were closed on the wrong
    # side this would attribute it.
    lines = ["FM wall=5021 mod=stats_discord_webhook self=800 top=sweep:790",
             "FH wall=5020 gap=1200 self=0 gs=0 players=6 lt=1 paused=0"]
    r = fhr.parse(lines)
    fhr.attribute(r)
    assert r.gaps[0].modules == {}
    # …and one exactly at the wall IS inside.
    r2 = fhr.parse(["FM wall=5020 mod=x self=5 top=a:1", "FH wall=5020 gap=100 self=0 gs=0 players=1"])
    fhr.attribute(r2)
    assert r2.gaps[0].modules == {"x": 5}
    assert r2.gaps[0].lt is None and r2.gaps[0].paused is False  # pre-6.13 line shape still parses
