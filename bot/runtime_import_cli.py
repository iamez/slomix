"""Explicit one-shot development importer; never a scheduler or service manager.

Run with python -m bot.runtime_import_cli --help. The operator authenticates the
database and both source expectations before invoking this command. Local paths,
hashes and receipts do not establish provenance. Peer authentication only; no
ambient credentials, dotenv, discovery, schema bootstrap or source deletion.

Required options: --execute --socket DIR --database NAME --user ROLE
--spool DIR --lock-directory DIR --journal enabled|disabled
--r1 GENERATION FILENAME BYTES SHA256 --r2 GENERATION FILENAME BYTES SHA256.
Optional --require-declared-identity rejects missing/contradictory producer IDs
before canonical preflight, including replay. It does not authenticate the source.
Optional --expected-round-identities R1_WIRE R2_WIRE supplies independently
authenticated v1 identities for atomic canonical mapping (migration099, journal
enabled, exclusive forward handover). Never copy these expectations from the
payload to manufacture trust. Both identities are required together.
Optional --defer-team-assignment leaves new team effects to the event consumer
and requires --journal enabled. Default remains legacy team assignment. This
option does not start a consumer or adopt existing rosters.
The schema must already exist. Directories must satisfy the existing private
spool/lock contracts. Exit 0 means canonical success (including warnings),
1 means incomplete/failed with potentially committed work, 2 is argument error,
130 is interruption. JSON never includes raw importer messages or credentials.
Retain both sources on every outcome. This command is not a daemon, a remote
source verifier, a cross-host writer lock or an approved deployment procedure.
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from bot.runtime_completed_import import CompletedRoundInput
from bot.runtime_import_batch import ImportJob, run_exclusive_import_batch
from bot.runtime_import_session import validate_team_policy
from shared.runtime_import_pool import ImportDatabaseConfig
from shared.runtime_round_identity import decode_round_identity, require_round_pair


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--execute', action='store_true', required=True,
                        help='Explicitly authorize writes to the supplied database')
    for name in ('socket', 'database', 'user', 'spool', 'lock-directory'):
        result.add_argument('--' + name, required=True)
    for number in (1, 2):
        result.add_argument(f'--r{number}', nargs=4, required=True,
                            metavar=('GENERATION', 'FILENAME', 'BYTES', 'SHA256'))
    result.add_argument('--attempt-timeout', type=float, default=60.0)
    result.add_argument('--journal', choices=('enabled', 'disabled'), required=True)
    result.add_argument('--defer-team-assignment', action='store_true',
                        help='Leave new team assignment to the event consumer; requires enabled journal')
    result.add_argument('--require-declared-identity', action='store_true',
                        help='Require matching explicit v1 producer identities; legacy default is off')
    result.add_argument('--expected-round-identities', nargs=2, type=decode_round_identity,
                        metavar=('R1_WIRE', 'R2_WIRE'),
                        help='Independently trusted pair for atomic mapping; requires enabled journal')
    return result


def expected_pair(args):
    validate_team_policy(args.defer_team_assignment, args.journal == 'enabled')
    if args.expected_round_identities is None:
        return None, None
    first, second = args.expected_round_identities
    require_round_pair(first, second)
    if args.journal != 'enabled':
        raise ValueError('Canonical identity mapping requires enabled journal')
    return first, second


async def execute(args):
    """One bounded pair, serially imported under the existing cooperative lock.

Partial commits are possible. A failure or timeout never proves rollback.
Canonical warning-success remains success; results do not certify validation.
No retries, cursor advancement, acknowledgements or removal of source files.
All cooperating writers must use this same stable lock directory/inode.
"""
    expected_first, expected_second = expected_pair(args)
    database = ImportDatabaseConfig(args.socket, args.database, args.user, '')
    root = Path(args.spool)
    inputs = []
    for number, fields in enumerate((args.r1, args.r2), start=1):
        generation, filename, size, digest = fields
        if not filename.endswith(f'-round-{number}.txt'):
            raise ValueError('Explicit ordered R1/R2 required')
        inputs.append(CompletedRoundInput(root, generation, filename, int(size), digest))
    first, second = inputs
    return await run_exclusive_import_batch(
        database, (ImportJob(first, expected_identity=expected_first),
                   ImportJob(second, first=first, expected_identity=expected_second)),
        lock_directory=Path(args.lock_directory), journal_enabled=args.journal == 'enabled',
        attempt_timeout=args.attempt_timeout,
        require_declared_identity=args.require_declared_identity,
        defer_team_assignment=args.defer_team_assignment,
    )


def main(argv=None):
    arguments = parser()
    args = arguments.parse_args(argv)
    try:
        expected_pair(args)
    except ValueError as exc:
        arguments.error(str(exc))
    # Legacy importer logs can contain payloads, paths and DB exceptions. This
    # explicit CLI emits only a bounded redacted summary; do not configure files.
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        outcomes = asyncio.run(execute(args))
        success = len(outcomes) == 2 and all(item[0] is True for item in outcomes)
        report = {'status': 'completed' if success else 'incomplete',
                  'attempted': len(outcomes),
                  'successful': sum(item[0] is True for item in outcomes),
                  'source_acknowledged': False}
        code = 0 if success else 1
    except KeyboardInterrupt:
        report, code = {'status': 'interrupted', 'source_acknowledged': False}, 130
    except Exception:
        # No raw exception text: database errors may contain sensitive details.
        report, code = {'status': 'failed', 'source_acknowledged': False}, 1
    finally:
        logging.disable(previous)
    sys.stdout.write(json.dumps(report, sort_keys=True) + '\n')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
