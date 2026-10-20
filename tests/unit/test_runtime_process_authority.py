"""Native process/disk authority proofs; ET bindings remain explicitly synthetic."""

import errno
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, asdict, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from shared.runtime_completion_manifest import record_completion_once
from shared.runtime_init_observation import decode_init_observation
from shared.runtime_process_authority import (
    prepare_observed_process_delivery,
    prepare_process_delivery,
    reserve_process_epoch,
    verify_process_epoch,
)
from shared.runtime_process_pin import pin_process
from shared.runtime_round_identity import stats_header_identity
from shared.runtime_stats_delivery import StatsDelivery
from tests.unit import test_runtime_process_pin as process_fixtures
from tests.unit.test_runtime_stats_dispatch import prepare, setup_pair

ROOT = Path(__file__).resolve().parents[2]
approved = process_fixtures.approved
child = process_fixtures.child


@pytest.fixture
def pin(child, approved):
    with pin_process(child.pid, **approved) as value:
        yield value


def record_path(root):
    paths = list(root.glob('*/process-epoch.json'))
    assert len(paths) == 1
    return paths[0]


def inventory(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob('*') if path.is_file()}


def test_exact_durable_record_sync_order_and_live_verification(tmp_path, pin, monkeypatch):
    syncs = []
    real_sync = os.fsync

    def sync(fd):
        info = os.fstat(fd)
        syncs.append((stat.S_ISDIR(info.st_mode), info.st_ino))
        real_sync(fd)

    monkeypatch.setattr(os, 'fsync', sync)
    value = reserve_process_epoch(tmp_path, pin, source_id='fixture-server')
    path = record_path(tmp_path)
    raw = json.loads(path.read_bytes())
    assert raw == json.loads(json.dumps({'version': 1, **asdict(value)}))
    assert raw['process']['pid'] == pin.identity.pid
    assert raw['process']['executable_sha256'] == pin.identity.executable_sha256
    assert {entry.name for entry in tmp_path.iterdir()} == {path.parent.name, value.process_epoch}
    assert path.parent.name != value.process_epoch
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert len(syncs) == 6
    assert syncs[-2:] == [(False, path.stat().st_ino), (True, path.parent.stat().st_ino)]
    before = inventory(tmp_path)
    assert verify_process_epoch(tmp_path, pin, value) == value
    assert inventory(tmp_path) == before
    with pytest.raises(FrozenInstanceError):
        value.source_id = 'other'
    print('PROCESS AUTHORITY: exact native PID/digest record, 2 reservations, 6 fsyncs, read-only live recheck')


@pytest.mark.parametrize('source', ['fixture-server', 'renamed-source'])
def test_same_process_cannot_mint_another_epoch_even_under_another_source(tmp_path, pin, source):
    first = reserve_process_epoch(tmp_path, pin, source_id='fixture-server')
    before = inventory(tmp_path)
    with pytest.raises(FileExistsError):
        reserve_process_epoch(tmp_path, pin, source_id=source)
    assert inventory(tmp_path) == before
    assert len(list(tmp_path.iterdir())) == 2
    assert verify_process_epoch(tmp_path, pin, first) == first


def test_fresh_controller_process_cannot_reallocate(tmp_path, child, approved, pin):
    reserve_process_epoch(tmp_path, pin, source_id='fixture-server')
    code = '''
import sys
from pathlib import Path
from shared.runtime_process_pin import pin_process
from shared.runtime_process_authority import reserve_process_epoch
with pin_process(int(sys.argv[2]), expected_uid=int(sys.argv[3]),
                 expected_executable=Path(sys.argv[4]), expected_sha256=sys.argv[5]) as pin:
    try:
        reserve_process_epoch(Path(sys.argv[1]), pin, source_id='renamed-source')
    except FileExistsError:
        print('DURABLE CLAIM REFUSED')
    else:
        raise AssertionError('duplicate process epoch allocated')
'''
    before = inventory(tmp_path)
    result = subprocess.run([sys.executable, '-c', code, str(tmp_path), str(child.pid),
        str(approved['expected_uid']), str(approved['expected_executable']), approved['expected_sha256']],
        cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'DURABLE CLAIM REFUSED'
    assert inventory(tmp_path) == before


def test_concurrent_controllers_have_exactly_one_winner(tmp_path, child, approved):
    def attempt(_):
        with pin_process(child.pid, **approved) as current:
            try:
                return reserve_process_epoch(tmp_path, current, source_id='fixture-server')
            except FileExistsError:
                return None

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(attempt, range(8)))
    winners = [value for value in results if value is not None]
    assert len(winners) == 1
    assert len(list(tmp_path.glob('*/process-epoch.json'))) == 1
    assert len(list(tmp_path.iterdir())) == 2
    assert json.loads(record_path(tmp_path).read_bytes())['process_epoch'] == winners[0].process_epoch


