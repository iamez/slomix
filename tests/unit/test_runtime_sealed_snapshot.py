"""Real Linux descriptor/sealing proofs without services, network or app data."""

import errno
import fcntl
import hashlib
import io
import mmap
import os
import subprocess

import pytest

from shared.runtime_sealed_snapshot import sealed_stats_snapshot

PAYLOAD = b'bounded stats snapshot\n'
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


def test_kernel_rejects_writes_and_resize_even_from_writable_duplicate(tmp_path):
    """Kernel protection survives source rewrite and a duplicate writable fd."""
    source = tmp_path / 'source'
    source.write_bytes(PAYLOAD)
    with source.open('rb') as original:
        original.seek(3)
        with sealed_stats_snapshot(original.fileno(), expected_size=len(PAYLOAD), expected_sha256=DIGEST) as view:
            fd = view.fileno()
            assert original.tell() == 3
            assert not os.get_inheritable(fd)
            with pytest.raises(io.UnsupportedOperation):
                view.write(b'x')
            source.write_bytes(b'x' * len(PAYLOAD))
            assert view.read() == PAYLOAD
            assert os.fstat(fd).st_size == len(PAYLOAD)
            actual = subprocess.check_output(['sha256sum', f'/proc/self/fd/{fd}'], pass_fds=(fd,), text=True)
            assert actual.split()[0] == DIGEST
            duplicate = os.dup(fd)
            try:
                for operation in (lambda: os.pwrite(duplicate, b'x', 0),
                                  lambda: os.ftruncate(duplicate, 1),
                                  lambda: os.ftruncate(duplicate, len(PAYLOAD) + 1),
                                  lambda: mmap.mmap(duplicate, len(PAYLOAD), access=mmap.ACCESS_WRITE)):
                    with pytest.raises(OSError) as failure:
                        operation()
                    assert failure.value.errno == errno.EPERM
            finally:
                os.close(duplicate)
            print('Kernel proof: original rewritten; sealed bytes/hash unchanged; write/grow/shrink/mmap denied')
        with pytest.raises(OSError):
            os.fstat(fd)
        assert not original.closed


@pytest.mark.parametrize('size,digest', [(0, DIGEST), (True, DIGEST), (8388609, DIGEST),
                                       (len(PAYLOAD), 'bad'), (len(PAYLOAD), '0' * 64)])
def test_invalid_contract_never_delivers_snapshot(tmp_path, size, digest):
    """Validation and hash failures do not leak descriptors or close the source."""
    source = tmp_path / 'source'
    source.write_bytes(PAYLOAD)
    with source.open('rb') as original:
        before = set(os.listdir('/proc/self/fd'))
        with pytest.raises(ValueError), sealed_stats_snapshot(
            original.fileno(), expected_size=size, expected_sha256=digest,
        ):
            pytest.fail('invalid input delivered')
        assert set(os.listdir('/proc/self/fd')) == before
        assert original.read() == PAYLOAD


def test_seal_failure_never_delivers_and_closes_descriptor(tmp_path, monkeypatch):
    """A failed kernel seal cannot degrade to a mutable successful snapshot."""
    source = tmp_path / 'source'
    source.write_bytes(PAYLOAD)
    real = fcntl.fcntl
    def reject(fd, operation, *args):
        if operation == fcntl.F_ADD_SEALS:
            raise OSError(errno.EPERM, 'fixture seal denied')
        return real(fd, operation, *args)
    monkeypatch.setattr(fcntl, 'fcntl', reject)
    with source.open('rb') as original:
        before = set(os.listdir('/proc/self/fd'))
        with pytest.raises(OSError, match='fixture seal denied'), sealed_stats_snapshot(
            original.fileno(), expected_size=len(PAYLOAD), expected_sha256=DIGEST,
        ):
            pytest.fail('unsealed snapshot delivered')
        assert set(os.listdir('/proc/self/fd')) == before


def test_consumer_failure_closes_snapshot(tmp_path):
    """A consumer exception does not keep the anonymous file alive."""
    source = tmp_path / 'source'
    source.write_bytes(PAYLOAD)
    with source.open('rb') as original:
        before = set(os.listdir('/proc/self/fd'))
        with pytest.raises(RuntimeError, match='consumer failed'), sealed_stats_snapshot(
            original.fileno(), expected_size=len(PAYLOAD), expected_sha256=DIGEST,
        ):
            raise RuntimeError('consumer failed')
        assert set(os.listdir('/proc/self/fd')) == before


def test_source_mutation_during_copy_refuses_delivery(tmp_path, monkeypatch):
    """Even originally correct read bytes do not excuse observed metadata drift."""
    source = tmp_path / 'source'
    source.write_bytes(PAYLOAD)
    real = os.pread
    def changed(fd, size, offset):
        data = real(fd, size, offset)
        source.write_bytes(b'changed')
        return data
    monkeypatch.setattr(os, 'pread', changed)
    with source.open('rb') as original, pytest.raises(ValueError, match='Source changed'), sealed_stats_snapshot(
        original.fileno(), expected_size=len(PAYLOAD), expected_sha256=DIGEST,
    ):
        pytest.fail('changed source delivered')
