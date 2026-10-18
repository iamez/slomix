"""A final transfer cannot overwrite independent edits in the copied state."""
import copy
import json
from pathlib import Path

import pytest

from scripts import plan_runtime_state_delta as delta
from scripts import prepare_runtime_state as seed


def item(digest):
    return {'size': 1, 'sha256': digest, 'mtime_ns': 1} if digest is not None else None


@pytest.mark.parametrize('base,old,new,expected', [
    ('a', 'a', 'a', 'unchanged'), ('a', 'b', 'b', 'converged'),
    (None, 'a', 'a', 'converged'), ('a', None, None, 'converged'),
    (None, 'a', None, 'copy_new'), ('a', 'b', 'a', 'replace_requires_archive'),
    ('a', 'a', 'b', 'target_changed_preserve'), ('a', 'a', None, 'target_changed_preserve'),
    ('a', 'b', 'c', 'conflict'), (None, 'a', 'b', 'conflict'),
    ('a', None, 'a', 'source_absent_preserve_target'),
    (None, None, 'a', 'source_absent_preserve_target'),
    ('a', None, 'b', 'source_absent_preserve_target'),
])
def test_three_way_contract(base, old, new, expected):
    assert delta.classify(item(base), item(old), item(new)) == expected


@pytest.fixture(autouse=True)
def service_account_for_ci(monkeypatch):
    # CI may not have Samba's passwd entry; substitute only the expected UID.
    import os
    from types import SimpleNamespace

    def account(name):
        assert name == 'samba'
        return SimpleNamespace(pw_uid=os.geteuid())

    monkeypatch.setattr(seed.pwd, 'getpwnam', account)


@pytest.fixture
def baseline(tmp_path):
    sources = {}
    for name in sorted(seed.NAMES):
        root = tmp_path / 'old' / name
        root.mkdir(parents=True)
        (root / 'original.txt').write_bytes(b'initial')
        sources[name] = str(root)
    return seed.seed(seed.plan(sources, tmp_path / 'shared'))


def test_real_three_way_scan_is_nonmutating(baseline):
    old = Path(baseline['sources']['stats'])
    new = Path(baseline['state']) / 'data/stats'
    (old / 'added.txt').write_bytes(b'new file')
    (old / 'original.txt').write_bytes(b'changed source')
    (new / 'independent.txt').write_bytes(b'new runtime file')
    before = (seed.inventory(old), seed.inventory(new))
    report = delta.compare(baseline)
    assert report['ready_for_activation'] is False
    assert report['requires_quiesced_recheck'] is True
    assert report['summary']['stats']['classifications'] == {
        'copy_new': 1, 'replace_requires_archive': 1, 'source_absent_preserve_target': 1}
    assert (seed.inventory(old), seed.inventory(new)) == before


def test_mtime_alone_does_not_propose_replacement():
    original = item('same')
    touched = dict(original, mtime_ns=900)
    assert delta.classify(original, touched, original) == 'unchanged'
    assert delta.classify(None, {'size': 0, 'sha256': 'empty'}, None) == 'copy_new'


def test_changed_inventory_refuses(baseline, monkeypatch):
    actual = delta.inventory
    calls = 0
    def drift(root):
        nonlocal calls
        calls += 1
        result = actual(root)
        if calls > 14 and root == Path(baseline['sources']['stats']):
            result['files'] = {}
        return result
    monkeypatch.setattr(delta, 'inventory', drift)
    with pytest.raises(ValueError, match='changed during comparison'):
        delta.compare(baseline)


@pytest.mark.parametrize('damage', ['dry_run', 'overlap', 'missing_scope', 'symlink'])
def test_bad_scope_refused(baseline, damage):
    record = copy.deepcopy(baseline)
    if damage == 'dry_run':
        record['status'] = 'dry_run_not_copied'
    elif damage == 'overlap':
        record['sources']['stats'] = record['sources']['gametimes']
    elif damage == 'missing_scope':
        record['sources'].pop('stats')
    else:
        (Path(record['state']) / 'data/stats/link').symlink_to(record['sources']['stats'])
    with pytest.raises(ValueError):
        delta.compare(record)


