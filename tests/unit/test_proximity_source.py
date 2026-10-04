"""Verified proximity input must be bounded, private and the exact bytes parsed."""

import hashlib
import os

import pytest

from proximity.parser import ProximityParserV4
from shared.proximity_source import read_verified_proximity_source


@pytest.fixture
def source(tmp_path):
    path = tmp_path / '2026-10-04-120000-fixture-round-1_engagements.txt'
    path.write_bytes(b'# map=fixture\r\n# round=1\n')
    path.chmod(0o600)
    return path


def read(path, payload=b'# map=fixture\r\n# round=1\n', **overrides):
    options = dict(expected_size=len(payload), expected_sha256=hashlib.sha256(payload).hexdigest())
    options.update(overrides)
    return read_verified_proximity_source(path, **options)


@pytest.mark.parametrize('mode', [0o400, 0o600])
def test_verified_bytes_survive_later_path_replacement(source, mode):
    source.chmod(mode)
    payload = read(source)
    replacement = source.with_suffix('.replacement')
    replacement.write_bytes(b'# map=replaced\n# round=2\n')
    replacement.replace(source)
    parser = ProximityParserV4()
    assert parser.parse_file(str(source), source_bytes=payload)
    assert parser.metadata['map_name'] == 'fixture'
    assert parser.metadata['round_num'] == 1


@pytest.mark.parametrize('options', [
    {'expected_size': 0}, {'expected_size': True}, {'expected_size': 1},
    {'max_bytes': 1}, {'max_bytes': False}, {'expected_sha256': 'a' * 64},
    {'expected_sha256': 'A' * 64}, {'expected_sha256': 'bad'},
])
def test_bad_metadata_rejected(source, options):
    with pytest.raises(ValueError):
        read(source, **options)


def test_non_private_file_rejected(source):
    source.chmod(0o644)
    with pytest.raises(ValueError, match='private regular'):
        read(source)


def test_non_private_directory_rejected(source):
    source.parent.chmod(0o755)
    with pytest.raises(ValueError, match='mode 0700'):
        read(source)


def test_symlink_and_fifo_rejected(source, tmp_path):
    directory = tmp_path / 'private'
    directory.mkdir(mode=0o700)
    link = directory / source.name
    link.symlink_to(source)
    with pytest.raises(OSError):
        read(link)
    fifo = tmp_path / '2026-10-04-120001-fixture-round-1_engagements.txt'
    os.mkfifo(fifo, 0o600)
    with pytest.raises(ValueError, match='private regular'):
        read(fifo)


@pytest.mark.parametrize('kind', ['in_place', 'replacement'])
def test_mutation_during_read_rejected(source, monkeypatch, kind):
    original_read = os.read
    changed = False
    def mutate(fd, size):
        nonlocal changed
        chunk = original_read(fd, size)
        if not changed:
            changed = True
            if kind == 'in_place':
                before = source.stat()
                source.write_bytes(b'# map=changed\r\n# round=1\n')
                # Same-size writes within one filesystem clock tick may have
                # identical metadata. Make this metadata-guard test deterministic;
                # exact-byte authenticity is separately enforced by the digest.
                os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns + 2_000_000_000))
            else:
                other = source.with_suffix('.replacement')
                other.write_bytes(chunk)
                other.chmod(0o600)
                other.replace(source)
        return chunk
    monkeypatch.setattr(os, 'read', mutate)
    with pytest.raises(RuntimeError, match='changed during read'):
        read(source)


@pytest.mark.parametrize('name', ['relative', '2026-10-04-120000-fixture-round-0_engagements.txt',
                                '2026-10-04-120000-fixture..bad-round-1_engagements.txt'])
def test_unsafe_filename_rejected(source, name):
    with pytest.raises(ValueError):
        read(source.with_name(name))
