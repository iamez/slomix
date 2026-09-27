"""One caller-driven capture attempt; no loop or source acknowledgement."""

from collections.abc import Iterable
from pathlib import Path
from typing import Literal

from shared.runtime_spool import inspect_published_stats_file, publish_stats_file


def capture_once(
    directory: Path, filename: str, chunks: Iterable[bytes], *,
    expected_size: int, expected_sha256: str, max_bytes: int = 8 * 1024 * 1024,
) -> Literal['published', 'content_present', 'conflict']:
    """Inspect first and consume the bounded source only when the final is absent.

    Caller owns immutable source identity, timeouts, iterator cleanup, retries
    and a private stable spool. content_present is not a durability/import ack;
    conflict requires explicit caller intervention, never replacement/deletion.
    All exceptions propagate, including publication races and post-link fsync
    failures. A later attempt inspects the final entry before consuming input.
    No catch of FileExistsError: the source itself may raise that exception,
    which must not be mistaken for a publication race or successful capture.
    """
    state = inspect_published_stats_file(
        directory, filename, expected_size=expected_size,
        expected_sha256=expected_sha256, max_bytes=max_bytes,
    )
    if state == 'match':
        return 'content_present'
    if state == 'conflict':
        return 'conflict'
    publish_stats_file(directory, filename, chunks, expected_size=expected_size,
                       expected_sha256=expected_sha256, max_bytes=max_bytes)
    return 'published'
