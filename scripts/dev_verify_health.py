"""Owner deployment gate: configured DEV units, fresh processes and exact build.

Read-only. Never starts/restarts a service or attempts automatic rollback.
"""
import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.dev_runtime_contract import load_contract  # noqa: E402
from shared.release_manifest import file_hash  # noqa: E402
from shared.runtime_environment import read_external_environment, refuse_config_overrides  # noqa: E402


def command_matches(value, expected):
    command = re.fullmatch(r'\{ path=([^;]+) ; argv\[\]=([^;]+) ; ignore_errors=no ; .* \}', value)
    return bool(command and command[1] == expected[0] and shlex.split(command[2]) == expected)


def release_unit_matches(name, values, specification):
    """Inspect resolved systemd properties, including overrides from drop-ins."""
    environment = dict(item.split('=', 1) for item in shlex.split(values.get('Environment', '')))
    if (values.get('Group') != specification['group'] or environment != specification['environment']
            or values.get('PassEnvironment') or values.get('UnsetEnvironment')
            or values.get('EnvironmentFiles')
            or values.get('ProtectSystem') != 'strict'
            or values.get('NoNewPrivileges') != 'yes' or values.get('PrivateTmp') != 'yes'
            or set(shlex.split(values.get('ReadOnlyPaths', ''))) != set(specification['read_only'])
            or set(shlex.split(values.get('ReadWritePaths', ''))) != set(specification['read_write'])
            or not command_matches(values.get('ExecStartPre', ''), specification['pre_argv'])):
        raise ValueError(f'{name}: release unit configuration differs from prepared contract')


def units(run, contract=None):
    if contract is not None and contract['release'] != str(run):
        raise ValueError('Release contract uses another working directory')
    result = {}
    for name, directory in (('etlegacy-bot', run), ('etlegacy-web', run / 'website')):
        output = subprocess.check_output([
            'systemctl', 'show', name, '-p', 'LoadState', '-p', 'ActiveState', '-p', 'MainPID',
            '-p', 'WorkingDirectory', '-p', 'Environment', '-p', 'EnvironmentFiles',
            '-p', 'ExecStart', '-p', 'User', '-p', 'PassEnvironment', '-p', 'Group',
            '-p', 'UnsetEnvironment', '-p', 'ExecStartPre', '-p', 'ProtectSystem',
            '-p', 'ReadOnlyPaths', '-p', 'ReadWritePaths', '-p', 'NoNewPrivileges', '-p', 'PrivateTmp',
        ], text=True, timeout=5)
        values = dict(line.split('=', 1) for line in output.splitlines() if '=' in line)
        if values.get('LoadState') != 'loaded' or values.get('WorkingDirectory') != str(directory):
            raise ValueError(f'{name}: unexpected unit/working directory')
        # Compare the existing unit command; this read-only probe never binds.
        expected = ([str(run / 'venv/bin/python3'), 'bot/ultimate_bot.py'] if name == 'etlegacy-bot'
                    else [str(run / 'website/venv/bin/python'), '-m', 'uvicorn', 'backend.main:app',
                          '--host', '0.0.0.0', '--port', '8000'])  # noqa: S104  # nosec B104
        if contract is not None:
            specification = contract['services'][name]
            expected = specification['argv']
            release_unit_matches(name, values, specification)
        if values.get('User') != 'samba' or not command_matches(values.get('ExecStart', ''), expected):
            raise ValueError(f'{name}: unexpected executable, arguments or service user')
        # dotenv override=False: an inherited DB override invalidates file proof.
        overrides = shlex.split(values.get('Environment', '')) + shlex.split(values.get('PassEnvironment', ''))
        if values.get('EnvironmentFiles') or any(
                value.split('=', 1)[0].startswith(('POSTGRES_', 'DB_', 'PG', 'DATABASE_')) for value in overrides):
            raise ValueError(f'{name}: unsupported inherited database configuration')
        result[name] = {'pid': int(values['MainPID']), 'active': values.get('ActiveState'),
                        'cwd': str(directory)}
    return result


