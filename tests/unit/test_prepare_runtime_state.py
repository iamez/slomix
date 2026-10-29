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


@pytest.mark.parametrize('nested', [False, True])
@pytest.mark.parametrize('kind', ['empty_directory', 'file', 'symlink'])
def test_git_source_component_refused_before_type_dispatch(source_map, tmp_path, nested, kind):
    origin = Path(source_map['stats'])
    marker = origin / 'nested' / '.git' if nested else origin / '.git'
    if kind == 'empty_directory':
        marker.mkdir()
    elif kind == 'file':
        marker.write_text('gitdir: synthetic metadata')
    else:
        marker.symlink_to(origin / 'missing-target')
    with pytest.raises(ValueError, match='Git metadata'):
        transfer.plan(source_map, tmp_path / 'shared')
    assert not (tmp_path / 'shared').exists()


@pytest.mark.parametrize('command', ['plan', 'seed'])
def test_native_cli_empty_git_directory_refuses_without_output(source_map, tmp_path, command):
    import subprocess
    import sys

    state = tmp_path / 'shared'
    # A directory arriving after a valid plan must also be rejected before copy.
    record = source_map if command == 'plan' else transfer.plan(source_map, state)
    marker = Path(source_map['stats']) / 'nested' / '.git'
    marker.mkdir()
    before = {str(path.relative_to(tmp_path)): (path.is_dir(), path.read_bytes() if path.is_file() else None)
              for path in tmp_path.rglob('*')}
    source = tmp_path / 'input.json'
    source.write_text(json.dumps(record))
    report = tmp_path / 'report.json'
    args = [sys.executable, '-B', str(Path(transfer.__file__)), command,
            '--input', str(source), '--report', str(report)]
    if command == 'plan':
        args += ['--state', str(state)]
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    assert result.returncode == 1
    assert json.loads(result.stdout)['status'] == 'refused'
    assert not result.stderr
    assert not state.exists() and not report.exists()
    after = {str(path.relative_to(tmp_path)): (path.is_dir(), path.read_bytes() if path.is_file() else None)
             for path in tmp_path.rglob('*') if path != source}
    assert after == before


@pytest.mark.parametrize('name', ['.env', '.env.d', '.environment'])
@pytest.mark.parametrize('nested', [False, True])
def test_configuration_directory_components_refused(source_map, tmp_path, name, nested):
    root = Path(source_map['stats'])
    directory = root / 'nested' / name if nested else root / name
    directory.mkdir()
    (directory / 'token').write_text('synthetic-private-value')
    with pytest.raises(ValueError, match='Configuration'):
        transfer.plan(source_map, tmp_path / 'shared')
    assert not (tmp_path / 'shared').exists()


@pytest.mark.parametrize('name', ['.git', '.env.d'])
def test_selected_configuration_or_git_root_is_refused(tmp_path, name):
    root = tmp_path / name
    root.mkdir()
    (root / 'token').write_text('synthetic-private-value')
    with pytest.raises(ValueError, match='source root'):
        transfer.inventory(root)


