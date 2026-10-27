"""Importer startup is caller-owned; legacy setup is lazy and ordered."""

import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest

from shared import importer_startup


@pytest.mark.parametrize('round_number', [1, 2])
def test_neutral_import_and_constructor_in_fresh_process(tmp_path, round_number):
    """Run canonical validation/parsing with presentation and setup forbidden."""
    script = r'''
import importlib.abc
import logging
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import asyncpg
import asyncio
import hashlib
from unittest.mock import AsyncMock

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
player, issues = manager.validate_player_stats({'kills':0, 'objective_stats':{'team_kills':3}})
assert player == {'kills':0, 'objective_stats':{'team_kills':3}} and not issues
player, issues = manager.validate_player_stats({
    'kills':-5, 'objective_stats':{'team_kills':7, 'headshot_kills':2},
})
assert player == {'kills':0, 'objective_stats':{'team_kills':7, 'headshot_kills':0}}
assert 'kills (-5) is negative' in issues
print('Counter proof: kills=0, team_kills=3 retained; negative base normalized before headshot cap')
parsed = manager.parser.parse_player_line(chr(92).join(['a'*32, 'Fixture', '1', '1', '1 10 20 3 2 1']))
assert parsed['kills'] == 3
from bot.runtime_completed_import import CompletedRoundInput, import_completed_round
from bot.runtime_import_session import open_import_session
from shared.runtime_completion_manifest import record_completion_once
from shared.runtime_source_reservation import reserve_source_generation
from shared.runtime_spool import publish_stats_file

spool = Path.cwd() / 'spool'
spool.mkdir(mode=0o700)
inputs = []
for number in (1, 2):
    name = f'2026-09-25-120000-supply-round-{number}.txt'
    raw = (f'x\\supply\\x\\{number}\\2\\1\\20:00\\10:00\n'
           f'12345678\\Player\\1\\1\\1 {number} {number} {number} {number} {number}\n').encode()
    digest = hashlib.sha256(raw).hexdigest()
    generation = str(number) * 32
    directory = reserve_source_generation(spool, generation)
    publish_stats_file(directory, name, [raw], expected_size=len(raw), expected_sha256=digest)
    record_completion_once(directory, {
        'version': 1, 'filename': name, 'bytes': len(raw), 'state': 'writer_closed',
    }, expected_sha256=digest)
    inputs.append(CompletedRoundInput(spool, generation, name, len(raw), digest))
number = int(sys.argv[1])
class OwnedPool:
    closed = 0
    async def close(self):
        self.closed += 1
    def terminate(self):
        raise AssertionError('Normal session must close gracefully')
owned = OwnedPool()
async def factory():
    return owned
async def run():
    async with open_import_session(
        SimpleNamespace(database_type='postgresql'), pool_factory=factory, journal_enabled=True,
    ) as session_manager:
        session_manager.is_file_processed = AsyncMock(return_value=True)
        result = await import_completed_round(
            session_manager, inputs[number - 1], first=inputs[0] if number == 2 else None,
        )
        assert result == (True, 'Already processed')
        session_manager.is_file_processed.assert_awaited_once_with(inputs[number - 1].filename)
        assert session_manager.pool is owned and owned.closed == 0
    assert session_manager.pool is None and owned.closed == 1
asyncio.run(run())
assert manager.pool is None
assert before == (dict(os.environ), list(sys.path), os.getcwd(), tuple(root.handlers), root.level)
assert not Path(os.environ['BOT_LOG_DIR']).exists()
assert not Path('postgresql_manager.log').exists()
assert 'discord' not in sys.modules and 'bot.config' not in sys.modules
print(f'Neutral importer proof: R{number} owned session/receipt/seal/parser/preflight; DB stubbed, pool closed')
'''
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, '-c', script, str(round_number)], cwd=tmp_path,
        env={**os.environ, 'PYTHONPATH': str(root), 'BOT_LOG_DIR': str(tmp_path / 'logs')},
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Neutral importer proof:' in result.stdout
    assert 'Counter proof:' in result.stdout
    print(result.stdout, end='')


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
