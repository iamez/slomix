"""Copy-only state seed is not readiness; no real service or DB is touched."""
import copy
import json
import os
from pathlib import Path

import pytest

from scripts import prepare_runtime_state as transfer


@pytest.fixture(autouse=True)
def service_account_for_ci(monkeypatch):
    # CI may not have Samba's passwd entry; substitute only the expected UID.
    import os
    from types import SimpleNamespace

    def account(name):
        assert name == 'samba'
        return SimpleNamespace(pw_uid=os.geteuid())

    monkeypatch.setattr(transfer.pwd, 'getpwnam', account)


@pytest.fixture
def source_map(tmp_path):
    sources = {}
    for name in sorted(transfer.NAMES):
        root = tmp_path / 'old' / name
        root.mkdir(parents=True)
        (root / 'empty').mkdir()
        (root / 'nested').mkdir()
        (root / 'nested/payload.txt').write_bytes(b'original synthetic bytes')
        sources[name] = str(root)
    return sources


def test_plan_then_seed_preserves_sources_and_never_claims_readiness(source_map, tmp_path):
    state = tmp_path / 'shared'
    record = transfer.plan(source_map, state)
    assert not state.exists()
    result = transfer.seed(record)
    assert result['status'] == 'seed_only_requires_quiesced_reconciliation'
    assert result['ready_for_activation'] is False
    assert result['files'] == 7
    for name, original in source_map.items():
        assert transfer.inventory(Path(original)) == transfer.inventory(state / 'data' / name)
    assert list((state / 'config').iterdir()) == []
    assert list((state / 'logs/bot/metrics').iterdir()) == []
    with pytest.raises(ValueError, match='new'):
        transfer.seed(record)


@pytest.mark.parametrize('damage', ['new_file', 'bytes', 'symlink', 'new_optional_scope', 'forged_plan'])
def test_drift_refuses_before_destination_created(source_map, tmp_path, damage):
    optional = Path(source_map['processed'])
    if damage == 'new_optional_scope':
        # Explicit None is a scope decision, not a watched absent pathname.
        source_map['processed'] = None
    record = transfer.plan(source_map, tmp_path / 'shared')
    origin = Path(source_map['stats'])
    if damage == 'new_file':
        (origin / 'extra').write_bytes(b'new')
    elif damage == 'bytes':
        (origin / 'nested/payload.txt').write_bytes(b'changed')
    elif damage == 'symlink':
        (origin / 'link').symlink_to(origin / 'nested/payload.txt')
    elif damage == 'new_optional_scope':
        record['sources']['processed'] = str(optional)
    else:
        record['inventory']['stats']['files']['../../escape'] = {'size': 0}
    with pytest.raises(ValueError):
        transfer.seed(record)
    assert not (tmp_path / 'shared').exists()


@pytest.mark.parametrize('damage', ['link', 'fifo', 'db', 'sqlite_magic', 'sqlite_journal', 'env'])
def test_unsafe_source_refused(source_map, tmp_path, damage):
    origin = Path(source_map['stats'])
    if damage == 'link':
        (origin / 'link').symlink_to(origin / 'nested')
    elif damage == 'fifo':
        os.mkfifo(origin / 'pipe')
    elif damage == 'db':
        (origin / 'metrics.db').write_bytes(b'database')
    elif damage == 'sqlite_journal':
        (origin / 'metrics.db-journal').write_bytes(b'synthetic rollback journal')
    elif damage == 'sqlite_magic':
        (origin / 'disguised.txt').write_bytes(b'SQLite format 3\x00more')
    else:
        (origin / '.env').write_text('synthetic=private')
    with pytest.raises(ValueError):
        transfer.plan(source_map, tmp_path / 'shared')


@pytest.mark.parametrize('damage', ['git', 'source', 'overlap', 'required_absent'])
def test_scope_refusals(source_map, tmp_path, damage):
    state = tmp_path / 'shared'
    if damage == 'git':
        (tmp_path / '.git').mkdir()
    elif damage == 'source':
        state = Path(source_map['stats']) / 'shared'
    elif damage == 'overlap':
        source_map['gametimes'] = source_map['stats']
    else:
        source_map['stats'] = None
    with pytest.raises(ValueError):
        transfer.plan(source_map, state)


def test_corrupt_copy_retained_but_refused(source_map, tmp_path, monkeypatch):
    state = tmp_path / 'shared'
    record = transfer.plan(source_map, state)
    original = transfer.inventory
    def damaged(root):
        measured = original(root)
        if root is not None and root.is_relative_to(state):
            measured = copy.deepcopy(measured)
            measured['files']['nested/payload.txt']['sha256'] = 'wrong'
        return measured
    monkeypatch.setattr(transfer, 'inventory', damaged)
    with pytest.raises(ValueError, match='Copied data differs'):
        transfer.seed(record)
    assert state.is_dir()
    assert len(list(state.rglob('payload.txt'))) == 1
    assert Path(source_map['stats'], 'nested/payload.txt').read_bytes() == b'original synthetic bytes'