@pytest.mark.parametrize('source', ['', 'UPPER', 'a/b', None, 'a' * 65])
def test_invalid_source_never_reserves(tmp_path, pin, source):
    with pytest.raises(ValueError, match='source'):
        reserve_process_epoch(tmp_path, pin, source_id=source)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('failure', [1, 2, 3, 4, 5, 6])
def test_each_sync_failure_retains_claim_and_refuses_retry(tmp_path, pin, monkeypatch, failure):
    real_sync, calls = os.fsync, 0

    def failing_sync(fd):
        nonlocal calls
        calls += 1
        if calls == failure:
            raise OSError(errno.EIO, 'injected fsync failure')
        real_sync(fd)

    with monkeypatch.context() as patch:
        patch.setattr(os, 'fsync', failing_sync)
        with pytest.raises(OSError, match='injected fsync failure'):
            reserve_process_epoch(tmp_path, pin, source_id='fixture-server')
    before = inventory(tmp_path)
    names = sorted(path.name for path in tmp_path.iterdir())
    assert names
    with pytest.raises(FileExistsError):
        reserve_process_epoch(tmp_path, pin, source_id='fixture-server')
    assert inventory(tmp_path) == before
    assert sorted(path.name for path in tmp_path.iterdir()) == names


def test_short_record_write_preserves_partial_and_never_reuses(tmp_path, pin, monkeypatch):
    real_write = os.write
    with monkeypatch.context() as patch:
        patch.setattr(os, 'write', lambda fd, payload: real_write(fd, payload[:7]))
        with pytest.raises(OSError, match='Incomplete process epoch record'):
            reserve_process_epoch(tmp_path, pin, source_id='fixture-server')
    assert record_path(tmp_path).stat().st_size == 7
    before = inventory(tmp_path)
    with pytest.raises(FileExistsError):
        reserve_process_epoch(tmp_path, pin, source_id='fixture-server')
    assert inventory(tmp_path) == before


def test_epoch_collision_retains_both_preexisting_state_and_process_claim(tmp_path, pin, monkeypatch):
    token = 'a' * 32
    (tmp_path / token).mkdir(mode=0o700)
    monkeypatch.setattr('shared.runtime_process_authority.uuid.uuid4', lambda: SimpleNamespace(hex=token))
    with pytest.raises(FileExistsError):
        reserve_process_epoch(tmp_path, pin, source_id='fixture-server')
    assert len(list(tmp_path.iterdir())) == 2
    assert not list(tmp_path.glob('*/process-epoch.json'))
    with pytest.raises(FileExistsError):
        reserve_process_epoch(tmp_path, pin, source_id='fixture-server')


@pytest.mark.parametrize('kind', ['shared', 'symlink'])
def test_unsafe_root_refused_before_claim(tmp_path, pin, kind):
    root = tmp_path / 'authority'
    root.mkdir(mode=0o700)
    candidate = root
    if kind == 'shared':
        root.chmod(0o755)
    else:
        candidate = tmp_path / 'alias'
        candidate.symlink_to(root, target_is_directory=True)
    with pytest.raises((ValueError, OSError)):
        reserve_process_epoch(candidate, pin, source_id='fixture-server')
    assert list(root.iterdir()) == []