def test_native_cli_configuration_directory_refuses_without_copy(source_map, tmp_path):
    import subprocess
    import sys

    directory = Path(source_map['stats']) / '.env.d'
    directory.mkdir()
    token = directory / 'token'
    token.write_bytes(b'synthetic-private-value')
    source = tmp_path / 'sources.json'
    source.write_text(json.dumps(source_map))
    report = tmp_path / 'report.json'
    state = tmp_path / 'shared'
    result = subprocess.run([sys.executable, '-B', transfer.__file__, 'plan', '--input', str(source),
                             '--state', str(state), '--report', str(report)],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 1 and json.loads(result.stdout)['status'] == 'refused'
    assert not result.stderr and not report.exists() and not state.exists()
    assert token.read_bytes() == b'synthetic-private-value'
    assert b'synthetic-private-value' not in result.stdout.encode()


@pytest.mark.parametrize('marker', ['.git', '.env.d'])
def test_selected_source_beneath_metadata_ancestor_is_refused(source_map, tmp_path, marker):
    root = tmp_path / 'metadata-parent' / marker / 'payload'
    root.mkdir(parents=True)
    token = root / 'innocent'
    token.write_bytes(b'synthetic-private-bytes')
    source_map['stats'] = str(root)
    with pytest.raises(ValueError, match='source root'):
        transfer.plan(source_map, tmp_path / 'shared')
    assert not (tmp_path / 'shared').exists()
    assert token.read_bytes() == b'synthetic-private-bytes'


@pytest.mark.parametrize('operation', ['destination', 'state-report', 'writer-report'])
def test_bare_git_repository_output_ancestry_refused(tmp_path, operation):
    import subprocess

    from scripts import runtime_writer_inventory as writer

    bare = tmp_path / 'bare-repository'
    subprocess.run(['git', 'init', '--bare', '--template=', str(bare)],
                   check=True, capture_output=True)
    parent = bare / 'nested'
    parent.mkdir()
    target = parent / ('shared' if operation == 'destination' else 'report.json')
    with pytest.raises(ValueError, match='outside'):
        if operation == 'destination':
            transfer.new_outside_git(target)
        elif operation == 'state-report':
            transfer.write_report(target, {'state': str(tmp_path / 'shared'), 'sources': {}})
        else:
            writer.write_report(target, '{}')
    assert not target.exists()


@pytest.mark.parametrize('boundary', ['source', 'destination'])
def test_native_cli_hidden_source_or_bare_destination_refuses(source_map, tmp_path, boundary):
    import subprocess
    import sys

    state = tmp_path / 'shared'
    if boundary == 'source':
        root = tmp_path / '.env.d' / 'payload'
        root.mkdir(parents=True)
        (root / 'token').write_bytes(b'synthetic-private-bytes')
        source_map['stats'] = str(root)
    else:
        bare = tmp_path / 'bare-repository'
        subprocess.run(['git', 'init', '--bare', '--template=', str(bare)],
                       check=True, capture_output=True)
        state = bare / 'shared'
    source = tmp_path / 'sources.json'
    source.write_text(json.dumps(source_map))
    report = tmp_path / 'report.json'
    result = subprocess.run([sys.executable, '-B', transfer.__file__, 'plan', '--input', str(source),
                             '--state', str(state), '--report', str(report)],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 1 and json.loads(result.stdout)['status'] == 'refused'
    assert not result.stderr and not report.exists() and not state.exists()



def test_seed_report_is_reserved_before_copy_and_completed_on_same_stream(source_map, tmp_path, monkeypatch, capsys):
    state, report = tmp_path / 'shared', tmp_path / 'seed-report.json'
    record = transfer.plan(source_map, state)
    initial = tmp_path / 'plan.json'
    initial.write_text(json.dumps(record))
    original = transfer.seed
    def checked_seed(value):
        assert not state.exists()
        assert report.stat().st_mode & 0o777 == 0o600
        with pytest.raises(FileExistsError), report.open('x'):
            pass
        return original(value)
    monkeypatch.setattr(transfer, 'seed', checked_seed)
    assert transfer.main(['seed', '--input', str(initial), '--report', str(report)]) == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'seed_only_requires_quiesced_reconciliation'
    result = json.loads(report.read_text())
    assert result['files'] == 7 and result['ready_for_activation'] is False
    assert all(transfer.inventory(Path(source_map[name])) == transfer.inventory(state / 'data' / name)
               for name in source_map)


@pytest.mark.parametrize('operation', ['plan', 'seed', 'delta'])
def test_native_data_reads_preserve_file_and_directory_access_times(source_map, tmp_path, operation):
    from scripts import plan_runtime_state_delta as delta
    state = tmp_path / 'shared'
    record = transfer.plan(source_map, state)
    if operation == 'delta':
        record = transfer.seed(record)
    roots = [Path(root) for root in source_map.values()]
    if operation == 'delta':
        roots += [state / 'data' / name for name in source_map]
    paths = [path for root in roots for path in [root, *root.rglob('*')]]
    old = 946684800000000000
    for path in paths:
        info = path.stat()
        os.utime(path, ns=(old, info.st_mtime_ns))
    before = {path: path.stat().st_atime_ns for path in paths}
    if operation == 'plan':
        transfer.plan(source_map, state)
    elif operation == 'seed':
        transfer.seed(record)
    else:
        delta.compare(record)
    assert {path: path.stat().st_atime_ns for path in paths} == before


def test_no_atime_support_is_required_before_read(tmp_path, monkeypatch):
    path = tmp_path / 'data'
    path.write_bytes(b'content')
    monkeypatch.delattr(os, 'O_NOATIME')
    with pytest.raises(ValueError, match='No-atime'):
        transfer.fingerprint(path)


def test_no_atime_permission_failure_is_not_retried(tmp_path, monkeypatch):
    path = tmp_path / 'data'
    path.write_bytes(b'content')
    calls = []
    def denied(*args):
        calls.append(args)
        raise PermissionError('no no-atime capability')
    monkeypatch.setattr(os, 'open', denied)
    with pytest.raises(PermissionError):
        transfer.fingerprint(path)
    assert len(calls) == 1 and calls[0][1] & os.O_NOATIME


def create_bare_repository(path):
    import subprocess

    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'init', '--bare', '--template=', str(path)],
                   check=True, capture_output=True, text=True)
    assert (path / 'HEAD').is_file() and (path / 'objects').is_dir()
    assert not (path / '.git').exists()


