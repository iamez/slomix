"""Private proximity publication must not loosen legacy stats input contracts."""

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from proximity.parser import ProximityParserV4
from shared.proximity_source import read_verified_proximity_source
from shared.runtime_spool import publish_proximity_file, publish_stats_file

NAME = '2026-10-04-120000-fixture-round-1_engagements.txt'
PAYLOAD = b'# PROXIMITY_TRACKER_V4\n# map=fixture\n# round=1\n'
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


def publish(directory, chunks=None, **overrides):
    options = dict(expected_size=len(PAYLOAD), expected_sha256=DIGEST)
    options.update(overrides)
    return publish_proximity_file(directory, NAME, [PAYLOAD] if chunks is None else chunks, **options)


def verified(path):
    return read_verified_proximity_source(path, expected_size=len(PAYLOAD), expected_sha256=DIGEST)


def test_complete_publication_reaches_canonical_parser(tmp_path):
    def chunks():
        for chunk in (PAYLOAD[:10], PAYLOAD[10:]):
            assert not (tmp_path / NAME).exists()
            yield chunk
    path = publish(tmp_path, chunks())
    assert path.stat().st_size == len(PAYLOAD)
    assert path.stat().st_mode & 0o777 == 0o600
    assert verified(path) == PAYLOAD
    parser = ProximityParserV4()
    assert parser.parse_file(str(path), source_bytes=verified(path))
    assert parser.metadata['map_name'] == 'fixture'
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize('name', [NAME.replace('_engagements', ''), '../' + NAME,
                                NAME.replace('round-1', 'round-0'), NAME.replace('fixture', '..')])
def test_proximity_names_are_explicit(tmp_path, name):
    with pytest.raises(ValueError, match='filename'):
        publish_proximity_file(tmp_path, name, [PAYLOAD], expected_size=len(PAYLOAD), expected_sha256=DIGEST)
    assert list(tmp_path.iterdir()) == []


def test_stats_allowlist_not_widened(tmp_path):
    with pytest.raises(ValueError, match='filename'):
        publish_stats_file(tmp_path, NAME, [PAYLOAD], expected_size=len(PAYLOAD), expected_sha256=DIGEST)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('options', [
    {'expected_size': 0}, {'expected_size': True}, {'max_bytes': 1},
    {'expected_sha256': None}, {'expected_sha256': 'invalid'}, {'expected_sha256': 'A' * 64},
])
def test_invalid_metadata_does_not_consume_source(tmp_path, options):
    def chunks():
        raise AssertionError('invalid metadata consumed source')
        yield b''
    with pytest.raises(ValueError):
        publish(tmp_path, chunks(), **options)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('chunks', [[PAYLOAD[:-1]], [PAYLOAD + b'x'],
                                  [PAYLOAD.replace(b'fixture', b'changed')], ['not bytes']])
def test_bad_bytes_never_publish(tmp_path, chunks):
    with pytest.raises((ValueError, TypeError)):
        publish(tmp_path, chunks)
    assert list(tmp_path.iterdir()) == []


def test_stream_error_preserves_shared_source_and_no_final_file(tmp_path):
    shared = tmp_path / 'legacy'
    shared.mkdir(mode=0o775)
    source = shared / NAME
    source.write_bytes(PAYLOAD)
    source.chmod(0o664)
    private = tmp_path / 'private'
    private.mkdir(mode=0o700)
    def chunks():
        yield source.read_bytes()[:10]
        raise OSError('source unavailable')
    with pytest.raises(OSError, match='source unavailable'):
        publish(private, chunks())
    assert list(private.iterdir()) == []
    assert source.read_bytes() == PAYLOAD
    assert source.stat().st_mode & 0o777 == 0o664


@pytest.mark.parametrize('kind', ['same', 'different', 'symlink', 'fifo'])
def test_existing_final_never_replaced(tmp_path, kind):
    path = tmp_path / NAME
    if kind in ('same', 'different'):
        path.write_bytes(PAYLOAD if kind == 'same' else b'original')
    elif kind == 'symlink':
        path.symlink_to(tmp_path / 'absent')
    else:
        os.mkfifo(path, 0o600)
    before = path.lstat()
    with pytest.raises(FileExistsError):
        publish(tmp_path)
    after = path.lstat()
    assert (before.st_ino, before.st_mode, before.st_size) == (after.st_ino, after.st_mode, after.st_size)
    if kind in ('same', 'different'):
        assert path.read_bytes() == (PAYLOAD if kind == 'same' else b'original')
    assert list(tmp_path.iterdir()) == [path]


def test_concurrent_publishers_only_one_final(tmp_path):
    def attempt(_):
        try:
            return publish(tmp_path)
        except FileExistsError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert sum(result is not None for result in results) == 1
    assert verified(tmp_path / NAME) == PAYLOAD
    assert len(list(tmp_path.iterdir())) == 1


@pytest.mark.parametrize('fail_at', [1, 2])
def test_fsync_failures_keep_correct_evidence(tmp_path, monkeypatch, fail_at):
    original = os.fsync
    calls = 0
    def sync(fd):
        nonlocal calls
        calls += 1
        if calls == fail_at:
            raise OSError('injected fsync failure')
        original(fd)
    monkeypatch.setattr(os, 'fsync', sync)
    with pytest.raises(OSError, match='injected fsync failure'):
        publish(tmp_path)
    if fail_at == 1:
        assert list(tmp_path.iterdir()) == []
    else:
        assert verified(tmp_path / NAME) == PAYLOAD
        with pytest.raises(FileExistsError):
            publish(tmp_path)


def test_private_absolute_directory_required(tmp_path):
    with pytest.raises(ValueError, match='absolute Path'):
        publish(Path('relative'))
    target = tmp_path / 'shared'
    target.mkdir(mode=0o755)
    with pytest.raises(ValueError, match='0700'):
        publish(target)
    assert target.stat().st_mode & 0o777 == 0o755
    target.chmod(0o700)
    link = tmp_path / 'linked'
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(OSError):
        publish(link)
