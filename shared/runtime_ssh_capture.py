"""Picklable, capture-only SSH task for the disposable runtime worker."""

import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from shared.runtime_capture import capture_stats_stream
from shared.runtime_ssh import RuntimeSSHConfig, open_runtime_sftp


def _source_metadata(attributes):
    """Require regular-file metadata; omitted SFTP fields are not consent."""
    values = tuple(getattr(attributes, name, None) for name in ('st_mode', 'st_size', 'st_mtime'))
    if (any(type(value) is not int or value < 0 for value in values)
            or not stat.S_ISREG(values[0])):
        raise ValueError('Remote snapshot requires regular file mode, size and mtime')
    return values


class _CheckedReader:
    """Run remote stability checks before EOF can trigger local publication."""

    def __init__(self, source, verify):
        self.source = source
        self.verify = verify

    def settimeout(self, seconds):
        """Forward cooperative timeout to the remote file channel."""
        self.source.settimeout(seconds)

    def read(self, size):
        """Only a bytes EOF may trigger metadata verification."""
        chunk = self.source.read(size)
        if isinstance(chunk, bytes) and not chunk:
            self.verify()
        return chunk


@dataclass(frozen=True)
class SSHCaptureTask:
    """Capture one caller-selected immutable snapshot; never acknowledge/delete it.

    Run with run_bounded_capture_task, not on an event loop. Only configuration
    crosses spawn; SSH/session/file ownership starts inside the child. Caller
    supplies trusted size/digest and an absolute remote file path, not a shell
    command. No discovery, remote hashing, source immutability guarantee, retry
    reconciliation, DB import or service activation is provided here.

    A failed/timed-out worker can leave a partial or a complete final file (even
    on close failure after publication). Retain source and reconcile before any
    retry/acknowledgement. Normal completion alone is not an import receipt.
    Path/handle metadata must agree before and after reading, but SFTP metadata
    is not inode identity or a writer lock: same-size/same-mtime replacement and
    parent symlinks remain outside this guard. Trusted snapshot/digest required.
    """

    ssh: RuntimeSSHConfig
    remote_path: str
    directory: Path
    expected_size: int
    expected_sha256: str
    max_bytes: int = 8 * 1024 * 1024
    read_timeout: float = 5.0
    stream_timeout: float = 30.0

    def __post_init__(self):
        """Reject ambiguous paths before connecting to a remote host."""
        if (not isinstance(self.remote_path, str) or '\x00' in self.remote_path
                or not self.remote_path.startswith('/')
                or any(part in ('', '.', '..') for part in self.remote_path.split('/')[1:])):
            raise ValueError('Remote snapshot path must be absolute and canonical')
        if not isinstance(self.directory, Path) or not self.directory.is_absolute():
            raise ValueError('Spool directory must be an absolute Path')

    def __call__(self) -> None:
        """Close remote file before SFTP/SSH; propagate all capture/close failures."""
        with open_runtime_sftp(self.ssh) as sftp:
            before = _source_metadata(sftp.lstat(self.remote_path))
            if before[1] != self.expected_size:
                raise ValueError('Remote snapshot size differs from expected size')
            with sftp.open(self.remote_path, 'rb') as source:
                def verify():
                    if (_source_metadata(source.stat()) != before
                            or _source_metadata(sftp.lstat(self.remote_path)) != before):
                        raise RuntimeError('Remote snapshot changed during capture')

                verify()
                capture_stats_stream(
                    _CheckedReader(source, verify), self.directory, PurePosixPath(self.remote_path).name,
                    expected_size=self.expected_size, expected_sha256=self.expected_sha256,
                    max_bytes=self.max_bytes, total_timeout=self.stream_timeout,
                    read_timeout=self.read_timeout,
                )
