"""Reserved IDs -> actual shipped Lua writer -> real files -> strict sealed import.

ET bindings are synthetic. No module lifecycle/IPC, game server or DB activation.
The manager boundary is observed here; the native companion test uses PostgreSQL.
"""

import hashlib
import json
import shutil
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.community_stats_parser import C0RNP0RN3StatsParser
from bot.runtime_completed_import import CompletedRoundInput, import_completed_round
from shared.runtime_completion_manifest import record_completion_once
from shared.runtime_identity_allocation import allocate_round_pair, inspect_round_pair
from shared.runtime_round_identity import stats_header_identity
from shared.runtime_source_reservation import claim_source_generation, reserve_source_generation
from shared.runtime_stats_delivery import StatsDelivery
from shared.runtime_stats_dispatch import StatsDispatch

ROOT = Path(__file__).resolve().parents[2]


def run_writer(lua, root, pair, half, scenario='ok', *, dispatch=None, entrypoint=False):
    if dispatch is None:
        generation = uuid.uuid4().hex
        directory = reserve_source_generation(root, generation)
        claim_source_generation(root, generation)
    else:
        assert dispatch.identity == (pair.first if half == 1 else pair.second)
        generation = dispatch.generation
        directory = root / generation
        assert (directory / '.writer-claimed').is_file()
    delivery = ''
    if scenario.startswith('bound-ipc'):
        ticket = dispatch or StatsDispatch(pair.first if half == 1 else pair.second, generation, 'supply')
        delivery = StatsDelivery('1' * 32, '2' * 32, 0, ticket).encode()
    output = subprocess.run([
        lua, str(ROOT / 'tests/lua/runtime_identity_writer_harness.lua'), str(ROOT), str(directory),
        pair.first.source_id, pair.first.match_id, pair.first.round_id, pair.second.round_id,
        str(half), generation, scenario, delivery, 'required-entrypoint' if entrypoint else 'legacy-entrypoint',
    ], capture_output=True, text=True, timeout=10, umask=0o077)
    assert output.returncode == 0, output.stdout + output.stderr
    receipts = [json.loads(line.removeprefix('receipt ')) for line in output.stdout.splitlines()
                if line.startswith('receipt ')]
    if scenario not in ('ok', 'bound-frame', 'bound-shutdown', 'bound-mutate', 'bound-repeat',
                        'bound-ipc', 'bound-ipc-retry', 'bound-stale-intermission'):
        assert receipts == []
        return directory
    assert len(receipts) == 1
    envelope = receipts[0]
    assert envelope['generation'] == generation
    receipt = envelope['completion']
    filename = receipt['filename']
    path = directory / filename
    raw = path.read_bytes()
    assert receipt['bytes'] == len(raw) == path.stat().st_size
    assert stats_header_identity(raw.splitlines(keepends=True)[0].decode()) == (
        pair.first if half == 1 else pair.second)
    digest = hashlib.sha256(raw).hexdigest()
    # This harness is the trusted local dispatcher; no remote digest/ack claim.
    assert record_completion_once(directory, receipt, expected_sha256=digest) == 'published'
    with pytest.raises(FileExistsError):
        claim_source_generation(root, generation)
    return CompletedRoundInput(root, generation, filename, len(raw), digest)


def written_pair(root, lua='lua5.4'):
    root.mkdir(mode=0o700, exist_ok=True)
    authority, spool = root / 'authority', root / 'spool'
    authority.mkdir(mode=0o700)
    spool.mkdir(mode=0o700)
    pair = allocate_round_pair(authority, 'fixture-server')
    assert inspect_round_pair(authority, pair.first.match_id, expected_source='fixture-server') == pair
    return [run_writer(lua, spool, pair, half) for half in (1, 2)]


@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
async def test_allocated_identity_reaches_actual_writer_and_import(lua, tmp_path):
    assert shutil.which(lua), f'{lua} required for connected writer proof'
    first, second = written_pair(tmp_path, lua)
    parsed = []
    async def process(path, *, input_source):
        result = input_source.parse(None)
        assert input_source.read_bytes()
        parsed.append(result)
        return True, path.name
    manager = SimpleNamespace(parser=C0RNP0RN3StatsParser(), process_file=process)
    assert (await import_completed_round(manager, first, require_declared_identity=True))[0]
    assert (await import_completed_round(manager, second, first=first, require_declared_identity=True))[0]
    assert [value['round_num'] for value in parsed] == [1, 2]
    assert parsed[1]['r1_filename'] == first.filename
    assert parsed[1]['match_summary']['players']
    print(f'CONNECTED {lua}: reserved IDs -> full c0rn SaveStats -> real files/receipts '
          '-> sealed strict R1/R2 -> canonical manager boundary; ET synthetic, DB not used')


async def test_two_actual_matches_cannot_be_cross_paired(tmp_path):
    first, _ = written_pair(tmp_path / 'one')
    _, other = written_pair(tmp_path / 'two')
    manager = SimpleNamespace(parser=C0RNP0RN3StatsParser(), process_file=AsyncMock())
    with pytest.raises(ValueError, match='pair disagrees'):
        await import_completed_round(manager, other, first=first, require_declared_identity=True)
    manager.process_file.assert_not_called()


@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
@pytest.mark.parametrize('half', [1, 2])
def test_full_writer_legacy_bytes_preserved_except_explicit_extension(tmp_path, lua, half):
    authority, spool = tmp_path / 'authority', tmp_path / 'spool'
    authority.mkdir(mode=0o700)
    spool.mkdir(mode=0o700)
    pair = allocate_round_pair(authority, 'fixture-server')
    runtime = run_writer(lua, spool, pair, half)
    legacy = run_writer(lua, spool, pair, half, 'legacy')
    actual = (runtime.root / runtime.generation / runtime.filename).read_bytes()
    header, newline, body = actual.partition(b'\n')
    without_identity = header.rsplit(b'\\', 1)[0] + newline + body
    assert without_identity == (legacy / runtime.filename).read_bytes()
    assert stats_header_identity(without_identity.splitlines(keepends=True)[0].decode()) is None


@pytest.mark.parametrize('scenario', ['bad-identity', 'bad-ticket', 'bad-map', 'bad-generation', 'bad-callback',
    'open-error', 'write-error', 'short-write', 'close-error', 'notify-error'])
@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
def test_actual_writer_failures_never_publish_completion(tmp_path, lua, scenario):
    authority, spool = tmp_path / 'authority', tmp_path / 'spool'
    authority.mkdir(mode=0o700)
    spool.mkdir(mode=0o700)
    pair = allocate_round_pair(authority, 'fixture-server')
    directory = run_writer(lua, spool, pair, 1, scenario)
    assert not list(directory.glob('*.complete.json'))
