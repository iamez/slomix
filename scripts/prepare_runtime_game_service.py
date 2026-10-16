"""Prepare an offline rehearsal unit. Never link, enable or start a service.

Trusted stable same-UID ancestors are required. Capture-only is the default;
explicit proof import options do not prove database readiness or approval.
LimitFSIZE bounds individual files, NOT
aggregate disk use. Source and fresh workspace are checked again at launch.
"""

import argparse
import hashlib
import json
import os
import re
import secrets
import stat
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.prepare_runtime_game_bundle import _write_new  # noqa: E402
from scripts.runtime_game_startup import startup_recipe  # noqa: E402
from scripts.runtime_game_supervisor import supervisor_argv, verify_source  # noqa: E402


def safe_path(path):
    if (not isinstance(path, Path) or not path.is_absolute()
            or re.fullmatch(r'/[A-Za-z0-9_./-]+', str(path)) is None
            or '..' in path.parts or str(path).startswith('//')):
        raise ValueError('Explicit ASCII path without systemd expansions required')
    return str(path)


def _validate_team_policy(defer_team_assignment, proof_socket, proof_database_name,
                          import_lock_directory):
    if type(defer_team_assignment) is not bool:
        raise ValueError('Explicit boolean team ownership policy required')
    if defer_team_assignment and any(value is None for value in
                                    (proof_socket, proof_database_name, import_lock_directory)):
        raise ValueError('Deferred team assignment requires the complete proof import target')


def render(*, source, interpreter, workspace, destination, unit, commit,
           bot_fixture=None, bot_manifest_sha256=None, proof_socket=None,
           proof_database_name=None, import_lock_directory=None, defer_team_assignment=False):
    _validate_team_policy(defer_team_assignment, proof_socket, proof_database_name,
                          import_lock_directory)
    for path in (source, interpreter, workspace, destination):
        safe_path(path)
    if (re.fullmatch(r'slomix-et-proof-[a-f0-9]{16}\.service', unit) is None
            or re.fullmatch(r'[a-f0-9]{40}', commit) is None):
        raise ValueError('Invalid unit or commit')
    if (bot_fixture is None) != (bot_manifest_sha256 is None):
        raise ValueError('Bot fixture and manifest pin required together')
    options = (proof_socket, proof_database_name, import_lock_directory)
    if any(value is not None for value in options):
        if any(value is None for value in options):
            raise ValueError('Proof socket, database and import lock required together')
        safe_path(proof_socket)
        safe_path(import_lock_directory)
        if re.fullmatch(r'slomix_fixture_[0-9a-f]{32}', proof_database_name) is None:
            raise ValueError('Explicit disposable proof database required')
    if bot_fixture is not None:
        safe_path(bot_fixture)
        if re.fullmatch(r'[a-f0-9]{64}', bot_manifest_sha256) is None:
            raise ValueError('Invalid bot manifest pin')
    argv = supervisor_argv(source, interpreter, workspace, unit, commit,
        bot_fixture=bot_fixture, bot_manifest_sha256=bot_manifest_sha256,
        proof_socket=proof_socket, proof_database_name=proof_database_name,
        import_lock_directory=import_lock_directory, defer_team_assignment=defer_team_assignment)
    return f'''[Unit]
Description=Slomix isolated ET capture rehearsal (owner activation only)

[Service]
Type=exec
ExecStart={' '.join(argv)}
WorkingDirectory={source}
Restart=no
RemainAfterExit=no
RuntimeMaxSec=60min
TimeoutStopSec=30s
KillMode=control-group
KillSignal=SIGTERM
FinalKillSignal=SIGKILL
SendSIGKILL=yes
Delegate=no
PrivateNetwork=no
NoNewPrivileges=yes
UnsetEnvironment=PYTHONPATH PYTHONHOME LD_PRELOAD LD_LIBRARY_PATH LD_AUDIT
UMask=0077
MemoryMax=768M
TasksMax=64
LimitCORE=0
LimitFSIZE=64M
StandardInput=null
StandardOutput=append:{destination}/service.log
StandardError=inherit
'''


