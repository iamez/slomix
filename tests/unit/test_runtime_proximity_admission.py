"""Persistent expected identity, no-clobber faults and fresh-process recovery."""

import hashlib
import json
import os
import stat
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from shared.runtime_proximity_admission import publish_proximity_admission, read_proximity_admission
from shared.runtime_source_reservation import reserve_source_generation

GENERATION = '0123456789abcdef' * 2
SOURCE = 'fixture-server'
NAME = '2026-10-05-120000-fixture-round-1_engagements.txt'
HASH = hashlib.sha256(b'fixture').hexdigest()
COMPLETION = dict(version=1, filename=NAME, bytes=7, state='writer_closed')
OPTIONS = dict(source_id=SOURCE, generation=GENERATION, completion=COMPLETION,
               expected_sha256=HASH, session_date=date(2026, 10, 4))
ENTRY = '.proximity-admission.json'


@pytest.fixture
def directory(tmp_path):
    tmp_path.chmod(0o700)
    return reserve_source_generation(tmp_path, GENERATION)


def read(directory, **overrides):
    return read_proximity_admission(directory, **(dict(source_id=SOURCE, generation=GENERATION) | overrides))


def test_publish_before_capture_and_recover_in_fresh_processes(directory, monkeypatch):
    assert read(directory) is None
    actual_sync = os.fsync
    phases = []

    def sync(fd):
        phase = 'directory' if stat.S_ISDIR(os.fstat(fd).st_mode) else 'file'
        phases.append(phase)
        assert (directory / ENTRY).exists() == (phase == 'directory')
        actual_sync(fd)

    with monkeypatch.context() as patch:
        patch.setattr(os, 'fsync', sync)
        path = publish_proximity_admission(directory, **OPTIONS)
    assert phases == ['file', 'directory']
    assert list(directory.iterdir()) == [path]  # No payload, DB or completion required.
    before = (path.stat().st_ino, path.stat().st_mode, path.read_bytes())
    script = '''
import importlib.abc, json, sys
from pathlib import Path
class NoDatabase(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'asyncpg', 'discord', 'website'}:
            raise AssertionError('Forbidden recovery dependency: ' + fullname)
sys.meta_path.insert(0, NoDatabase())
from shared.runtime_proximity_admission import read_proximity_admission
value = read_proximity_admission(Path(sys.argv[1]), source_id=sys.argv[2], generation=sys.argv[3])
print(json.dumps(dict(source=value.source_id, generation=value.generation,
    day=value.session_date.isoformat(), receipt=value.completion(), digest=value.sha256)))
'''
    results = []
    for _ in range(2):
        result = subprocess.run([sys.executable, '-B', '-c', script, str(directory), SOURCE, GENERATION],
                                cwd=Path(__file__).resolve().parents[2], capture_output=True,
                                text=True, timeout=10, check=True)
        results.append(json.loads(result.stdout))
    assert results[0] == results[1] == dict(source=SOURCE, generation=GENERATION,
        day='2026-10-04', receipt=COMPLETION, digest=HASH)
    on_disk = json.loads(path.read_text())
    assert on_disk['session_date'] == results[0]['day']
    assert on_disk['sha256'] == results[0]['digest']
    assert (path.stat().st_ino, path.stat().st_mode, path.read_bytes()) == before
    print('Admission proof: file fsync -> atomic link -> directory fsync; two fresh '
          'processes recover source/generation/date/size/hash without payload, DB or Discord')


@pytest.mark.parametrize('override', [{}, {'expected_sha256': '0' * 64}, {'session_date': date(2026, 10, 5)}])
def test_existing_identity_never_replaced(directory, override):
    path = publish_proximity_admission(directory, **OPTIONS)
    before = (path.stat().st_ino, path.read_bytes())
    with pytest.raises(FileExistsError):
        publish_proximity_admission(directory, **(OPTIONS | override))
    assert (path.stat().st_ino, path.read_bytes()) == before
    assert list(directory.iterdir()) == [path]


