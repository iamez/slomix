"""Copy-only initial data seed, NEVER a quiesced snapshot or activation approval.

Plan first, seed only into a NEW shared directory. Refuse source drift, links,
special files and SQLite databases. Preserve originals AND any partial output.
Do not select historical log/archive, credential or DB-backup roots. This is
not a generic secret scanner: review the selected data manifest before seeding.
Reports stay outside runtime state and Git; no services or databases contacted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.dev_runtime_contract import state_paths  # noqa: E402

NAMES = frozenset({'stats', 'gametimes', 'proximity', 'processed', 'greatshot', 'uploads', 'retro-viz'})


def canonical(path: Path) -> Path:
    path = Path(path)
    if not path.is_absolute() or path.resolve(strict=True) != path or not path.is_dir():
        raise ValueError('Expected existing canonical directory')
    return path


def new_outside_git(path: Path):
    parent = canonical(path.parent)
    if (path.exists() or path.is_symlink() or path.name in {'.', '..'}
            or any((ancestor / marker).exists() or (ancestor / marker).is_symlink()
                   for ancestor in (parent, *parent.parents)
                   for marker in ('.git', '.slomix-release.json'))):
        raise ValueError('Destination must be new and outside Git or immutable releases')


def fingerprint(path: Path) -> dict:
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError('Only regular files may be seeded')
        if stream.read(16) == b'SQLite format 3\x00':
            raise ValueError('SQLite needs a separate consistent backup, not file copy')
        stream.seek(0)
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        after = os.fstat(stream.fileno())
    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError('File changed during measurement')
    return {'size': after.st_size, 'mtime_ns': after.st_mtime_ns, 'sha256': digest}


def inventory(root: Path | None) -> dict:
    if root is None:
        return {'directories': [], 'files': {}}
    canonical(root)
    directories, files = [], {}
    def fail(error):
        raise error
    for parent, dirs, names in os.walk(root, followlinks=False, onerror=fail):
        for name in sorted([*dirs, *names]):
            path = Path(parent) / name
            relative = path.relative_to(root).as_posix()
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                raise ValueError('Nested symlinks require explicit review before seeding')
            if stat.S_ISDIR(info.st_mode):
                directories.append(relative)
            elif stat.S_ISREG(info.st_mode):
                if (name.startswith('.env') or name.lower().endswith(('.db', '.sqlite', '.sqlite3', '-wal', '-shm', '-journal'))
                        or '.git' in path.relative_to(root).parts):
                    raise ValueError('Configuration, Git or database file found in data source')
                files[relative] = fingerprint(path)
            else:
                raise ValueError('Special files require explicit review before seeding')
    return {'directories': sorted(directories), 'files': dict(sorted(files.items()))}


def plan(sources: dict, state: Path) -> dict:
    if set(sources) != NAMES or state.name != 'shared':
        raise ValueError('Expected all seven data sources and a new shared destination')
    new_outside_git(state)
    resolved = {}
    for name, value in sources.items():
        if value is None and name not in {'processed', 'retro-viz'}:
            raise ValueError('Only explicitly absent optional sources may be empty')
        root = canonical(Path(value)) if value is not None else None
        if root is not None and (state.is_relative_to(root) or root.is_relative_to(state)):
            raise ValueError('Source and destination must not overlap')
        resolved[name] = root
    roots = [root for root in resolved.values() if root is not None]
    if any(left.is_relative_to(right) for i, left in enumerate(roots) for j, right in enumerate(roots) if i != j):
        raise ValueError('Data source scopes must not overlap')
    return {'version': 1, 'status': 'dry_run_not_copied', 'ready_for_activation': False,
            'state': str(state), 'sources': {name: str(root) if root else None for name, root in resolved.items()},
            'inventory': {name: inventory(root) for name, root in resolved.items()}}


def seed(record: dict) -> dict:
    # Reconstruct the plan rather than trusting user-supplied relative filenames.
    state = Path(record['state'])
    fresh = plan(record['sources'], state)
    if record != fresh:
        raise ValueError('Source or dry-run plan changed; no copy admitted')
    needed = sum(item['size'] for group in fresh['inventory'].values() for item in group['files'].values())
    if shutil.disk_usage(state.parent).free < needed + 64 * 1024 * 1024:
        raise ValueError('Insufficient free space for seed plus safety margin')
    state.mkdir(mode=0o700)
    for name in NAMES:
        root = state / 'data' / name
        root.mkdir(parents=True, mode=0o700)
        group = fresh['inventory'][name]
        for relative in group['directories']:
            (root / relative).mkdir(parents=True, exist_ok=True, mode=0o700)
        for relative, expected in group['files'].items():
            origin = Path(fresh['sources'][name]) / relative
            target = root / relative
            with os.fdopen(os.open(origin, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as source:
                if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                    raise ValueError('Source is no longer a regular file')
                with target.open('xb') as output:
                    target.chmod(0o600)
                    remaining = expected['size']
                    while remaining:
                        chunk = source.read(min(remaining, 1024 * 1024))
                        if not chunk:
                            raise ValueError('Source shortened during copy; partial seed retained')
                        output.write(chunk)
                        remaining -= len(chunk)
                    if source.read(1):
                        raise ValueError('Source grew during copy; partial seed retained')
                    output.flush()
                    os.fsync(output.fileno())
            os.utime(target, ns=(expected['mtime_ns'], expected['mtime_ns']))
        if inventory(root) != group:
            raise ValueError('Copied data differs from dry-run; partial seed retained')
    # Never copy historical rotating logs or live auxiliary SQLite files.
    (state / 'config').mkdir(mode=0o700)
    for role in ('bot', 'web'):
        for key, path in state_paths(state, role).items():
            (path.parent if key == 'METRICS_DB_PATH' else path).mkdir(parents=True, exist_ok=True, mode=0o700)
    if any(inventory(Path(value) if value is not None else None) != fresh['inventory'][name]
           for name, value in fresh['sources'].items()):
        raise ValueError('Source changed during copy; initial seed retained but not certified')
    return {**fresh, 'status': 'seed_only_requires_quiesced_reconciliation',
            'files': sum(len(group['files']) for group in fresh['inventory'].values()), 'bytes': needed}


def write_report(path: Path, record: dict):
    new_outside_git(path)
    protected = [Path(record['state']), *(Path(value) for value in record['sources'].values() if value is not None)]
    if any(path.is_relative_to(root) for root in protected):
        raise ValueError('Evidence must stay outside source and destination data trees')
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write('\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['plan', 'seed'])
    parser.add_argument('--input', required=True, type=Path, help='Source map for plan; saved plan for seed')
    parser.add_argument('--state', type=Path, help='New external shared directory (plan only)')
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == 'plan' and args.state is None:
        parser.error('plan requires --state')
    if args.command == 'seed' and args.state is not None:
        parser.error('seed uses only the destination pinned in the saved plan')
    try:
        new_outside_git(args.report)
        record = json.loads(args.input.read_text())
        # Validate evidence placement before copying any data.
        target = args.state if args.command == 'plan' else Path(record['state'])
        sources = record if args.command == 'plan' else record['sources']
        if any(args.report.is_relative_to(Path(root)) for root in [str(target), *sources.values()] if root is not None):
            raise ValueError('Report overlaps data')
        result = plan(record, args.state) if args.command == 'plan' else seed(record)
        write_report(args.report, result)
        print(json.dumps({'status': result['status'], 'ready_for_activation': False,
                          'report': str(args.report)}, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({'status': 'refused', 'ready_for_activation': False,
                          'error': 'Invalid or changing inputs; originals and partial output retained'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
