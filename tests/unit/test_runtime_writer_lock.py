"""Actual kernel-lock and fresh-process proofs; no application services or DB."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from shared.runtime_writer_lock import ImportWriterBusy, local_import_writer

SCRIPT = '''
import os
from pathlib import Path
import sys
from shared.runtime_writer_lock import ImportWriterBusy, local_import_writer
try:
    with local_import_writer(Path(sys.argv[1])):
        print('owned', flush=True)
        if sys.argv[2] == 'exit':
            os._exit(23)
except ImportWriterBusy:
    print('busy', flush=True)
'''


def child(directory, mode='normal'):
    return subprocess.run(
        [sys.executable, '-c', SCRIPT, str(directory), mode],
        cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=5,
    )


def test_other_process_refused_then_acquires_after_release(tmp_path):
    tmp_path.chmod(0o700)
    with local_import_writer(tmp_path):
        result = child(tmp_path)
        assert result.returncode == 0 and result.stdout.strip() == 'busy', result.stderr
        with pytest.raises(ImportWriterBusy), local_import_writer(tmp_path):
            pytest.fail('Second descriptor acquired the same lock')
        inode = (tmp_path / '.import-writer.lock').stat().st_ino
    result = child(tmp_path)
    assert result.returncode == 0 and result.stdout.strip() == 'owned', result.stderr
    assert (tmp_path / '.import-writer.lock').stat().st_ino == inode
    print('Independent process refused while held; same persistent inode reusable after release')


def test_abrupt_owner_process_exit_releases_kernel_lock(tmp_path):
    tmp_path.chmod(0o700)
    exited = child(tmp_path, 'exit')
    assert exited.returncode == 23 and exited.stdout.strip() == 'owned', exited.stderr
    inode = (tmp_path / '.import-writer.lock').stat().st_ino
    following = child(tmp_path)
    assert following.returncode == 0 and following.stdout.strip() == 'owned', following.stderr
    assert (tmp_path / '.import-writer.lock').stat().st_ino == inode
    print('Abrupt test-process exit releases kernel lock without deleting a stale PID file')


def test_exception_releases_descriptors_and_preserves_file(tmp_path):
    tmp_path.chmod(0o700)
    before = set(os.listdir('/proc/self/fd'))
    with pytest.raises(RuntimeError, match='fixture'), local_import_writer(tmp_path):
        raise RuntimeError('fixture')
    assert set(os.listdir('/proc/self/fd')) == before
    with local_import_writer(tmp_path):
        assert (tmp_path / '.import-writer.lock').read_bytes() == b''


@pytest.mark.parametrize('kind', ['root_mode', 'root_symlink', 'file_mode', 'file_symlink', 'hardlink', 'fifo'])
def test_unsafe_namespace_refused_without_fd_leak(tmp_path, kind):
    directory = tmp_path / 'private'
    directory.mkdir(mode=0o700)
    lock = directory / '.import-writer.lock'
    if kind == 'root_mode':
        directory.chmod(0o755)
    elif kind == 'root_symlink':
        alias = tmp_path / 'alias'
        alias.symlink_to(directory, target_is_directory=True)
        directory = alias
    elif kind == 'file_symlink':
        lock.symlink_to(tmp_path / 'absent')
    elif kind == 'fifo':
        os.mkfifo(lock, 0o600)
    else:
        lock.touch(mode=0o600)
        if kind == 'file_mode':
            lock.chmod(0o644)
        else:
            os.link(lock, tmp_path / 'second-link')
    before = set(os.listdir('/proc/self/fd'))
    with pytest.raises((ValueError, OSError)), local_import_writer(directory):
        pytest.fail('Unsafe namespace accepted')
    assert set(os.listdir('/proc/self/fd')) == before
