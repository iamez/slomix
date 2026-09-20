"""Real filesystem proofs for complete-only, immutable stats publication."""

import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from shared.runtime_spool import publish_stats_file

NAME = '2026-09-20-120000-goldrush-round-1.txt'


def test_publication_visible_only_after_all_chunks(tmp_path):
    """Readers see no final filename during writes, then the exact complete file."""
    def chunks():
        for chunk in [b'header\n', b'player\n']:
            assert not (tmp_path / NAME).exists()
            yield chunk
    path = publish_stats_file(tmp_path, NAME, chunks(), expected_size=14)
    assert path.read_bytes() == b'header\nplayer\n'
    assert path.stat().st_size == 14
    assert list(tmp_path.iterdir()) == [path]
    assert path.stat().st_mode & 0o777 == 0o600
    print('Spool proof: final absent during streaming; complete 14-byte file published with mode 0600')


@pytest.mark.parametrize('chunks,size', [([b'x'], 2), ([b'xxx'], 2), (['x'], 1)])
def test_bad_stream_never_publishes(tmp_path, chunks, size):
    """Short, oversized and non-byte sources leave no final or temporary file."""
    with pytest.raises((ValueError, TypeError)):
        publish_stats_file(tmp_path, NAME, chunks, expected_size=size)
    assert list(tmp_path.iterdir()) == []


def test_source_failure_cleans_partial_file(tmp_path):
    """Transport exceptions cannot expose a partial final file."""
    def chunks():
        yield b'x'
        raise OSError('fixture disconnected')
    with pytest.raises(OSError, match='fixture disconnected'):
        publish_stats_file(tmp_path, NAME, chunks(), expected_size=2)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('symlink', [False, True])
def test_existing_destination_is_never_overwritten(tmp_path, symlink):
    """Both existing regular files and symlinks retain their original contents."""
    destination = tmp_path / NAME
    if symlink:
        other = tmp_path / 'target'
        other.write_bytes(b'old')
        destination.symlink_to(other)
    else:
        destination.write_bytes(b'old')
    with pytest.raises(FileExistsError):
        publish_stats_file(tmp_path, NAME, [b'new'], expected_size=3)
    assert destination.read_bytes() == b'old'
    assert not list(tmp_path.glob('*.part'))


@pytest.mark.parametrize('name', [
    '../escape.txt', '/absolute.txt', 'file.part', 'x\nround-1.txt',
    '2026-09-20-120000-map..name-round-1.txt',
])
def test_untrusted_names_rejected(tmp_path, name):
    """Only regular stats basenames may become import candidates."""
    with pytest.raises(ValueError, match='filename'):
        publish_stats_file(tmp_path, name, [b'x'], expected_size=1)


@pytest.mark.parametrize('map_name', ['map.with.dots', 'map+plus', 'map-with_dash'])
def test_transport_compatible_map_names(tmp_path, map_name):
    """Preserve the supported transport map alphabet without accepting traversal."""
    name = f'2026-09-20-120000-{map_name}-round-1.txt'
    path = publish_stats_file(tmp_path, name, [b'x'], expected_size=1)
    assert path.read_bytes() == b'x'


def test_directory_permissions_and_symlink_rejected(tmp_path):
    """The primitive requires a private non-symlink destination directory."""
    directory = tmp_path / 'spool'
    directory.mkdir(mode=0o755)
    with pytest.raises(ValueError, match='0700'):
        publish_stats_file(directory, NAME, [b'x'], expected_size=1)
    directory.chmod(0o700)
    link = tmp_path / 'link'
    link.symlink_to(directory, target_is_directory=True)
    with pytest.raises(OSError):
        publish_stats_file(link, NAME, [b'x'], expected_size=1)


def test_file_fsync_failure_prevents_publication(tmp_path, monkeypatch):
    """Durability errors before linking must not expose the destination."""
    def fail(fd):
        raise OSError('fixture fsync failed')
    monkeypatch.setattr(os, 'fsync', fail)
    with pytest.raises(OSError, match='fixture fsync failed'):
        publish_stats_file(tmp_path, NAME, [b'x'], expected_size=1)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('size,limit', [(0, 8), (-1, 8), (9, 8), (True, 8), (1, False)])
def test_invalid_limits_do_not_consume_source(tmp_path, size, limit):
    """Reject invalid metadata before reading any source bytes."""
    def chunks():
        raise AssertionError('Source must not be consumed')
        yield b''
    with pytest.raises(ValueError):
        publish_stats_file(tmp_path, NAME, chunks(), expected_size=size, max_bytes=limit)


def test_two_publishers_cannot_clobber_each_other(tmp_path):
    """Exactly one concurrent publisher wins the final filename."""
    def publish(payload):
        try:
            publish_stats_file(tmp_path, NAME, [payload], expected_size=3)
            return payload
        except FileExistsError:
            return None
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(publish, [b'one', b'two']))
    winners = [result for result in results if result is not None]
    assert len(winners) == 1
    assert (tmp_path / NAME).read_bytes() == winners[0]
    assert len(list(tmp_path.iterdir())) == 1


def test_directory_fsync_failure_keeps_complete_published_file(tmp_path, monkeypatch):
    """A post-publication error is ambiguous durability, not permission to overwrite."""
    original = os.fsync
    calls = []
    def sync(fd):
        calls.append(fd)
        if len(calls) == 2:
            raise OSError('fixture directory sync failed')
        original(fd)
    monkeypatch.setattr(os, 'fsync', sync)
    with pytest.raises(OSError, match='directory sync failed'):
        publish_stats_file(tmp_path, NAME, [b'one'], expected_size=3)
    assert (tmp_path / NAME).read_bytes() == b'one'
    assert len(list(tmp_path.iterdir())) == 1
