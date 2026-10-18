"""Readiness requires completion of this bot process's on_ready callback."""
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from scripts import dev_verify_health as health


@pytest.mark.parametrize('damage', [None, 'missing', 'pid', 'invocation', 'unit', 'message', 'stale', 'future', 'oversized'])
def test_bot_readiness_is_scoped_to_current_invocation(monkeypatch, damage):
    state = {'pid': 101, 'invocation_id': 'a' * 32}
    marker = '[RUNTIME-READY] pid=101 invocation=' + 'a' * 32
    row = {'_PID': '101', '_SYSTEMD_INVOCATION_ID': 'a' * 32,
           '_SYSTEMD_UNIT': 'etlegacy-bot.service', 'MESSAGE': 'INFO ' + marker,
           '__REALTIME_TIMESTAMP': '15000000'}
    field = {'pid': '_PID', 'invocation': '_SYSTEMD_INVOCATION_ID', 'unit': '_SYSTEMD_UNIT',
             'message': 'MESSAGE'}.get(damage)
    if field:
        row[field] = 'wrong'
    if damage in ('stale', 'future'):
        row['__REALTIME_TIMESTAMP'] = '1000000' if damage == 'stale' else '25000000'
    output = '' if damage == 'missing' else ('x' * 65537 if damage == 'oversized' else json.dumps(row))
    commands = []
    def journal(argv, **kwargs):
        commands.append(argv)
        return output
    monkeypatch.setattr(health.subprocess, 'check_output', journal)
    monkeypatch.setattr(health.time, 'time', lambda: 20)
    if damage:
        with pytest.raises(ValueError):
            health.bot_ready(state, 10)
    else:
        health.bot_ready(state, 10)
    assert '_SYSTEMD_INVOCATION_ID=' + 'a' * 32 in commands[0]
    assert '_PID=101' in commands[0]


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [None, 'security', 'voice'])
async def test_actual_on_ready_emits_only_after_startup_checks(monkeypatch, failure):
    from bot import ultimate_bot

    bot = SimpleNamespace(user=SimpleNamespace(id=123), config=SimpleNamespace(database_type='postgresql',
                          postgres_database='fixture', postgres_host='fixture'), commands=[], cogs={}, guilds=[],
                          monitoring_enabled=False, tree=SimpleNamespace(clear_commands=Mock(), sync=AsyncMock()),
                          _validate_webhook_security_config=AsyncMock(), close=AsyncMock(),
                          voice_session_service=SimpleNamespace(check_startup_voice_state=AsyncMock()))
    if failure == 'security':
        bot._validate_webhook_security_config.side_effect = RuntimeError('fixture security rejection')  # noqa: SLF001
    if failure == 'voice':
        bot.voice_session_service.check_startup_voice_state.side_effect = RuntimeError('fixture startup rejection')
    monkeypatch.setenv('INVOCATION_ID', 'a' * 32)
    logger = Mock()
    monkeypatch.setattr(ultimate_bot, 'logger', logger)
    if failure == 'voice':
        with pytest.raises(RuntimeError):
            await ultimate_bot.UltimateETLegacyBot.on_ready(bot)
    else:
        await ultimate_bot.UltimateETLegacyBot.on_ready(bot)
    signals = [call for call in logger.info.call_args_list if call.args[0].startswith('[RUNTIME-READY]')]
    assert len(signals) == (0 if failure else 1)
    if signals:
        assert signals[0].args == ('[RUNTIME-READY] pid=%s invocation=%s', os.getpid(), 'a' * 32)
