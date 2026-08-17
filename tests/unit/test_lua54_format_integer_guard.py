"""Lua 5.4 forbids %d on a non-integral float — pin every guard we shipped.

LuaJIT/5.1 silently truncated a float fed to string.format("%d", ...); Lua 5.4
(ET:Legacy 2.84.0) raises "number has no integer representation" instead. One
such line, deployed, killed et_InitGame on supply for months: the vehicle scan
threw, the objective scan after it never ran, and the whole round lost its
objective context. The mechanism was also proven as an on-disk event — a pair
of files 15 s apart, byte-identical, both cut off mid-write with a section
header and zero data lines (2026-05-19 204545/204600).

These tests read the Lua sources as text (there is no Lua runtime in CI) and
pin the exact guards, so a refactor that quietly reverts one fails loudly.
"""
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


def _tracker() -> str:
    return _read("proximity/lua/proximity_tracker.lua")


# ---------------------------------------------------------------------------
# proximity_tracker.lua
# ---------------------------------------------------------------------------

def test_the_vehicle_console_print_uses_no_bare_d_on_coordinates():
    """The line that actually crashed et_InitGame. Console-only, so %.0f."""
    src = _tracker()
    assert 'pos=(%d,%d,%d)' not in src
    assert 'pos=(%.0f,%.0f,%.0f) hp=%.0f' in src


def test_the_vehicle_progress_file_write_truncates_toward_zero():
    """File output the parser reads with a bare int(parts[i]) — %.0f would
    round half-to-even where LuaJIT %d truncated, silently changing the data
    contract. The guard is the SHOT_FIRED trunc pattern, applied to all six
    coordinates AND both health fields."""
    src = _tracker()
    i = src.index("# VEHICLE_PROGRESS")
    block = src[i:i + 2000]
    assert "math.floor(v) or math.ceil(v)" in block or "and math.floor" in block
    assert "trunc(veh.start_pos.x)" in block
    assert "trunc(veh.last_pos.z)" in block
    assert "trunc(veh.max_health)" in block
    assert "trunc(veh.last_health)" in block
    # the raw fields must no longer be format arguments
    assert "veh.start_pos.x, veh.start_pos.y" not in block


def test_the_two_init_scans_fail_independently_and_loudly():
    """Bare and sequential, one throw killed both. Each scan gets its own
    pcall, and a failure PRINTS — the etconsole.log line is the only reason
    the original crash was ever found, so never swallow silently."""
    src = _tracker()
    assert "pcall(scanVehicleEntities)" in src
    assert "pcall(scanObjectiveEntities)" in src
    assert "scanVehicleEntities FAILED" in src
    assert "scanObjectiveEntities FAILED" in src
    # the bare sequential form must be gone
    assert "\n    scanVehicleEntities()\n    scanObjectiveEntities()" not in src


def test_round_end_failure_cannot_replay_the_transition_every_frame():
    """The round-end body runs before `last_gamestate = gamestate`; an uncaught
    error re-detects the 0→3 transition each frame and re-closes every track
    into completed_tracks again (duplicated data). The body is pcall-wrapped
    and the failure printed."""
    src = _tracker()
    i = src.index("-- Detect round end")
    # the ASSIGNMENT at statement indent, not the mention of it in a comment
    block = src[i:src.index("\n    last_gamestate = gamestate", i)]
    assert "pcall(function()" in block
    assert "round-end handling FAILED" in block


# ---------------------------------------------------------------------------
# the other live scripts
# ---------------------------------------------------------------------------

def test_live_events_kill_line_floors_its_raw_origin_floats():
    """live_events.lua is loaded and enabled on the game server; its K line fed
    six raw tonumber(ps.origin) floats (plus health) straight into %d."""
    src = _read("vps_scripts/live_events.lua")
    assert "math.floor(kx), math.floor(ky), math.floor(kz)" in src
    assert "math.floor(vx), math.floor(vy), math.floor(vz)" in src
    assert "math.floor(khp)" in src
    assert "kx, ky, kz, vx, vy, vz, khp, dist))" not in src


def test_bit_lshift_shims_return_an_integer_subtype():
    """2^b is always a float in Lua 5.4, so the shim's product was float-typed
    even when integral — a landmine for any future %d on a shifted value."""
    for rel in ("vps_scripts/c0rnp0rn8.lua", "vps_scripts/endstats.lua"):
        src = _read(rel)
        assert "return to_int(a) * (2 ^ to_int(b))" not in src
        assert "return es_to_int(a) * (2 ^ es_to_int(b))" not in src
        assert "math.floor(to_int(a) * (2 ^ to_int(b)))" in src or \
               "math.floor(es_to_int(a) * (2 ^ es_to_int(b)))" in src


def test_denied_run_detection_reads_the_track_captured_before_it_was_cleared():
    """et_Obituary calls endPlayerTrack (which nils player_tracks[victim]) and
    the v6.01 denied-run block then read that same entry — always nil, so the
    entire denied-run path was dead code: 0 `approach_killed`/`denied` rows in
    4.5 months of production while 3,008 successful runs imported fine. The
    track must be captured BEFORE endPlayerTrack and the block must use the
    captured reference."""
    src = _tracker()
    i = src.index("function et_Obituary")
    end_call = src.index("endPlayerTrack(victim", i)
    capture = src.index("local victim_track = tracker.player_tracks[victim]", i)
    assert capture < end_call, "capture must precede endPlayerTrack"
    denied = src.index("Denied objective run detection", i)
    block = src[denied:denied + 400]
    assert "local orun_track = victim_track" in block
    assert "tracker.player_tracks[victim]" not in block
