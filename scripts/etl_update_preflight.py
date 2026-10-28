"""Read-only archive and Lua-load checks for the owner-run ET updater."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import stat
import struct
import tarfile
from pathlib import Path, PurePosixPath

EXPECTED_LUA = frozenset({
    'luascripts/team-lock.lua', 'c0rnp0rn8.lua', 'endstats.lua',
    'luascripts/proximity_tracker.lua', 'luascripts/stats_discord_webhook.lua',
    'luascripts/live_events.lua',
})


def inspect_archive(path: Path, expected_hash: str) -> dict:
    if not re.fullmatch(r'[0-9a-f]{64}', expected_hash):
        raise ValueError('An explicit lowercase SHA256 is required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > 128 * 1024 * 1024:
            raise ValueError('Expected a bounded regular archive')
        digest = hashlib.sha256()
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
        if digest.hexdigest() != expected_hash:
            raise ValueError('Archive SHA256 mismatch')
        source.seek(0)
        with tarfile.open(fileobj=source, mode='r:gz') as archive:
            members = []
            total = 0
            names = set()
            roots = set()
            for item in archive:
                relative = PurePosixPath(item.name)
                if (relative.is_absolute() or '..' in relative.parts
                        or '\\' in item.name or not relative.parts
                        or not (item.isfile() or item.isdir())
                        or item.mode & 0o7000 or str(relative) in names
                        or item.name.rstrip('/') != str(relative)):
                    raise ValueError('Unsafe or duplicate archive member')
                roots.add(relative.parts[0])
                names.add(str(relative))
                members.append(item)
                total += item.size
                if len(members) > 20000 or total > 512 * 1024 * 1024:
                    raise ValueError('Archive expansion limit exceeded')
            if len(roots) != 1:
                raise ValueError('Expected one release root')
            root = next(iter(roots))
            if not re.fullmatch(r'etlegacy-v\d+\.\d+\.\d+(?:-\d+-g[0-9a-f]{7,40})?-x86_64', root):
                raise ValueError('Expected an explicit x86_64 release root')
            files = {m.name: m for m in members if m.isfile()}
            native = {}
            for relative, allowed_type in [('etlded.x86_64', {2, 3}),
                                            ('legacy/qagame.mp.x86_64.so', {3})]:
                member = files.get(root + '/' + relative)
                if member is None or member.size < 64:
                    raise ValueError('Missing engine or server module')
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError('Native member is not readable')
                with stream:
                    header = stream.read(64)
                if (header[:7] != b'\x7fELF\x02\x01\x01'
                        or struct.unpack_from('<H', header, 18)[0] != 62
                        or struct.unpack_from('<H', header, 16)[0] not in allowed_type):
                    raise ValueError('Expected Linux x86_64 ELF engine/module')
                native[relative] = member.size
            packages = [name for name in files
                        if name.startswith(root + '/legacy/legacy_v') and name.endswith('.pk3')]
            if packages != [root + '/legacy/legacy_' + root.removeprefix('etlegacy-').removesuffix('-x86_64') + '.pk3']:
                raise ValueError('Expected exactly one matching mod package')
        after = os.fstat(source.fileno())
        def identity(s):
            return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns
        if identity(before) != identity(after):
            raise ValueError('Archive changed during inspection')
    return {'status': 'archive_verified_not_activated', 'root': root,
            'sha256': expected_hash, 'members': len(members),
            'uncompressed_bytes': total, 'native': native, 'pk3': packages[0]}


def verify_lua_log(path: Path) -> dict:
    text = path.read_text(errors='replace')
    loaded = set(re.findall(r"file '([^']+)' loaded into Lua VM", text))
    if loaded != EXPECTED_LUA:
        raise ValueError('Lua module set differs from the six approved Puran modules')
    if re.search(r'nil value|stack traceback|attempt to |outputData ERROR|Lua.*syntax error', text, re.I):
        raise ValueError('Lua failure in startup log')
    return {'status': 'lua_load_set_verified', 'modules': sorted(loaded)}


def require_empty_server() -> dict:
    """Query all connected slots, including spectators, without authentication."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
        client.settimeout(2)
        client.sendto(b'\xff\xff\xff\xffgetstatus\n', ('127.0.0.1', 27960))
        payload, origin = client.recvfrom(32768)
    if origin != ('127.0.0.1', 27960) or not payload.startswith(b'\xff\xff\xff\xffstatusResponse\n'):
        raise ValueError('Game status unavailable or malformed')
    lines = payload.split(b'\n')
    if len(lines) < 2 or not lines[1].startswith(b'\\'):
        raise ValueError('Game status information missing')
    players = [line for line in lines[2:] if line.strip()]
    if any(not re.fullmatch(rb'\s*-?\d+\s+-?\d+\s+".*"\s*', line) for line in players):
        raise ValueError('Game status slot list malformed')
    if players:
        raise ValueError('Connected clients present; owner must wait for an empty server')
    return {'status': 'empty_server_verified', 'connected_slots': 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--archive', type=Path)
    group.add_argument('--lua-log', type=Path)
    group.add_argument('--require-empty', action='store_true')
    parser.add_argument('--sha256', default='')
    args = parser.parse_args()
    try:
        result = (inspect_archive(args.archive, args.sha256) if args.archive
                  else verify_lua_log(args.lua_log) if args.lua_log else require_empty_server())
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, tarfile.TarError) as error:
        print(json.dumps({'status': 'refused', 'error': str(error)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
