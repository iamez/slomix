"""Explicit bounded development team consumer; no service or startup wiring.

Use --execute with an owner-approved private /tmp/slomix-runtime-pg-* socket,
existing slomix_fixture_<32hex> database and explicit role. Peer authentication
only. Naming/0700 ownership restrict accidental targets, not cluster identity.
The operator must verify the target, schema and exclusive writer handover first.
No dotenv, ambient database credentials, TCP fallback, migrations or source ACK.
EVENT_STREAM_ENABLED, RUNTIME_TEAM_EVENTS_ENABLED and RUNTIME_TEAM_WORKER_ENABLED
must all already be true. This command never enables them.

--run-seconds requests cooperative stop: an active page can finish or reach its
attempt timeout, then the owned adapter closes the pool. Cancellation-resistant
code can exceed these budgets; this is not a hard process deadline. SIGINT uses
asyncio.run cancellation and adapter cleanup. CLI SIGTERM requests cooperative
stop, allowing the active page to finish or time out before pool cleanup. Repeated
SIGTERM is idempotent. This bounded proof command is not a deployment procedure.
JSON describes lifecycle and the last completed page, not current database
health, complete backlog or source acknowledgement. Exit 0 requires at least
one completed page with no later recorded failure; 1 means failed, or stopped
without a completed page or with a later error;
2 means invalid arguments, 3 means disabled, 130 means interrupted.
"""

import argparse
import asyncio
import json
import logging
import math
import os
import re
import signal
import stat
import sys
from pathlib import Path

from shared.runtime_import_pool import ImportDatabaseConfig
from shared.runtime_team_session import run_team_worker
from shared.runtime_team_worker import RuntimeTeamWorker, TeamWorkerState, team_worker_enabled


class InvalidConfiguration(ValueError):
    """Rejected explicit CLI inputs, before pool construction."""


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--execute', action='store_true', required=True,
                        help='Explicitly authorize team effect/receipt writes to the approved target')
    for name in ('socket', 'database', 'user'):
        result.add_argument('--' + name, required=True)
    result.add_argument('--port', type=int, default=5432)
    result.add_argument('--run-seconds', type=float, required=True)
    result.add_argument('--batch-size', type=int, default=100)
    result.add_argument('--poll-seconds', type=float, default=5.0)
    result.add_argument('--attempt-timeout', type=float, default=10.0)
    result.add_argument('--close-timeout', type=float, default=5.0)
    return result


def _configuration(args):
    try:
        for value, upper in ((args.run_seconds, 3600), (args.poll_seconds, 300),
                             (args.attempt_timeout, 300), (args.close_timeout, 30)):
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= upper:
                raise ValueError('Invalid finite execution budget')
        socket = Path(args.socket)
        # This literal is an admission boundary, not a temporary file allocation.
        if (socket.parent != Path('/tmp')  # nosec B108
                or re.fullmatch(r'slomix-runtime-pg-[A-Za-z0-9_-]+', socket.name) is None
                or socket.resolve(strict=True) != socket):
            raise ValueError('Explicit private proof socket required')
        info = socket.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o700):
            raise ValueError('Private owner-only socket required')
        if re.fullmatch(r'slomix_fixture_[0-9a-f]{32}', args.database) is None:
            raise ValueError('Explicit disposable database required')
        database = ImportDatabaseConfig(str(socket), args.database, args.user, '', port=args.port,
                                        application_name='slomix-runtime-team-dev')
        worker = RuntimeTeamWorker(batch_size=args.batch_size, poll_seconds=args.poll_seconds,
                                   attempt_timeout=args.attempt_timeout)
        return database, worker
    except (ValueError, OSError, TypeError):
        raise InvalidConfiguration('Invalid explicit team consumer configuration') from None


def _report(state):
    completed = state.last_success_monotonic is not None
    return {'status': state.status, 'has_successful_page': completed,
            'last_page': {name: getattr(state, name) for name in
                          ('inspected', 'processed', 'pending', 'already_processed')} if completed else None,
            'last_error_type': state.error_type, 'source_acknowledged': False}


async def execute(args, *, handle_sigterm=False):
    """Await the existing owned session; cancel the stop timer on every exit."""
    if not team_worker_enabled():
        return _report(TeamWorkerState())
    database, worker = _configuration(args)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    timer = None
    installed = False
    try:
        # Only the process entrypoint opts in; borrowed async callers must not
        # replace their application's signal handlers.
        if handle_sigterm:
            loop.add_signal_handler(signal.SIGTERM, stop.set)
            installed = True
        timer = loop.call_later(args.run_seconds, stop.set)
        state = await run_team_worker(database, worker, stop, close_timeout=args.close_timeout)
        return _report(state)
    except Exception as error:
        report = _report(worker.state)
        report.update(status='failed', last_error_type=type(error).__name__)
        return report
    finally:
        if timer is not None:
            timer.cancel()
        if installed:
            loop.remove_signal_handler(signal.SIGTERM)


def main(argv=None):
    args = parser().parse_args(argv)
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        report = asyncio.run(execute(args, handle_sigterm=True))
        code = (3 if report['status'] == 'disabled' else
                0 if report['status'] == 'stopped' and report['has_successful_page']
                and report['last_error_type'] is None else 1)
    except InvalidConfiguration:
        report, code = _report(TeamWorkerState(status='invalid')), 2
    except KeyboardInterrupt:
        report, code = _report(TeamWorkerState(status='interrupted')), 130
        report['has_successful_page'] = None  # Interrupted caller has no final session report.
    except Exception as error:
        report, code = _report(TeamWorkerState(status='failed', error_type=type(error).__name__)), 1
        report['has_successful_page'] = None
    finally:
        logging.disable(previous)
    sys.stdout.write(json.dumps(report, sort_keys=True) + '\n')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
