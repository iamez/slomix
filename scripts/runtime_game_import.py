"""Explicit private proof target for a live capture handoff; no DB discovery.

Naming and filesystem checks narrow accidental targets, not authentication.
The operator must approve the cluster and provision the schema separately.
No service lifecycle, database creation, retries or recovered-file authority.
"""

import asyncio
import logging
import os
import pwd
import re
import stat
from pathlib import Path

from bot.runtime_captured_import import import_captured_match
from scripts.dev_schema_preflight import inspect_database, migration_checksums
from shared.runtime_import_pool import ImportDatabaseConfig
from shared.runtime_writer_lock import local_import_writer


def proof_database(socket, database):
    """Validate the same local socket namespace used by prepared proof clusters.

    Recheck immediately before import; do not rely on a pre-game check alone.
    Same-UID trusted ownership is required throughout, not just at this instant.
    """
    # Fixed namespace comparison, not temporary file allocation.
    if (not isinstance(socket, Path) or not socket.is_absolute()
            or socket.parent != Path('/tmp')  # nosec B108
            or re.fullmatch(r'slomix-runtime-pg-[A-Za-z0-9_-]+', socket.name) is None
            or socket.resolve(strict=True) != socket):
        raise ValueError('Explicit private proof socket required')
    info = socket.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise ValueError('Private owner-only proof socket required')
    if not isinstance(database, str) or re.fullmatch(r'slomix_fixture_[0-9a-f]{32}', database) is None:
        raise ValueError('Explicit disposable proof database required')
    return ImportDatabaseConfig(str(socket), database, pwd.getpwuid(os.getuid()).pw_name, '')


async def preflight_import(*, socket, database, lock_directory):
    """Bounded read-only DB probe plus cooperative lock availability snapshot.

    Reuses ledger/checksum/minimum-column gate, not a full schema or privilege
    certificate. Lock may create its persistent empty file, never DB objects.
    Released before game launch; canonical import must acquire it again.
    """
    try:
        target = proof_database(socket, database)
        options = dict(host=target.socket, port=target.port, database=target.database,
                       user=target.user, password='', passfile=None, ssl=False,
                       timeout=5, command_timeout=8,
                       server_settings={'default_transaction_read_only': 'on',
                                        'statement_timeout': '8000', 'lock_timeout': '2000',
                                        'search_path': 'pg_catalog, public'})
        checksums = migration_checksums(Path(__file__).resolve().parents[1] / 'migrations')
        with local_import_writer(lock_directory):
            report = await asyncio.wait_for(inspect_database(options, checksums), timeout=20)
        if not report['clean'] or report['unknown_checksums']:
            raise ValueError('Proof schema contract is not confirmed')
        return {'status': 'readiness_snapshot_passed', 'full_schema_verified': False}
    except Exception:
        raise ValueError('Proof import readiness failed; no game should start') from None


async def import_live_capture(captured, *, socket, database, lock_directory, defer_team_assignment=False):
    """Recheck the explicit target and consume the live handoff once.

    Partial commits are possible on every unsuccessful outcome. No raw importer
    messages in the service log. This supervisor owns its single interpreter;
    logging suppression must not be shared with concurrent application tasks.
    """
    if type(defer_team_assignment) is not bool:
        raise ValueError('Explicit boolean team ownership policy required')
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        await preflight_import(socket=socket, database=database, lock_directory=lock_directory)
        target = proof_database(socket, database)
        outcomes = await import_captured_match(target, captured,
                                              lock_directory=lock_directory,
                                              attempt_timeout=60.0,
                                              defer_team_assignment=defer_team_assignment)
        successful = sum(item[0] is True for item in outcomes)
        return {'status': 'completed' if len(outcomes) == successful == 2 else 'incomplete',
                'attempted': len(outcomes), 'successful': successful,
                'source_acknowledged': False}
    except Exception as exc:
        return {'status': 'outcome_unknown', 'error_type': type(exc).__name__,
                'partial_commits_possible': True, 'source_acknowledged': False}
    finally:
        logging.disable(previous)
