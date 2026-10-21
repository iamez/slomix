"""Fresh game placement only: no game/service launch or application database."""

import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from scripts import prepare_runtime_game_bundle as game
from scripts import prepare_runtime_game_workspace as workspace
from tests.unit.test_runtime_game_bundle import inputs  # noqa: F401


@pytest.fixture
def placement(inputs, tmp_path):  # noqa: F811
    target = tmp_path / 'layout'
    # Long pytest names would exceed sun_path; only bundle preparation needs
    # the precise real socket pathname, so use a short fixture test basetemp.
    inputs['socket_path'] = str(target / 'control/m.sock')
    game.prepare(**inputs)
    executable = tmp_path / 'etlded'
    executable.write_bytes(b'explicit fixture executable, never executed\n')
    executable.chmod(0o700)
    assets = {}
    for index, name in enumerate(sorted(workspace.ASSETS)):
        path = tmp_path / f'asset{index}.pk3'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('maps/supply.bsp' if 'supply_sp' in name else 'fixture.dat', b'fixture')
        path.chmod(0o600)
        assets[name] = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    return dict(destination=target, bundle=inputs['destination'], executable=executable,
                executable_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(), assets=assets)


def test_new_layout_is_private_separate_and_exact(placement):
    result = workspace.prepare(**placement)
    root = placement['destination']
    assert result['activation_ready'] is False and result['status'] == 'prepared_not_started'
    roots = [Path(p) for p in result['roots'].values()]
    assert len(roots) == 4
    assert all(os.stat(p).st_uid == os.getuid() and os.stat(p).st_mode & 0o777 == 0o700 for p in roots)
    assert all(not a.is_relative_to(b) for a in roots for b in roots if a != b)
    assert Path(result['roots']['producer_spool']) == root / 'home/legacy/gamestats/runtime-snapshots'
    assert all(not list(p.iterdir()) for p in roots)
    assert len(list((root / 'base').rglob('*.pk3'))) == 5
    assert (root / 'home/legacy/autoexec.cfg').read_bytes() == workspace.EMPTY_CONFIG
    assert (root / 'base/LICENSE').read_bytes() == (placement['bundle'] / 'LICENSE').read_bytes()
    assert (root / 'base/LuaSocket-COPYRIGHT').is_file()
    for name in game.FILES:
        if name.startswith('legacy/'):
            staged = root / 'base' / name
            original = placement['bundle'] / name
            assert staged.read_bytes() == original.read_bytes()
            assert staged.stat().st_ino != original.stat().st_ino
            assert subprocess.check_output(['sha256sum', str(staged)], text=True).split()[0] == (
                hashlib.sha256(original.read_bytes()).hexdigest())
    engine = root / 'base/legacy/qagame.mp.x86_64.so'
    assert engine.is_symlink() and engine.samefile(result['engine_library'])
    assert workspace.verify(root) == result
    assert game.verify(placement['bundle'])['activation_ready'] is False
    with pytest.raises(ValueError, match='NEW'):
        workspace.prepare(**placement)


@pytest.mark.parametrize('fault', ['executable-hash', 'asset-hash', 'asset-mode', 'asset-link',
                                 'missing-asset', 'extra-asset', 'socket', 'inside-bundle'])
def test_bad_approval_refuses_before_output(placement, fault):
    first = placement['assets']['etmain/pak0.pk3']
    if fault == 'executable-hash':
        placement['executable_sha256'] = '0' * 64
    elif fault == 'asset-hash':
        first['sha256'] = '0' * 64
    elif fault == 'asset-mode':
        Path(first['path']).chmod(0o666)
    elif fault == 'asset-link':
        link = Path(first['path']).with_suffix('.alias')
        link.symlink_to(first['path'])
        first['path'] = str(link)
    elif fault == 'missing-asset':
        del placement['assets']['etmain/pak0.pk3']
    elif fault == 'extra-asset':
        placement['assets']['etmain/extra.pk3'] = first
    elif fault == 'socket':
        placement['destination'] = placement['destination'].with_name('other')
    else:
        placement['destination'] = placement['bundle'] / 'nested'
    with pytest.raises(ValueError):
        workspace.prepare(**placement)
    assert not placement['destination'].exists()


