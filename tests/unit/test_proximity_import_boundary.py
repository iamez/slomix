"""The runtime boundary owns neither Discord, connections nor acknowledgments."""

import os
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from shared import proximity_import


@pytest.mark.parametrize('day', [None, '2026-10-03', datetime(2026, 10, 3, tzinfo=timezone.utc)])
async def test_session_identity_must_be_explicit(day, tmp_path):
    with pytest.raises(TypeError, match='explicitly resolved'):
        await proximity_import.import_proximity_file(
            tmp_path / 'file', adapter=None, session_date=day, gametimes_dir=tmp_path,
        )


@pytest.mark.parametrize('adapter', [None, object(), SimpleNamespace(transaction=None)])
async def test_nontransactional_adapter_is_rejected_before_parser(adapter, tmp_path, monkeypatch):
    factory = Mock()
    monkeypatch.setattr(proximity_import, 'ProximityParserV4', factory)
    with pytest.raises(TypeError, match='transaction-capable'):
        await proximity_import.import_proximity_file(
            tmp_path / 'file', adapter=adapter, session_date=date(2026, 10, 3), gametimes_dir=tmp_path,
        )
    factory.assert_not_called()


@pytest.mark.parametrize('success', [True, False])
async def test_explicit_dependencies_and_failure_result(success, tmp_path, monkeypatch):
    source = tmp_path / 'fixture.txt'
    source.write_text('fixture')
    parser = SimpleNamespace(import_file=AsyncMock(return_value=success),
                             get_stats=Mock(return_value={'total_tracks': 2}))
    factory = Mock(return_value=parser)
    monkeypatch.setattr(proximity_import, 'ProximityParserV4', factory)
    adapter = SimpleNamespace(transaction=Mock())
    day = date(2026, 10, 3)
    result = await proximity_import.import_proximity_file(
        source, adapter=adapter, session_date=day, gametimes_dir=tmp_path / 'times',
    )
    factory.assert_called_once_with(db_adapter=adapter, output_dir=str(tmp_path),
                                    gametimes_dir=str(tmp_path / 'times'))
    parser.import_file.assert_awaited_once_with(str(source), day)
    assert result.success is success
    assert result.parsed_stats == ({'total_tracks': 2} if success else None)
    assert parser.get_stats.call_count == int(success)
    assert list(tmp_path.iterdir()) == [source]


def test_real_parser_boundary_imports_without_presentation_or_setup(tmp_path):
    script = '''
import importlib.abc
import sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'discord', 'dotenv', 'website'} or fullname in {'bot.config', 'bot.logging_config'}:
            raise AssertionError('Forbidden startup import: ' + fullname)
sys.meta_path.insert(0, Guard())
from shared.proximity_import import ProximityParserV4
parser = ProximityParserV4(db_adapter=None, gametimes_dir='not-used')
assert parser.parse_file('missing-fixture.txt') is False
print('Real parser loaded without Discord/config; missing source rejected')
'''
    result = subprocess.run([sys.executable, '-c', script], cwd=tmp_path,
        env={**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[2])},
        capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'missing source rejected' in result.stdout
    assert not list(tmp_path.iterdir())
