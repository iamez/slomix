"""Prepare a user-systemd consumer unit for a pinned release; never install/start it."""

import argparse
import json
import os
import re
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.release_manifest import file_hash, verify_release  # noqa: E402

COMPONENTS = {
    'team': {
        'description': 'team event consumer',
        'module': 'shared.runtime_team_main',
        'required': {'shared/runtime_team_main.py', 'shared/runtime_team_worker.py',
                     'shared/runtime_cache_main.py', 'shared/runtime_import_pool.py'},
        'handover_required': True,
    },
    'cache': {
        'description': 'HTTP cache event consumer',
        'module': 'shared.runtime_cache_main',
        'required': {'shared/runtime_cache_main.py', 'shared/runtime_cache_worker.py',
                     'shared/runtime_cache_consumer.py'},
        'handover_required': False,
    },
}


def canonical(path, *, interpreter=False):
    path = Path(path)
    if (not re.fullmatch(r'/[A-Za-z0-9_./-]+', str(path))
            or (path.parent.resolve(strict=True) != path.parent if interpreter
                else path.resolve(strict=True) != path)):
        raise ValueError('Existing canonical path without systemd expansions required')
    return path


# Check actual mount flags, not permission bits (the owner can chmod its files).
# Descendants are checked too, so a writable nested mount cannot evade the gate.
# Isolated stdlib startup avoids importing release code before this check.
READ_ONLY_RELEASE_CHECK = (
    "import os;from pathlib import Path;p=Path.cwd();"
    "paths=[p,*p.rglob('*')];"
    "raise SystemExit(0 if all(not q.is_symlink() and "
    "os.statvfs(q).f_flag & os.ST_RDONLY for q in paths) else 1)"
)


def render_unit(release, python, environment, expected_commit, *, component):
    """Exact unit policy, shared by preparation and independent verification."""
    spec = COMPONENTS[component]
    return f'''# Prepared only: owner installs as a USER unit after final acceptance.
# Source revision: {expected_commit}
[Unit]
Description=Slomix runtime {spec['description']} (DEV)
StartLimitIntervalSec=60
StartLimitBurst=3

[Service]
Type=simple
WorkingDirectory={release}
EnvironmentFile={environment}
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=PYTHONNOUSERSITE=1
Environment=PYTHONUNBUFFERED=1
UnsetEnvironment=PYTHONPATH PYTHONHOME LD_PRELOAD LD_LIBRARY_PATH LD_AUDIT
ExecStartPre={python} -I -B -c "{READ_ONLY_RELEASE_CHECK}"
ExecStart={python} -B -m {spec['module']}
Restart=on-failure
RestartSec=5
KillSignal=SIGTERM
KillMode=control-group
TimeoutStopSec=25
NoNewPrivileges=true
# User mount sandbox requires user namespaces; the pre-start guard fails closed.
PrivateUsers=true
ReadOnlyPaths={release}
UMask=0077
# Must see the configured host Unix socket, including private /tmp sockets.
PrivateTmp=false
StandardOutput=journal
StandardError=journal
SyslogIdentifier=slomix-runtime-{component}

[Install]
WantedBy=default.target
'''


def prepare(release, python, environment, destination, expected_commit, *, component):
    if component not in COMPONENTS:
        raise ValueError('Unknown runtime consumer')
    spec = COMPONENTS[component]
    release, environment = map(canonical, (release, environment))
    python = canonical(python, interpreter=True)
    record = verify_release(release)
    if (not re.fullmatch(r'[0-9a-f]{40}', expected_commit)
            or record['source_commit'] != expected_commit or release.name != expected_commit):
        raise ValueError('Expected immutable release named by its exact source revision')
    if not spec['required'] <= record['files'].keys():
        raise ValueError('Release lacks standalone consumer entrypoint')
    if not python.is_file() or not os.access(python, os.X_OK):
        raise ValueError('Explicit executable interpreter required')
    info = environment.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600 or environment.is_relative_to(release)):
        raise ValueError('Owner-only external configuration file required')
    destination = Path(destination).absolute()
    if destination.parent.resolve(strict=True) != destination.parent or destination.exists() or destination.is_symlink():
        raise ValueError('A new output directory under a canonical parent is required')
    if destination.is_relative_to(release):
        raise ValueError('Prepared units must stay outside the immutable release')
    unit = render_unit(release, python, environment, expected_commit, component=component)
    destination.mkdir(mode=0o700)
    unit_path = destination / f'slomix-runtime-{component}.service'
    with unit_path.open('x') as stream:
        stream.write(unit)
    unit_path.chmod(0o644)
    contract = dict(status='prepared_not_activated', scope='user', component=component,
                    source_commit=expected_commit,
                    release=str(release), interpreter=str(python), environment=str(environment),
                    unit_sha256=file_hash(unit_path), environment_sha256=file_hash(environment),
                    interpreter_sha256=file_hash(python), configuration_validated=False,
                    handover_required=spec['handover_required'],
                    handover_verified=False, runtime_acceptance='pending')
    with (destination / 'contract.json').open('x') as stream:
        json.dump(contract, stream, indent=2)
        stream.write('\n')
    return contract


