"""Executable legacy-clock contract and visible engine-alignment gaps.

Oracle provenance: ET:Legacy v2.85.0 / 489f1c4f142903aa9d1619f1c107d00b554d0dd6:
g_main.c G_RunFrame, g_active.c SpectatorClientEndFrame, g_match.c G_loadMatchGame.
Strict xfails are desired contracts awaiting a versioned capture change, NOT proof
that the current tracker correctly handles pauses. Harness failures never xfail.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def observations():
    lua = shutil.which("lua5.4")
    if not lua:
        raise RuntimeError("lua5.4 is required for the engine clock contract")
    result = subprocess.run(
        [lua, "tests/lua/engine_clock_contract_harness.lua"], cwd=ROOT,
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0 or "64 seed pairs; no live engine" not in result.stdout:
        raise RuntimeError(result.stdout + result.stderr)
    rows, phases = {}, []
    for line in result.stdout.splitlines():
        if "," not in line:
            continue
        name, *values = line.split(",")
        numbers = [float(value) for value in values]
        if name == "phase":
            phases.append(numbers)
        elif name == "event":
            rows[name] = dict(zip(("captured", "engine_elapsed"), numbers, strict=True))
        else:
            rows[name] = dict(zip(
                ("level", "engine_elapsed", "tracker_elapsed", "anchor", "sample_time",
                 "axis_wait", "allies_wait", "cs_start", "path_points"), numbers, strict=True))
    if len(rows) != 9 or len(phases) != 8:
        raise RuntimeError("incomplete engine clock harness output")
    print(result.stdout)
    return rows, phases


def test_declared_legacy_basis_is_raw_level_offset(observations):
    rows, _ = observations
    for name, row in rows.items():
        if name == "event":
            continue
        assert row["tracker_elapsed"] == row["level"] - row["anchor"]
    assert rows["pause_short"]["engine_elapsed"] == 200
    assert rows["pause_long"]["engine_elapsed"] == 200
    assert rows["resumed"]["engine_elapsed"] == 250
    assert rows["resumed"]["tracker_elapsed"] == 900


def test_resume_transition_and_pre_frame_event_are_not_fabricated_exact_time(observations):
    rows, _ = observations
    assert rows["resume_transition"]["engine_elapsed"] == 200
    assert rows["resume_transition"]["cs_start"] == 1650
    assert rows["event"] == {"captured": 200, "engine_elapsed": 250}


def test_fresh_module_does_not_inherit_pause_or_anchor(observations):
    rows, _ = observations
    for name in ("aligned", "fresh_module"):
        row = rows[name]
        assert row["engine_elapsed"] == row["tracker_elapsed"] == row["sample_time"] == 200
        assert row["axis_wait"] == 29800
        assert row["allies_wait"] == 19800


def test_pause_capture_keeps_only_pre_pause_position_samples(observations):
    rows, _ = observations
    assert rows["aligned"]["path_points"] == 2  # spawn plus normal sample
    assert rows["pause_short"]["path_points"] == 2
    assert rows["pause_long"]["path_points"] == 2
    assert rows["pause_long"]["sample_time"] == 200
    assert rows["resume_transition"]["path_points"] == 2
    assert rows["resumed"]["path_points"] == 2


def test_configstring_is_not_an_exact_active_clock(observations):
    rows, _ = observations
    short, long = rows["pause_short"], rows["pause_long"]
    assert short["cs_start"] == 1000  # 250ms accumulated: below 500ms publish threshold
    assert short["level"] - short["cs_start"] != short["engine_elapsed"]
    assert long["cs_start"] == 1600
    assert long["level"] - long["cs_start"] == long["engine_elapsed"]


def test_spawn_phase_matches_independent_next_boundary_oracle(observations):
    _, phases = observations
    for elapsed, axis, allies, axis_score, allies_score in phases:
        # Count to the next STRICTLY later phase boundary, not the client UI's
        # rounded seconds and not a guarantee that a corpse will respawn there.
        for offset, interval, wait, score in (
            (4000, 30000, axis, axis_score), (6000, 20000, allies, allies_score)
        ):
            cycle = int((elapsed + offset) // interval)
            next_boundary = (cycle + 1) * interval - offset
            assert wait == next_boundary - elapsed
            assert score == pytest.approx(wait / interval)


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="raw v1 clock includes pauses; versioned clock change pending")
def test_desired_gameplay_clock_excludes_pause(observations):
    rows, _ = observations
    assert rows["resumed"]["tracker_elapsed"] == rows["resumed"]["engine_elapsed"]


def test_desired_sampling_does_not_advance_during_pause(observations):
    rows, _ = observations
    assert rows["pause_long"]["path_points"] == rows["aligned"]["path_points"]


@pytest.mark.parametrize("name", ["first_frame_delay", "synthetic_live_without_restart"])
@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="tracker live-frame anchor differs from engine init anchor")
def test_desired_spawn_phase_uses_engine_anchor(observations, name):
    rows, _ = observations
    row = rows[name]
    expected = 30000 - (row["engine_elapsed"] % 30000)
    assert row["axis_wait"] == expected
