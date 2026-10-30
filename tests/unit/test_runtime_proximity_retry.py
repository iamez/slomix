"""Retry pacing survives fresh processes and serializes cooperating workers."""

import asyncio
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from shared.runtime_proximity_admission import publish_proximity_admission
from shared.runtime_proximity_retry import reserve_proximity_retry
from shared.runtime_source_reservation import reserve_source_generation
from tests.unit.test_runtime_proximity_admission import GENERATION, OPTIONS, SOURCE


@pytest.fixture
def directory(tmp_path):
    tmp_path.chmod(0o700)
    return reserve_source_generation(tmp_path, GENERATION)


def reserve(directory, now=1000):
    return reserve_proximity_retry(directory, source_id=SOURCE, generation=GENERATION, now=now)


def snapshot(directory):
    return {p.name: (p.stat().st_ino, p.read_bytes()) for p in directory.iterdir()}


def child(directory, now):
    script = '''
import json, sys
from dataclasses import asdict
from pathlib import Path
from shared.runtime_proximity_retry import reserve_proximity_retry
with reserve_proximity_retry(Path(sys.argv[1]), source_id=sys.argv[2],
        generation=sys.argv[3], now=int(sys.argv[4])) as permit:
    print(json.dumps(asdict(permit)))
'''
    result = subprocess.run([sys.executable, '-c', script, str(directory), SOURCE, GENERATION, str(now)],
        cwd=Path(__file__).resolve().parents[2], text=True, capture_output=True, check=True, timeout=10)
    return json.loads(result.stdout)


def test_restart_backoff_and_cross_process_exclusion(directory):  # noqa: F811
    publish_proximity_admission(directory, **OPTIONS)
    with reserve(directory) as first:
        assert (first.status, first.attempt, first.retry_at) == ('reserved', 1, 1030)
        # It is already persistent before any work enters the guarded body.
        stored = json.loads((directory / '.proximity-attempt-001.json').read_text())
        assert stored['attempt'] == first.attempt and stored['retry_at'] == first.retry_at
        assert child(directory, 9000) == dict(status='busy', attempt=None, retry_at=None)
    before = snapshot(directory)
    for now in (900, 1029):
        assert child(directory, now) == dict(status='not_due', attempt=1, retry_at=1030)
    assert snapshot(directory) == before
    assert child(directory, 1030) == dict(status='reserved', attempt=2, retry_at=1090)
    records = [json.loads(p.read_text()) for p in sorted(directory.glob('.proximity-attempt-*.json'))]
    assert [r['attempt'] for r in records] == [1, 2]
    assert records[1]['started_at'] == records[0]['retry_at']
    print('Retry proof: fresh process busy while directory locked; restart retains '
          '1030 deadline and spent count; next process charges attempt 2 before work')


@pytest.mark.parametrize('failure', [RuntimeError, asyncio.CancelledError])
def test_error_spends_attempt_and_releases_lock(directory, failure):  # noqa: F811
    publish_proximity_admission(directory, **OPTIONS)
    with pytest.raises(failure), reserve(directory) as permit:
        assert permit.status == 'reserved'
        raise failure()
    assert child(directory, 1001)['status'] == 'not_due'
    assert child(directory, 1030)['attempt'] == 2


def test_abrupt_process_exit_releases_lock_without_reset(directory):  # noqa: F811
    publish_proximity_admission(directory, **OPTIONS)
    script = '''
import os, sys
from pathlib import Path
from shared.runtime_proximity_retry import reserve_proximity_retry
with reserve_proximity_retry(Path(sys.argv[1]), source_id=sys.argv[2],
        generation=sys.argv[3], now=1000) as permit:
    assert permit.status == 'reserved'
    os._exit(23)
'''
    result = subprocess.run([sys.executable, '-c', script, str(directory), SOURCE, GENERATION],
        cwd=Path(__file__).resolve().parents[2], timeout=10, check=False)
    assert result.returncode == 23
    assert child(directory, 1001)['status'] == 'not_due'
    assert child(directory, 1030)['attempt'] == 2


