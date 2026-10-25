"""Prepare/verify a NEW local ET2.85 rehearsal layout; NEVER launch or deploy.

Read-only approved assets remain external links; only verified Lua is copied.
The writable game home is separate from the immutable source Lua bundle. This
is a pre-FIRST-launch check, not a recovery tool or a running-engine attestation.
Stable trusted ancestors and cooperative same-UID ownership remain required.
"""

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import zipfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import prepare_runtime_game_bundle as game  # noqa: E402

# Companion CLI deliberately reuses the bundle's bounded/exclusive I/O policy.
from scripts.prepare_runtime_game_bundle import (  # noqa: E402
    _read_file as read_approved_file,
)
from scripts.prepare_runtime_game_bundle import (
    _sha as require_hash,
)
from scripts.prepare_runtime_game_bundle import (
    _write_new as write_new,
)
from shared.release_manifest import MANIFEST  # noqa: E402

ASSETS = {'etmain/pak0.pk3', 'etmain/pak1.pk3', 'etmain/pak2.pk3',
          'etmain/supply_sp.pk3', 'legacy/legacy_v2.85.0.pk3'}
MARKER = 'workspace.json'
EMPTY_CONFIG = b'// Isolated rehearsal: no inherited startup commands or automatic map.\n'


def _canonical(path):
    if (not isinstance(path, Path) or re.fullmatch(r'/[A-Za-z0-9_./-]+', str(path)) is None
            or str(path).startswith('//') or path.resolve(strict=True) != path):
        raise ValueError('Explicit existing canonical ASCII path required')
    return path