@pytest.mark.parametrize('side', ['source', 'target'])
def test_file_directory_collision_is_never_copy_new(baseline, side):
    old = Path(baseline['sources']['stats'])
    new = Path(baseline['state']) / 'data/stats'
    file_root, dir_root = (old, new) if side == 'source' else (new, old)
    (file_root / 'collision').write_text('file')
    (dir_root / 'collision').mkdir()
    (dir_root / 'collision/child').write_text('child')
    changes = delta.compare(baseline)['changes']['stats']
    assert changes['collision']['classification'] == 'path_type_conflict'
    assert changes['collision/child']['classification'] == 'path_type_conflict'


@pytest.mark.parametrize('damage', ['list', 'path', 'hash', 'bool_size', 'dirs'])
def test_malformed_baseline_refused(baseline, damage):
    group = baseline['inventory']['stats']
    if damage == 'list':
        group['files'] = []
    elif damage == 'path':
        group['files']['../escape'] = group['files'].pop('original.txt')
    elif damage == 'hash':
        group['files']['original.txt']['sha256'] = 'invalid'
    elif damage == 'bool_size':
        group['files']['original.txt']['size'] = True
    else:
        group['directories'] = ['original.txt']
    with pytest.raises(ValueError):
        delta.compare(baseline)


def test_cli_malformed_source_map_returns_structured_refusal(tmp_path, capsys):
    baseline = tmp_path / 'invalid.json'
    baseline.write_text(json.dumps({'sources': [], 'state': str(tmp_path / 'shared')}))
    report = tmp_path / 'not-created.json'
    assert delta.main(['--seed-report', str(baseline), '--report', str(report)]) == 1
    assert json.loads(capsys.readouterr().out)['status'] == 'refused'
    assert not report.exists()


@pytest.mark.parametrize('base_kind,source_kind,target_kind,expected', [
    ('file', 'absent', 'directory', 'source_absent_preserve_target'),
    ('file', 'directory', 'absent', 'conflict'),
    ('directory', 'absent', 'directory', 'source_absent_preserve_target'),
    ('directory', 'directory', 'absent', 'target_changed_preserve'),
    ('directory', 'file', 'absent', 'conflict'),
    ('absent', 'directory', 'absent', 'copy_new'),
    ('absent', 'absent', 'directory', 'source_absent_preserve_target'),
    ('directory', 'absent', 'absent', 'converged'),
    ('file', 'directory', 'directory', 'converged'),
    ('directory', 'file', 'file', 'converged'),
])
def test_native_empty_directory_three_way_state(baseline, base_kind, source_kind, target_kind, expected):
    old = Path(baseline['sources']['stats'])
    new = Path(baseline['state']) / 'data/stats'
    group = baseline['inventory']['stats']
    name = 'kind-change'
    # Define a valid baseline snapshot; current trees then independently evolve.
    if base_kind == 'directory':
        group['directories'].append(name)
    elif base_kind == 'file':
        group['files'][name] = {'size': 0, 'mtime_ns': 1,
                               'sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'}
    for root, kind in ((old, source_kind), (new, target_kind)):
        if kind == 'directory':
            (root / name).mkdir()
        elif kind == 'file':
            (root / name).write_bytes(b'')
    before = seed.inventory(old), seed.inventory(new)
    result = delta.compare(baseline)
    change = result['changes']['stats'][name]
    assert change['classification'] == expected
    for label, kind in (('baseline', base_kind), ('source', source_kind), ('target', target_kind)):
        assert change[label] is None if kind == 'absent' else change[label]['kind'] == kind
    assert (seed.inventory(old), seed.inventory(new)) == before
    assert result['summary']['stats']['source_directories'] == (source_kind == 'directory')
    assert result['summary']['stats']['target_directories'] == (target_kind == 'directory')
