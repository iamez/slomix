"""Versioned packaging and actual wrapper -> Lua/socket/supervisor capture.

Synthetic ET bindings and ELF packaging inputs; no actual game is executed.
"""
import hashlib
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from scripts import prepare_runtime_game_bundle as game
from scripts import prepare_runtime_game_workspace as workspace
from scripts import runtime_game_supervisor as supervisor
from shared.release_manifest import MANIFEST
from tests.unit.test_runtime_game_bundle import inputs  # noqa: F401
from tests.unit.test_spa_artifact_preflight import git

ROOT = Path(__file__).resolve().parents[2]


def commit_whole_producers(options):
    source = options['source']
    names = [f'vps_scripts/{name}.lua' for name in game.TIMING_MODULES]
    for name in names:
        (source / name).write_bytes((ROOT / name).read_bytes())
    git(source, 'add', '--', *names)
    git(source, 'commit', '-m', 'fixture whole timing producers')
    options['revision'] = git(source, 'rev-parse', 'HEAD')


@pytest.fixture
def timed_placement(inputs, tmp_path):  # noqa: F811
    commit_whole_producers(inputs)
    target = tmp_path / 'w'
    inputs.update(socket_path=str(target / 'control/m.sock'),
        producer_spool=str(target / 'home/legacy/gamestats/runtime-snapshots'),
        timing_sockets={str(half): str(target / f'control/t{half}.sock') for half in (1, 2)})
    game.prepare(**inputs)
    executable = Path(shutil.which('lua5.4')).resolve()
    assets = {}
    for index, name in enumerate(sorted(workspace.ASSETS)):
        path = tmp_path / f'a{index}.pk3'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('maps/supply.bsp' if 'supply_sp' in name else 'fixture.dat', b'fixture')
        path.chmod(0o600)
        assets[name] = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    return dict(destination=target, bundle=inputs['destination'], executable=executable,
        executable_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(), assets=assets)


def test_timing_profile_has_exact_inventory_and_private_layout(timed_placement):
    result = workspace.prepare(**timed_placement)
    assert result['version'] == 2 and len(result['roots']) == 5
    assert Path(result['roots']['timing_capture_root']).stat().st_mode & 0o777 == 0o700
    contract = json.loads((timed_placement['bundle'] / game.CONTRACT).read_bytes())
    assert contract['version'] == 2 and contract['kind'] == 'et285-runtime-lua-timing'
    assert set(json.loads((timed_placement['bundle'] / MANIFEST).read_bytes())['files']) == game.required_files(contract)
    assert len(game.required_files(contract)) == len(game.FILES) + 5
    config = Path(result['fs_homepath']) / 'legacy/luascripts/stats_discord_webhook_config.lua'
    assert config.read_bytes() == workspace.TIMING_CONFIG
    assert workspace.verify(timed_placement['destination']) == result
    for name in game.required_files(contract):
        path = timed_placement['bundle'] / name
        assert subprocess.check_output(['sha256sum', str(path)], text=True).split()[0] == hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize('fault', ['shared', 'missing', 'spool', 'extra'])
def test_timing_options_refused_before_output(inputs, fault):  # noqa: F811
    commit_whole_producers(inputs)
    inputs.update(producer_spool='/private/spool', timing_sockets={'1': '/private/t1', '2': '/private/t2'})
    if fault == 'shared':
        inputs['timing_sockets']['1'] = inputs['socket_path']
    elif fault == 'missing':
        del inputs['timing_sockets']['2']
    elif fault == 'spool':
        inputs['producer_spool'] = '/private/../spool'
    else:
        inputs['timing_sockets']['3'] = '/private/t3'
    with pytest.raises(ValueError):
        game.prepare(**inputs)
    assert not inputs['destination'].exists()


