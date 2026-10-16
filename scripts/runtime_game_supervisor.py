"""Owner-run, systemd-contained capture rehearsal. No install/start/stop command.

CLI requires Python isolated mode (-I); project imports wait for source admission.

The run command launches ET ONLY from the validated dedicated unit's main PID.
Systemd owns cleanup of the whole cgroup on main exit/error/timeout. A capture
receipt is diagnostic, not a recoverable import capability or shutdown proof.
No bots or round rotation are provisioned here; those remain activation gates.
The global 60-minute unit lifetime can interrupt per-phase readiness/completion
waits earlier. An interrupted or incomplete capture is never a successful proof.
"""
# ruff: noqa: E402 -- the isolated CLI guard must precede script-directory imports

import sys

if __name__ == '__main__':
    if not sys.flags.isolated:
        sys.stderr.write('{"status": "refused_or_failed", "error_type": "ValueError", '
                         '"reason": "isolated_python_required", '
                         '"shutdown_verified": false, "evidence_retained": true}\n')
        raise SystemExit(1)
    sys.dont_write_bytecode = True

import argparse
import asyncio
import json
import os
import re
import subprocess
from pathlib import Path

POLICY = {'Type': 'exec', 'KillMode': 'control-group', 'Restart': 'no',
          'RemainAfterExit': 'no', 'RuntimeMaxUSec': '1h', 'TimeoutStopUSec': '30s',
          'SendSIGKILL': 'yes', 'KillSignal': '15', 'FinalKillSignal': '9',
          'Delegate': 'no', 'PrivateNetwork': 'no', 'NetworkNamespacePath': '',
          'MemoryMax': '805306368', 'TasksMax': '64', 'LimitFSIZE': '67108864',
          'LimitCORE': '0', 'NoNewPrivileges': 'yes', 'UMask': '0077'}
CLEARED_ENVIRONMENT = ('PYTHONPATH', 'PYTHONHOME', 'LD_PRELOAD', 'LD_LIBRARY_PATH', 'LD_AUDIT')
PROPERTIES = (*POLICY, 'UnsetEnvironment', 'Id', 'MainPID', 'ControlGroup', 'ActiveState', 'SubState',
              'InvocationID', 'Result')


def unit_properties(unit):
    if not isinstance(unit, str) or re.fullmatch(r'slomix-et-proof-[a-z0-9]{8,32}\.service', unit) is None:
        raise ValueError('Explicit dedicated rehearsal unit name required')
    env = {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C',
           'XDG_RUNTIME_DIR': f'/run/user/{os.getuid()}'}
    result = subprocess.run(['/usr/bin/systemctl', '--user', 'show', '--all', unit,
                             '--property=' + ','.join(PROPERTIES)], env=env,
                            capture_output=True, text=True, check=True, timeout=5)
    if len(result.stdout) > 16384:
        raise ValueError('Unit property response exceeds bound')
    values = {}
    for line in result.stdout.splitlines():
        key, separator, value = line.partition('=')
        if not separator or key in values:
            raise ValueError('Invalid or duplicate unit property')
        values[key] = value
    if values.get('Id') != unit or any(values.get(k) != v for k, v in POLICY.items()):
        raise ValueError('Dedicated unit cleanup/lifetime policy disagrees')
    if set(values.get('UnsetEnvironment', '').split()) != set(CLEARED_ENVIRONMENT):
        raise ValueError('Dedicated unit inherited import environment is not cleared')
    return values


def require_containment(unit):
    values = unit_properties(unit)
    if (values.get('MainPID') != str(os.getpid()) or values.get('ActiveState') != 'active'
            or values.get('SubState') != 'running'
            or re.fullmatch(r'[0-9a-f]{32}', values.get('InvocationID', '')) is None):
        raise ValueError('Run only as the active dedicated systemd main process')
    group = values.get('ControlGroup', '')
    if (not group.startswith('/user.slice/') or '..' in group.split('/')
            or not group.endswith('/' + unit)
            or f'0::{group}' not in Path('/proc/self/cgroup').read_text().splitlines()):
        raise ValueError('Supervisor is not in the declared unified service cgroup')
    return values