@pytest.mark.parametrize('nested', [False, True])
def test_bare_git_source_is_not_data(source_map, tmp_path, nested):
    root = Path(source_map['stats'])
    create_bare_repository(root / 'nested/repository' if nested else root)
    with pytest.raises(ValueError, match='Git metadata'):
        transfer.plan(source_map, tmp_path / 'shared')
    assert not (tmp_path / 'shared').exists()


@pytest.mark.parametrize('nested', [False, True])
def test_bare_git_arriving_after_plan_refuses_before_seed(source_map, tmp_path, nested):
    record = transfer.plan(source_map, tmp_path / 'shared')
    root = Path(source_map['stats'])
    create_bare_repository(root / 'nested/repository' if nested else root)
    with pytest.raises(ValueError, match='Git metadata'):
        transfer.seed(record)
    assert not (tmp_path / 'shared').exists()


@pytest.mark.parametrize('nested', [False, True])
def test_native_plan_cli_refuses_bare_git_before_copy(source_map, tmp_path, nested):
    import subprocess
    import sys

    root = Path(source_map['stats'])
    create_bare_repository(root / 'nested/repository' if nested else root)
    source_file = tmp_path / 'sources.json'
    source_file.write_text(json.dumps(source_map))
    report = tmp_path / 'bare-refusal.json'
    result = subprocess.run(
        [sys.executable, str(Path(transfer.__file__)), 'plan', '--input', str(source_file),
         '--state', str(tmp_path / 'shared'), '--report', str(report)],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert json.loads(result.stdout)['status'] == 'refused'
    assert json.loads(result.stdout)['ready_for_activation'] is False
    assert not report.exists() and not (tmp_path / 'shared').exists()


@pytest.mark.parametrize('side', ['source', 'target'])
def test_delta_refuses_bare_git_metadata_in_either_tree(source_map, tmp_path, side):
    from scripts.plan_runtime_state_delta import compare

    record = transfer.seed(transfer.plan(source_map, tmp_path / 'shared'))
    root = (Path(source_map['stats']) if side == 'source'
            else tmp_path / 'shared/data/stats')
    original = (root / 'nested/payload.txt').read_bytes()
    create_bare_repository(root / 'nested/repository')
    with pytest.raises(ValueError, match='Git metadata'):
        compare(record)
    assert (root / 'nested/payload.txt').read_bytes() == original
