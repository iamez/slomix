"""Release preparation must preserve sources and refuse stale/mixed payloads."""
import json

import pytest

from scripts import prepare_runtime_release as package
from shared.release_manifest import MANIFEST, file_hash, verify_release
from tests.unit.test_spa_artifact_preflight import build, git
from tests.unit.test_spa_artifact_preflight import fixture as source_fixture  # noqa: F401 - pytest fixture
from website.backend import build_info


@pytest.fixture
def release(tmp_path):
    root = tmp_path / 'release'
    root.mkdir()
    (root / 'app.py').write_text('VALUE = 1\n')
    record = {'version': 1, 'source_commit': 'a' * 40,
              'files': {'app.py': file_hash(root / 'app.py')}}
    (root / MANIFEST).write_text(json.dumps(record))
    return root


def test_verified_git_free_identity_without_git(release, monkeypatch):
    monkeypatch.setattr(build_info, 'PROJECT_ROOT', release)
    monkeypatch.setattr(build_info.subprocess, 'run', lambda *a, **kw: pytest.fail('Git must not run'))
    assert build_info._read_git_revision() == ('a' * 40, 'a' * 8)  # noqa: SLF001 - startup boundary


@pytest.mark.parametrize('damage', ['bytes', 'extra', 'missing', 'symlink', 'revision', 'traversal'])
def test_corrupt_release_never_falls_back_to_git(release, monkeypatch, damage):
    marker = release / MANIFEST
    record = json.loads(marker.read_text())
    if damage == 'bytes':
        (release / 'app.py').write_text('VALUE = 2\n')
    elif damage == 'extra':
        (release / 'extra.py').write_text('pass\n')
    elif damage == 'missing':
        (release / 'app.py').rename(release.parent / 'retained-app.py')
    elif damage == 'symlink':
        (release / 'linked.py').symlink_to(release / 'app.py')
    elif damage == 'revision':
        record['source_commit'] = 'not-a-sha'
        marker.write_text(json.dumps(record))
    else:
        record['files']['../outside'] = '0' * 64
        marker.write_text(json.dumps(record))
    monkeypatch.setattr(build_info, 'PROJECT_ROOT', release)
    monkeypatch.setattr(build_info.subprocess, 'run', lambda *a, **kw: pytest.fail('Git fallback forbidden'))
    with pytest.raises(ValueError):
        build_info._read_git_revision()  # noqa: SLF001 - startup boundary


def test_unmarked_non_checkout_does_not_use_ancestor_git(tmp_path, monkeypatch):
    monkeypatch.setattr(build_info, 'PROJECT_ROOT', tmp_path)
    monkeypatch.setattr(build_info.subprocess, 'run', lambda *a, **kw: pytest.fail('No own .git'))
    assert build_info._read_git_revision() == (None, None)  # noqa: SLF001 - startup boundary


def test_package_prepares_only_allowed_runtime_files_and_never_overwrites(source_fixture):  # noqa: F811
    source, _ = source_fixture
    additions = set(package.EXPLICIT) | {
        'shared/release_manifest.py', 'bot/worker.py', 'greatshot/tests/test_demo.py',
        'tests/test_worker.py', 'docs/research/notes.md', 'website/assets/game/map.png',
    }
    for name in additions:
        path = source / name
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('synthetic\n')
    git(source, 'add', '--', *sorted(additions))
    git(source, 'commit', '-m', 'fixture runtime inputs')
    (source / '.env').write_text('PRIVATE_DO_NOT_COPY=fixture\n')
    build(source)
    before = git(source, 'rev-parse', 'HEAD')
    destination = source.parent / 'prepared'
    result = package.prepare(source, destination)
    assert result['status'] == 'prepared_not_activated'
    record = verify_release(destination)
    assert record['source_commit'] == before
    assert record['files'].keys() >= package.EXPLICIT
    for excluded in ['.git', '.env', 'tests', 'docs', 'greatshot/tests', 'website/frontend']:
        assert not (destination / excluded).exists()
    assert (destination / 'website/static/app/app.html').is_file()
    assert (destination / 'website/assets/game/map.png').is_file()
    with pytest.raises(ValueError, match='NEW'):
        package.prepare(source, destination)
    assert verify_release(destination) == record
    assert git(source, 'rev-parse', 'HEAD') == before
    assert (source / '.env').read_text() == 'PRIVATE_DO_NOT_COPY=fixture\n'


@pytest.fixture
def committed_runtime_source(source_fixture):  # noqa: F811 -- imported pytest fixture
    source, _ = source_fixture
    for name in package.EXPLICIT:
        path = source / name
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('# synthetic, never executed\n')
    git(source, 'add', '--', *sorted(package.EXPLICIT))
    git(source, 'commit', '-m', 'fixture runtime inputs')
    build(source)
    return source