@pytest.mark.parametrize('phase', ['file', 'directory'])
def test_sync_failure_does_not_claim_success_or_overwrite(directory, monkeypatch, phase):
    original = os.fsync

    def sync(fd):
        kind = 'directory' if stat.S_ISDIR(os.fstat(fd).st_mode) else 'file'
        if kind == phase:
            raise OSError('fixture admission sync failure')
        original(fd)

    with monkeypatch.context() as patch:
        patch.setattr(os, 'fsync', sync)
        with pytest.raises(OSError, match='admission sync failure'):
            publish_proximity_admission(directory, **OPTIONS)
    if phase == 'file':
        assert read(directory) is None and list(directory.iterdir()) == []
        publish_proximity_admission(directory, **OPTIONS)
    else:
        assert read(directory).sha256 == HASH  # Observation, not durability recovery.
        with pytest.raises(FileExistsError):
            publish_proximity_admission(directory, **OPTIONS)


@pytest.mark.parametrize('override', [
    {'generation': 'a' * 32}, {'generation': '../unsafe'}, {'source_id': ''},
    {'source_id': 'Fixture'}, {'source_id': 'x' * 65}, {'source_id': 'secret\nvalue'}, {'session_date': None},
    {'session_date': '2026-10-05'}, {'expected_sha256': None}, {'expected_sha256': 'invalid'},
    {'completion': {**COMPLETION, 'bytes': True}},
    {'completion': {**COMPLETION, 'state': 'round_ended'}},
    {'completion': {**COMPLETION, 'filename': NAME.replace('_engagements', '')}},
])
def test_invalid_admission_does_not_write(directory, override):
    with pytest.raises((TypeError, ValueError)):
        publish_proximity_admission(directory, **(OPTIONS | override))
    assert list(directory.iterdir()) == []


@pytest.mark.parametrize('override', [{'source_id': 'another-server'}, {'generation': 'f' * 32}])
def test_reader_cannot_adopt_another_scope(directory, override):
    publish_proximity_admission(directory, **OPTIONS)
    with pytest.raises(ValueError):
        read(directory, **override)


@pytest.mark.parametrize('kind', ['truncated', 'null', 'oversize', 'duplicate', 'wrong_version',
                                  'wrong_kind', 'wrong_date', 'symlink', 'fifo', 'permissions'])
def test_unsafe_or_corrupt_admission_is_not_absent(directory, kind):
    path = publish_proximity_admission(directory, **OPTIONS)
    if kind == 'symlink' or kind == 'fifo':
        saved = directory / 'retained'
        path.rename(saved)
        if kind == 'symlink':
            path.symlink_to(saved)
        else:
            os.mkfifo(path, 0o600)
    elif kind == 'permissions':
        path.chmod(0o644)
    else:
        value = json.loads(path.read_text())
        if kind == 'wrong_version':
            value['version'] = True
        elif kind == 'wrong_kind':
            value['input_kind'] = 'stats'
        elif kind == 'wrong_date':
            value['session_date'] = '20261004'
        raw = dict(truncated='{', null='null', oversize=' ' * 4097,
                   duplicate=json.dumps(value)[:-1] + ',"version":1}').get(kind, json.dumps(value))
        path.write_text(raw)
    with pytest.raises((ValueError, OSError)):
        read(directory)


def test_missing_directory_is_not_missing_admission(tmp_path):
    with pytest.raises(FileNotFoundError):
        read(tmp_path / GENERATION)


def test_read_only_record_from_umask_stays_readable(directory):
    mask = os.umask(0o277)
    try:
        path = publish_proximity_admission(directory, **OPTIONS)
    finally:
        os.umask(mask)
    assert stat.S_IMODE(path.stat().st_mode) == 0o400
    assert read(directory).completion() == COMPLETION


@pytest.mark.parametrize('mask', [0o777, 0o677, 0o477])
def test_unreadable_admission_refused_before_publication(directory, mask):
    original = os.umask(mask)
    try:
        with pytest.raises(ValueError, match='owner-readable private file'):
            publish_proximity_admission(directory, **OPTIONS)
    finally:
        os.umask(original)
    assert list(directory.iterdir()) == []
    assert read(directory) is None
    # Refusal did not consume the no-clobber name; an ordinary retry recovers.
    publish_proximity_admission(directory, **OPTIONS)
    assert read(directory).sha256 == HASH
