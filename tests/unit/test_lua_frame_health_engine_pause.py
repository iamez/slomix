"""Execute the real tracker against ET 2.85 pause/configstring semantics."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_tracker_reports_engine_pause_not_frozen_level_time():
    lua = shutil.which("lua5.4")
    if lua is None:
        pytest.fail("lua5.4 is required for the engine pause contract proof")
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [lua, "tests/lua/frame_health_harness.lua"], cwd=root,
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PAUSE PROOF:" in result.stdout
    assert "NO-PAUSE PROOF:" in result.stdout
    assert "HARNESS OK" in result.stdout
