"""Offline package admission must retain build identity and reject false parity."""
import hashlib
import json
import os
import subprocess

import pytest

from scripts.prepare_runtime_release import EXPLICIT
from scripts.spa_artifact import MANIFEST as BUILD_MANIFEST
from scripts.spa_artifact import TARGETS
from scripts.verify_runtime_source import main, verify_source
from shared.release_manifest import MANIFEST, file_hash, payload_files


def command(repo, *args):
    return subprocess.check_output(
        ['git', '-C', str(repo), *args],
        env={**os.environ, 'GIT_AUTHOR_NAME': 'Fixture', 'GIT_AUTHOR_EMAIL': 'fixture@example.invalid',
             'GIT_COMMITTER_NAME': 'Fixture', 'GIT_COMMITTER_EMAIL': 'fixture@example.invalid'},
        stderr=subprocess.DEVNULL,
    ).decode().strip()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)
    path.chmod(0o644)


def seal(release, source):
    paths = payload_files(release)
    record = {'version': 2, 'source_commit': source,
              'files': {name: file_hash(path) for name, path in paths.items()},
              'modes': {name: path.stat().st_mode & 0o7777 for name, path in paths.items()}}
    for path in [release, *(p for p in release.rglob('*') if p.is_dir())]:
        path.chmod(0o755)
    write(release / MANIFEST, json.dumps(record))
    return file_hash(release / MANIFEST)


@pytest.fixture
def package(tmp_path):
    repo = tmp_path / 'repository'
    repo.mkdir()
    command(repo, 'init', '-q')
    for name in sorted(EXPLICIT):
        write(repo / name, 'fixture source\n')
        command(repo, 'add', '--', name)
    command(repo, 'commit', '-qm', 'fixture source')
    source = command(repo, 'rev-parse', 'HEAD')
    tree = command(repo, 'rev-parse', 'HEAD^{tree}')
    accepted = command(repo, 'commit-tree', tree, '-p', source, '-m', 'squash identity fixture')
    command(repo, 'update-ref', 'refs/heads/accepted', accepted)
    release = tmp_path / 'package'
    for name in EXPLICIT:
        write(release / name, (repo / name).read_text())
    for kind, (directory, _) in TARGETS.items():
        names = ['app.html', 'main.js'] if kind == 'app' else ['route-host.js', 'route-host.css']
        outputs = {}
        for name in names:
            write(release / directory / name, 'fixture output\n')
            outputs[name] = file_hash(release / directory / name)
        write(release / directory / BUILD_MANIFEST, json.dumps(
            {'version': 1, 'kind': kind, 'source_commit': source, 'outputs': outputs}))
    pin = seal(release, source)
    return repo, release, source, accepted, pin


def test_distinct_commits_with_equal_trees_preserve_original_package(package):
    repo, release, source, accepted, pin = package
    before = {name: file_hash(path) for name, path in payload_files(release).items()}
    report = verify_source(*package)
    assert source != accepted
    assert report['source_commit'] == source
    assert report['accepted_commit'] == accepted
    assert report['ready_for_activation'] is False
    assert 'github_merge_authority' in report['not_checked']
    assert before == {name: file_hash(path) for name, path in payload_files(release).items()}
    assert file_hash(release / MANIFEST) == pin


def test_different_accepted_tree_refused(package):
    repo, release, source, _, pin = package
    write(repo / 'requirements.txt', 'different source\n')
    command(repo, 'add', 'requirements.txt')
    command(repo, 'commit', '-qm', 'different accepted tree')
    accepted = command(repo, 'rev-parse', 'HEAD')
    with pytest.raises(ValueError, match='source trees differ'):
        verify_source(repo, release, source, accepted, pin)


@pytest.mark.parametrize('change', ['source', 'extra', 'build-source', 'output', 'mode'])
def test_resealed_package_cannot_invent_source_parity(package, change):
    repo, release, source, accepted, _ = package
    if change == 'source':
        write(release / 'requirements.txt', 'wrong source\n')
    elif change == 'extra':
        write(release / 'unreviewed.py', 'unreviewed source\n')
    elif change == 'build-source':
        p = release / TARGETS['app'][0] / BUILD_MANIFEST
        value = json.loads(p.read_text())
        value['source_commit'] = 'a' * 40
        write(p, json.dumps(value))
    elif change == 'output':
        write(release / TARGETS['modern'][0] / 'route-host.js', 'changed output\n')
    else:
        (release / 'requirements.txt').chmod(0o755)
    pin = seal(release, source)
    with pytest.raises(ValueError):
        verify_source(repo, release, source, accepted, pin)


@pytest.mark.parametrize('field,value', [(2, 'HEAD'), (3, 'accepted'), (4, '0' * 64),
                                         (4, 'bad'), (2, 'a' * 40)])
def test_exact_identity_and_manifest_pin_required(package, field, value):
    args = list(package)
    args[field] = value
    with pytest.raises((ValueError, subprocess.CalledProcessError)):
        verify_source(*args)


def test_cli_refusal_is_json_and_never_reports_activation(package, capsys):
    repo, release, source, accepted, _ = package
    result = main(['--repository', str(repo), '--release', str(release),
                   '--expected-source', source, '--accepted-commit', accepted,
                   '--expected-manifest-sha256', hashlib.sha256(b'wrong manifest').hexdigest()])
    report = json.loads(capsys.readouterr().out)
    assert result == 1
    assert report['status'] == 'refused'
    assert report['ready_for_activation'] is False


def test_legacy_manifest_without_mode_inventory_is_not_admitted(package):
    repo, release, source, accepted, _ = package
    marker = release / MANIFEST
    record = json.loads(marker.read_text())
    record['version'] = 1
    record.pop('modes')
    write(marker, json.dumps(record))
    with pytest.raises(ValueError, match='version 2 required'):
        verify_source(repo, release, source, accepted, file_hash(marker))
