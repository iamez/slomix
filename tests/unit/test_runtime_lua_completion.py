"""Execute the offline Lua completion prototype against a real temp filesystem."""

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('scenario', [
    'ok', 'open-fail', 'short-write', 'write-error', 'missing-count',
    'close-error', 'notify-error', 'sparse', 'empty', 'oversize', 'unsafe-name', 'round-zero',
])
def test_completion_requires_all_writes_and_close(tmp_path, scenario):
    """No failure emits a receipt; successful bytes agree with stat and SHA tool."""
    lua = shutil.which('lua5.4') or shutil.which('lua')
    if not lua:
        pytest.skip('Lua interpreter not installed')
    result = subprocess.run([
        lua, str(ROOT / 'tests/lua/runtime_completion_harness.lua'),
        str(ROOT / 'vps_scripts/runtime_completed_stats.lua'), str(tmp_path), scenario,
    ], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f'emitted={str(scenario == "ok").lower()}' in result.stdout
    final = tmp_path / '2026-09-20-120000-oasis-round-1.txt'
    if scenario in ('ok', 'close-error', 'notify-error'):
        payload = final.read_bytes()
        assert payload == b'header\nplayer-row\n'
        assert len(payload) == final.stat().st_size == 18
        assert subprocess.check_output(['sha256sum', str(final)], text=True).split()[0] == hashlib.sha256(payload).hexdigest()
    if scenario in ('open-fail', 'sparse', 'empty', 'oversize', 'unsafe-name', 'round-zero'):
        assert not final.exists()
    print(result.stdout.strip())