@pytest.mark.parametrize('member', ['AUTOEXEC.cfg', 'etconfig_server.cfg', 'runtime_host_hooks.lua',
                                   'lualibs/socket/unix.so', '../outside', '/absolute'])
def test_rehashed_asset_cannot_shadow_runtime_or_startup(placement, member):
    spec = placement['assets']['legacy/legacy_v2.85.0.pk3']
    path = Path(spec['path'])
    with zipfile.ZipFile(path, 'a') as archive:
        archive.writestr(member, b'forbidden shadow')
    spec['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='shadow'):
        workspace.prepare(**placement)
    assert not placement['destination'].exists()


@pytest.mark.parametrize('same_bytes', [True, False])
def test_duplicate_archive_headers_require_identical_bytes(placement, same_bytes):
    spec = placement['assets']['legacy/legacy_v2.85.0.pk3']
    path = Path(spec['path'])
    with zipfile.ZipFile(path, 'a') as archive:
        archive.writestr('ui/version_generated.h', b'original')
        with pytest.warns(UserWarning, match='Duplicate name'):
            archive.writestr('ui/version_generated.h', b'original' if same_bytes else b'changed')
    spec['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    if same_bytes:
        assert workspace.prepare(**placement)['activation_ready'] is False
    else:
        with pytest.raises(ValueError, match='Ambiguous duplicate'):
            workspace.prepare(**placement)
        assert not placement['destination'].exists()


@pytest.mark.parametrize('damage', ['root-mode', 'directory-mode', 'config-bytes', 'lua-bytes',
    'asset-bytes', 'executable-bytes', 'link-target', 'extra-home', 'missing-dir', 'manifest'])
def test_prelaunch_verifier_refuses_drift_without_repair(placement, damage):
    workspace.prepare(**placement)
    root = placement['destination']
    if damage == 'root-mode':
        root.chmod(0o755)
    elif damage == 'directory-mode':
        (root / 'home/legacy/gamestats').chmod(0o777)
    elif damage == 'config-bytes':
        (root / 'home/legacy/autoexec.cfg').write_text('map supply\n')
    elif damage == 'lua-bytes':
        (root / 'base/legacy/c0rnp0rn8.lua').write_text('return {} -- changed\n')
    elif damage == 'asset-bytes':
        with Path(placement['assets']['etmain/pak0.pk3']['path']).open('ab') as stream:
            stream.write(b'drift')
    elif damage == 'executable-bytes':
        with placement['executable'].open('ab') as stream:
            stream.write(b'drift')
    elif damage == 'link-target':
        link = root / 'base/legacy/qagame.mp.x86_64.so'
        link.rename(root.parent / 'held-link')
        link.symlink_to(placement['executable'])
    elif damage == 'extra-home':
        (root / 'home/legacy/new-state').mkdir(mode=0o700)
    elif damage == 'missing-dir':
        (root / 'control').rename(root.parent / 'held-control')
    else:
        path = root / workspace.MARKER
        record = json.loads(path.read_bytes())
        record['activation_ready'] = True
        path.write_text(json.dumps(record, sort_keys=True, indent=2) + '\n')
    with pytest.raises((ValueError, FileNotFoundError)):
        workspace.verify(root)
    assert root.exists()  # No removal/repair even when this cannot be reused.


def test_cli_verifies_prepared_layout(placement):
    workspace.prepare(**placement)
    command = [sys.executable, str(Path(workspace.__file__)), 'verify',
               '--directory', str(placement['destination'])]
    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['activation_ready'] is False
    (placement['destination'] / 'home/legacy/autoexec.cfg').write_text('map supply\n')
    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert result.returncode == 1
    assert json.loads(result.stderr)['status'] == 'refused'


def test_cli_prepare_requires_protected_approval_input(placement):
    approval = placement['destination'].parent / 'assets.json'
    approval.write_text(json.dumps(placement['assets']))
    approval.chmod(0o664)
    command = [sys.executable, str(Path(workspace.__file__)), 'prepare',
               '--destination', str(placement['destination']), '--bundle', str(placement['bundle']),
               '--executable', str(placement['executable']),
               '--executable-sha256', placement['executable_sha256'], '--assets', str(approval)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert result.returncode == 1 and not placement['destination'].exists()
    approval.chmod(0o600)
    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['activation_ready'] is False