def prepare(*, source, interpreter, workspace, destination, commit,
            bot_fixture=None, bot_manifest_sha256=None, proof_socket=None,
            proof_database_name=None, import_lock_directory=None, defer_team_assignment=False):
    _validate_team_policy(defer_team_assignment, proof_socket, proof_database_name,
                          import_lock_directory)
    for path in (source, interpreter, workspace, destination):
        safe_path(path)
    verify_source(source, commit)
    startup_recipe(workspace, bot_fixture=bot_fixture, bot_manifest_sha256=bot_manifest_sha256)
    # Preserve lexical venv interpreter path; resolving its symlink would lose
    # pyvenv.cfg lookup and may silently select a different Python environment.
    if (not interpreter.is_file() or not os.access(interpreter, os.X_OK)
            or interpreter.stat().st_mode & 0o022):
        raise ValueError('Read-only executable interpreter required')
    if (destination.parent.resolve(strict=True) != destination.parent
            or destination.exists() or destination.is_symlink()):
        raise ValueError('Destination must be NEW under a canonical parent')
    parent = destination.parent.stat()
    if parent.st_uid != os.getuid() or stat.S_IMODE(parent.st_mode) != 0o700:
        raise ValueError('Destination parent must be owned and private')
    if any((p / '.git').exists() or (p / '.git').is_symlink() for p in destination.parents):
        raise ValueError('Unit artifacts must stay outside Git')
    if destination.is_relative_to(workspace) or workspace.is_relative_to(destination):
        raise ValueError('Service output and game workspace must be separate')
    unit = 'slomix-et-proof-' + secrets.token_hex(8) + '.service'
    content = render(source=source, interpreter=interpreter, workspace=workspace,
                     destination=destination, unit=unit, commit=commit,
                     bot_fixture=bot_fixture, bot_manifest_sha256=bot_manifest_sha256,
                     proof_socket=proof_socket, proof_database_name=proof_database_name,
                     import_lock_directory=import_lock_directory,
                     defer_team_assignment=defer_team_assignment).encode('ascii')
    destination.mkdir(mode=0o700)
    _write_new(destination / unit, content)
    _write_new(destination / 'service.log', b'')
    # Offline parser validation only: does not load/link/start the unit.
    result = subprocess.run(['/usr/bin/systemd-analyze', '--user', 'verify', str(destination / unit)],
                            capture_output=True, text=True, timeout=15,
                            env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C',
                                 'XDG_RUNTIME_DIR': f'/run/user/{os.getuid()}'})
    _write_new(destination / 'verify.txt', (result.stdout + result.stderr).encode())
    if result.returncode or result.stdout or result.stderr:
        raise ValueError('Offline unit verification failed or warned; artifacts retained')
    record = {'status': 'prepared_not_installed', 'activation_ready': False,
              'unit': unit, 'source_commit': commit, 'workspace': str(workspace),
              'bot_fixture': str(bot_fixture) if bot_fixture else None,
              'bot_manifest_sha256': bot_manifest_sha256,
              'import_requested': proof_socket is not None,
              'defer_team_assignment': defer_team_assignment,
              'database_readiness_verified': False,
              'unit_sha256': hashlib.sha256(content).hexdigest(),
              'limits': {'runtime_seconds': 3600, 'stop_seconds': 30,
                         'memory_bytes': 805306368, 'tasks': 64, 'per_file_bytes': 67108864},
              'remaining': ['explicit round fixture', 'owner activation',
                            'actual success/error/timeout cleanup proof', 'actual ET-to-PG proof']}
    _write_new(destination / 'service.json', (json.dumps(record, indent=2) + '\n').encode())
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'interpreter', 'workspace', 'destination'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--bot-fixture', type=Path)
    parser.add_argument('--bot-manifest-sha256')
    parser.add_argument('--proof-socket', type=Path)
    parser.add_argument('--proof-database-name')
    parser.add_argument('--import-lock-directory', type=Path)
    parser.add_argument('--defer-team-assignment', action='store_true',
                        help='Request journal-owned team assignment for the explicit proof import; '
                             'does not start a team consumer or authorize activation')
    try:
        print(json.dumps(prepare(**vars(parser.parse_args())), sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(json.dumps({'status': 'refused', 'error_type': type(exc).__name__,
                          'activation_ready': False, 'evidence_retained': True}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
