"""Caller-owned blocking stream capture; no connections, threads or services."""

import math
import time
from pathlib import Path
from typing import Protocol

from shared.runtime_spool import publish_stats_file


class TimedReader(Protocol):
    """An exclusive stream whose read honours the timeout and requested size."""

    def settimeout(self, seconds: float) -> None:
        """Set the maximum blocking duration of the next read."""
        ...

    def read(self, size: int) -> bytes:
        """Read at most size bytes; empty bytes means end of snapshot."""
        ...


def capture_stats_stream(
    source: TimedReader, directory: Path, filename: str, *, expected_size: int,
    expected_sha256: str, max_bytes: int = 8 * 1024 * 1024,
    total_timeout: float = 30.0, read_timeout: float = 5.0,
    chunk_size: int = 64 * 1024,
) -> Path:
    """Publish a size/digest-verified stream within a cooperative read deadline.

    Caller opens/authenticates/closes the source and guarantees an immutable
    snapshot. This synchronous function changes its timeout (not restored) and
    must not run on an event loop. Reader must honour read size and timeout;
    arbitrary blocking Python cannot be forcibly interrupted here. No executor
    or cancellation claim is made. Deadline covers stream consumption, not
    connection setup, filesystem fsync/link or cleanup. EOF is required, so a
    source left open after sending expected bytes times out without publication.
    """
    for value in (total_timeout, read_timeout):
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError('Capture timeouts must be positive finite numbers')
    if type(chunk_size) is not int or not 1 <= chunk_size <= 64 * 1024:
        raise ValueError('Capture chunk size must be between 1 and 65536')
    if expected_sha256 is None:
        raise ValueError('Capture requires an expected SHA-256')
    deadline = time.monotonic() + total_timeout

    def chunks():
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Capture deadline exceeded')
            source.settimeout(min(read_timeout, remaining))
            chunk = source.read(chunk_size)
            if time.monotonic() >= deadline:
                raise TimeoutError('Capture deadline exceeded')
            if not isinstance(chunk, bytes) or len(chunk) > chunk_size:
                raise ValueError('Reader violated bounded bytes contract')
            if not chunk:
                return
            yield chunk

    return publish_stats_file(directory, filename, chunks(), expected_size=expected_size,
                              expected_sha256=expected_sha256, max_bytes=max_bytes)