def test_workspace_refuses_timing_spool_outside_its_declared_root(timed_placement):
    root = timed_placement['bundle']
    contract = json.loads((root / game.CONTRACT).read_bytes())
    contract['producer_spool'] = '/private/wrong-spool'
    (root / game.CONTRACT).write_text(json.dumps(contract, sort_keys=True, indent=2) + '\n')
    (root / game.ENTRY).write_bytes(game.wrapper(contract))
    manifest = json.loads((root / MANIFEST).read_bytes())
    for name in (game.CONTRACT, game.ENTRY):
        manifest['files'][name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    (root / MANIFEST).write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
    assert game.verify(root)['activation_ready'] is False
    with pytest.raises(ValueError, match='exact workspace spool'):
        workspace.prepare(**timed_placement)
    assert not timed_placement['destination'].exists()


@pytest.mark.parametrize('fault', ['missing-module', 'extra-module', 'profile'])
def test_rehashed_timing_bundle_cannot_change_inventory(timed_placement, fault):
    root = timed_placement['bundle']
    manifest = json.loads((root / MANIFEST).read_bytes())
    if fault == 'missing-module':
        name = 'legacy/runtime_gametime_binding.lua'
        (root / name).rename(root.parent / 'retained-binding.lua')
        del manifest['files'][name]
    elif fault == 'extra-module':
        name = 'legacy/extra.lua'
        (root / name).write_bytes(b'return {}\n')
        (root / name).chmod(0o600)
        manifest['files'][name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    else:
        contract = json.loads((root / game.CONTRACT).read_bytes())
        contract['version'] = 1
        (root / game.CONTRACT).write_text(json.dumps(contract, sort_keys=True, indent=2) + '\n')
        manifest['files'][game.CONTRACT] = hashlib.sha256((root / game.CONTRACT).read_bytes()).hexdigest()
    (root / MANIFEST).write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
    with pytest.raises(ValueError):
        game.verify(root)


def capture_packaged_pair(timed_placement, monkeypatch, missing_timing=False, with_players=False):
    record = workspace.prepare(**timed_placement)
    if missing_timing:
        from shared import runtime_timing_listener
        listen = runtime_timing_listener.serve_timing_match

        def short_wait(*args, **kwargs):
            assert kwargs['timing_wait'] == 30
            kwargs['timing_wait'] = 0.05
            return listen(*args, **kwargs)

        monkeypatch.setattr(runtime_timing_listener, 'serve_timing_match', short_wait)
    command = [record['executable'], str(ROOT / 'tests/lua/runtime_combined_source_harness.lua'),
        str(ROOT), record['roots']['producer_spool'], 'supervisor', record['socket_path'],
        record['timing_socket_paths']['1'], record['timing_socket_paths']['2'],
        record['source_id'], 'c' * 32, 'b' * 32, 'd' * 32,
        str(timed_placement['bundle'] / game.ENTRY),
        str(timed_placement['bundle'] / 'legacy'), record['fs_homepath'],
        'missing-first-timing' if missing_timing else 'none', 'with-players' if with_players else 'none']
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, umask=0o077) as peer:
        try:
            assert peer.stdout.readline().strip() == 'READY'
            os.set_blocking(peer.stdin.fileno(), False)
            result = supervisor.capture_process(record, peer.pid, peer.stdin.fileno())
            assert result.timing_status == {1: 'pending' if missing_timing else 'captured', 2: 'captured'}
            result.stats.verify()
            if missing_timing:
                assert result.timing_match is None
                assert len(list(Path(record['roots']['producer_spool']).glob('*/*.json'))) == 2
            else:
                assert result.timing_match is not None
                result.timing_match.verify()
                for item in result.timing_match.timings:
                    data = json.loads((item.root / item.generation / item.filename).read_bytes())
                    assert data['meta']['runtime_identity'] == item.identity.encode()
            peer.stdin.write('done\n')
            peer.stdin.flush()
        finally:
            stdout, stderr = peer.communicate(timeout=10)
            assert peer.returncode == 0, stdout + stderr
    assert 'half 1 closed' in stdout and 'half 2 closed' in stdout
    print('GENERATED TIMING WRAPPER: whole packaged Lua, real peer credentials, actual supervisor, '
          f'both stats halves captured; missing first timing={missing_timing}')
    return result


@pytest.mark.parametrize('missing_timing', [False, True])
def test_generated_wrapper_runs_both_halves_through_actual_supervisor_capture(timed_placement, monkeypatch, missing_timing):
    capture_packaged_pair(timed_placement, monkeypatch, missing_timing)


def test_packaged_player_observations_are_accepted_by_actual_parser(timed_placement, monkeypatch):
    from bot.community_stats_parser import C0RNP0RN3StatsParser
    result = capture_packaged_pair(timed_placement, monkeypatch, with_players=True)
    for stats in (result.stats.first, result.stats.second):
        ref = stats.reference
        parsed = C0RNP0RN3StatsParser().parse_regular_stats_file(str(stats.root / ref.generation / ref.filename))
        assert len(parsed['players']) == 1
