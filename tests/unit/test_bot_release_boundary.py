"""Native marked release startup refusals before mutable state or bot imports."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def release(tmp_path):
    root = tmp_path / 'release'
    (root / 'shared').mkdir(parents=True)
    (root / 'bot').mkdir()
    (root / '.slomix-release.json').write_text('{}')
    for name in ('shared/runtime_environment.py', 'bot/ultimate_bot.py'):
        shutil.copyfile(ROOT / name, root / name)
    state = tmp_path / 'state'
    values = {key: str(state / key.lower()) for key in
              ('BOT_LOG_DIR', 'STATS_DIRECTORY', 'LOCAL_STATS_PATH', 'BACKUP_DIRECTORY')}
    values.update(POSTGRES_HOST='approved-host', GAMETIMES_ENABLED='false', PROXIMITY_ENABLED='false')
    return root, values, tmp_path / 'bot.env'


def run(release, *, inherited=None, code=None):
    root, values, config = release
    config.write_text(''.join(f'{key}={value}\n' for key, value in values.items()))
    config.chmod(0o600)
    env = {'PATH': '/usr/bin:/bin', 'SLOMIX_ENV_FILE': str(config), **(inherited or {})}
    code = code or '''
import json, os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from shared.runtime_environment import load_environment, validate_bot_state_paths
load_environment()
load_environment()
validate_bot_state_paths()
Path(os.environ['STATS_DIRECTORY']).mkdir(parents=True)
print(json.dumps({'host': os.environ['POSTGRES_HOST'], 'stats': os.environ['STATS_DIRECTORY']}))
'''
    return subprocess.run([sys.executable, '-I', '-B', '-c', code, str(root)],
                          cwd=root, env=env, text=True, capture_output=True, timeout=20)


def test_approved_configuration_reaches_external_write(release):
    result = run(release)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['host'] == 'approved-host'
    assert Path(release[1]['STATS_DIRECTORY']).is_dir()
    assert sorted(p.name for p in release[0].iterdir()) == ['.slomix-release.json', 'bot', 'shared']


@pytest.mark.parametrize('inherited', [{'POSTGRES_HOST': 'wrong-host'}, {'PGHOST': 'wrong-host'},
                                      {'STATS_DIRECTORY': '/wrong-stats'}])
def test_inherited_configuration_refused_before_write(release, inherited):
    result = run(release, inherited=inherited)
    assert result.returncode != 0
    assert 'Inherited environment overrides' in result.stderr
    assert 'wrong-host' not in result.stderr
    assert not Path(release[1]['STATS_DIRECTORY']).exists()


@pytest.mark.parametrize('name', ['STATS_DIRECTORY', 'LOCAL_STATS_PATH', 'BACKUP_DIRECTORY',
                                 'BOT_LOG_DIR', 'METRICS_DB_PATH', 'LOCAL_GAMETIMES_PATH',
                                 'PROXIMITY_LOCAL_PATH', 'MPLCONFIGDIR', 'XDG_CACHE_HOME'])
@pytest.mark.parametrize('damage', ['relative', 'payload', 'symlink'])
def test_mutable_paths_refused_before_write(release, name, damage):
    root, values, config = release
    if damage == 'relative':
        values[name] = 'relative-state'
    elif damage == 'payload':
        values[name] = str(root / 'state')
    else:
        link = config.parent / 'linked-state'
        link.symlink_to(root, target_is_directory=True)
        values[name] = str(link / 'state')
    result = run(release)
    assert result.returncode != 0
    assert 'canonical external mutable paths' in result.stderr
    assert not (root / 'state').exists()
    assert not (root / 'relative-state').exists()


@pytest.mark.parametrize('name,enabled', [('STATS_DIRECTORY', None), ('BOT_LOG_DIR', None),
                                         ('LOCAL_GAMETIMES_PATH', 'GAMETIMES_ENABLED'),
                                         ('PROXIMITY_LOCAL_PATH', 'PROXIMITY_ENABLED')])
def test_required_path_has_no_relative_fallback(release, name, enabled):
    release[1].pop(name, None)
    if enabled:
        release[1][enabled] = 'true'
    result = run(release)
    assert result.returncode != 0
    assert 'canonical external mutable paths' in result.stderr


def test_direct_marked_bot_requires_external_bootstrap(release):
    result = run(release, code='''
import runpy, sys
from pathlib import Path
runpy.run_path(str(Path(sys.argv[1]) / 'bot/ultimate_bot.py'), run_name='__main__')
''')
    assert result.returncode != 0
    assert 'requires verified external release bootstrap' in result.stderr
    assert not Path(release[1]['BOT_LOG_DIR']).exists()
