"""Importer startup is caller-owned; legacy setup is lazy and ordered."""

import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest

from shared import importer_startup


def test_neutral_import_and_constructor_in_fresh_process(tmp_path):
    """Run canonical validation/parsing with presentation and setup forbidden."""
    script = r'''
import importlib.abc
import logging
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import asyncpg

class BlockSetup(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'discord', 'dotenv', 'website'} or fullname in {
            'bot.config', 'bot.logging_config', 'shared.importer_startup',
        }:
            raise ModuleNotFoundError('Forbidden startup dependency: ' + fullname)
sys.meta_path.insert(0, BlockSetup())
def forbidden(*args, **kwargs):
    raise AssertionError('No database access during construction')
asyncpg.create_pool = forbidden
asyncpg.connect = forbidden
root = logging.getLogger()
before = (dict(os.environ), list(sys.path), os.getcwd(), tuple(root.handlers), root.level)
import postgresql_database_manager as module
manager = module.PostgreSQLDatabaseManager(config=SimpleNamespace(database_type='postgresql'))
assert before == (dict(os.environ), list(sys.path), os.getcwd(), tuple(root.handlers), root.level)
assert manager.pool is None
assert not Path(os.environ['BOT_LOG_DIR']).exists()
assert not Path('postgresql_manager.log').exists()
player, issues = manager.validate_player_stats({'kills':3, 'objective_stats':{'headshot_kills':5}})
assert player['objective_stats']['headshot_kills'] == 3 and issues
parsed = manager.parser.parse_player_line(chr(92).join(['a'*32, 'Fixture', '1', '1', '1 10 20 3 2 1']))
assert parsed['kills'] == 3
print('Neutral importer proof: parsed player, validated stats, no setup or connections')
'''
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, '-c', script], cwd=tmp_path,
        env={**os.environ, 'PYTHONPATH': str(root), 'BOT_LOG_DIR': str(tmp_path / 'logs')},
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Neutral importer proof:' in result.stdout


@pytest.mark.parametrize('failure', [None, PermissionError('fixture logging error')])
def test_legacy_setup_once_and_failure_propagates(monkeypatch, failure):
    """Only successful logging setup is memoized; configuration loads each call."""
    config_module = ModuleType('bot.config')
    config_module.load_config = Mock(return_value=object())
    logging_module = ModuleType('bot.logging_config')
    logging_module.setup_logging = Mock(side_effect=failure)
    monkeypatch.setitem(sys.modules, 'bot.config', config_module)
    monkeypatch.setitem(sys.modules, 'bot.logging_config', logging_module)
    monkeypatch.setattr(importer_startup, '_logging_initialized', False)
    if failure:
        with pytest.raises(PermissionError, match='fixture logging error'):
            importer_startup.load_legacy_config()
        config_module.load_config.assert_not_called()
        logging_module.setup_logging.side_effect = None
    assert importer_startup.load_legacy_config() is config_module.load_config.return_value
    assert importer_startup.load_legacy_config() is config_module.load_config.return_value
    assert logging_module.setup_logging.call_count == (2 if failure else 1)
    assert config_module.load_config.call_count == 2


@pytest.mark.parametrize('ambient_ssh', ['true', 'false'])
def test_legacy_dotenv_precedes_log_directory_selection(tmp_path, monkeypatch, ambient_ssh):
    """Real imports select the dotenv-provided log directory before setup."""
    monkeypatch.setenv('SSH_ENABLED', ambient_ssh)
    script = r'''
import os
import sys
from types import ModuleType
from pathlib import Path
import logging
events = []
dotenv = ModuleType('dotenv')
def load_dotenv(*args, **kwargs):
    events.append('dotenv')
    os.environ['BOT_LOG_DIR'] = str(Path.cwd() / 'chosen-logs')
dotenv.load_dotenv = load_dotenv
sys.modules['dotenv'] = dotenv
from shared.importer_startup import load_legacy_config
config = load_legacy_config()
assert config.ssh_enabled is False and config.automation_enabled is False
handlers = tuple(logging.getLogger().handlers)
load_legacy_config()
assert tuple(logging.getLogger().handlers) == handlers
assert events == ['dotenv']
from bot.logging_config import LOGS_DIR
assert LOGS_DIR == Path.cwd() / 'chosen-logs'
assert (LOGS_DIR / 'bot.log').is_file()
print('Legacy startup proof: dotenv before file logging, handlers stable')
'''
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, '-c', script], cwd=tmp_path,
        env={**os.environ, 'PYTHONPATH': str(root), 'BOT_ENVIRONMENT': 'dev',
             'SSH_ENABLED': 'false', 'AUTOMATION_ENABLED': 'false'},
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Legacy startup proof:' in result.stdout
