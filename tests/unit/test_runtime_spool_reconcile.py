"""Read-only filesystem reconciliation after ambiguous publication outcomes."""

import os

import pytest

from shared.runtime_spool import inspect_published_stats_file, publish_stats_file

NAME = '2026-09-20-120000-map-round-1.txt'
DIGEST = 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'


def inspect(directory):
    """Verify the same immutable snapshot in every scenario."""
    return inspect_published_stats_file(directory, NAME, expected_size=3, expected_sha256=DIGEST)


def publish(directory):
    """Produce a real durable spool entry, not a mocked file descriptor."""
    return publish_stats_file(directory, NAME, [b'abc'], expected_size=3, expected_sha256=DIGEST)


def test_missing_then_matching(tmp_path):
    """Absence and verified content are distinct; inspection does not replace."""
    assert inspect(tmp_path) == 'missing'
    path = publish(tmp_path)
    before = path.stat()
    assert inspect(tmp_path) == 'match'
    assert path.read_bytes() == b'abc' and path.stat().st_size == 3
    assert path.stat().st_ino == before.st_ino
    assert path.stat().st_mtime_ns == before.st_mtime_ns
    print('Reconciliation proof: missing -> published -> match; exact bytes and inode retained')


@pytest.mark.parametrize('payload', [b'abd', b'ab', b'abcd'])
def test_conflict_is_never_overwritten(tmp_path, payload):
    """Equal-length corruption and size differences remain untouched conflicts."""
    path = publish(tmp_path)
    path.write_bytes(payload)
    assert inspect(tmp_path) == 'conflict'
    assert path.read_bytes() == payload


def test_directory_failure_is_not_missing(tmp_path):
    """Unavailable or insecure spool is not an empty successful observation."""
    with pytest.raises(FileNotFoundError):
        inspect(tmp_path / 'absent')
    tmp_path.chmod(0o755)
    with pytest.raises(ValueError, match='0700'):
        inspect(tmp_path)


@pytest.mark.parametrize('kind', ['symlink', 'fifo', 'directory', 'permissions'])
def test_unsafe_entries_rejected_without_blocking(tmp_path, kind):
    """Never follow symlinks or block opening a FIFO as if it were a file."""
    path = tmp_path / NAME
    if kind == 'symlink':
        path.symlink_to(tmp_path / 'missing-target')
    elif kind == 'fifo':
        os.mkfifo(path, 0o600)
    elif kind == 'directory':
        path.mkdir(mode=0o700)
    else:
        publish(tmp_path).chmod(0o644)
    with pytest.raises((ValueError, OSError)):
        inspect(tmp_path)
    assert os.path.lexists(path)


def test_io_error_is_not_conflict_or_missing(tmp_path, monkeypatch):
    """Unreadable content must propagate an operational failure."""
    publish(tmp_path)
    def fail(*args):
        raise OSError('fixture read failure')
    monkeypatch.setattr(os, 'read', fail)
    with pytest.raises(OSError, match='fixture read failure'):
        inspect(tmp_path)


def test_replacement_during_read_is_not_match(tmp_path, monkeypatch):
    """An opened old inode cannot certify a replacement at the final name."""
    path = publish(tmp_path)
    original_read = os.read
    replaced = False
    def read(fd, size):
        nonlocal replaced
        chunk = original_read(fd, size)
        if not replaced:
            replacement = tmp_path / 'replacement'
            replacement.write_bytes(b'xyz')
            replacement.chmod(0o600)
            os.replace(replacement, path)
            replaced = True
        return chunk
    monkeypatch.setattr(os, 'read', read)
    with pytest.raises(RuntimeError, match='changed during inspection'):
        inspect(tmp_path)
    assert path.read_bytes() == b'xyz'


def test_post_link_failure_can_be_inspected(tmp_path, monkeypatch):
    """Inspection recognizes content after directory fsync failed, not durability."""
    real_sync = os.fsync
    calls = 0
    def sync(fd):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError('fixture directory sync failed')
        real_sync(fd)
    monkeypatch.setattr(os, 'fsync', sync)
    with pytest.raises(OSError, match='directory sync'):
        publish(tmp_path)
    assert inspect(tmp_path) == 'match'
    assert (tmp_path / NAME).read_bytes() == b'abc'
    assert len(list(tmp_path.iterdir())) == 1


def test_inspection_requires_digest(tmp_path):
    """Never certify a retry using size alone."""
    with pytest.raises(ValueError, match='requires an expected SHA-256'):
        inspect_published_stats_file(tmp_path, NAME, expected_size=3, expected_sha256=None)