def test_missing_admission_does_not_publish(directory):  # noqa: F811
    with reserve(directory) as permit:
        assert permit.status == 'missing_admission'
    assert list(directory.iterdir()) == []


def test_capped_backoff_and_exhaustion_never_overwrites(directory):  # noqa: F811
    publish_proximity_admission(directory, **OPTIONS)
    now = 1000
    delays = []
    for number in range(1, 65):
        with reserve(directory, now) as permit:
            assert permit.status == 'reserved' and permit.attempt == number
            delays.append(permit.retry_at - now)
            now = permit.retry_at
    assert delays[:8] == [30, 60, 120, 240, 480, 960, 1800, 1800]
    assert set(delays[6:]) == {1800}
    before = snapshot(directory)
    assert child(directory, now + 86400)['status'] == 'exhausted'
    assert len(list(directory.glob('.proximity-attempt-*.json'))) == 64
    assert snapshot(directory) == before


@pytest.mark.parametrize('now', [True, -1, 1.0, float('nan'), None, '1000', 253402299000])
def test_invalid_clock_cannot_charge(directory, now):  # noqa: F811
    publish_proximity_admission(directory, **OPTIONS)
    before = snapshot(directory)
    with pytest.raises(ValueError, match='clock'), reserve(directory, now):
        pytest.fail('invalid clock admitted')
    assert snapshot(directory) == before


@pytest.mark.parametrize('kind', ['gap', 'corrupt', 'identity', 'deadline', 'overlap',
                                  'version', 'attempt', 'symlink', 'permissions'])
def test_bad_history_never_resets_or_admits(directory, kind):  # noqa: F811
    publish_proximity_admission(directory, **OPTIONS)
    with reserve(directory):
        pass
    path = directory / '.proximity-attempt-001.json'
    if kind == 'gap':
        path.rename(directory / '.proximity-attempt-002.json')
    elif kind == 'symlink':
        saved = directory / 'retained'
        path.rename(saved)
        path.symlink_to(saved)
    elif kind == 'permissions':
        path.chmod(0o644)
    elif kind == 'corrupt':
        path.write_text('{')
    else:
        data = json.loads(path.read_text())
        if kind == 'identity':
            data['identity_sha256'] = '0' * 64
        elif kind == 'deadline':
            data['retry_at'] = 1001
        elif kind == 'version':
            data['version'] = True
        elif kind == 'attempt':
            data['attempt'] = True
        else:
            path = directory / '.proximity-attempt-002.json'
            data.update(attempt=2, started_at=1029, retry_at=1089)
        path.write_text(json.dumps(data))
        path.chmod(0o600)
    with pytest.raises((ValueError, OSError)), reserve(directory, 9000):
        pytest.fail('bad history admitted')
    assert not (directory / '.proximity-attempt-003.json').exists()


@pytest.mark.parametrize('phase', ['file', 'directory'])
def test_failed_fsync_never_admits_work(directory, monkeypatch, phase):  # noqa: F811
    publish_proximity_admission(directory, **OPTIONS)
    original = os.fsync

    def sync(fd):
        kind = 'directory' if stat.S_ISDIR(os.fstat(fd).st_mode) else 'file'
        if kind == phase:
            raise OSError('fixture retry fsync failure')
        original(fd)

    with monkeypatch.context() as patch:
        patch.setattr(os, 'fsync', sync)
        with pytest.raises(OSError, match='fixture retry fsync failure'), reserve(directory):
            pytest.fail('failed publication admitted work')
    expected = 'reserved' if phase == 'file' else 'not_due'
    assert child(directory, 1000)['status'] == expected


def test_completion_does_not_imply_acknowledgment(directory):  # noqa: F811
    publish_proximity_admission(directory, **OPTIONS)
    admission = (directory / '.proximity-admission.json').read_bytes()
    with reserve(directory):
        pass  # Work may have returned successfully, but no commit proof exists.
    assert child(directory, 1030)['status'] == 'reserved'
    assert (directory / '.proximity-admission.json').read_bytes() == admission
