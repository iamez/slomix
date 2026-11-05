"""Public bundle/profile admission using synthetic ELF; no actual engine launch."""
import hashlib
import json
import zipfile

import pytest

from scripts import prepare_runtime_game_bundle as game
from scripts import prepare_runtime_game_workspace as workspace
from tests.unit.test_runtime_game_bundle import inputs  # noqa: F401


def test_comp13_profile_survives_closed_bundle_verification(inputs, monkeypatch):  # noqa: F811
    # Exercise the profile with synthetic native bytes; actual snapshot proof is separate.
    monkeypatch.setattr(game, 'COMP13_ENGINE_SHA256', inputs['engine_sha256'])
    result = game.prepare(**inputs, engine_profile='et286-comp13')
    record = json.loads((inputs['destination'] / game.CONTRACT).read_text())
    assert record['kind'] == 'et286-comp13-runtime-lua'
    assert record['engine_profile'] == 'et286-comp13'
    assert result['activation_ready'] is False
    assert game.verify(inputs['destination']) == result


@pytest.mark.parametrize('profile,error', [('latest', 'Unknown explicit'),
                                          ('et286-comp13', 'pinned snapshot')])
def test_unknown_profile_and_wrong_snapshot_refuse_before_output(inputs, profile, error):  # noqa: F811
    with pytest.raises(ValueError, match=error):
        game.prepare(**inputs, engine_profile=profile)
    assert not inputs['destination'].exists()


def test_comp13_workspace_uses_its_explicit_mod_inventory(inputs, tmp_path, monkeypatch):  # noqa: F811
    target = tmp_path / 'layout'
    inputs['socket_path'] = str(target / 'control/m.sock')
    monkeypatch.setattr(game, 'COMP13_ENGINE_SHA256', inputs['engine_sha256'])
    game.prepare(**inputs, engine_profile='et286-comp13')
    executable = tmp_path / 'etlded'
    executable.write_bytes(b'synthetic executable, never launched')
    executable.chmod(0o700)
    digest = hashlib.sha256(executable.read_bytes()).hexdigest()
    monkeypatch.setattr(workspace, 'COMP13_EXECUTABLE_SHA256', digest)
    assets = {}
    for index, name in enumerate(sorted(workspace.COMP13_ASSETS)):
        path = tmp_path / f'asset{index}.pk3'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('maps/supply.bsp' if 'supply_sp' in name else 'fixture.dat', b'fixture')
        path.chmod(0o600)
        value = hashlib.sha256(path.read_bytes()).hexdigest()
        assets[name] = {'path': str(path), 'sha256': value}
        if name.startswith('legacy/'):
            monkeypatch.setattr(workspace, 'COMP13_MOD_SHA256', value)
    args = dict(bundle=inputs['destination'], destination=target, executable=executable,
                executable_sha256=digest, assets=assets)
    # Renaming an old/default inventory is not an upgrade.
    wrong = dict(assets)
    wrong['legacy/legacy_v2.85.0.pk3'] = wrong.pop('legacy/legacy_v2.86.0-13-g39c75a3.pk3')
    with pytest.raises(ValueError, match='five-asset'):
        workspace.prepare(**{**args, 'assets': wrong})
    result = workspace.prepare(**args)
    assert workspace.verify(target) == result
    assert (target / 'base/legacy/legacy_v2.86.0-13-g39c75a3.pk3').is_symlink()
    assert not (target / 'base/legacy/legacy_v2.85.0.pk3').exists()