def test_process_exit_after_final_sync_cannot_return_authority(tmp_path, pin, child, monkeypatch):
    real_sync, calls = os.fsync, 0

    def sync_then_exit(fd):
        nonlocal calls
        real_sync(fd)
        calls += 1
        if calls == 6:
            child.stdin.write('exit\n')
            child.stdin.flush()
            child.wait(timeout=5)

    monkeypatch.setattr(os, 'fsync', sync_then_exit)
    with pytest.raises(ValueError, match='exited'):
        reserve_process_epoch(tmp_path, pin, source_id='fixture-server')
    assert json.loads(record_path(tmp_path).read_bytes())['version'] == 1
    assert len(list(tmp_path.iterdir())) == 2  # Evidence retained, NOT returned authority.


@pytest.mark.parametrize('change', ['source', 'epoch', 'pid', 'version', 'extra', 'missing', 'mode', 'epoch-dir'])
def test_fresh_check_rejects_record_or_reservation_drift(tmp_path, pin, change):
    expected = reserve_process_epoch(tmp_path, pin, source_id='fixture-server')
    path = record_path(tmp_path)
    raw = json.loads(path.read_bytes())
    if change == 'missing':
        path.rename(path.with_suffix('.saved'))
    elif change == 'mode':
        path.chmod(0o644)
    elif change == 'epoch-dir':
        epoch = tmp_path / expected.process_epoch
        epoch.rename(tmp_path / 'saved-epoch')
    else:
        if change == 'source':
            raw['source_id'] = 'other'
        elif change == 'epoch':
            raw['process_epoch'] = 'f' * 32
        elif change == 'pid':
            raw['process']['pid'] += 1
        elif change == 'version':
            raw['version'] = True
        else:
            raw['unknown'] = None
        path.write_text(json.dumps(raw, separators=(',', ':'), sort_keys=True) + '\n')
    before = inventory(tmp_path)
    with pytest.raises((ValueError, FileNotFoundError)):
        verify_process_epoch(tmp_path, pin, expected)
    assert inventory(tmp_path) == before


def test_copied_root_is_not_the_expected_authority(tmp_path, pin):
    original = tmp_path / 'authority'
    original.mkdir(mode=0o700)
    expected = reserve_process_epoch(original, pin, source_id='fixture-server')
    copied = tmp_path / 'copied'
    shutil.copytree(original, copied)
    with pytest.raises(ValueError, match='root changed'):
        verify_process_epoch(copied, pin, expected)
    assert verify_process_epoch(original, pin, expected) == expected


def test_closed_pin_or_different_process_cannot_verify(tmp_path, child, approved):
    with pin_process(child.pid, **approved) as current:
        expected = reserve_process_epoch(tmp_path, current, source_id='fixture-server')
    with pytest.raises(ValueError, match='closed'):
        verify_process_epoch(tmp_path, current, expected)
    with pin_process(os.getpid(), **approved) as other, pytest.raises(ValueError, match='another process'):
        verify_process_epoch(tmp_path, other, expected)


def test_delivery_uses_fresh_record_and_exact_source(tmp_path, pin):
    host = tmp_path / 'host'
    host.mkdir(mode=0o700)
    expected = reserve_process_epoch(host, pin, source_id='fixture-server')
    authority, spool, pair = setup_pair(tmp_path / 'rounds')
    dispatch = prepare(authority, spool, pair)
    result = prepare_process_delivery(host, pin, expected, lifecycle_epoch='2' * 32,
                                      init_time=0, dispatch=dispatch)
    assert result.process_epoch == expected.process_epoch
    wrong = replace(dispatch, identity=replace(dispatch.identity, source_id='other'))
    with pytest.raises(ValueError, match='source disagrees'):
        prepare_process_delivery(host, pin, expected, lifecycle_epoch='2' * 32, init_time=0, dispatch=wrong)
    path = record_path(host)
    path.rename(path.with_suffix('.saved'))
    with pytest.raises(ValueError, match='record missing'):
        prepare_process_delivery(host, pin, expected, lifecycle_epoch='2' * 32, init_time=0, dispatch=dispatch)


