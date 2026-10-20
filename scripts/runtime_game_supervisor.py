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
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path

POLICY = {'Type': 'exec', 'KillMode': 'control-group', 'Restart': 'no',
          'RemainAfterExit': 'no', 'RuntimeMaxUSec': '1h', 'TimeoutStopUSec': '30s',
          'SendSIGKILL': 'yes', 'KillSignal': '15', 'FinalKillSignal': '9',
          'Delegate': 'no', 'PrivateNetwork': 'no', 'NetworkNamespacePath': '',
          'MemoryMax': '805306368', 'TasksMax': '64', 'LimitFSIZE': '67108864',
          'LimitCORE': '0', 'NoNewPrivileges': 'yes', 'UMask': '0077'}
CLEARED_ENVIRONMENT = ('PYTHONPATH', 'PYTHONHOME', 'LD_PRELOAD', 'LD_LIBRARY_PATH', 'LD_AUDIT')
REHEARSAL_PORT = 27962
AUXILIARY_COMMANDS = ('ExecCondition', 'ExecStartPre', 'ExecStartPost', 'ExecReload', 'ExecStop', 'ExecStopPost')
PROPERTIES = (*POLICY, *AUXILIARY_COMMANDS, 'ExecStart', 'StandardOutput', 'StandardError', 'UnsetEnvironment', 'Environment', 'EnvironmentFiles', 'Id', 'MainPID', 'ControlGroup', 'ActiveState', 'SubState',
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
    if values.get('Environment', '') or values.get('EnvironmentFiles', ''):
        raise ValueError('Dedicated unit application environment must be empty')
    return values


# Trusted launch program is embedded verbatim in the prepared unit.
SUPERVISOR_BOOTSTRAP = "exec(bytes.fromhex('696d706f727420686173686c69622c6f732c737461742c7379730a706174682c6469676573742c736f757263653d7379732e617267765b313a345d0a7472793a0a2066643d6f732e6f70656e28706174682c6f732e4f5f52444f4e4c597c6f732e4f5f4e4f464f4c4c4f577c6f732e4f5f4e4f4e424c4f434b7c6f732e4f5f434c4f45584543290a207472793a0a2020696e666f3d6f732e6673746174286664290a20206966206e6f7420737461742e535f495352454728696e666f2e73745f6d6f646529206f7220696e666f2e73745f756964213d6f732e6765747569642829206f7220737461742e535f494d4f444528696e666f2e73745f6d6f646529213d306f3630303a2072616973652056616c75654572726f7228290a202077697468206f732e66646f70656e2866642c227262222c636c6f736566643d46616c7365292061732073747265616d3a207261773d73747265616d2e726561642831303438353737290a2066696e616c6c793a206f732e636c6f7365286664290a206966206c656e28726177293e31303438353736206f7220686173686c69622e73686132353628726177292e6865786469676573742829213d6469676573743a2072616973652056616c75654572726f7228290a65786365707420457863657074696f6e3a0a207379732e7374646572722e777269746528277b22737461747573223a22726566757365645f6f725f6661696c6564222c22726561736f6e223a2273757065727669736f725f61727469666163745f72656675736564222c2273687574646f776e5f7665726966696564223a66616c73652c2265766964656e63655f72657461696e6564223a747275657d5c6e27290a2072616973652053797374656d457869742831292066726f6d204e6f6e650a7379732e617267763d5b736f757263652c2a7379732e617267765b343a5d5d0a6578656328636f6d70696c65287261772c736f757263652c226578656322292c7b225f5f6e616d655f5f223a225f5f6d61696e5f5f222c225f5f66696c655f5f223a736f757263652c225f53555045525649534f525f534841323536223a6469676573747d290a'))"

def supervisor_argv(source, interpreter, directory, unit, commit, *, bot_fixture=None,
                    bot_manifest_sha256=None, proof_socket=None, proof_database_name=None,
                    import_lock_directory=None, defer_team_assignment=False, evidence_log=None,
                    supervisor_sha256=None):
    """One unambiguous argv shared by offline generation and live admission."""
    digest = supervisor_sha256 or globals().get('_SUPERVISOR_SHA256') or hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if re.fullmatch(r'[a-f0-9]{64}', digest) is None:
        raise ValueError('Pinned supervisor digest required')
    artifact = (evidence_log.parent if evidence_log is not None else directory.parent) / ('supervisor-' + digest + '.py')
    argv = ['/usr/bin/env', '-i', 'PATH=/usr/bin:/bin', 'LC_ALL=C', str(interpreter), '-I', '-B', '-c',
            SUPERVISOR_BOOTSTRAP, str(artifact), digest, str(source / 'scripts/runtime_game_supervisor.py'),
            'run', '--directory', str(directory), '--unit', unit, '--commit', commit]
    if bot_fixture is not None:
        argv += ['--bot-fixture', str(bot_fixture), '--bot-manifest-sha256', bot_manifest_sha256]
    if proof_socket is not None:
        argv += ['--proof-socket', str(proof_socket), '--proof-database-name', proof_database_name,
                 '--import-lock-directory', str(import_lock_directory)]
    if defer_team_assignment:
        argv += ['--defer-team-assignment']
    if evidence_log is not None:
        argv += ['--evidence-log', str(evidence_log)]
    if any(not isinstance(value, str) or (value != SUPERVISOR_BOOTSTRAP and re.fullmatch(r'[A-Za-z0-9_./=:-]+', value) is None)
           for value in argv):
        raise ValueError('Unambiguous ASCII supervisor arguments required')
    return argv


def validate_launch_commands(properties, expected_argv):
    """Check effective manager configuration, not historical absence of effects.

    systemctl omits unset execution-array properties even with --all. Any
    populated auxiliary command is forbidden. Same-UID actors that changed a
    unit after executing a command remain outside this cooperative proof.
    """
    if any(properties.get(name, '') for name in AUXILIARY_COMMANDS):
        raise ValueError('Auxiliary unit commands are forbidden')
    # Native systemctl display: exactly one non-ignored command, followed by
    # manager-owned execution metadata. No shell/wrapper or extra argv allowed.
    raw = properties.get('ExecStart', '')
    match = re.fullmatch(r'\{ path=([^ ;]+) ; argv\[\]=([^;]+) ; ignore_errors=no ; '
                         r'start_time=\[[^\]\n]*\] ; stop_time=\[[^\]\n]*\] ; '
                         r'pid=[0-9]+ ; code=[^;{}\n]+ ; status=[^;{}\n]+ \}', raw)
    if (match is None or match[1] != expected_argv[0]
            or match[2].strip() != ' '.join(expected_argv)):
        raise ValueError('Effective supervisor ExecStart disagrees')
    if '--evidence-log' not in expected_argv:
        raise ValueError('Explicit retained evidence log required')
    validate_evidence_sink(properties, Path(expected_argv[expected_argv.index('--evidence-log') + 1]))


def validate_evidence_sink(properties, path):
    """Verify the actual open descriptors as well as the manager's output modes."""
    if properties.get('StandardOutput') != 'append' or properties.get('StandardError') != 'inherit':
        raise ValueError('Effective retained evidence output policy disagrees')
    if not path.is_absolute() or path.resolve(strict=True) != path:
        raise ValueError('Canonical retained evidence path required')
    target = path.stat()
    if (not stat.S_ISREG(target.st_mode) or target.st_uid != os.getuid()
            or target.st_mode & 0o077):
        raise ValueError('Private owned regular evidence log required')
    for fd in (1, 2):
        actual = os.fstat(fd)
        if ((actual.st_dev, actual.st_ino) != (target.st_dev, target.st_ino)
                or not fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_APPEND):
            raise ValueError('Actual evidence descriptors disagree')


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
    if any(key not in {'PATH', 'LC_ALL', 'LC_CTYPE'} for key in os.environ):
        raise ValueError('Unexpected effective application environment')
    return values


def verify_source(source, expected_commit):
    if (not isinstance(source, Path) or source.resolve(strict=True) != source
            or re.fullmatch(r'[0-9a-f]{40}', expected_commit) is None):
        raise ValueError('Canonical committed source required')
    env = {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C', 'GIT_NO_REPLACE_OBJECTS': '1'}
    head = subprocess.run(['/usr/bin/git', '-c', 'core.fsmonitor=false', '-C', str(source), 'rev-parse', 'HEAD'],
                          env=env, capture_output=True, text=True, check=True, timeout=5)
    if head.stdout.strip() != expected_commit:
        raise ValueError('Supervisor source commit moved')
    entries = subprocess.run(['/usr/bin/git', '-c', 'core.fsmonitor=false', '-C', str(source), 'ls-files', '-v', '-z'],
                             env=env, capture_output=True, check=True, timeout=5).stdout
    if any(entry[:1].islower() or entry.startswith(b'S ') for entry in entries.split(b'\0') if entry):
        raise ValueError('Source has hidden index flags')
    # No excluded-standard flag: ignored Python modules/bytecode can shadow
    # imports too. Use a dedicated source checkout without generated state.
    unknown = subprocess.run(['/usr/bin/git', '-c', 'core.fsmonitor=false', '-C', str(source), 'ls-files', '--others', '-z'],
                             env=env, capture_output=True, check=True, timeout=5).stdout
    if unknown:
        raise ValueError('Source inventory must be closed, including ignored files')
    # Compare raw Git objects/index/worktree bytes: diff may execute local
    # clean filters even with fsmonitor disabled. No attributes conversion.
    command = ['/usr/bin/git', '-c', 'core.fsmonitor=false', '-C', str(source)]
    tree = subprocess.run([*command, 'ls-tree', '-r', '-z', expected_commit], env=env,
                          capture_output=True, check=True, timeout=5).stdout
    index = subprocess.run([*command, 'ls-files', '--stage', '-z'], env=env,
                           capture_output=True, check=True, timeout=5).stdout
    expected = {}
    for entry in tree.split(b'\0'):
        if not entry:
            continue
        meta, name = entry.split(b'\t', 1)
        mode, kind, oid = meta.split()
        if kind != b'blob' or mode not in {b'100644', b'100755', b'120000'}:
            raise ValueError('Unsupported committed source entry')
        expected[name] = (mode, oid)
    actual = {}
    for entry in index.split(b'\0'):
        if not entry:
            continue
        meta, name = entry.split(b'\t', 1)
        mode, oid, stage = meta.split()
        if stage != b'0' or name in actual:
            raise ValueError('Unmerged source index')
        actual[name] = (mode, oid)
    if actual != expected:
        raise subprocess.CalledProcessError(1, ['raw-source-index-comparison'])
    for name, (mode, oid) in expected.items():
        path = source / os.fsdecode(name)
        info = path.lstat()
        if mode == b'120000':
            if not stat.S_ISLNK(info.st_mode):
                raise ValueError('Source file type drift')
            raw = os.fsencode(os.readlink(path))
        else:
            if not stat.S_ISREG(info.st_mode):
                raise ValueError('Source file type drift')
            if bool(info.st_mode & 0o111) != (mode == b'100755'):
                raise subprocess.CalledProcessError(1, ['raw-source-mode-comparison'])
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
            try:
                opened = os.fstat(fd)
                if (not stat.S_ISREG(opened.st_mode)
                        or (opened.st_dev, opened.st_ino, opened.st_mode, opened.st_mtime_ns, opened.st_ctime_ns) !=
                        (info.st_dev, info.st_ino, info.st_mode, info.st_mtime_ns, info.st_ctime_ns)):
                    raise ValueError('Source changed while opening')
                with os.fdopen(fd, 'rb', closefd=False) as stream:
                    raw = stream.read()
                after = os.fstat(fd)
                if (opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns) != (
                        after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                    raise ValueError('Source changed while reading')
            finally:
                os.close(fd)
        encoded = b'blob ' + str(len(raw)).encode() + b'\0' + raw
        digest = (hashlib.sha1(encoded, usedforsecurity=False).hexdigest() if len(oid) == 40
                  else hashlib.sha256(encoded).hexdigest())
        if digest.encode() != oid:
            raise subprocess.CalledProcessError(1, ['raw-source-byte-comparison'])


def require_workspace_commit(recipe, expected_commit):
    """Bind the admitted Lua workspace bytes to the supervisor revision."""
    if recipe['workspace']['source_commit'] != expected_commit:
        raise ValueError('Workspace source commit does not match supervisor source')


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
                                 initial_readiness_wait=1800, bootstrap_wait=1800, completion_wait=3600)
        result.verify()
        return result


def run(directory, unit, expected_commit, *, bot_fixture=None, bot_manifest_sha256=None,
        proof_socket=None, proof_database_name=None, import_lock_directory=None,
        defer_team_assignment=False, evidence_log=None):
    if __name__ == '__main__' and not globals().get('_SUPERVISOR_SHA256'):
        raise ValueError('Verified external supervisor bootstrap required')
    if type(defer_team_assignment) is not bool:
        raise ValueError('Explicit boolean team ownership policy required')
    if defer_team_assignment and any(value is None for value in
                                    (proof_socket, proof_database_name, import_lock_directory)):
        raise ValueError('Deferred team assignment requires the complete proof import target')
    # No game side effect before all admission checks. Environment flags alone
    # do not prove service membership; ask the manager AND inspect kernel cgroup.
    expected_argv = supervisor_argv(Path(__file__).resolve().parents[1], sys.executable,
        directory, unit, expected_commit, bot_fixture=bot_fixture,
        bot_manifest_sha256=bot_manifest_sha256, proof_socket=proof_socket,
        proof_database_name=proof_database_name, import_lock_directory=import_lock_directory,
        defer_team_assignment=defer_team_assignment, evidence_log=evidence_log)
    admitted = require_containment(unit)
    validate_launch_commands(admitted, expected_argv)
    verify_source(Path(__file__).resolve().parents[1], expected_commit)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import_options = (proof_socket, proof_database_name, import_lock_directory)
    if any(value is not None for value in import_options):
        if any(value is None for value in import_options):
            raise ValueError('Proof socket, database and import lock required together')
        from scripts.runtime_game_import import preflight_import
        asyncio.run(preflight_import(socket=proof_socket, database=proof_database_name,
                                    lock_directory=import_lock_directory))
    recipe = startup_recipe(directory, port=REHEARSAL_PORT,
                            bot_fixture=bot_fixture, bot_manifest_sha256=bot_manifest_sha256)
    rechecked = require_containment(unit)
    validate_launch_commands(rechecked, expected_argv)
    if rechecked['InvocationID'] != admitted['InvocationID']:
        raise ValueError('Service invocation changed during admission')
    require_workspace_commit(recipe, expected_commit)
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
    if type(port) is not int or port != REHEARSAL_PORT:
        raise ValueError('Shutdown proof requires the fixed launched rehearsal UDP port')
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
    launch.add_argument('--evidence-log', type=Path)
    launch.add_argument('--bot-fixture', type=Path)
    launch.add_argument('--bot-manifest-sha256')
    launch.add_argument('--proof-socket', type=Path)
    launch.add_argument('--proof-database-name')
    launch.add_argument('--import-lock-directory', type=Path)
    launch.add_argument('--defer-team-assignment', action='store_true',
                        help='Defer team effects to the consumer; requires the complete proof import target')
    check = actions.add_parser('verify-stopped')
    check.add_argument('--unit', required=True)
    check.add_argument('--port', type=int, default=REHEARSAL_PORT)
    check.add_argument('--invocation-id', required=True)
    args = parser.parse_args(argv)
    try:
        result = (run(args.directory, args.unit, args.commit, bot_fixture=args.bot_fixture,
                      bot_manifest_sha256=args.bot_manifest_sha256,
                      proof_socket=args.proof_socket, proof_database_name=args.proof_database_name,
                      import_lock_directory=args.import_lock_directory,
                      defer_team_assignment=args.defer_team_assignment, evidence_log=args.evidence_log) if args.action == 'run'
                  else verify_stopped(args.unit, args.port, args.invocation_id))
        print(json.dumps(result, sort_keys=True), flush=True)
        return 0 if result.get('import', {}).get('status', 'completed') == 'completed' else 1
    except Exception as exc:
        print(json.dumps({'status': 'refused_or_failed', 'error_type': type(exc).__name__,
                          'shutdown_verified': False, 'evidence_retained': True}),
              file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
