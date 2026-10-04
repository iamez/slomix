"""Execute the offline Lua completion prototype against a real temp filesystem."""

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

from shared.runtime_source_reservation import claim_source_generation, reserve_source_generation

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('scenario', [
    'ok', 'open-fail', 'short-write', 'write-error', 'missing-count',
    'close-error', 'notify-error', 'sparse', 'empty', 'oversize', 'unsafe-name', 'round-zero',
    'unsafe-generation', 'uppercase-generation',
])
def test_completion_requires_all_writes_and_close(tmp_path, scenario):
    """No failure emits a receipt; successful bytes agree with stat and SHA tool."""
    lua = shutil.which('lua5.4') or shutil.which('lua')
    if not lua:
        pytest.skip('Lua interpreter not installed')
    tmp_path.chmod(0o700)
    generation = '0123456789abcdef' * 2
    reserved = reserve_source_generation(tmp_path, generation)
    assert claim_source_generation(tmp_path, generation) == reserved
    result = subprocess.run([
        lua, str(ROOT / 'tests/lua/runtime_completion_harness.lua'),
        str(ROOT / 'vps_scripts/runtime_completed_stats.lua'), str(reserved), scenario, generation,
    ], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f'emitted={str(scenario == "ok").lower()}' in result.stdout
    final = reserved / '2026-09-20-120000-oasis-round-1.txt'
    if scenario in ('ok', 'close-error', 'notify-error'):
        payload = final.read_bytes()
        assert payload == b'header\nplayer-row\n'
        assert len(payload) == final.stat().st_size == 18
        assert subprocess.check_output(['sha256sum', str(final)], text=True).split()[0] == hashlib.sha256(payload).hexdigest()
    if scenario in ('open-fail', 'sparse', 'empty', 'oversize', 'unsafe-name', 'round-zero',
                    'unsafe-generation', 'uppercase-generation'):
        assert not final.exists()
    before = final.read_bytes() if final.exists() else None
    with pytest.raises(FileExistsError):
        claim_source_generation(tmp_path, generation)
    assert (final.read_bytes() if final.exists() else None) == before
    print(result.stdout.strip())
