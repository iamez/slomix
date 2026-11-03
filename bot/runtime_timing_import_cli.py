"""Explicit bounded stats + declared timing import; never a daemon or activation.

Run python -m bot.runtime_timing_import_cli --help. Supply all runtime_import_cli
arguments, plus --timing-directory, --timing-r1/--timing-r2 GENERATION FILENAME
BYTES SHA256 and --timing-writer-handover-confirmed. Enabled journal, explicit
--defer-team-assignment and independently trusted --expected-round-identities
are mandatory. Agreement with source bytes does not authenticate the producer.

Use one stable private lock directory shared with all cooperating import writers.
The operator must separately hand over legacy/manual stats AND correction writers;
flags and flock do not stop them or fence other hosts. Timing files are separate
from stats completion receipts; all four sources remain on EVERY outcome.

One writer pool (capacity one) serves stats and timing serially; a separately
owned readonly connection verifies committed receipts without starving the pool.
Current timing adapter supports Unix sockets, IPv4 and localhost, not IPv6.
Each stage owns its existing transaction. Failures, cancellation and close errors
can leave earlier commits. JSON reports only bounded stage statuses, never raw
exceptions, source content or credentials. Exit0 means independently observed
application of both halves AND successful cleanup;1 means incomplete/failed,
2 argument error,130 interruption. No retries, historical adoption, clock pairing,
source ACK/delete, schema bootstrap, Discord/web startup or service management.
"""

import asyncio
import json
import logging
import os
import signal
import stat
import sys
from contextlib import contextmanager
from pathlib import Path

from bot.runtime_completed_import import CompletedRoundInput, import_completed_round
from bot.runtime_gametime_application import apply_declared_gametime, inspect_declared_gametime_application
from bot.runtime_gametime_correlation import inspect_declared_gametime
from bot.runtime_gametime_link import link_declared_gametime
from bot.runtime_gametime_retention import retain_gametime_source
from bot.runtime_gametime_source import parse_verified_gametime
from bot.runtime_import_attempt import validate_attempt_policy, validate_import_envelope
from bot.runtime_import_cli import database_from_arguments, expected_pair, validate_database_mode
from bot.runtime_import_cli import parser as stats_parser
from bot.runtime_snapshot_pair import validate_pair_metadata
from shared.runtime_timing_resources import timing_import_resources
from shared.runtime_writer_lock import local_import_writer


def parser():
    result = stats_parser()
    result.description = __doc__
    result.add_argument('--timing-directory', required=True)
    result.add_argument('--timing-generation-directories', action='store_true',
                        help='Open each timing source inside its explicit generation directory')
    result.add_argument('--timing-writer-handover-confirmed', action='store_true', required=True)
    for half in (1, 2):
        result.add_argument(f'--timing-r{half}', nargs=4, required=True,
                            metavar=('GENERATION', 'FILENAME', 'BYTES', 'SHA256'))
    result.add_argument('--pipeline-timeout', type=float, default=180.0,
                        help='Cooperative whole-pipeline budget, including resource cleanup; max300seconds')
    return result


def validate_arguments(args):
    identities = expected_pair(args)
    validate_database_mode(args)
    if (None in identities or args.journal != 'enabled' or not args.defer_team_assignment
            or not args.timing_writer_handover_confirmed):
        raise ValueError('Timing pipeline requires trusted identities, enabled journal and deferred teams/handover')
    validate_attempt_policy(True, args.attempt_timeout)
    validate_attempt_policy(True, args.pipeline_timeout)
    return identities


@contextmanager
def _owned_descriptor(path, flags, *, dir_fd=None):
    fd = os.open(path, flags, dir_fd=dir_fd)
    try:
        yield fd
    finally:
        os.close(fd)


@contextmanager
def _timing_source(root_fd, fields, identity, map_name):
    generation, filename, size, digest = fields
    if not filename or Path(filename).name != filename or '\x00' in filename:
        raise ValueError('One explicit timing filename component required')
    with _owned_descriptor(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                           dir_fd=root_fd) as fd:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o002 or info.st_nlink != 1):
            # Lua commonly emits0664; the owned0700 directory bounds path
            # access. Hash/sealed-copy validation, not chmod, binds bytes.
            raise ValueError('Owned regular timing file without world writes or extra links required')
        binding = dict(source_id=identity.source_id, generation=generation, filename=filename,
                       expected_size=int(size), expected_sha256=digest, expected_identity=identity)
        timing = parse_verified_gametime(fd, **binding)
        if timing.map_name != map_name:
            raise ValueError('Timing map conflicts with declared stats pair')
        yield fd, binding


@contextmanager
def timing_sources(args, identities, map_name):
    """Own both explicit inputs lexically; verify ALL timing bytes before SQL."""
    root = Path(args.timing_directory)
    if not root.is_absolute() or root.resolve(strict=True) != root:
        raise ValueError('Canonical absolute timing directory required')
    with _owned_descriptor(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC) as root_fd:
        info = os.fstat(root_fd)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError('Timing directory must be private and owned by the operator')
        with (_generation_timing_source(root_fd, args.timing_r1, identities[0], map_name,
                                       getattr(args, 'timing_generation_directories', False)) as first,
              _generation_timing_source(root_fd, args.timing_r2, identities[1], map_name,
                                       getattr(args, 'timing_generation_directories', False)) as second):
            yield first, second