def _hash(path, maximum, *, executable=False):
    _canonical(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if (not stat.S_ISREG(before.st_mode) or before.st_mode & 0o022
                or not 0 < before.st_size <= maximum
                or (executable and not os.access(path, os.X_OK))):
            raise ValueError('Approved input must be bounded regular and not group/world writable')
        digest = hashlib.sha256()
        size = 0
        while chunk := stream.read(1024 * 1024):
            size += len(chunk)
            if size > maximum:
                raise ValueError('Input grew beyond limit')
            digest.update(chunk)
        after = os.fstat(stream.fileno())
        if (size != before.st_size or (before.st_dev, before.st_ino, before.st_size,
                before.st_mtime_ns, before.st_ctime_ns) != (after.st_dev, after.st_ino,
                after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
            raise ValueError('Approved input changed during read')
    return digest.hexdigest()


def _check_archive(path, name):
    # Never extract archive contents. Reject names that could shadow the private
    # startup/module contract; this does not certify every map script as safe.
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if not 0 < len(entries) <= 10000:
            raise ValueError('Asset archive entry count outside bound')
        names = [entry.filename.replace('\\', '/').lower() for entry in entries]
        reserved = {'autoexec.cfg', 'etconfig_server.cfg', 'slomix_runtime_entry.lua'}
        reserved |= {module + '.lua' for module in game.MODULES}
        if any(n in reserved or n.startswith(('lualibs/', '/'))
               or '..' in n.split('/') or '.' in n.split('/') for n in names):
            raise ValueError('Asset archive can shadow startup or runtime modules')
        # Shipped ET2.85 has two byte-identical ui/version_generated.h entries.
        # Accept only bounded, proven-identical duplicates, never ambiguous ones.
        duplicates = {n for n, count in Counter(names).items() if count > 1}
        selected = [(n, entry) for n, entry in zip(names, entries) if n in duplicates]
        if sum(entry.file_size for _, entry in selected) > 8 * 1024 * 1024:
            raise ValueError('Duplicate archive evidence exceeds bound')
        observed = {}
        for n, entry in selected:
            if entry.file_size > 1024 * 1024:
                raise ValueError('Duplicate archive member exceeds bound')
            with archive.open(entry) as stream:
                raw = stream.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise ValueError('Duplicate archive member exceeds bound')
            digest = hashlib.sha256(raw).digest()
            if n in observed and observed[n] != digest:
                raise ValueError('Ambiguous duplicate archive member')
            observed[n] = digest
        if name == 'etmain/supply_sp.pk3' and 'maps/supply.bsp' not in names:
            raise ValueError('Approved rehearsal map is missing')


def _contract(bundle, executable, executable_sha256, assets, destination):
    bundle, executable = _canonical(bundle), _canonical(executable)
    source = game.verify(bundle)
    contract = json.loads(read_approved_file(bundle / game.CONTRACT, 4096))
    socket_path = destination / 'control/m.sock'
    if contract['socket_path'] != str(socket_path):
        raise ValueError('Lua bundle socket must target this NEW workspace control/m.sock')
    require_hash(executable_sha256, 64)
    if _hash(executable, 64 * 1024 * 1024, executable=True) != executable_sha256:
        raise ValueError('Dedicated executable differs from approved hash')
    if type(assets) is not dict or set(assets) != ASSETS:
        raise ValueError('Explicit five-asset rehearsal inventory required')
    for name, value in assets.items():
        if type(value) is not dict or set(value) != {'path', 'sha256'} or not isinstance(value['path'], str):
            raise ValueError('Invalid approved asset record')
        path = Path(value['path'])
        require_hash(value['sha256'], 64)
        if _hash(path, 512 * 1024 * 1024) != value['sha256']:
            raise ValueError('Asset differs from approved hash')
        _check_archive(path, name)
    return {'version': 1, 'status': 'prepared_not_started', 'activation_ready': False,
            'directory': str(destination), 'uid': os.getuid(), 'bundle': str(bundle),
            'bundle_manifest_sha256': _hash(bundle / MANIFEST, 4 * 1024 * 1024),
            'source_commit': source['source_commit'], 'executable': str(executable),
            'executable_sha256': executable_sha256, 'assets': assets,
            'engine_library': contract['engine_library'], 'socket_path': str(socket_path),
            'source_id': contract['source_id'], 'fs_game': 'legacy', 'map_name': 'supply',
            'roots': {'authority': str(destination / 'authority'),
                      'host_authority': str(destination / 'host-authority'),
                      'producer_spool': str(destination / 'home/legacy/gamestats/runtime-snapshots'),
                      'capture_root': str(destination / 'capture')},
            'fs_basepath': str(destination / 'base'), 'fs_homepath': str(destination / 'home')}


def _layout(record):
    bundle = Path(record['bundle'])
    # Preserve licenses and carrier source alongside every copied Lua/native file.
    files = {'base/' + name: read_approved_file(bundle / name, 4 * 1024 * 1024)
             for name in game.FILES}
    files.update({'home/legacy/autoexec.cfg': EMPTY_CONFIG,
                  'home/legacy/etconfig_server.cfg': EMPTY_CONFIG})
    # Keep the engine's actual inode/path: copying qagame would load a second
    # embedded Lua alongside the carrier's explicit external dependency.
    links = {'base/' + name: value['path'] for name, value in record['assets'].items()}
    links['base/legacy/qagame.mp.x86_64.so'] = record['engine_library']
    directories = {Path('.'), Path('control'), Path('authority'), Path('host-authority'),
                   Path('capture'), Path('home/legacy/gamestats/runtime-snapshots')}
    for name in (*files, *links):
        directories.update(Path(name).parents)
    for path in tuple(directories):
        directories.update(path.parents)
    return files, links, directories


def _private(path, directory=False):
    info = path.lstat()
    if (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != (0o700 if directory else 0o600)
            or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))):
        raise ValueError('Workspace must remain owned and private before first launch')


def verify(directory):
    _canonical(directory)
    _private(directory, True)
    _private(directory / MARKER)
    raw = read_approved_file(directory / MARKER, 65536)
    record = json.loads(raw)
    if type(record) is not dict:
        raise ValueError('Invalid workspace contract')
    expected = _contract(Path(record['bundle']), Path(record['executable']),
                         record['executable_sha256'], record['assets'], directory)
    if record != expected or raw != _json(expected):
        raise ValueError('Workspace contract drifted')
    files, links, directories = _layout(record)
    files[MARKER] = raw
    # Check only the fixed shallow tree, without following external asset links.
    for relative in sorted(directories):
        path = directory / relative
        _private(path, True)
        children = {Path(n).name for n in (*files, *links, *directories)
                    if Path(n) != relative and Path(n).parent == relative}
        seen = set()
        for entry in path.iterdir():
            if entry.name not in children:
                raise ValueError('Unexpected workspace entry; not a fresh prelaunch layout')
            seen.add(entry.name)
            name = entry.relative_to(directory).as_posix()
            if name in files:
                _private(entry)
                if read_approved_file(entry, 4 * 1024 * 1024) != files[name]:
                    raise ValueError('Staged workspace bytes differ from approved bundle/config')
            elif name in links:
                if (not entry.is_symlink() or entry.lstat().st_uid != os.getuid()
                        or os.readlink(entry) != links[name]):
                    raise ValueError('Approved external asset/engine link drifted')
        if seen != children:
            raise ValueError('Workspace entry missing')
    return record


def _json(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode('ascii')


def prepare(*, destination, bundle, executable, executable_sha256, assets):
    _canonical(destination.parent)
    if (not destination.is_absolute() or destination.exists() or destination.is_symlink()
            or re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', destination.name) is None
            or destination.parent.stat().st_uid != os.getuid()
            or any((p / '.git').exists() or (p / '.git').is_symlink() for p in destination.parents)
            or destination.is_relative_to(bundle)):
        raise ValueError('NEW owned outside-Git destination separate from Lua bundle required')
    record = _contract(bundle, executable, executable_sha256, assets, destination)
    files, links, directories = _layout(record)
    for relative in sorted(directories, key=lambda p: (len(p.parts), str(p))):
        (destination / relative).mkdir(mode=0o700)
    for name, data in files.items():
        write_new(destination / name, data)
    for name, target in links.items():
        (destination / name).symlink_to(target)
    write_new(destination / MARKER, _json(record))
    for relative in sorted(directories, key=lambda p: len(p.parts), reverse=True):
        fd = os.open(destination / relative, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    return verify(destination)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('prepare')
    for name in ('destination', 'bundle', 'executable', 'assets'):
        build.add_argument('--' + name, type=Path, required=True)
    build.add_argument('--executable-sha256', required=True)
    check = commands.add_parser('verify')
    check.add_argument('--directory', type=Path, required=True)
    args = vars(parser.parse_args(argv))
    command = args.pop('command')
    try:
        if command == 'prepare':
            args['assets'] = json.loads(read_approved_file(args['assets'], 65536))
        result = prepare(**args) if command == 'prepare' else verify(**args)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        print(json.dumps({'status': 'refused', 'error_type': type(exc).__name__,
                          'activation_ready': False, 'partial_output_retained': True}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
