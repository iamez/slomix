"""Prepare/verify a NEW offline ET2.85 Lua5.4 bundle, never install or launch it.

Only the explicit committed revision is copied, never dirty worktree files.
Approved native inputs are read/linked but NOT executed. This Lua-only bundle
is not a complete game installation: engine/assets/config, real ABI/load order,
same-UID output mapping and listener-before-InitGame still need separate proof.
No dotenv, downloads, package installation, service control or automatic cleanup.
"""

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.release_manifest import MANIFEST, payload_files, verify_release  # noqa: E402
from shared.runtime_socket_path import validate_socket_path  # noqa: E402

MODULES = (
    'c0rnp0rn8', 'runtime_c0rn_host', 'runtime_c0rn_entrypoint',
    'runtime_host_hooks', 'runtime_host_bootstrap', 'runtime_host_channel',
    'runtime_host_completion', 'runtime_init_lease', 'runtime_completed_stats',
    'runtime_stats_delivery', 'runtime_round_identity',
)
ENTRY = 'legacy/slomix_runtime_entry.lua'
NATIVE = 'legacy/lualibs/socket/unix.so'
UNIX = 'legacy/lualibs/socket/liblua5.4-socket-unix.so.2'
LINK_SOURCE = 'native-link.c'
LINK_CODE = b'/* Dependency scope only; no game callbacks or Lua API. */\nint slomix_runtime_link_anchor(void) { return 0; }\n'
CONTRACT = 'game-contract.json'
FILES = {f'legacy/{name}.lua' for name in MODULES} | {
    ENTRY, NATIVE, UNIX, LINK_SOURCE, CONTRACT, 'LICENSE', 'LuaSocket-COPYRIGHT',
}
TOOL_ENV = {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'}


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _sha(value, length):
    if not isinstance(value, str) or re.fullmatch(f'[0-9a-f]{{{length}}}', value) is None:
        raise ValueError('Explicit lowercase full commit/hash required')
    return value


def _contract(source_id, socket_path, bootstrap_ms, completion_ms, unix_sha256,
              engine_library, engine_sha256):
    if not isinstance(source_id, str) or re.fullmatch(r'[a-z0-9][a-z0-9_.-]{0,63}', source_id) is None:
        raise ValueError('Invalid explicit game source ID')
    validate_socket_path(socket_path)
    if any(type(value) is not int or not 1 <= value <= 10000 for value in (bootstrap_ms, completion_ms)):
        raise ValueError('Game exchange deadlines must be integer milliseconds in 1..10000')
    if (not isinstance(engine_library, str)
            or re.fullmatch(r'/[A-Za-z0-9_./-]+', engine_library) is None
            or '..' in PurePosixPath(engine_library).parts
            or PurePosixPath(engine_library).as_posix() != engine_library
            or len(engine_library) > 1024):
        raise ValueError('Explicit canonical ASCII engine library path required')
    return {'version': 1, 'kind': 'et285-runtime-lua', 'lua_version': 'Lua 5.4',
            'source_id': source_id, 'socket_path': socket_path,
            'bootstrap_timeout_ms': bootstrap_ms, 'completion_timeout_ms': completion_ms,
            'socket_unix_sha256': _sha(unix_sha256, 64), 'entrypoint': ENTRY,
            'engine_library': engine_library, 'engine_sha256': _sha(engine_sha256, 64),
            'native_link_scope': 'local-explicit-engine-dependency',
            'activation_ready': False}


def wrapper(contract):
    # Contract restricts strings to plain ASCII without quoting/escape syntax.
    return ('-- Generated offline: REPLACE c0rnp0rn8 in lua_modules, NEVER add a second writer.\n'
            '-- Trusted search paths and separately verified engine ABI are required.\n'
            'assert(_VERSION == "Lua 5.4", "Runtime bundle requires Lua 5.4")\n'
            'return require("runtime_c0rn_host").configure({\n'
            f'    source_id="{contract["source_id"]}",\n'
            f'    socket_path="{contract["socket_path"]}",\n'
            f'    bootstrap_timeout_ms={contract["bootstrap_timeout_ms"]},\n'
            f'    completion_timeout_ms={contract["completion_timeout_ms"]},\n'
            '})\n').encode('ascii')


def _read_file(path, limit):
    if not isinstance(path, Path) or not path.is_absolute() or path.resolve(strict=True) != path:
        raise ValueError('Explicit canonical dependency path required; resolve symlinks first')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if (not stat.S_ISREG(before.st_mode) or before.st_mode & 0o022
                or not 0 < before.st_size <= limit):
            raise ValueError('Dependency must be bounded regular and not group/world writable')
        data = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
        if (before.st_size != len(data) or (before.st_mtime_ns, before.st_ctime_ns, before.st_size)
                != (after.st_mtime_ns, after.st_ctime_ns, after.st_size)):
            raise ValueError('Dependency changed during read')
    return data


def _git(source, *args):
    return subprocess.run(['git', '-C', str(source), *args], check=True, capture_output=True,
                          env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'}, timeout=15).stdout


def _dynamic(path):
    """Inspect ELF metadata without dlopen/ldd or running the approved binary."""
    result = subprocess.run(['/usr/bin/readelf', '-d', '--', str(path)], check=True,
                            capture_output=True, text=True, env=TOOL_ENV, timeout=10)
    return {tag: re.findall(r'\(' + tag + r'\).*?\[([^\]]*)\]', result.stdout)
            for tag in ('NEEDED', 'SONAME', 'RPATH', 'RUNPATH')}


def _engine(path, approved_hash):
    if _digest(_read_file(path, 64 * 1024 * 1024)) != approved_hash:
        raise ValueError('Engine library differs from independently approved hash')
    if _dynamic(path)['SONAME']:
        raise ValueError('Engine SONAME would replace the required absolute dependency')


def _unix_metadata(path):
    metadata = _dynamic(path)
    if (metadata['SONAME'] != [Path(UNIX).name] or metadata['NEEDED'] != ['libc.so.6']
            or metadata['RPATH'] or metadata['RUNPATH']):
        raise ValueError('Unsupported LuaSocket dependency closure')


def _link_metadata(path, engine):
    if _dynamic(path) != {'NEEDED': [engine, Path(UNIX).name], 'SONAME': [],
                          'RPATH': [], 'RUNPATH': ['$ORIGIN']}:
        raise ValueError('Native carrier differs from fixed local dependency contract')


def _write_new(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        if stream.write(data) != len(data):
            raise OSError('Incomplete bundle output')
        stream.flush()
        os.fsync(stream.fileno())


def _blob(source, revision, name):
    entry = _git(source, 'ls-tree', '-z', revision, '--', name).split(b'\0')
    if (len(entry) != 2 or entry[-1] != b'' or not entry[0].startswith(b'100644 blob ')
            or entry[0].split(b'\t', 1)[-1] != name.encode('ascii')):
        raise ValueError('Required committed regular game input missing')
    oid = entry[0].split()[2].decode('ascii')
    size = int(_git(source, 'cat-file', '-s', oid))
    if not 0 < size <= 2 * 1024 * 1024:
        raise ValueError('Committed game input size outside bound')
    data = _git(source, 'cat-file', 'blob', oid)
    if len(data) != size:
        raise ValueError('Committed game input changed')
    data.decode('utf-8')
    return data


def _private_inventory(directory):
    """Game-only placement gate, including directories and the manifest.

    Check a fixed shallow tree before the generic byte verifier traverses it.
    Builder-owned directories must be0700; files may be0600 or read-only0400.
    This is point-in-time evidence, not protection against hostile same-UID
    changes. Stable trusted ancestors remain an operator precondition.
    """
    files = {Path(name) for name in FILES | {MANIFEST}}
    directories = {parent for name in files for parent in name.parents}
    for relative in sorted(directories):
        path = directory / relative
        info = path.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o700):
            raise ValueError('Game bundle directories must be owned and private0700')
        expected = {name.name for name in files | directories
                    if name != relative and name.parent == relative}
        seen = set()
        for entry in path.iterdir():
            if entry.name not in expected:
                raise ValueError('Game bundle directory inventory differs from required closed set')
            seen.add(entry.name)
            if entry.relative_to(directory) in files:
                info = entry.lstat()
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                        or stat.S_IMODE(info.st_mode) not in (0o400, 0o600)):
                    raise ValueError('Game bundle files must be owned and private0400/0600')
        if seen != expected:
            raise ValueError('Game bundle directory inventory differs from required closed set')


def verify(directory):
    """Point-in-time byte/contract check, NOT provenance signature or ABI proof."""
    if not directory.is_absolute() or directory.resolve(strict=True) != directory:
        raise ValueError('Explicit canonical game bundle directory required')
    _private_inventory(directory)
    files = payload_files(directory)
    if set(files) != FILES:
        raise ValueError('Game bundle inventory differs from required closed set')
    for name, path in files.items():
        limit = 4 * 1024 * 1024 if name in (NATIVE, UNIX) else 2 * 1024 * 1024
        info = path.stat()
        if not 0 < info.st_size <= limit or info.st_mode & 0o022:
            raise ValueError('Game bundle payload is oversized or writable by another user')
    record = verify_release(directory)
    if (set(record) != {'version', 'source_commit', 'files'} or type(record['version']) is not int
            or set(record['files']) != FILES):
        raise ValueError('Game bundle inventory differs from required closed set')
    raw = _read_file(directory / CONTRACT, 4096)
    value = json.loads(raw)
    expected = _contract(value['source_id'], value['socket_path'], value['bootstrap_timeout_ms'],
                         value['completion_timeout_ms'], value['socket_unix_sha256'],
                         value['engine_library'], value['engine_sha256'])
    if (raw != (json.dumps(expected, sort_keys=True, indent=2) + '\n').encode('ascii')
            or (directory / ENTRY).read_bytes() != wrapper(expected)):
        raise ValueError('Game wrapper disagrees with fixed contract')
    if record['files'][UNIX] != expected['socket_unix_sha256']:
        raise ValueError('Game native dependency differs from approved hash')
    if (directory / LINK_SOURCE).read_bytes() != LINK_CODE:
        raise ValueError('Native carrier source differs from fixed contract')
    _engine(Path(expected['engine_library']), expected['engine_sha256'])
    _unix_metadata(directory / UNIX)
    _link_metadata(directory / NATIVE, expected['engine_library'])
    return {'status': 'game_lua_bundle_verified_not_activated', 'source_commit': record['source_commit'],
            'files': len(record['files']), 'directory': str(directory), 'activation_ready': False,
            'not_checked': ['real_engine_lua_abi', 'actual_module_resolution_and_load_order',
                            'game_assets_and_configuration', 'same_uid_output_mapping',
                            'clean_dynamic_loader_environment', 'listener_before_init',
                            'actual_engine_capture_and_import']}


def prepare(*, source, revision, destination, unix_library, unix_sha256, unix_license,
            engine_library, engine_sha256, source_id, socket_path,
            bootstrap_ms=5000, completion_ms=1000):
    """Copy only approved inputs into a fresh private outside-Git directory.

    Stable trusted ancestors/owner are required, as for other runtime bundles.
    Preserve partial output on every failure; never merge, overwrite or remove.
    Does not change ownership or make an assertion about the future game UID.
    """
    _sha(revision, 40)
    contract = _contract(source_id, socket_path, bootstrap_ms, completion_ms, unix_sha256,
                         str(engine_library), engine_sha256)
    source = source.resolve(strict=True)
    if _git(source, 'rev-parse', '--verify', revision + '^{commit}').decode().strip() != revision:
        raise ValueError('Expected exact committed source revision')
    if (not destination.is_absolute() or destination.parent.resolve(strict=True) != destination.parent
            or destination.exists() or destination.is_symlink()):
        raise ValueError('Game bundle destination must be NEW under a canonical parent')
    if any((parent / '.git').exists() or (parent / '.git').is_symlink()
           for parent in destination.parents):
        raise ValueError('Game bundle destination must be outside Git checkouts')
    if destination.parent.stat().st_uid != os.getuid():
        raise ValueError('Game bundle parent must belong to this user')
    native = _read_file(unix_library, 4 * 1024 * 1024)
    if _digest(native) != unix_sha256:
        raise ValueError('Native dependency differs from independently approved hash')
    # This is only a coarse ELF64 little-endian x86_64 shared-object gate.
    # A matching header/hash is NOT Lua ABI or real-engine module-load proof.
    if len(native) < 64 or native[:7] != b'\x7fELF\x02\x01\x01' or native[16:20] != b'\x03\x00\x3e\x00':
        raise ValueError('Expected Linux x86_64 ELF shared native dependency')
    _unix_metadata(unix_library)
    _engine(engine_library, engine_sha256)
    payload = {f'legacy/{name}.lua': _blob(source, revision, f'vps_scripts/{name}.lua') for name in MODULES}
    payload.update({ENTRY: wrapper(contract), UNIX: native, LINK_SOURCE: LINK_CODE,
                    'LICENSE': _blob(source, revision, 'LICENSE'),
                    'LuaSocket-COPYRIGHT': _read_file(unix_license, 256 * 1024),
                    CONTRACT: (json.dumps(contract, sort_keys=True, indent=2) + '\n').encode('ascii')})
    destination.mkdir(mode=0o700)
    directories = [destination, *(destination / name for name in ('legacy', 'legacy/lualibs', 'legacy/lualibs/socket'))]
    for directory in directories[1:]:
        directory.mkdir(mode=0o700)
    for name, data in payload.items():
        _write_new(destination / name, data)
    # ET dlopens qagame RTLD_LOCAL. A plain distro module cannot resolve its
    # embedded Lua symbols. Keep them local using an explicit dependency group;
    # never promote qagame RTLD_GLOBAL, patch it, or link a second liblua.
    subprocess.run(['/usr/bin/cc', '-shared', '-fPIC', '-nostdlib',
                    str(destination / LINK_SOURCE), '-Wl,--no-as-needed',
                    str(engine_library), str(destination / UNIX), '-Wl,-rpath,$ORIGIN',
                    '-o', str(destination / NATIVE)], check=True, capture_output=True,
                   env=TOOL_ENV, timeout=30, umask=0o077)
    (destination / NATIVE).chmod(0o600)
    _link_metadata(destination / NATIVE, str(engine_library))
    payload[NATIVE] = _read_file(destination / NATIVE, 4 * 1024 * 1024)
    with (destination / NATIVE).open('rb') as stream:
        os.fsync(stream.fileno())
    # The external engine path is a dependency, not copied into this Lua bundle.
    # Recheck after linking; activation must independently pin it again.
    _engine(engine_library, engine_sha256)
    record = {'version': 1, 'source_commit': revision, 'files': {name: _digest(data) for name, data in payload.items()}}
    _write_new(destination / MANIFEST, (json.dumps(record, sort_keys=True, indent=2) + '\n').encode('ascii'))
    for directory in reversed(directories):
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    return verify(destination)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('prepare', help='Create a NEW offline Lua bundle only')
    for name in ('source', 'destination', 'unix-library', 'unix-license', 'engine-library'):
        build.add_argument('--' + name, type=Path, required=True)
    for name in ('revision', 'unix-sha256', 'engine-sha256', 'source-id', 'socket-path'):
        build.add_argument('--' + name, required=True)
    build.add_argument('--bootstrap-ms', type=int, default=5000)
    build.add_argument('--completion-ms', type=int, default=1000)
    check = commands.add_parser('verify', help='Read-only inventory/hash/contract check')
    check.add_argument('--directory', type=Path, required=True)
    args = vars(parser.parse_args(argv))
    command = args.pop('command')
    try:
        result = prepare(**args) if command == 'prepare' else verify(**args)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(json.dumps({'status': 'refused', 'activation_ready': False, 'error_type': type(exc).__name__,
                          'partial_output_retained': True}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
