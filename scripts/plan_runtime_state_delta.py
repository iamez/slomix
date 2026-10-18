"""Read-only three-way comparison of an initial seed, old data and new state.

Never copies/deletes/replaces files or claims cutover readiness. A change in the
new tree must not be overwritten by an old-tree sync. Auxiliary SQLite, config,
logs and DB rows have separate reconciliation contracts.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.prepare_runtime_state import (  # noqa: E402
    NAMES,
    canonical,
    inventory,
    new_outside_git,
    write_report,
)


def content(item: dict | None):
    if item is None:
        return None
    if item.get('kind') == 'directory':
        return ('directory',)
    return ('file', item['size'], item['sha256'])


def entries(group):
    """Preserve path kind even for empty directories and zero-byte files."""
    return {**{name: {'kind': 'directory'} for name in group['directories']},
            **{name: {'kind': 'file', **metadata} for name, metadata in group['files'].items()}}


def validate_inventory(group):
    if not isinstance(group, dict) or set(group) != {'directories', 'files'}:
        raise ValueError('Invalid baseline inventory')
    dirs, files = group['directories'], group['files']
    if not isinstance(dirs, list) or not isinstance(files, dict):
        raise ValueError('Invalid baseline collections')
    for name in [*dirs, *files]:
        if (not isinstance(name, str) or not name or '\0' in name
                or Path(name).is_absolute() or '..' in Path(name).parts
                or Path(name).as_posix() != name or name == '.'):
            raise ValueError('Invalid baseline relative path')
    if len(set(dirs)) != len(dirs) or set(dirs) & files.keys():
        raise ValueError('Conflicting baseline path kinds')
    for name in [*dirs, *files]:
        if any(str(parent) in files for parent in Path(name).parents if str(parent) != '.'):
            raise ValueError('Baseline file cannot be a parent')
    for metadata in files.values():
        if (not isinstance(metadata, dict) or set(metadata) != {'size', 'mtime_ns', 'sha256'}
                or type(metadata['size']) is not int or metadata['size'] < 0
                or type(metadata['mtime_ns']) is not int or metadata['mtime_ns'] < 0
                or not isinstance(metadata['sha256'], str)
                or not re.fullmatch('[0-9a-f]{64}', metadata['sha256'])):
            raise ValueError('Invalid baseline file metadata')


def classify(base, source, target) -> str:
    """Compare path kind and file content; absence, empty dirs and files differ."""
    base, source, target = map(content, (base, source, target))
    if source == target:
        return 'unchanged' if source == base else 'converged'
    if source is None:
        return 'source_absent_preserve_target'
    if target == base:
        return 'copy_new' if base is None else 'replace_requires_archive'
    if source == base:
        return 'target_changed_preserve'
    return 'conflict'


def compare(record: dict) -> dict:
    if (not isinstance(record, dict) or not isinstance(record.get('sources'), dict)
            or not isinstance(record.get('inventory'), dict)
            or record.get('version') != 1 or record.get('status') != 'seed_only_requires_quiesced_reconciliation'
            or record.get('ready_for_activation') is not False
            or set(record['sources']) != NAMES or set(record['inventory']) != NAMES):
        raise ValueError('Expected verified initial seed report')
    for group in record['inventory'].values():
        validate_inventory(group)
    state = canonical(Path(record['state']))
    if state.name != 'shared':
        raise ValueError('Expected existing shared state directory')
    roots = {name: canonical(Path(value)) if value is not None else None
             for name, value in record['sources'].items()}
    if any(root is None and name not in {'processed', 'retro-viz'} for name, root in roots.items()):
        raise ValueError('Required source cannot be absent')
    present = [root for root in roots.values() if root is not None]
    if any(root.is_relative_to(state) or state.is_relative_to(root) for root in present):
        raise ValueError('Source and state must not overlap')
    if any(left.is_relative_to(right) for i, left in enumerate(present)
           for j, right in enumerate(present) if i != j):
        raise ValueError('Source scopes must not overlap')
    sources = {name: inventory(root) for name, root in roots.items()}
    targets = {name: inventory(state / 'data' / name) for name in NAMES}
    changes, totals = {}, {}
    for name in sorted(NAMES):
        base = entries(record['inventory'][name])
        old, new = entries(sources[name]), entries(targets[name])
        old_files, new_files = sources[name]['files'], targets[name]['files']
        changes[name] = {}
        counts = {}
        for path in sorted(base.keys() | old.keys() | new.keys()):
            action = classify(base.get(path), old.get(path), new.get(path))
            parents = [str(parent) for parent in Path(path).parents if str(parent) != '.']
            if ((path in old_files and path in targets[name]['directories'])
                    or (path in new_files and path in sources[name]['directories'])
                    or (path in old and any(parent in new_files for parent in parents))
                    or (path in new and any(parent in old_files for parent in parents))):
                action = 'path_type_conflict'
            counts[action] = counts.get(action, 0) + 1
            if action != 'unchanged':
                changes[name][path] = {'classification': action, 'baseline': base.get(path),
                                      'source': old.get(path), 'target': new.get(path)}
        totals[name] = {'classifications': counts, 'source_files': len(old_files), 'target_files': len(new_files),
                        'source_directories': len(sources[name]['directories']),
                        'target_directories': len(targets[name]['directories']),
                        'source_bytes': sum(item['size'] for item in old_files.values()),
                        'target_bytes': sum(item['size'] for item in new_files.values()),
                        'source_only_directories': sorted(set(sources[name]['directories']) - set(targets[name]['directories'])),
                        'target_only_directories': sorted(set(targets[name]['directories']) - set(sources[name]['directories']))}
    # Two stable passes are still not a lock/snapshot of live writers.
    if any(inventory(root) != sources[name] for name, root in roots.items()):
        raise ValueError('Source changed during comparison; retry after review')
    if any(inventory(state / 'data' / name) != targets[name] for name in NAMES):
        raise ValueError('Target changed during comparison; retry after review')
    return {'version': 1, 'status': 'delta_observed_no_files_changed', 'ready_for_activation': False,
            'state': str(state), 'sources': record['sources'], 'summary': totals, 'changes': changes,
            'explicitly_absent_source_scopes': sorted(name for name, root in roots.items() if root is None),
            'excluded_scopes': ['configuration', 'logs', 'auxiliary_sqlite', 'database_rows'],
            'requires_quiesced_recheck': True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed-report', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        new_outside_git(args.report)
        baseline = json.loads(args.seed_report.read_text())
        if not isinstance(baseline, dict) or not isinstance(baseline.get('sources'), dict):
            raise ValueError('Invalid seed report structure')
        if any(args.report.is_relative_to(Path(root)) for root in
               [baseline['state'], *baseline['sources'].values()] if root is not None):
            raise ValueError('Evidence must be outside data scopes')
        result = compare(baseline)
        write_report(args.report, result)
        print(json.dumps({'status': result['status'], 'summary': result['summary'],
                          'ready_for_activation': False}, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({'status': 'refused', 'ready_for_activation': False,
                          'error': 'Invalid or changing comparison inputs; no data files changed'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
