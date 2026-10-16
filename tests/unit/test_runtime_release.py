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
