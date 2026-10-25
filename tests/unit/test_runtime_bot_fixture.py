"""Private bot artifact preparation without native loading or game startup."""

import hashlib
import json
import shlex

import pytest

from scripts import prepare_runtime_bot_fixture as module
from scripts import runtime_game_startup as startup


@pytest.fixture
def inputs(tmp_path):
    tmp_path.chmod(0o700)
    source = tmp_path / 'source'
    source.mkdir()
    for name in (*module.FIXED, 'global_scripts/base.gm', 'et/scripts/et_autoexec.gm',
                 'et/user/old.cfg', 'et/logs/private.log'):
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'fixture bytes')
        path.chmod(0o600)
    return source, tmp_path / 'copy', hashlib.sha256(b'fixture bytes').hexdigest()


def test_copy_is_separate_and_omits_old_state(inputs):
    source, destination, digest = inputs
    record = module.prepare(*inputs)
    assert record['activation_ready'] is False
    assert (destination / 'et/user/omni-bot.cfg').read_bytes() == module.PROFILE
    assert b'BotsPerHuman = 0' in module.PROFILE
    assert b'SaveConfigChanges = 0' in module.PROFILE
    assert not (destination / 'et/user/old.cfg').exists()
    assert list((destination / 'et/logs').iterdir()) == []
    assert (source / 'et/logs/private.log').read_bytes() == b'fixture bytes'
    for name, info in record['files'].items():
        path = destination / name
        assert path.stat().st_mode & 0o777 == 0o600
        assert hashlib.sha256(path.read_bytes()).hexdigest() == info['sha256']
    assert json.loads((destination / 'fixture.json').read_text()) == record
    pin = hashlib.sha256((destination / 'fixture.json').read_bytes()).hexdigest()
    assert module.verify(destination, pin) == record
    with pytest.raises(ValueError, match='NEW'):
        module.prepare(source, destination, digest)


@pytest.mark.parametrize('fault', ['hash', 'symlink', 'mode', 'missing'])
def test_bad_source_refuses_before_copy(inputs, fault):
    source, destination, digest = inputs
    if fault == 'hash':
        digest = '0' * 64
    elif fault == 'symlink':
        (source / 'global_scripts/link.gm').symlink_to(source / 'README.txt')
    elif fault == 'mode':
        (source / 'README.txt').chmod(0o666)
    else:
        (source / 'et/nav/supply.way').rename(source / 'retained.way')
    expected = {'hash': 'hash disagrees', 'symlink': 'Linked distribution',
                'mode': 'not group/world writable', 'missing': 'No such file'}[fault]
    with pytest.raises((ValueError, OSError), match=expected):
        module.prepare(source, destination, digest)
    assert not destination.exists()


@pytest.mark.parametrize('fault', ['payload', 'extra', 'pin', 'symlink', 'mode'])
def test_verify_rejects_drift(inputs, fault):
    _, directory, _ = inputs
    module.prepare(*inputs)
    pin = hashlib.sha256((directory / 'fixture.json').read_bytes()).hexdigest()
    if fault == 'payload':
        (directory / 'README.txt').write_bytes(b'changed')
    elif fault == 'extra':
        (directory / 'et/logs/old.log').write_bytes(b'old')
        (directory / 'et/logs/old.log').chmod(0o600)
    elif fault == 'pin':
        pin = '0' * 64
    elif fault == 'symlink':
        (directory / 'et/logs/link').symlink_to(directory / 'README.txt')
    else:
        (directory / 'et/logs').chmod(0o777)
    with pytest.raises(ValueError, match={'payload': 'payload drift', 'extra': 'inventory drift',
                                        'pin': 'pin disagrees', 'symlink': 'private and unlinked',
                                        'mode': 'private and unlinked'}[fault]):
        module.verify(directory, pin)


def test_verified_fixture_reaches_startup_settings(inputs, monkeypatch):
    source, directory, _ = inputs
    module.prepare(*inputs)
    pin = hashlib.sha256((directory / 'fixture.json').read_bytes()).hexdigest()
    record = {'executable': '/bin/false', 'fs_homepath': str(source), 'fs_basepath': str(source)}
    monkeypatch.setattr(startup, 'verify', lambda p: record)
    result = startup.startup_recipe(source, bot_fixture=directory, bot_manifest_sha256=pin)
    assert result['activation_ready'] is False
    assert result['settings']['omnibot_enable'] == '1'
    assert result['settings']['omnibot_path'] == str(directory)
    assert result['settings']['g_warmup'] == '10'
    assert result['settings']['g_doWarmup'] == '0'
    assert result['settings']['g_customConfig'] == ''
    wire = shlex.split(' '.join(result['argv'][1:]))
    assert {wire[i+1]: wire[i+2] for i in range(0, len(wire), 3)} == result['settings']
    with pytest.raises(ValueError, match='together'):
        startup.startup_recipe(source, bot_fixture=directory)
    with pytest.raises(ValueError, match='pin disagrees'):
        startup.startup_recipe(source, bot_fixture=directory, bot_manifest_sha256='0' * 64)
