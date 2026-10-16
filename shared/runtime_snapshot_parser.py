"""Opt-in R1 parser bridge; never pass mutable spool paths to the parser."""

import re
from collections.abc import Callable
from datetime import datetime
from typing import Any

from shared.runtime_round_identity import stats_header_identity
from shared.runtime_sealed_snapshot import sealed_stats_snapshot


def parse_sealed_round_one(
    source_fd: int, *, filename: str, expected_size: int, expected_sha256: str,
    parse_regular: Callable[[str], dict[str, Any]],
    require_declared_identity: bool = False,
) -> dict[str, Any]:
    """Run the existing regular-file parser against verified kernel-sealed bytes.

    Caller supplies the bound parse_regular_stats_file method, trusted receipt
    metadata, and an authenticated source descriptor. Logical filename remains
    separate from the ephemeral /proc/self/fd path. No database or file identity
    is derived from that descriptor path. The callback must synchronously finish
    reading and return ordinary data; retaining descriptors is unsupported.
    Reject R2 rather than invoke filesystem discovery or import raw cumulative
    stats. Explicit sealed R1/R2 pairing is a separate integration gate.
    This does not activate ingestion, authenticate receipts, establish durable
    capture, or change the legacy parser's error/encoding conventions.
    Explicit require_declared_identity additionally requires a valid v1 header
    declaration, NOT proof of producer authenticity or non-reused physical IDs.
    """
    if type(require_declared_identity) is not bool:
        raise ValueError('Explicit boolean identity policy required')
    if (not isinstance(filename, str) or len(filename) > 240 or '..' in filename
            or re.fullmatch(r'\d{4}-\d{2}-\d{2}-\d{6}-[A-Za-z0-9_.+-]+-round-1\.txt', filename,
                            flags=re.ASCII) is None):
        raise ValueError('Sealed parser currently requires a round-1 filename')
    # Match the existing runtime dependency gate: syntactic digits are not
    # evidence of a real date/time. Fail before opening a snapshot or parsing.
    try:
        datetime.strptime(filename[:17] + '+0000', '%Y-%m-%d-%H%M%S%z')
    except ValueError as exc:
        raise ValueError('Snapshot filename has an invalid calendar timestamp') from exc
    with sealed_stats_snapshot(source_fd, expected_size=expected_size, expected_sha256=expected_sha256) as view:
        # Validate raw header before the legacy parser can default invalid round
        # text to R1. Decode identically to the existing parser, then rewind.
        raw_header = view.readline()
        if require_declared_identity:
            # Never let legacy ignore-errors decoding repair an identity token.
            if stats_header_identity(raw_header.decode('utf-8')) is None:
                raise ValueError('Declared round identity required')
        fields = raw_header.decode('utf-8', errors='ignore').strip().split('\\')
        expected_map = filename[18:-len('-round-1.txt')]
        if len(fields) < 8 or fields[3] != '1' or fields[1] != expected_map:
            raise ValueError('Snapshot header disagrees with round-1 identity')
        view.seek(0)
        result = parse_regular(f'/proc/self/fd/{view.fileno()}')
        if not isinstance(result, dict):
            raise ValueError('Parser must return a result dictionary')
        if result.get('success') is True and (
            type(result.get('round_num')) is not int or result['round_num'] != 1
            or result.get('map_name') != expected_map
        ):
            raise ValueError('Parser result disagrees with verified identity')
        return result