def verify_prepared(contract_path):
    """Observe prepared bytes only; never execute the unit or load its environment."""
    path = canonical(contract_path)
    if not path.is_file() or path.stat().st_size > 65536:
        raise ValueError('Invalid prepared contract file')
    record = json.loads(path.read_text())
    if not isinstance(record, dict) or record.get('component') not in COMPONENTS:
        raise ValueError('Invalid prepared component')
    if record.get('status') != 'prepared_not_activated' or record.get('scope') != 'user':
        raise ValueError('Expected offline user-unit contract')
    release = canonical(record['release'])
    manifest = verify_release(release)
    if manifest['source_commit'] != record['source_commit'] or release.name != record['source_commit']:
        raise ValueError('Prepared release identity changed')
    if not COMPONENTS[record['component']]['required'] <= manifest['files'].keys():
        raise ValueError('Release lacks standalone consumer entrypoint')
    environment = canonical(record['environment'])
    interpreter = canonical(record['interpreter'], interpreter=True)
    info = environment.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600 or environment.is_relative_to(release)):
        raise ValueError('Owner-only external configuration file required')
    if not interpreter.is_file() or not os.access(interpreter, os.X_OK):
        raise ValueError('Explicit executable interpreter required')
    unit = canonical(path.parent / f"slomix-runtime-{record['component']}.service")
    if not unit.is_file():
        raise ValueError('Prepared unit must be a regular file')
    expected_unit = render_unit(release, interpreter, environment, record['source_commit'],
                                component=record['component'])
    if unit.read_bytes() != expected_unit.encode('utf-8'):
        raise ValueError('Prepared unit differs from required consumer policy')
    for artifact, key in ((environment, 'environment_sha256'),
                          (interpreter, 'interpreter_sha256'), (unit, 'unit_sha256')):
        expected = record.get(key)
        if (not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}', expected)
                or file_hash(artifact) != expected):
            raise ValueError('Prepared artifact fingerprint missing or changed')
    return dict(component=record['component'], source_commit=record['source_commit'],
                prepared_files_match=True, configuration_validated=False,
                effective_environment='unmeasured', handover_verified=False,
                release_write_boundary='required_at_start_unmeasured',
                activation_ready=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-contract', type=Path)
    for name in ('release', 'python', 'environment', 'destination'):
        parser.add_argument('--' + name, type=Path)
    parser.add_argument('--expected-commit')
    parser.add_argument('--component', choices=sorted(COMPONENTS))
    args = parser.parse_args(argv)
    if not args.verify_contract and any(getattr(args, name) is None for name in
            ('release', 'python', 'environment', 'destination', 'expected_commit', 'component')):
        parser.error('Preparation requires release, python, environment, destination, expected-commit and component')
    try:
        if args.verify_contract:
            if any(getattr(args, name) is not None for name in
                   ('release', 'python', 'environment', 'destination', 'expected_commit', 'component')):
                raise ValueError('Verification cannot be combined with preparation')
            print(json.dumps(verify_prepared(args.verify_contract)))
            return 0
        print(json.dumps(prepare(args.release, args.python, args.environment,
                                 args.destination, args.expected_commit,
                                 component=args.component)))
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f'Consumer unit preparation failed: {type(error).__name__}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