@pytest.mark.parametrize('staged', [False, True])
def test_dirty_tracked_runtime_bytes_cannot_ship_under_head(committed_runtime_source, staged):
    source = committed_runtime_source
    runtime = source / 'bot/runtime.py'
    runtime.write_text(runtime.read_text() + '# changed runtime source\n')
    if staged:
        git(source, 'add', '--', 'bot/runtime.py')
    destination = source.parent / 'refused-dirty'
    with pytest.raises(ValueError):
        package.prepare(source, destination)
    assert not destination.exists()
    assert runtime.read_text().endswith('# changed runtime source\n')


def test_tracked_drift_during_copy_retains_incomplete_unstamped_output(committed_runtime_source, monkeypatch):
    source = committed_runtime_source
    original = package.shutil.copyfile
    changed = False

    def copy(*args, **kwargs):
        nonlocal changed
        result = original(*args, **kwargs)
        if not changed:
            path = source / 'bot/runtime.py'
            path.write_text(path.read_text() + '# mid-copy drift\n')
            changed = True
        return result

    monkeypatch.setattr(package.shutil, 'copyfile', copy)
    destination = source.parent / 'retained-partial'
    with pytest.raises(ValueError):
        package.prepare(source, destination)
    assert changed and destination.is_dir()
    assert not (destination / MANIFEST).exists()
    assert (source / 'bot/runtime.py').read_text().endswith('# mid-copy drift\n')


def test_transient_runtime_drift_cannot_receive_the_original_commit_stamp(committed_runtime_source, monkeypatch):
    source = committed_runtime_source
    runtime = source / 'bot/runtime.py'
    before = runtime.read_bytes()
    copy_file, hash_file = package.shutil.copyfile, package.file_hash
    changed = restored = False

    poisoned = before + b'# transient runtime change\n'

    def copy(*args, **kwargs):
        nonlocal changed
        if not changed:
            runtime.write_bytes(poisoned)
            changed = True
        result = copy_file(*args, **kwargs)
        if args[0] == runtime:
            runtime.write_bytes(before)  # The next SPA/source snapshot sees clean HEAD.
        return result

    def digest(path):
        nonlocal restored
        if path == runtime:
            assert runtime.read_bytes() == before
            runtime.write_bytes(poisoned)  # A second edit coincides with source hashing.
            try:
                return hash_file(path)  # Actual bytes, not a fabricated hash value.
            finally:
                runtime.write_bytes(before)
                restored = True
        return hash_file(path)

    monkeypatch.setattr(package.shutil, 'copyfile', copy)
    monkeypatch.setattr(package, 'file_hash', digest)
    destination = source.parent / 'transient-drift-output'
    with pytest.raises(ValueError, match='committed source blob'):
        package.prepare(source, destination)
    assert changed and restored and runtime.read_bytes() == before
    assert git(source, 'diff', '--name-only', 'HEAD', '--') == ''
    assert destination.is_dir() and not (destination / MANIFEST).exists()


def test_payload_executable_mode_comes_from_committed_tree(committed_runtime_source):
    source = committed_runtime_source
    runtime = source / 'bot/runtime.py'
    git(source, 'config', 'core.filemode', 'false')
    git(source, 'update-index', '--chmod=+x', '--', 'bot/runtime.py')
    git(source, 'commit', '-m', 'fixture executable mode')
    runtime.chmod(0o600)
    build(source)
    assert git(source, 'diff', '--name-only', 'HEAD', '--') == ''
    destination = source.parent / 'committed-mode'
    package.prepare(source, destination)
    assert (destination / 'bot/runtime.py').stat().st_mode & 0o777 == 0o755
    assert runtime.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('mode', [0o600, 0o755, 0o666, 0o4644])
def test_version_two_refuses_changed_modes(release, mode):
    marker = release / MANIFEST
    record = json.loads(marker.read_text())
    record.update(version=2, modes={'app.py': 0o644})
    (release / 'app.py').chmod(0o644)
    marker.write_text(json.dumps(record))
    verify_release(release)
    (release / 'app.py').chmod(mode)
    with pytest.raises(ValueError):
        verify_release(release)


def test_packaged_tools_include_their_real_bootstrap_dependency(committed_runtime_source):
    import subprocess
    import sys
    from pathlib import Path

    source = committed_runtime_source
    project = Path(__file__).resolve().parents[2]
    actual = ['scripts/dev_runtime_contract.py', 'scripts/dev_verify_health.py',
              'scripts/runtime_app_bootstrap.py', 'shared/release_manifest.py',
              'shared/runtime_environment.py']
    for name in actual:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((project / name).read_bytes())
    git(source, 'add', '--', *actual)
    git(source, 'commit', '-m', 'fixture actual packaged tools')
    build(source)
    destination = source.parent / 'real-tools'
    package.prepare(source, destination)
    record = verify_release(destination)
    assert record['version'] == 2
    assert record['modes'].keys() == record['files'].keys()
    assert (destination / 'scripts/runtime_app_bootstrap.py').is_file()
    for tool in ('dev_runtime_contract.py', 'dev_verify_health.py'):
        result = subprocess.run([sys.executable, '-I', str(destination / 'scripts' / tool), '--help'],
                                cwd=destination, capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stderr
        assert 'usage:' in result.stdout
    assert verify_release(destination) == record
