"""Real filesystem proofs for exclusive source namespace reservation."""

import os
import stat
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from shared.runtime_source_reservation import claim_source_generation, reserve_source_generation

GENERATION_ID = '0123456789abcdef' * 2


def test_reservation_syncs_child_then_parent(tmp_path, monkeypatch):
    """Confirm directory mode/identity and child-before-parent sync ordering."""
    tmp_path.chmod(0o700)
    root_inode = tmp_path.stat().st_ino
    synced = []
    original = os.fsync
    def sync(fd):
        info = os.fstat(fd)
        assert stat.S_ISDIR(info.st_mode)
        synced.append(info.st_ino)
        original(fd)
    monkeypatch.setattr('shared.runtime_source_reservation.os.fsync', sync)
    result = reserve_source_generation(tmp_path, GENERATION_ID)
    assert result == tmp_path / GENERATION_ID
    assert stat.S_IMODE(result.stat().st_mode) == 0o700
    assert synced == [result.stat().st_ino, root_inode]
    assert list(result.iterdir()) == []
    print('Reservation proof: one private generation, child fsync then parent fsync')


@pytest.mark.parametrize('kind', ['empty', 'payload', 'file', 'symlink'])
def test_existing_generation_never_reused(tmp_path, kind):
    """All existing kinds block reservation, preserving identity and bytes."""
    tmp_path.chmod(0o700)
    target = tmp_path / GENERATION_ID
    if kind in ('empty', 'payload'):
        target.mkdir(mode=0o700)
        if kind == 'payload':
            (target / 'retained').write_bytes(b'original')
    elif kind == 'file':
        target.write_bytes(b'original')
    else:
        target.symlink_to(tmp_path, target_is_directory=True)
    inode = target.lstat().st_ino
    with pytest.raises(FileExistsError):
        reserve_source_generation(tmp_path, GENERATION_ID)
    assert target.lstat().st_ino == inode
    if kind == 'payload':
        assert (target / 'retained').read_bytes() == b'original'
    elif kind == 'file':
        assert target.read_bytes() == b'original'
    elif kind == 'symlink':
        assert target.is_symlink()


def test_concurrent_same_token_has_one_winner(tmp_path):
    """Two simultaneous real mkdir calls cannot reserve the same generation."""
    tmp_path.chmod(0o700)
    barrier = Barrier(2)
    def attempt():
        barrier.wait(timeout=5)
        try:
            return reserve_source_generation(tmp_path, GENERATION_ID)
        except FileExistsError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt) for _ in range(2)]
        results = [future.result(timeout=10) for future in futures]
    assert results.count(None) == 1
    assert [value for value in results if value is not None] == [tmp_path / GENERATION_ID]
    assert list(tmp_path.iterdir()) == [tmp_path / GENERATION_ID]


@pytest.mark.parametrize('failed_sync', [1, 2])
def test_sync_failure_retains_reservation(tmp_path, monkeypatch, failed_sync):
    """An ambiguous failure must not permit a second writer to reuse the token."""
    tmp_path.chmod(0o700)
    count = 0
    original = os.fsync
    def sync(fd):
        nonlocal count
        count += 1
        if count == failed_sync:
            raise OSError('fixture reservation sync failure')
        original(fd)
    monkeypatch.setattr('shared.runtime_source_reservation.os.fsync', sync)
    with pytest.raises(OSError, match='fixture reservation sync failure'):
        reserve_source_generation(tmp_path, GENERATION_ID)
    assert (tmp_path / GENERATION_ID).is_dir()
    with pytest.raises(FileExistsError):
        reserve_source_generation(tmp_path, GENERATION_ID)


@pytest.mark.parametrize('token', ['', '..', 'A' * 32, 'a' * 31, 'a' * 33, '../' + 'a' * 29, None])
def test_invalid_tokens_have_no_effect(tmp_path, token):
    """No path normalization, traversal or implicit generation repair."""
    with pytest.raises(ValueError):
        reserve_source_generation(tmp_path, token)
    assert list(tmp_path.iterdir()) == []


def test_unsafe_root_is_rejected(tmp_path):
    """Never reserve in a shared or symlinked root."""
    tmp_path.chmod(0o755)
    with pytest.raises(ValueError, match='owner|owned'):
        reserve_source_generation(tmp_path, GENERATION_ID)
    tmp_path.chmod(0o700)
    link = tmp_path / 'link'
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(OSError):
        reserve_source_generation(link, GENERATION_ID)
    assert not (tmp_path / GENERATION_ID).exists()


def test_claim_has_one_concurrent_winner(tmp_path):
    """Persistent exclusive marker prevents duplicate dispatch, including later calls."""
    tmp_path.chmod(0o700)
    reserved = reserve_source_generation(tmp_path, GENERATION_ID)
    barrier = Barrier(2)
    def attempt():
        barrier.wait(timeout=5)
        try:
            return claim_source_generation(tmp_path, GENERATION_ID)
        except FileExistsError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt) for _ in range(2)]
        results = [future.result(timeout=10) for future in futures]
    assert results.count(None) == 1 and results.count(reserved) == 1
    marker = reserved / '.writer-claimed'
    assert marker.read_bytes() == b'writer-claim-v1\n'
    assert stat.S_IMODE(marker.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        claim_source_generation(tmp_path, GENERATION_ID)


@pytest.mark.parametrize('phase', ['write', 'file-sync', 'dir-sync'])
def test_failed_claim_remains_consumed(tmp_path, monkeypatch, phase):
    """Even an empty/ambiguous claim cannot be silently reused after interruption."""
    tmp_path.chmod(0o700)
    reserved = reserve_source_generation(tmp_path, GENERATION_ID)
    original = os.fsync
    def sync(fd):
        is_dir = stat.S_ISDIR(os.fstat(fd).st_mode)
        if (phase == 'dir-sync') == is_dir:
            raise OSError('fixture claim sync failure')
        original(fd)
    with monkeypatch.context() as patch:
        if phase == 'write':
            patch.setattr('shared.runtime_source_reservation.os.write', lambda fd, data: 0)
        else:
            patch.setattr('shared.runtime_source_reservation.os.fsync', sync)
        with pytest.raises(OSError):
            claim_source_generation(tmp_path, GENERATION_ID)
    assert (reserved / '.writer-claimed').exists()
    with pytest.raises(FileExistsError):
        claim_source_generation(tmp_path, GENERATION_ID)
