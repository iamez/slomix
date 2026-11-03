"""One-shot durable timing capture; no disk adoption after an ambiguous failure."""
import json
from dataclasses import dataclass
from pathlib import Path

from shared.runtime_host_bootstrap import _write_once
from shared.runtime_host_capture import _separate_roots
from shared.runtime_host_timing_completion import verify_timing_completion
from shared.runtime_round_identity import RoundIdentity
from shared.runtime_source_reservation import reserve_source_generation
from shared.runtime_spool import _publish_file
from shared.runtime_timing_snapshot import timing_snapshot


@dataclass(frozen=True)
class CapturedTiming:
    root: Path
    generation: str
    filename: str
    size: int
    sha256: str
    identity: RoundIdentity
    map_name: str


def capture_closed_timing(authority, pin, expected, *, accepted, completed,
                          expected_filename, source_directory, capture_root):
    """Reserve once, publish sealed bytes and fsynced manifest, retaining source.

    Caller owns independently approved roots and successful receiver result from
    the same attempt. A failed attempt may leave a reservation/payload/manifest;
    do not retry or treat a discovered manifest as successful authentication.
    Content parsing/DB attribution remain the bounded importer's responsibility.
    """
    _separate_roots(authority, source_directory, capture_root)
    verify_timing_completion(authority, pin, expected, accepted=accepted,
                             completed=completed, expected_filename=expected_filename)
    # No-clobber reservation consumes this attempt before any source read.
    directory = reserve_source_generation(capture_root, completed.generation)
    with timing_snapshot(authority, pin, expected, accepted=accepted, completed=completed,
                         expected_filename=expected_filename,
                         source_directory=source_directory) as (stream, digest):
        # Name and size have been validated by the authenticated timing snapshot.
        _publish_file(directory, completed.filename,
                      iter(lambda: stream.read(65536), b''), completed.size, digest)
        dispatch = accepted.delivery.dispatch
        record = dict(version=1, kind='timing', generation=completed.generation,
                      filename=completed.filename, bytes=completed.size, sha256=digest,
                      identity=dispatch.identity.encode(), map_name=dispatch.map_name)
        payload = json.dumps(record, sort_keys=True, separators=(',', ':')).encode('ascii') + b'\n'
        _write_once(directory, completed.generation, 'timing-capture.json', payload)
    return CapturedTiming(capture_root, completed.generation, completed.filename,
                          completed.size, digest, dispatch.identity, dispatch.map_name)
