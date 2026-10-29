"""Prepare a NEW Git-free release; never deploy, start services or copy state.

Source must be committed/clean with exact-source verified SPA and modern route-host outputs.
Build both using npm run build:app and npm run build before preparation. Failure
retains its incomplete destination for inspection; never overwrite or delete.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))

from scripts.spa_artifact import MANIFEST as SPA_MANIFEST  # noqa: E402
from scripts.spa_artifact import TARGETS, git, reject_symlink_path, validate  # noqa: E402
from shared.release_manifest import MANIFEST, file_hash, payload_files, verify_release  # noqa: E402

EXPLICIT = {
    'LICENSE', 'requirements.txt', 'website/requirements.txt',
    'postgresql_database_manager.py', 'website/index.html',
    'bot/services/data/supastats_glyphs.json', 'proximity/objective_coords_template.json',
    'greatshot/contracts/schema/analysis.schema.json', 'greatshot/scanner/etl_demo_scan',
    'scripts/apply_migrations.py', 'scripts/dev_schema_preflight.py',
    'scripts/dev_verify_health.py', 'scripts/data_plausibility_audit.py',
    'scripts/dev_runtime_contract.py', 'scripts/runtime_app_bootstrap.py',
}
PYTHON_ROOTS = ('bot/', 'shared/', 'greatshot/', 'proximity/parser/', 'website/backend/')
ASSET_ROOTS = ('website/js/', 'website/css/', 'website/assets/')


def included(name: str) -> bool:
    parts = Path(name).parts
    if any(part in {'tests', '__pycache__', 'node_modules'} for part in parts):
        return False
    return (name in EXPLICIT or name == 'proximity/__init__.py'
            or (name.startswith(PYTHON_ROOTS) and name.endswith('.py'))
            or name.startswith(ASSET_ROOTS)
            or (name.startswith('migrations/') and len(parts) == 2 and name.endswith('.sql')))


def verify_source_state(source: Path, target: str) -> None:
    """A manifest SHA cannot label tracked bytes from a different tree/index."""
    if (git(source, 'rev-parse', 'HEAD').decode().strip() != target
            or git(source, 'diff', '--name-only', '-z', 'HEAD', '--')):
        raise ValueError('Release source must remain at its clean committed revision')
    entries = git(source, 'ls-files', '-v', '-z').split(b'\0')
    if any(entry[:1].islower() or entry.startswith(b'S ') for entry in entries if entry):
        raise ValueError('Source has hidden index flags')



def payload_parent(destination: Path, relative: Path) -> None:
    """Create every component safely even when the caller uses umask 000."""
    current = destination
    for part in relative.parts:
        current = current / part
        current.mkdir(mode=0o755, exist_ok=True)
        if current.is_symlink() or not current.is_dir():
            raise ValueError('Payload parent must be a regular directory')
        current.chmod(0o755)


def copy_payload(origin: Path, output: Path, mode: int) -> None:
    """Reserve owner-only bytes before copyfile opens its existing destination."""
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    os.close(descriptor)
    shutil.copyfile(origin, output)
    output.chmod(mode)


def prepare(source: Path, destination: Path) -> dict:
    source = source.resolve(strict=True)
    destination = destination.absolute()
    parent = destination.parent.resolve(strict=True)
    if parent != destination.parent or destination.exists() or destination.is_symlink():
        raise ValueError('Destination must be NEW under a canonical existing parent')
    if any((ancestor / '.git').exists() for ancestor in (parent, *parent.parents)):
        raise ValueError('Release destination must be outside every Git checkout')
    target = git(source, 'rev-parse', 'HEAD').decode().strip()
    verify_source_state(source, target)
    artifacts = {kind: validate(source, source / output, target, kind)
                 for kind, (output, _) in TARGETS.items()}
    paths = [os.fsdecode(p) for p in git(source, 'ls-files', '-z').split(b'\0') if p]
    selected = sorted(name for name in paths if included(name))
    if not set(selected) >= EXPLICIT:
        raise ValueError('Required runtime files are missing from source')
    committed = {}
    for entry in git(source, 'ls-tree', '-r', '-z', target).split(b'\0'):
        if entry:
            metadata, name = entry.split(b'\t', 1)
            committed[os.fsdecode(name)] = metadata.split()
    for name in selected:
        metadata = committed.get(name)
        if (not metadata or metadata[0] not in (b'100644', b'100755')
                or metadata[1] != b'blob'):
            raise ValueError('Runtime input must be a committed regular blob')
    destination.mkdir(mode=0o755)  # exclusive; all failures preserve this directory
    destination.chmod(0o755)
    for name in selected:
        reject_symlink_path(source, Path(name))
        origin = source / name
        if not origin.is_file():
            raise ValueError('Runtime input is not a regular file')
        output = destination / name
        payload_parent(destination, output.parent.relative_to(destination))
        copy_payload(origin, output, 0o755 if committed[name][0] == b'100755' else 0o644)
    for kind, artifact in artifacts.items():
        directory = TARGETS[kind][0]
        for name in [*artifact['outputs'], SPA_MANIFEST]:
            output = destination / directory / name
            payload_parent(destination, output.parent.relative_to(destination))
            copy_payload(source / directory / name, output, 0o644)
    # Source must not have changed while copying. Verify copied bytes separately.
    for kind, (directory, _) in TARGETS.items():
        validate(source, source / directory, target, kind)
    for name in selected:
        if file_hash(destination / name) != file_hash(source / name):
            raise ValueError('Source changed during release preparation')
        actual = git(source, 'hash-object', '--no-filters', '--', str(destination / name)).strip()
        if actual != committed[name][2]:
            raise ValueError('Copied runtime differs from its committed source blob')
    for kind, artifact in artifacts.items():
        for name, digest in artifact['outputs'].items():
            if file_hash(destination / TARGETS[kind][0] / name) != digest:
                raise ValueError('Copied frontend differs from verified artifact')
    verify_source_state(source, target)
    files = {name: file_hash(path) for name, path in sorted(payload_files(destination).items())}
    modes = {name: path.stat().st_mode & 0o7777
             for name, path in sorted(payload_files(destination).items())}
    record = {'version': 2, 'source_commit': target, 'files': files, 'modes': modes}
    marker = destination / MANIFEST
    descriptor = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
        json.dump(record, stream, sort_keys=True, indent=2)
        stream.write('\n')
    marker.chmod(0o644)
    verify_release(destination)
    return {'status': 'prepared_not_activated', 'path': str(destination),
            'source_commit': target, 'files': len(files)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--destination', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(prepare(args.source, args.destination), sort_keys=True))
        return 0
    except (OSError, ValueError) as error:
        print(f'Release preparation refused; partial output retained: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
