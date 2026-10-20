"""Execute the offline Lua completion prototype against a real temp filesystem."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from shared.runtime_capture import capture_proximity_stream
from shared.runtime_completion_manifest import record_proximity_completion_once
from shared.runtime_manifest_reader import inspect_proximity_completion_manifest
from shared.runtime_source_reservation import claim_source_generation, reserve_source_generation

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('scenario', [
    'ok', 'open-fail', 'short-write', 'write-error', 'missing-count',
    'close-error', 'notify-error', 'sparse', 'empty', 'oversize', 'unsafe-name', 'round-zero',
    'unsafe-generation', 'uppercase-generation', 'wrong-protocol',
])
@pytest.mark.parametrize('protocol', ['stats', 'proximity'])
def test_completion_requires_all_writes_and_close(tmp_path, scenario, protocol):
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
        str(ROOT / 'vps_scripts/runtime_completed_stats.lua'), str(reserved), scenario, generation, protocol,
    ], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f'emitted={str(scenario == "ok").lower()}' in result.stdout
    suffix = '_engagements.txt' if protocol == 'proximity' else '.txt'
    final = reserved / ('2026-09-20-120000-oasis-round-1' + suffix)
    if scenario in ('ok', 'close-error', 'notify-error'):
        payload = final.read_bytes()
        assert payload == b'header\nplayer-row\n'
        assert len(payload) == final.stat().st_size == 18
        assert subprocess.check_output(['sha256sum', str(final)], text=True).split()[0] == hashlib.sha256(payload).hexdigest()
    if scenario in ('open-fail', 'sparse', 'empty', 'oversize', 'unsafe-name', 'round-zero',
                    'unsafe-generation', 'uppercase-generation', 'wrong-protocol'):
        assert not final.exists()
    messages = [line.removeprefix('receipt ') for line in result.stdout.splitlines() if line.startswith('receipt ')]
    assert len(messages) == int(scenario == 'ok')
    if messages:
        envelope = json.loads(messages[0])
        assert envelope['generation'] == generation
        assert envelope['completion'] == dict(version=1, filename=final.name, bytes=18, state='writer_closed')
    before = final.read_bytes() if final.exists() else None
    with pytest.raises(FileExistsError):
        claim_source_generation(tmp_path, generation)
    assert (final.read_bytes() if final.exists() else None) == before
    print(result.stdout.strip())


def test_lua_proximity_completion_to_python_manifest(tmp_path):
    """Real Lua close -> callback pipe -> copied bytes -> persisted receipt.

    Harness-owned pipe supplies trusted synthetic delivery, NOT proof of a live
    authenticated game-server transport. Digest is independently measured only
    after producer exit; a real dispatcher must establish the same trust boundary.
    """
    lua = shutil.which('lua5.4') or shutil.which('lua')
    if not lua:
        pytest.skip('Lua interpreter not installed')
    tmp_path.chmod(0o700)
    generation = 'fedcba9876543210' * 2
    reserved = reserve_source_generation(tmp_path, generation)
    claim_source_generation(tmp_path, generation)
    result = subprocess.run([
        lua, str(ROOT / 'tests/lua/runtime_completion_harness.lua'),
        str(ROOT / 'vps_scripts/runtime_completed_stats.lua'), str(reserved), 'ok', generation, 'proximity',
    ], capture_output=True, text=True, timeout=10, check=True)
    message, = [line.removeprefix('receipt ') for line in result.stdout.splitlines() if line.startswith('receipt ')]
    envelope = json.loads(message)
    assert envelope['generation'] == reserved.name == generation
    receipt = envelope['completion']
    source = reserved / receipt['filename']
    original = source.read_bytes()
    digest = subprocess.check_output(['sha256sum', str(source)], text=True).split()[0]
    assert digest == hashlib.sha256(original).hexdigest()
    assert receipt['bytes'] == source.stat().st_size == len(original)
    spool = tmp_path / 'captured'
    spool.mkdir(mode=0o700)

    class ClosedSource:
        def __init__(self, stream):
            self.stream = stream

        def settimeout(self, timeout):
            assert timeout > 0  # Local fixture only; no claim of file-I/O deadline.

        def read(self, size):
            return self.stream.read(size)

    with source.open('rb') as stream:
        captured = capture_proximity_stream(
            ClosedSource(stream), spool, source.name, expected_size=receipt['bytes'],
            expected_sha256=digest, chunk_size=5,
        )
    assert record_proximity_completion_once(spool, receipt, expected_sha256=digest) == 'published'
    before = {p.name: (p.stat().st_ino, p.read_bytes()) for p in spool.iterdir()}
    for _ in range(2):
        observed = inspect_proximity_completion_manifest(spool, source.name)
        assert observed.status == 'match' and observed.sha256 == digest and observed.size == len(original)
        assert record_proximity_completion_once(spool, receipt, expected_sha256=digest) == 'content_present'
    assert captured.read_bytes() == source.read_bytes() == original
    assert {p.name: (p.stat().st_ino, p.read_bytes()) for p in spool.iterdir()} == before
    with pytest.raises(FileExistsError):
        claim_source_generation(tmp_path, generation)
    print('Lua/Python proximity proof: one generation claim, close before callback, '
          'size/SHA independently agree, capture + manifest + repeated recovery; source retained')
