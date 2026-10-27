"""Default-off standalone DEV team service; no Discord, dotenv or schema setup.

Run with python -m shared.runtime_team_main. Unlike the bounded proof CLI this
process keeps polling until SIGTERM/SIGINT. Configuration and owner-confirmed
team-writer handover must be supplied explicitly; confirmation is not a database
fence and does not stop legacy writers. No source acknowledgement is performed.
"""

import asyncio
import os
import signal
import time

from shared.runtime_cache_main import emit_status, serve
from shared.runtime_import_pool import ImportDatabaseConfig
from shared.runtime_team_worker import RuntimeTeamWorker, TeamWorkerState, team_worker_enabled


def database_from_environment():
    if (os.getenv('BOT_ENVIRONMENT') != 'dev'
            or os.getenv('RUNTIME_TEAM_DEV_HANDOVER_CONFIRMED') != 'true'):
        raise ValueError('Explicit DEV environment and team writer handover confirmation required')
    names = ('POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_DATABASE', 'POSTGRES_USER')
    if any(not os.getenv(name, '').strip() for name in names):
        raise ValueError('Explicit PostgreSQL configuration required')
    host, port, database, user = (os.environ[name] for name in names)
    return ImportDatabaseConfig(host, database, user, os.getenv('POSTGRES_PASSWORD', ''),
                                port=int(port), application_name='slomix-runtime-team-dev')


def report(state):
    """Last completed page, not total backlog, producer health or DB readiness."""
    completed = state.last_success_monotonic is not None
    age = None if not completed else max(0, time.monotonic() - state.last_success_monotonic)
    emit_status(dict(
        component='runtime_team_consumer', status=state.status,
        has_successful_page=completed,
        last_page={name: getattr(state, name) for name in
                   ('inspected', 'processed', 'pending', 'already_processed')} if completed else None,
        last_success_age_seconds=age, error_type=state.error_type, source_acknowledged=False,
    ))


async def run():
    if not team_worker_enabled():
        report(TeamWorkerState())
        return 0
    database = database_from_environment()
    worker = RuntimeTeamWorker()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    installed = []
    try:
        for signum in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(signum, stop.set)
            installed.append(signum)
        # Existing lifecycle owns its pool, task, periodic reporting and drain.
        # min_size=0 lets connection outages enter the worker retry loop.
        await serve(database, stop, worker=worker, reporter=report, task_prefix='runtime-team')
    finally:
        for signum in installed:
            loop.remove_signal_handler(signum)
    return 1 if worker.state.error_type is not None else 0


def main():
    try:
        return asyncio.run(run())
    except Exception as error:
        emit_status(dict(component='runtime_team_consumer', status='failed',
                         error_type=type(error).__name__, source_acknowledged=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
