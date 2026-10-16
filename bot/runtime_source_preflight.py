"""Read-only R1/R2 receipt and byte inspection; never import or acquire a lock.

Expectations must come from independently trusted capture records. This command
checks their agreement with local artifacts, not their provenance. It does not
parse gameplay statistics, connect to a database, acknowledge sources or authorize
activation. A later importer must revalidate its own inputs.
"""

import argparse
import json
import os
import sys
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path

from bot.runtime_completed_import import CompletedRoundInput
from bot.runtime_import_attempt import validate_import_envelope
from shared.runtime_completed_snapshot import open_completed_snapshot
from shared.runtime_round_identity import decode_round_identity, require_round_pair, stats_header_identity


def inspect_sources(first, second, *, expected_identities=None):
    """Verify both sealed snapshots; report no partial success if either fails."""
    started = datetime.now(timezone.utc).isoformat()
    if expected_identities is None:
        identities = (None, None)
    else:
        if not isinstance(expected_identities, tuple) or len(expected_identities) != 2:
            raise ValueError('Explicit pair of independently trusted identities required')
        require_round_pair(*expected_identities)
        identities = expected_identities
    validate_import_envelope(first, None, identities[0], journal_enabled=True)
    validate_import_envelope(second, first, identities[1], journal_enabled=True)
    with ExitStack() as stack:
        for item, expected in zip((first, second), identities, strict=True):
            view = stack.enter_context(open_completed_snapshot(
                item.root, item.generation, item.filename,
                expected_size=item.size, expected_sha256=item.sha256,
            ))
            if expected is not None:
                header = os.pread(view.fileno(), min(item.size, 4097), 0).splitlines(keepends=True)
                if not header or stats_header_identity(header[0].decode('utf-8')) != expected:
                    raise ValueError('Sealed header does not match independently trusted identity')
    return {
        'status': 'verified', 'scope': 'receipt_and_sealed_bytes_only',
        'capture_started_at_utc': started,
        'capture_finished_at_utc': datetime.now(timezone.utc).isoformat(),
        'verified_inputs': 2,
        'declared_identity': 'matched' if expected_identities is not None else 'unmeasured',
        'parser_checked': False, 'database_checked': False,
        'writer_exclusion_verified': False, 'source_acknowledged': False,
        'activation_ready': False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spool', required=True, type=Path)
    for half in (1, 2):
        parser.add_argument(f'--r{half}', required=True, nargs=4,
                            metavar=('GENERATION', 'FILENAME', 'BYTES', 'SHA256'))
    parser.add_argument('--expected-round-identities', nargs=2, type=decode_round_identity,
                        metavar=('R1_WIRE', 'R2_WIRE'))
    args = parser.parse_args(argv)
    try:
        inputs = [CompletedRoundInput(args.spool, values[0], values[1], int(values[2]), values[3])
                  for values in (args.r1, args.r2)]
        expected = tuple(args.expected_round_identities) if args.expected_round_identities else None
        report = inspect_sources(*inputs, expected_identities=expected)
        code = 0
    except KeyboardInterrupt:
        report, code = {'status': 'interrupted', 'activation_ready': False, 'source_acknowledged': False}, 130
    except Exception:
        # Do not print raw paths, source content or parser/OS exception strings.
        report, code = {'status': 'failed', 'activation_ready': False, 'source_acknowledged': False}, 1
    sys.stdout.write(json.dumps(report, sort_keys=True) + '\n')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
