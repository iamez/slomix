"""The runtime boundary owns neither Discord, connections nor acknowledgments."""
# ruff: noqa: SLF001 -- exercise the private strict-parent guard directly

import hashlib
import os
import subprocess
import sys
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from shared import proximity_import


@pytest.mark.parametrize(('metadata', 'rows', 'reason'), [
    ({'round_start_is_fallback': True}, [(10, 20)], 'source_identity_unavailable'),
    ({'round_start_unix': True}, [(10, 20)], 'source_identity_unavailable'),
    ({'round_start_unix': 1}, [(10, 20)], 'source_identity_unavailable'),
    ({'round_start_unix': 999999999999}, [(10, 20)], 'source_identity_unavailable'),
    ({'round_num': 0}, [(10, 20)], 'source_identity_unavailable'),
    ({'round_num': True}, [(10, 20)], 'source_identity_unavailable'),
    ({'map_name': ''}, [(10, 20)], 'source_identity_unavailable'),
    ({}, [], 'parent_missing'),
    ({}, [(10, 20), (11, 20)], 'parent_ambiguous'),
    ({}, [(10, None)], 'session_missing'),
])
async def test_strict_parent_does_not_guess(metadata, rows, reason):
    source = {'map_name': 'fixture', 'round_num': 1, 'round_start_unix': 1789794600}
    source.update(metadata)
    adapter = SimpleNamespace(fetch_all=AsyncMock(return_value=rows))
    with pytest.raises(proximity_import._ParentPending, match=reason):
        await proximity_import._linked_parent(adapter, source)
    if reason == 'source_identity_unavailable':
        adapter.fetch_all.assert_not_awaited()
    else:
        query, params = adapter.fetch_all.call_args.args
        assert params == ('fixture', 1, 1789794600)
        assert 'LIMIT 2 FOR SHARE' in query
        assert '$' not in query


async def test_strict_parent_database_failure_is_not_missing_data():
    adapter = SimpleNamespace(fetch_all=AsyncMock(side_effect=RuntimeError('database unavailable')))
    with pytest.raises(RuntimeError, match='database unavailable'):
        await proximity_import._linked_parent(adapter, {
            'map_name': 'fixture', 'round_num': 2, 'round_start_unix': 1789794600,
        })


@pytest.mark.parametrize('flag', ['false', 'true', 0, 1, None])
async def test_strict_parent_policy_requires_actual_boolean(flag, tmp_path):
    with pytest.raises(TypeError, match='must be a boolean'):
        await proximity_import.import_proximity_file(
            tmp_path / 'missing', adapter=None, session_date=date(2026, 10, 4),
            gametimes_dir=tmp_path, expected_size=1, expected_sha256='a' * 64,
            require_linked_parent=flag,
        )


@pytest.mark.parametrize('day', [None, '2026-10-03', datetime(2026, 10, 3, tzinfo=timezone.utc)])
async def test_session_identity_must_be_explicit(day, tmp_path):
    with pytest.raises(TypeError, match='explicitly resolved'):
        await proximity_import.import_proximity_file(
            tmp_path / 'file', adapter=None, session_date=day, gametimes_dir=tmp_path,
            expected_size=1, expected_sha256='a' * 64,
        )


@pytest.mark.parametrize('adapter', [None, object(), SimpleNamespace(transaction=None)])
async def test_nontransactional_adapter_is_rejected_before_parser(adapter, tmp_path, monkeypatch):
    factory = Mock()
    monkeypatch.setattr(proximity_import, 'ProximityParserV4', factory)
    with pytest.raises(TypeError, match='transaction-capable'):
        await proximity_import.import_proximity_file(
            tmp_path / 'file', adapter=adapter, session_date=date(2026, 10, 3), gametimes_dir=tmp_path,
            expected_size=1, expected_sha256='a' * 64,
        )
    factory.assert_not_called()


@pytest.mark.parametrize('success', [True, False])
async def test_explicit_dependencies_and_failure_result(success, tmp_path, monkeypatch):
    source = tmp_path / '2026-10-04-120000-fixture-round-1_engagements.txt'
    source.write_text('fixture')
    source.chmod(0o600)
    parser = SimpleNamespace(import_file=AsyncMock(return_value=success),
                             get_stats=Mock(return_value={'total_tracks': 2}))
    factory = Mock(return_value=parser)
    monkeypatch.setattr(proximity_import, 'ProximityParserV4', factory)
    rollbacks = []
    @asynccontextmanager
    async def transaction():
        try:
            yield
        except Exception:
            rollbacks.append(True)
            raise
    adapter = SimpleNamespace(transaction=transaction, execute=AsyncMock(),
                              fetch_one=AsyncMock(return_value=(hashlib.sha256(b'fixture').hexdigest(),)))
    day = date(2026, 10, 3)
    result = await proximity_import.import_proximity_file(
        source, adapter=adapter, session_date=day, gametimes_dir=tmp_path / 'times',
        expected_size=7, expected_sha256=hashlib.sha256(b'fixture').hexdigest(),
    )
    factory.assert_called_once_with(db_adapter=adapter, output_dir=str(tmp_path),
                                    gametimes_dir=str(tmp_path / 'times'))
    parser.import_file.assert_awaited_once_with(str(source), day, source_bytes=b'fixture')
    assert rollbacks == ([] if success else [True])
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