@contextmanager
def _generation_timing_source(root_fd, fields, identity, map_name, nested):
    if not nested:
        with _timing_source(root_fd, fields, identity, map_name) as source:
            yield source
        return
    import re

    if re.fullmatch('[0-9a-f]{32}', fields[0]) is None:
        raise ValueError('Explicit timing generation directory required')
    with _owned_descriptor(fields[0], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                           dir_fd=root_fd) as child:
        info = os.fstat(child)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError('Timing generation directory must be private and owned')
        with _timing_source(child, fields, identity, map_name) as source:
            yield source



def initial_progress():
    return dict(status='not_started', active_stage='preflight', effect_state='not_started',
                source_acknowledged=False,
                stats=[dict(round_number=half, status='not_attempted') for half in (1, 2)],
                timing=[dict(round_number=half, retention='not_attempted', correlation='not_attempted',
                             link='not_attempted', application='not_attempted', observation='not_attempted')
                        for half in (1, 2)])


async def execute(args, progress):
    identities = validate_arguments(args)
    database = database_from_arguments(args)
    first, second = (CompletedRoundInput(Path(args.spool), gen, name, int(size), digest)
                     for gen, name, size, digest in (args.r1, args.r2))
    for current, dependency, identity in ((first, None, identities[0]), (second, first, identities[1])):
        validate_import_envelope(current, dependency, identity, journal_enabled=True)
    map_name = validate_pair_metadata(first, second)
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    loop.add_signal_handler(signal.SIGTERM, task.cancel)
    try:
        with local_import_writer(Path(args.lock_directory)), timing_sources(args, identities, map_name) as timings:
            async with asyncio.timeout(args.pipeline_timeout):
                progress['active_stage'] = 'resources'
                async with timing_import_resources(database) as (manager, adapter, observer):
                    # There is no encompassing transaction. Each stage may commit.
                    progress['effect_state'] = 'possibly_partial'

                    async def stage(name, operation):
                        progress['active_stage'] = name
                        return await asyncio.wait_for(operation, args.attempt_timeout)

                    for index, (fd, binding) in enumerate(timings):
                        progress['timing'][index]['retention'] = 'unknown'
                        await stage(f'retain_r{index + 1}', retain_gametime_source(adapter, fd, **binding))
                        progress['timing'][index]['retention'] = 'retained'
                    for index, current in enumerate((first, second)):
                        progress['stats'][index]['status'] = 'unknown'
                        outcome = await stage(f'stats_r{index + 1}', import_completed_round(
                            manager, current, first=None if index == 0 else first,
                            expected_identity=identities[index], require_declared_identity=True,
                        ))
                        progress['stats'][index]['status'] = 'accepted' if outcome[0] is True else 'not_successful'
                        if outcome[0] is not True:
                            return False
                    for index, (fd, binding) in enumerate(timings):
                        row = progress['timing'][index]
                        row['correlation'] = 'unknown'
                        observed = await stage(f'correlate_r{index + 1}',
                                               inspect_declared_gametime(observer, fd, **binding))
                        row['correlation'] = observed.status
                        if observed.status != 'canonical_target_verified':
                            return False
                        row['link'] = 'unknown'
                        linked = await stage(f'link_r{index + 1}', link_declared_gametime(adapter, fd, **binding))
                        row['link'] = linked.status
                        if linked.status not in {'linked', 'already_linked'}:
                            return False
                        row['application'] = 'unknown'
                        applied = await stage(f'apply_r{index + 1}', apply_declared_gametime(adapter, fd, **binding))
                        row['application'] = applied.status
                        if applied.status not in {'applied', 'already_applied'}:
                            return False
                        row['observation'] = 'unknown'
                        visible = await stage(f'observe_r{index + 1}',
                                              inspect_declared_gametime_application(observer, fd, **binding))
                        row['observation'] = visible.status
                        if visible.status != 'applied':
                            return False
                    progress['effect_state'] = 'observed_complete'
                    progress['active_stage'] = 'cleanup'
                progress['active_stage'] = 'finished'
                return True
    finally:
        loop.remove_signal_handler(signal.SIGTERM)


def main(argv=None):
    arguments = parser()
    args = arguments.parse_args(argv)
    try:
        validate_arguments(args)
    except ValueError as error:
        arguments.error(str(error))
    progress = initial_progress()
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        success = asyncio.run(execute(args, progress))
        progress['status'], code = ('completed', 0) if success else ('incomplete', 1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        progress['status'], code = 'interrupted', 130
    except Exception:
        progress['status'], code = 'failed', 1
    finally:
        logging.disable(previous)
    sys.stdout.write(json.dumps(progress, sort_keys=True) + '\n')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