def read_json(path):
    # Fixed loopback origin; disable ambient proxies and redirects.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open('http://127.0.0.1:8000' + path, timeout=3) as response:
        if response.status != 200:
            raise ValueError('Unexpected HTTP status')
        payload = response.read(65537)
        if len(payload) > 65536:
            raise ValueError('Oversized readiness response')
        result = json.loads(payload)
        if not isinstance(result, dict):
            raise ValueError('Readiness response must be an object')
        return result


def check(run, target, previous, contract=None):
    if contract is not None and contract['revision'] != target:
        raise ValueError('Release contract revision differs from requested target')
    current = units(run) if contract is None else units(run, contract)
    for name, state in current.items():
        if (state['active'] != 'active' or state['pid'] <= 0
                or state['pid'] == previous[name]['pid']):
            raise ValueError(f'{name}: not a fresh active process')
        if os.readlink(f'/proc/{state["pid"]}/cwd') != state['cwd']:
            raise ValueError(f'{name}: running process uses another checkout')
        if contract is not None:
            specification = contract['services'][name]
            if file_hash(Path(f'/proc/{state["pid"]}/exe')) != specification['python_sha256']:
                raise ValueError(f'{name}: running interpreter differs from contract')
            actual = Path(f'/proc/{state["pid"]}/cmdline').read_bytes().split(b'\0')
            if [os.fsdecode(part) for part in actual if part] != specification['argv']:
                raise ValueError(f'{name}: running command differs from release contract')
            process_env = dict(os.fsdecode(item).split('=', 1) for item in
                               Path(f'/proc/{state["pid"]}/environ').read_bytes().split(b'\0') if item)
            if any(process_env.get(key) != value for key, value in specification['environment'].items()):
                raise ValueError(f'{name}: running bootstrap environment differs from contract')
            env_path = Path(specification['environment']['SLOMIX_ENV_FILE'])
            refuse_config_overrides(read_external_environment(env_path, root=run), process_env)
    health = read_json('/health')
    if health.get('status') != 'ok' or health.get('database') != 'ok':
        raise ValueError('HTTP/database readiness is not healthy')
    build = read_json('/api/build')
    if build.get('revision') != target:
        raise ValueError('HTTP build does not match deployment target')
    if not isinstance(build.get('started_at'), str):
        raise ValueError('HTTP build is missing a valid start timestamp')
    started = datetime.fromisoformat(build['started_at'])
    if started.tzinfo is None or not previous['_captured_at'] <= started.timestamp() <= time.time():
        raise ValueError('HTTP build predates deployment capture or has an invalid clock')
    # Recheck processes after HTTP; don't certify a server that restarted mid-proof.
    if (units(run) if contract is None else units(run, contract)) != current:
        raise ValueError('Services changed during readiness verification')
    return current


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['capture', 'verify'])
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--target')
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--contract', type=Path, help='Prepared clean-release contract; omit for legacy capture')
    args = parser.parse_args(argv)
    if args.command == 'verify' and (not args.target or not args.previous):
        parser.error('verify requires --target and --previous')
    try:
        run = args.run.resolve(strict=True)
        contract = load_contract(args.contract) if args.contract else None
        if args.command == 'capture':
            captured = time.time()
            state = units(run) if contract is None else units(run, contract)
            print(json.dumps(dict(state, _captured_at=captured), sort_keys=True))
            return 0
        previous = json.loads(args.previous.read_text())
        deadline = time.monotonic() + 45
        while True:
            try:
                state = (check(run, args.target, previous) if contract is None
                         else check(run, args.target, previous, contract))
                if args.contract and load_contract(args.contract) != contract:
                    raise ValueError('Release contract changed during readiness verification')
                print(json.dumps({'healthy': True, 'revision': args.target, 'services': state}, sort_keys=True))
                return 0
            except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
                if time.monotonic() >= deadline:
                    raise ValueError('DEV readiness failed: units, process identity, HTTP or build mismatch') from None
                time.sleep(2)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        # Never echo unit Environment or HTTP response contents (may be secret).
        message = ('DEV readiness inspection could not complete' if args.contract or not isinstance(error, ValueError)
                   else str(error))
        print(json.dumps({'healthy': False, 'error': message}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
