"""Host dispatch through actual Lua file writes; no live engine/transport."""

import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from shared.runtime_completion_manifest import record_completion_once
from shared.runtime_identity_allocation import allocate_round_pair
from shared.runtime_stats_dispatch import CompletedStatsReference, prepare_stats_dispatch
from tests.unit.test_runtime_identity_writer_path import run_writer


def setup_pair(root):
    root.mkdir(mode=0o700, exist_ok=True)
    authority, spool = root / 'authority', root / 'spool'
    authority.mkdir(mode=0o700)
    spool.mkdir(mode=0o700)
    return authority, spool, allocate_round_pair(authority, 'fixture-server')


def prepare(authority, spool, pair, half=1, previous=None, **overrides):
    kwargs = dict(expected_source='fixture-server', map_name='supply', half=half, previous=previous)
    kwargs.update(overrides)
    return prepare_stats_dispatch(authority, spool, pair.first.match_id, **kwargs)


def reference(completed):
    return CompletedStatsReference(completed.generation, completed.filename, completed.size, completed.sha256)


def dispatched_pair(root, lua='lua5.4', *, ipc=False):
    authority, spool, pair = setup_pair(root)
    with pytest.raises(ValueError, match='requires a completed R1'):
        prepare(authority, spool, pair, 2)
    first_ticket = prepare(authority, spool, pair)
    first = run_writer(lua, spool, pair, 1, 'bound-ipc' if ipc else 'bound-frame', dispatch=first_ticket)
    second_ticket = prepare(authority, spool, pair, 2, reference(first))
    second = run_writer(lua, spool, pair, 2, 'bound-ipc-retry' if ipc else 'bound-shutdown', dispatch=second_ticket)
    for half, previous in ((1, None), (2, reference(first))):
        with pytest.raises(FileExistsError):
            prepare(authority, spool, pair, half, previous)
    return first, second


@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
def test_dispatch_links_real_closed_halves_and_never_redispatches(tmp_path, lua):
    first, second = dispatched_pair(tmp_path, lua)
    assert first.generation != second.generation
    assert len(list((tmp_path / 'spool').iterdir())) == 2
    records = list((tmp_path / 'authority').glob('*/dispatch.json'))
    assert len(records) == 2
    for path in records:
        assert path.stat().st_mode & 0o777 == 0o600
        data = json.loads(path.read_bytes())
        if data['previous']:
            assert data['previous'] == reference(first).__dict__
    print(f'DISPATCH {lua}: premature R2 denied; completed actual R1 -> R2; repeats denied')


def test_concurrent_dispatch_has_exactly_one_winner(tmp_path):
    authority, spool, pair = setup_pair(tmp_path)
    def attempt(_):
        try:
            return prepare(authority, spool, pair)
        except FileExistsError:
            return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(attempt, range(8)))
    assert sum(result is not None for result in results) == len(list(spool.iterdir())) == 1


@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
@pytest.mark.parametrize('scenario', ['bound-frame', 'bound-shutdown', 'bound-mutate', 'bound-repeat'])
@pytest.mark.parametrize('half', [1, 2])
def test_bound_callbacks_freeze_identity_and_never_rewrite(tmp_path, lua, scenario, half):
    _, spool, pair = setup_pair(tmp_path)
    run_writer(lua, spool, pair, half, scenario)


@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
@pytest.mark.parametrize('scenario', ['bound-noinit', 'bound-warmup-init', 'bound-warmup-now',
    'bound-queued', 'bound-counter', 'bound-map', 'bound-gametype', 'bound-reinit',
    'bound-open-error', 'bound-write-error', 'bound-short-write', 'bound-close-error', 'bound-notify-error'])
def test_bound_failures_cannot_publish_or_retry(tmp_path, lua, scenario):
    _, spool, pair = setup_pair(tmp_path)
    directory = run_writer(lua, spool, pair, 1, scenario)
    assert not list(directory.glob('*.complete.json'))


@pytest.mark.parametrize('change', ['copied-identity', 'map', 'digest', 'missing-receipt', 'spool', 'header'])
def test_r2_refuses_unbound_predecessor_without_consuming_half(tmp_path, change):
    authority, spool, pair = setup_pair(tmp_path)
    ticket = prepare(authority, spool, pair)
    first = run_writer('lua5.4', spool, pair, 1, dispatch=ticket)
    original = reference(first)
    previous, check_spool, kwargs = original, spool, {}
    if change == 'copied-identity':
        # Same IDs and bytes, genuinely closed by the same writer, WRONG dispatch.
        other = run_writer('lua5.4', spool, pair, 1)
        previous = reference(other)
    elif change == 'map':
        kwargs['map_name'] = 'radar'
    elif change == 'digest':
        previous = replace(previous, sha256='f' * 64)
    elif change == 'missing-receipt':
        # Preserve the file; moving its receipt only makes it unavailable.
        manifest = spool / first.generation / (first.filename + '.complete.json')
        manifest.rename(manifest.with_suffix('.saved'))
    elif change == 'spool':
        check_spool = tmp_path / 'other-spool'
        check_spool.mkdir(mode=0o700)
    elif change == 'header':
        # Re-publish real wrong-map bytes/receipt in the originally dispatched
        # generation to test the header guard independently of digest mismatch.
        path = spool / first.generation / first.filename
        path.write_bytes(path.read_bytes().replace(b'\\supply\\', b'\\radar\\', 1))
        manifest = path.with_name(path.name + '.complete.json')
        manifest.rename(manifest.with_suffix('.saved'))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        receipt = dict(version=1, filename=path.name, bytes=path.stat().st_size, state='writer_closed')
        record_completion_once(path.parent, receipt, expected_sha256=digest)
        previous = replace(previous, size=path.stat().st_size, sha256=digest)
    with pytest.raises(ValueError):
        prepare(authority, check_spool, pair, 2, previous, **kwargs)
    assert not (authority / pair.second.round_id / '.writer-claimed').exists()
    assert not (authority / pair.second.round_id / 'dispatch.json').exists()


