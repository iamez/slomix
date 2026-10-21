"""Copy a private Supply-only Omni-bot fixture, never load or enable it.

Trusted local installed distribution is the source, not a download. Preserve
scripts and notices; omit old user state, logs and unrelated map navigation.
The manifest is diagnostic inventory, not activation authority.
"""

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.prepare_runtime_game_bundle import _read_file, _write_new  # noqa: E402


def safe_path(path):
    if (not isinstance(path, Path) or not path.is_absolute()
            or re.fullmatch(r'/[A-Za-z0-9_./-]+', str(path)) is None
            or '..' in path.parts or str(path).startswith('//')):
        raise ValueError('Explicit canonical ASCII path required')

PROFILE = b'''[ServerManager]
MinBots = 6
MaxBots = 6
BalanceTeams = 1
SaveConfigChanges = 0
CountSpectators = 0
SleepBots = 0
InitialDelayTime = 2.1

[Versus]
BotTeam = -1
HumanTeam = -1
BotsPerHuman = 0

[Script]
LiveUpdate = false
'''
FIXED = ('README.txt', 'changelog.txt', 'omnibot_et.x86_64.so',
         'et/nav/supply.gm', 'et/nav/supply.way', 'et/nav/supply_goals.gm')


def verify(directory, manifest_sha256):
    """Pre-first-launch inventory check, externally pinned manifest, no loading."""
    safe_path(directory)
    if directory.resolve(strict=True) != directory:
        raise ValueError('Canonical bot directory required')
    raw = _read_file(directory / 'fixture.json', 1024 * 1024)
    if hashlib.sha256(raw).hexdigest() != manifest_sha256:
        raise ValueError('Bot manifest pin disagrees')
    record = json.loads(raw)
    files = record['files']
    if (record.get('status') != 'copied_not_enabled' or record.get('map') != 'supply'
            or record.get('activation_ready') is not False or not isinstance(files, dict)
            or not 7 <= len(files) <= 4097
            or not {*FIXED, 'et/user/omni-bot.cfg'} <= set(files)):
        raise ValueError('Invalid bot fixture inventory')
    expected_dirs = {'.', 'et/logs'}
    for name in files:
        path = Path(name)
        if path.is_absolute() or '..' in path.parts or str(path) != name:
            raise ValueError('Invalid bot inventory path')
        if name not in (*FIXED, 'et/user/omni-bot.cfg') and not name.startswith(('global_scripts/', 'et/scripts/')):
            raise ValueError('Unexpected bot inventory member')
        expected_dirs.update(str(p) for p in path.parents)
    observed_files, observed_dirs = set(), set()
    for current, dirs, names in os.walk(directory, followlinks=False):
        for path in (Path(current), *(Path(current) / n for n in dirs + names)):
            info = path.lstat()
            is_dir = stat.S_ISDIR(info.st_mode)
            if (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != (0o700 if is_dir else 0o600)
                    or not (is_dir or stat.S_ISREG(info.st_mode))):
                raise ValueError('Bot fixture must remain private and unlinked')
        observed_dirs.add(str(Path(current).relative_to(directory)))
        observed_files.update(str((Path(current) / n).relative_to(directory)) for n in names)
        if len(observed_files) + len(observed_dirs) > 8192:
            raise ValueError('Bot inventory exceeds bound')
    if observed_files != set(files) | {'fixture.json'} or observed_dirs != expected_dirs:
        raise ValueError('Bot fixture inventory drift')
    total = 0
    for name, expected in files.items():
        data = _read_file(directory / name, 32 * 1024 * 1024)
        total += len(data)
        if total > 64 * 1024 * 1024 + len(PROFILE):
            raise ValueError('Bot fixture exceeds byte bound')
        if len(data) != expected['bytes'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
            raise ValueError('Bot payload drift')
    if (directory / 'et/user/omni-bot.cfg').read_bytes() != PROFILE:
        raise ValueError('Bot profile disagrees')
    return record


def prepare(source, destination, native_sha256):
    safe_path(source)
    safe_path(destination)
    if source.resolve(strict=True) != source:
        raise ValueError('Canonical distribution required')
    if (destination.exists() or destination.is_symlink()
            or destination.parent.resolve(strict=True) != destination.parent
            or destination.is_relative_to(source) or source.is_relative_to(destination)):
        raise ValueError('NEW separate destination required')
    parent = destination.parent.stat()
    if parent.st_uid != os.getuid() or stat.S_IMODE(parent.st_mode) != 0o700:
        raise ValueError('Owned private destination parent required')
    if any((p / '.git').exists() or (p / '.git').is_symlink() for p in destination.parents):
        raise ValueError('Bot fixture must remain outside Git')
    names = list(FIXED)
    for subtree in ('global_scripts', 'et/scripts'):
        root = source / subtree
        if root.is_symlink() or not root.is_dir():
            raise ValueError('Distribution scripts missing or linked')
        for current, dirs, files in os.walk(root, followlinks=False):
            for name in dirs + files:
                if (Path(current) / name).is_symlink():
                    raise ValueError('Linked distribution member refused')
            names.extend(str((Path(current) / name).relative_to(source)) for name in files)
            if len(names) > 4096:
                raise ValueError('Distribution file count exceeds bound')
    payload, size = {}, 0
    for name in sorted(names):
        data = _read_file(source / name, 32 * 1024 * 1024)
        size += len(data)
        if size > 64 * 1024 * 1024:
            raise ValueError('Fixture exceeds total byte bound')
        payload[name] = data
    if hashlib.sha256(payload['omnibot_et.x86_64.so']).hexdigest() != native_sha256:
        raise ValueError('Approved native library hash disagrees')
    payload['et/user/omni-bot.cfg'] = PROFILE
    destination.mkdir(mode=0o700)
    for name, data in payload.items():
        parent = destination / Path(name).parent
        for directory in reversed((parent, *parent.parents)):
            if directory.is_relative_to(destination) and not directory.exists():
                directory.mkdir(mode=0o700)
        _write_new(destination / name, data)
    (destination / 'et/logs').mkdir(mode=0o700)
    record = {'status': 'copied_not_enabled', 'activation_ready': False, 'map': 'supply',
              'source': str(source), 'files': {n: {'bytes': len(d),
                  'sha256': hashlib.sha256(d).hexdigest()} for n, d in payload.items()},
              'remaining': ['fresh game workspace integration', 'effective bot config proof',
                            'native engine load and six-player activity', 'round and shutdown proof']}
    _write_new(destination / 'fixture.json', (json.dumps(record, indent=2) + '\n').encode())
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--native-sha256', required=True)
    try:
        record = prepare(**vars(parser.parse_args()))
        print(json.dumps({'status': record['status'], 'activation_ready': False,
                          'files': len(record['files']),
                          'bytes': sum(v['bytes'] for v in record['files'].values())}))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({'status': 'refused', 'error_type': type(exc).__name__,
                          'evidence_retained': True}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