def test_source_change_during_copy_is_not_certified(source_map, tmp_path, monkeypatch):
    record = transfer.plan(source_map, tmp_path / 'shared')
    original = transfer.inventory
    altered = False
    def during_copy(root):
        nonlocal altered
        if root is not None and root.is_relative_to(tmp_path / 'shared') and not altered:
            Path(source_map['stats'], 'late.txt').write_bytes(b'late arrival')
            altered = True
        return original(root)
    monkeypatch.setattr(transfer, 'inventory', during_copy)
    with pytest.raises(ValueError, match='Source changed during copy'):
        transfer.seed(record)
    assert (tmp_path / 'shared').exists()


def test_cli_requires_exclusive_external_report_before_copy(source_map, tmp_path, capsys):
    source_file = tmp_path / 'sources.json'
    source_file.write_text(json.dumps(source_map))
    plan_file = tmp_path / 'plan.json'
    assert transfer.main(['plan', '--input', str(source_file), '--state', str(tmp_path / 'shared'),
                          '--report', str(plan_file)]) == 0
    assert plan_file.stat().st_mode & 0o077 == 0
    assert transfer.main(['seed', '--input', str(plan_file), '--report', str(plan_file)]) == 1
    assert not (tmp_path / 'shared').exists()
    capsys.readouterr()


def test_seed_cannot_override_saved_destination(tmp_path):
    with pytest.raises(SystemExit) as error:
        transfer.main(['seed', '--input', str(tmp_path / 'absent-plan.json'),
                       '--state', str(tmp_path / 'shared'), '--report', str(tmp_path / 'report.json')])
    assert error.value.code == 2
    assert not (tmp_path / 'shared').exists()


@pytest.mark.parametrize('marker', ['release', 'release_link', 'git_link'])
@pytest.mark.parametrize('nested', [False, True])
def test_state_and_report_cannot_write_into_marked_payload(source_map, tmp_path, marker, nested):
    release = tmp_path / 'payload'
    release.mkdir()
    name = '.git' if marker == 'git_link' else '.slomix-release.json'
    if marker.endswith('link'):
        (release / name).symlink_to(release / 'missing-marker-target')
    else:
        (release / name).write_text('{}')
    parent = release / 'nested' if nested else release
    parent.mkdir(exist_ok=True)
    target, report = parent / 'shared', parent / 'report.json'
    with pytest.raises(ValueError, match='outside Git or immutable releases'):
        transfer.plan(source_map, target)
    with pytest.raises(ValueError, match='outside Git or immutable releases'):
        transfer.write_report(report, {'state': str(tmp_path / 'shared'), 'sources': source_map})
    assert not target.exists() and not report.exists()
    assert (release / name).exists() or (release / name).is_symlink()


@pytest.mark.parametrize('command', ['plan', 'seed'])
@pytest.mark.parametrize('payload', [[], [{}], None, 7, True, {'sources': []}])
def test_cli_malformed_json_refuses_without_traceback_or_output(tmp_path, capsys, command, payload):
    if isinstance(payload, dict):
        payload = dict(payload, state=str(tmp_path / 'shared'))
    source = tmp_path / 'malformed-private-input.json'
    source.write_text(json.dumps(payload))
    report = tmp_path / 'report.json'
    args = [command, '--input', str(source), '--report', str(report)]
    if command == 'plan':
        args += ['--state', str(tmp_path / 'shared')]
    assert transfer.main(args) == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out)['status'] == 'refused'
    assert not captured.err and str(source) not in captured.out
    assert not report.exists() and not (tmp_path / 'shared').exists()


@pytest.mark.parametrize('cli', [False, True])
def test_wrong_service_uid_refused_before_any_seed_output(source_map, tmp_path, monkeypatch, capsys, cli):
    from types import SimpleNamespace

    state = tmp_path / 'shared'
    record = transfer.plan(source_map, state)
    source_before = {name: transfer.inventory(Path(root)) for name, root in source_map.items()}
    plan_file = tmp_path / 'plan.json'
    plan_file.write_text(json.dumps(record))
    report = tmp_path / 'seed-report.json'
    monkeypatch.setattr(transfer.pwd, 'getpwnam', lambda _: SimpleNamespace(pw_uid=os.geteuid() + 1))
    if cli:
        assert transfer.main(['seed', '--input', str(plan_file), '--report', str(report)]) == 1
        captured = capsys.readouterr()
        assert json.loads(captured.out)['status'] == 'refused'
        assert not captured.err
    else:
        with pytest.raises(ValueError, match='samba service account'):
            transfer.seed(record)
    assert not state.exists() and not report.exists()
    assert {name: transfer.inventory(Path(root)) for name, root in source_map.items()} == source_before


@pytest.mark.parametrize('name', ['.git', '.slomix-release.json'])
@pytest.mark.parametrize('command', ['plan', 'seed'])
def test_cli_cannot_create_reserved_report_marker(source_map, tmp_path, capsys, name, command):
    state = tmp_path / 'shared'
    record = source_map if command == 'plan' else transfer.plan(source_map, state)
    source = tmp_path / 'input.json'
    source.write_text(json.dumps(record))
    before = set(tmp_path.iterdir())
    args = [command, '--input', str(source), '--report', str(tmp_path / name)]
    if command == 'plan':
        args += ['--state', str(state)]
    assert transfer.main(args) == 1
    assert json.loads(capsys.readouterr().out)['status'] == 'refused'
    assert set(tmp_path.iterdir()) == before
    assert not state.exists()