def verify_source(source, expected_commit):
    if (not isinstance(source, Path) or source.resolve(strict=True) != source
            or re.fullmatch(r'[0-9a-f]{40}', expected_commit) is None):
        raise ValueError('Canonical committed source required')
    env = {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'}
    head = subprocess.run(['/usr/bin/git', '-C', str(source), 'rev-parse', 'HEAD'],
                          env=env, capture_output=True, text=True, check=True, timeout=5)
    if head.stdout.strip() != expected_commit:
        raise ValueError('Supervisor source commit moved')
    entries = subprocess.run(['/usr/bin/git', '-C', str(source), 'ls-files', '-v', '-z'],
                             env=env, capture_output=True, check=True, timeout=5).stdout
    if any(entry[:1].islower() or entry.startswith(b'S ') for entry in entries.split(b'\0') if entry):
        raise ValueError('Source has hidden index flags')
    # No excluded-standard flag: ignored Python modules/bytecode can shadow
    # imports too. Use a dedicated source checkout without generated state.
    unknown = subprocess.run(['/usr/bin/git', '-C', str(source), 'ls-files', '--others', '-z'],
                             env=env, capture_output=True, check=True, timeout=5).stdout
    if unknown:
        raise ValueError('Source inventory must be closed, including ignored files')
    # Include staged and unstaged edits before admitting any project imports.
    subprocess.run(['/usr/bin/git', '-C', str(source), 'diff', '--quiet', 'HEAD', '--'],
                   env=env, capture_output=True, check=True, timeout=5)


def startup_recipe(*args, **kwargs):
    """Lazy boundary: the service run verifies source before importing this."""
    from scripts.runtime_game_startup import startup_recipe as recipe

    return recipe(*args, **kwargs)


def capture_process(record, pid, stdin_fd):
    """Live handoff only. Caller already owns process lifecycle and log sink."""
    from shared.runtime_game_console import map_release
    from shared.runtime_identity_allocation import allocate_round_pair
    from shared.runtime_match_controller import RuntimeMatchController
    from shared.runtime_match_listener import serve_match
    from shared.runtime_process_authority import reserve_process_epoch
    from shared.runtime_process_pin import pin_process

    roots = {k: Path(v) for k, v in record['roots'].items()}
    with pin_process(pid, expected_uid=record['uid'],
                     expected_executable=Path(record['executable']),
                     expected_sha256=record['executable_sha256']) as pin:
        epoch = reserve_process_epoch(roots['host_authority'], pin, source_id=record['source_id'])
        pair = allocate_round_pair(roots['authority'], record['source_id'])
        driver = RuntimeMatchController(**roots, match_id=pair.first.match_id,
                                        source_id=record['source_id'], map_name=record['map_name'],
                                        pin=pin, epoch=epoch)
        with map_release(pin, stdin_fd) as release:
            result = serve_match(driver, Path(record['socket_path']), on_ready=release,
                                 initial_readiness_wait=1800, bootstrap_wait=1800, completion_wait=1500)
        result.verify()
        return result


def run(directory, unit, expected_commit, *, bot_fixture=None, bot_manifest_sha256=None,
        proof_socket=None, proof_database_name=None, import_lock_directory=None,
        defer_team_assignment=False):
    if type(defer_team_assignment) is not bool:
        raise ValueError('Explicit boolean team ownership policy required')
    if defer_team_assignment and any(value is None for value in
                                    (proof_socket, proof_database_name, import_lock_directory)):
        raise ValueError('Deferred team assignment requires the complete proof import target')
    # No game side effect before all admission checks. Environment flags alone
    # do not prove service membership; ask the manager AND inspect kernel cgroup.
    admitted = require_containment(unit)
    verify_source(Path(__file__).resolve().parents[1], expected_commit)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import_options = (proof_socket, proof_database_name, import_lock_directory)
    if any(value is not None for value in import_options):
        if any(value is None for value in import_options):
            raise ValueError('Proof socket, database and import lock required together')
        from scripts.runtime_game_import import preflight_import
        asyncio.run(preflight_import(socket=proof_socket, database=proof_database_name,
                                    lock_directory=import_lock_directory))
    recipe = startup_recipe(directory, bot_fixture=bot_fixture, bot_manifest_sha256=bot_manifest_sha256)
    if require_containment(unit)['InvocationID'] != admitted['InvocationID']:
        raise ValueError('Service invocation changed during admission')
    print(json.dumps({'status': 'admitted_not_captured', 'unit': unit,
                      'invocation_id': admitted['InvocationID']}), flush=True)
    # stdout/stderr inherit the unit's retained log file, NOT undrained PIPEs.
    # No Popen context manager: it would wait forever for a hung game on exit.
    # The main process must exit promptly so systemd can stop the whole unit.
    child = subprocess.Popen(recipe['argv'], cwd=recipe['cwd'], env=recipe['env'],
                             stdin=subprocess.PIPE, bufsize=0, close_fds=True, umask=0o077)
    try:
        os.set_blocking(child.stdin.fileno(), False)
        captured = capture_process(recipe['workspace'], child.pid, child.stdin.fileno())
        report = {'status': 'captured_not_imported_shutdown_pending', 'pid': child.pid,
                'unit': unit, 'invocation_id': admitted['InvocationID'],
                'match_id': captured.first_identity.match_id,
                'sha256': [captured.first.reference.sha256, captured.second.reference.sha256]}
        if proof_socket is not None:
            from scripts.runtime_game_import import import_live_capture
            report['import'] = asyncio.run(import_live_capture(
                captured, socket=proof_socket, database=proof_database_name,
                lock_directory=import_lock_directory, defer_team_assignment=defer_team_assignment))
            report['status'] = 'captured_import_attempted_shutdown_pending'
        return report
    finally:
        child.stdin.close()
        # Do NOT kill, terminate, redispatch or delete anything. Systemd handles
        # normal/error exit and RuntimeMaxSec. Post-stop verification is separate.


def verify_stopped(unit, port, invocation_id):
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError('Explicit rehearsal UDP port required')
    if not isinstance(invocation_id, str) or re.fullmatch(r'[0-9a-f]{32}', invocation_id) is None:
        raise ValueError('Explicit recorded invocation ID required')
    values = unit_properties(unit)
    if (values.get('ActiveState') not in ('inactive', 'failed') or values.get('MainPID') != '0'
            or values.get('ControlGroup') != ''
            or values.get('InvocationID') != invocation_id):
        raise ValueError('Executed unit shutdown is not confirmed')
    # Same host network namespace as the non-PrivateNetwork unit. Reject ANY
    # holder of this port, not just a guessed PID or executable name.
    for name in ('udp', 'udp6'):
        with Path('/proc/net', name).open('rb') as stream:
            raw = stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError('UDP inventory exceeds bound')
        for row in raw.splitlines()[1:]:
            fields = row.split()
            if len(fields) < 2 or b':' not in fields[1]:
                raise ValueError('Invalid UDP inventory')
            if int(fields[1].rsplit(b':', 1)[1], 16) == port:
                raise ValueError('Rehearsal UDP port is still occupied')
    return {'status': 'stopped', 'result': values.get('Result'),
            'invocation_id': values['InvocationID'], 'unit': unit, 'port': port,
            'match_success': 'not_inferred_from_shutdown'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    launch = actions.add_parser('run')
    launch.add_argument('--directory', type=Path, required=True)
    launch.add_argument('--unit', required=True)
    launch.add_argument('--commit', required=True)
    launch.add_argument('--bot-fixture', type=Path)
    launch.add_argument('--bot-manifest-sha256')
    launch.add_argument('--proof-socket', type=Path)
    launch.add_argument('--proof-database-name')
    launch.add_argument('--import-lock-directory', type=Path)
    launch.add_argument('--defer-team-assignment', action='store_true',
                        help='Defer team effects to the consumer; requires the complete proof import target')
    check = actions.add_parser('verify-stopped')
    check.add_argument('--unit', required=True)
    check.add_argument('--port', type=int, default=27962)
    check.add_argument('--invocation-id', required=True)
    args = parser.parse_args(argv)
    try:
        result = (run(args.directory, args.unit, args.commit, bot_fixture=args.bot_fixture,
                      bot_manifest_sha256=args.bot_manifest_sha256,
                      proof_socket=args.proof_socket, proof_database_name=args.proof_database_name,
                      import_lock_directory=args.import_lock_directory,
                      defer_team_assignment=args.defer_team_assignment) if args.action == 'run'
                  else verify_stopped(args.unit, args.port, args.invocation_id))
        print(json.dumps(result, sort_keys=True), flush=True)
        return 0 if result.get('import', {}).get('status', 'completed') == 'completed' else 1
    except (OSError, ValueError, KeyError, TypeError, ImportError, subprocess.SubprocessError) as exc:
        print(json.dumps({'status': 'refused_or_failed', 'error_type': type(exc).__name__,
                          'shutdown_verified': False, 'evidence_retained': True}),
              file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