def test_process_exit_during_serialization_refuses_delivery(tmp_path, pin, child, monkeypatch):
    host = tmp_path / 'host'
    host.mkdir(mode=0o700)
    expected = reserve_process_epoch(host, pin, source_id='fixture-server')
    authority, spool, pair = setup_pair(tmp_path / 'rounds')
    dispatch = prepare(authority, spool, pair)
    original = StatsDelivery.encode

    def encode_then_exit(value):
        wire = original(value)
        child.stdin.write('exit\n')
        child.stdin.flush()
        child.wait(timeout=5)
        return wire

    monkeypatch.setattr(StatsDelivery, 'encode', encode_then_exit)
    with pytest.raises(ValueError, match='exited'):
        prepare_process_delivery(host, pin, expected, lifecycle_epoch='2' * 32, init_time=0, dispatch=dispatch)


@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
@pytest.mark.parametrize('wrong_pin', [False, True])
@pytest.mark.parametrize('entrypoint', [False, True])
def test_real_pinned_lua_process_epoch_reaches_full_stats_writer(tmp_path, lua, wrong_pin, entrypoint):
    executable = Path(shutil.which(lua)).resolve()
    authority, spool, pair = setup_pair(tmp_path / 'rounds')
    dispatch = prepare(authority, spool, pair)
    directory = spool / dispatch.generation
    host = tmp_path / 'host'
    host.mkdir(mode=0o700)
    command = [str(executable), str(ROOT / 'tests/lua/runtime_identity_writer_harness.lua'),
               str(ROOT), str(directory), pair.first.source_id, pair.first.match_id,
               pair.first.round_id, pair.second.round_id, '1', dispatch.generation, 'bound-ipc', '@stdin',
               'required-entrypoint' if entrypoint else 'legacy-entrypoint', '1234']
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, umask=0o077) as child:
        try:
            assert child.stdout.readline().strip() == 'HOST_READY'
            init_line = child.stdout.readline().strip()
            assert init_line.startswith('INIT ')
            observation = decode_init_observation(init_line.removeprefix('INIT '))
            assert observation.init_time == 1234 and observation.round_number == 1
            with pin_process(child.pid, expected_uid=os.getuid(), expected_executable=executable,
                             expected_sha256=hashlib.sha256(executable.read_bytes()).hexdigest()) as current:
                epoch = reserve_process_epoch(host, current, source_id=pair.first.source_id)
                delivery = prepare_observed_process_delivery(host, current, epoch, lifecycle_epoch='2' * 32,
                                                             observation=observation, dispatch=dispatch)
                receiver_epoch = 'f' * 32 if wrong_pin else epoch.process_epoch
                assert not wrong_pin or receiver_epoch != epoch.process_epoch
                stdout, stderr = child.communicate(
                    delivery.encode() + '\n' + receiver_epoch + '\n' + delivery.lifecycle_epoch + '\n',
                    timeout=10)
                with pytest.raises(ValueError, match='exited'):
                    verify_process_epoch(host, current, epoch)
        finally:
            if child.stdin and not child.stdin.closed:
                child.stdin.close()
            child.wait(timeout=5)
    if wrong_pin:
        assert child.returncode != 0 and 'sender context mismatch' in stderr
        assert not list(directory.glob('*.txt'))
        assert not list(directory.glob('*.complete.json'))
        assert record_path(host).is_file()  # Failure never releases the claim.
        return
    assert child.returncode == 0, stdout + stderr
    assert 'IPC FULL MODULE accepted' in stdout
    receipts = [json.loads(line.removeprefix('receipt ')) for line in stdout.splitlines()
                if line.startswith('receipt ')]
    assert len(receipts) == 1
    envelope = receipts[0]
    assert envelope['generation'] == dispatch.generation
    receipt = envelope['completion']
    path = directory / receipt['filename']
    raw = path.read_bytes()
    assert len(raw) == receipt['bytes'] == path.stat().st_size
    assert stats_header_identity(raw.splitlines(keepends=True)[0].decode()) == pair.first
    assert record_completion_once(directory, receipt, expected_sha256=hashlib.sha256(raw).hexdigest()) == 'published'
    assert json.loads(record_path(host).read_bytes())['process_epoch'] == delivery.process_epoch
    print(f'HOST {lua} required={entrypoint}: observed InitGame1234 -> pinned Lua PID -> durable epoch -> leased IPC '
          '-> full c0rn -> real stats and completion; ET observations synthetic, no live engine')