@pytest.mark.parametrize('half', [0, 3, True, '1'])
def test_bad_half_is_read_only(tmp_path, half):
    authority, spool, pair = setup_pair(tmp_path)
    with pytest.raises(ValueError, match='half 1 or 2'):
        prepare(authority, spool, pair, half)
    assert list(spool.iterdir()) == []


@pytest.mark.parametrize('map_name', ['', '../supply', 'x\\y', 'x\ny', 'x' * 65])
def test_bad_map_is_read_only(tmp_path, map_name):
    authority, spool, pair = setup_pair(tmp_path)
    with pytest.raises(ValueError, match='Invalid dispatch map'):
        prepare(authority, spool, pair, map_name=map_name)
    assert list(spool.iterdir()) == []


def test_root_alias_and_insecure_spool_rejected_before_claim(tmp_path):
    authority, spool, pair = setup_pair(tmp_path)
    with pytest.raises(ValueError, match='must be separate'):
        prepare(authority, authority, pair)
    spool.chmod(0o755)
    with pytest.raises(ValueError, match='0700'):
        prepare(authority, spool, pair)
    assert not (authority / pair.first.round_id / '.writer-claimed').exists()


def test_source_mismatch_r1_predecessor_and_missing_dispatch_are_read_only(tmp_path):
    authority, spool, pair = setup_pair(tmp_path)
    with pytest.raises(ValueError, match='namespace mismatch'):
        prepare(authority, spool, pair, expected_source='other-server')
    fake = CompletedStatsReference('d' * 32, '2026-09-25-120000-supply-round-1.txt', 1, 'a' * 64)
    with pytest.raises(ValueError, match='cannot have a predecessor'):
        prepare(authority, spool, pair, previous=fake)
    with pytest.raises(ValueError, match='dispatch record missing'):
        prepare(authority, spool, pair, 2, fake)
    assert list(spool.iterdir()) == []
    assert list(authority.glob('*/.writer-claimed')) == []


def test_dispatch_claim_survives_a_fresh_host_process(tmp_path):
    authority, spool, pair = setup_pair(tmp_path)
    prepare(authority, spool, pair)
    code = '''
import sys
from pathlib import Path
from shared.runtime_stats_dispatch import prepare_stats_dispatch
try:
    prepare_stats_dispatch(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3],
        expected_source='fixture-server', map_name='supply', half=1)
except FileExistsError:
    print('already consumed')
else:
    raise AssertionError('redispatched in a new process')
'''
    result = subprocess.run([sys.executable, '-c', code, str(authority), str(spool), pair.first.match_id],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'already consumed\n'
    assert len(list(spool.iterdir())) == 1


@pytest.mark.parametrize('unsafe', ['malformed', 'symlink', 'public'])
def test_unsafe_first_record_never_authorizes_r2(tmp_path, unsafe):
    authority, spool, pair = setup_pair(tmp_path)
    first = run_writer('lua5.4', spool, pair, 1, dispatch=prepare(authority, spool, pair))
    record = authority / pair.first.round_id / 'dispatch.json'
    if unsafe == 'malformed':
        record.write_bytes(b'{"version":1,"version":1}')
    elif unsafe == 'symlink':
        preserved = record.with_suffix('.saved')
        record.rename(preserved)
        record.symlink_to(preserved)
    else:
        record.chmod(0o644)
    with pytest.raises((ValueError, OSError)):
        prepare(authority, spool, pair, 2, reference(first))
    assert not (authority / pair.second.round_id / '.writer-claimed').exists()


@pytest.mark.parametrize('failure', ['short-write', 'fsync'])
def test_failed_persistence_burns_half_and_retains_artifacts(tmp_path, monkeypatch, failure):
    authority, spool, pair = setup_pair(tmp_path)
    original_write, original_fsync = os.write, os.fsync
    def write(fd, data):
        if data.startswith(b'{') and failure == 'short-write':
            return original_write(fd, data[:2])
        return original_write(fd, data)
    def fsync(fd):
        # Dispatch record only; all claims/reservations already persisted.
        if os.readlink(f'/proc/self/fd/{fd}').endswith('/dispatch.json') and failure == 'fsync':
            raise OSError('fixture dispatch fsync error')
        return original_fsync(fd)
    with monkeypatch.context() as patch:
        patch.setattr(os, 'write', write)
        patch.setattr(os, 'fsync', fsync)
        with pytest.raises(OSError, match='Incomplete stats dispatch|fixture dispatch fsync'):
            prepare(authority, spool, pair)
    assert (authority / pair.first.round_id / 'dispatch.json').exists()
    assert len(list(spool.iterdir())) == 1
    with pytest.raises(FileExistsError):
        prepare(authority, spool, pair)
