"""Explicit importer policy fails before IO and preserves legacy defaults."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from postgresql_database_manager import PostgreSQLDatabaseManager


@pytest.mark.parametrize('value', [None, 0, 1, 'true', [], object()])
def test_policy_requires_bool(value):
    with pytest.raises(ValueError, match='boolean team ownership'):
        PostgreSQLDatabaseManager(config=SimpleNamespace(database_type='postgresql'), defer_team_assignment=value)


def test_default_is_legacy():
    manager = PostgreSQLDatabaseManager(config=SimpleNamespace(database_type='postgresql'))
    assert manager.defer_team_assignment is False


@pytest.mark.parametrize('source,journal', [(None, True), (object(), False), (object(), 1)])
async def test_deferred_invalid_lane_fails_before_io(source, journal):
    manager = PostgreSQLDatabaseManager(config=SimpleNamespace(database_type='postgresql'), defer_team_assignment=True)
    manager.event_stream_enabled = journal
    hasher = Mock(side_effect=AssertionError('must not hash'))
    manager._compute_file_hashes = hasher  # noqa: SLF001 -- prove pre-IO rejection.
    with pytest.raises(ValueError, match='explicit input and enabled journal'):
        await manager.process_file(Path('not-read-round-1.txt'), input_source=source)
    hasher.assert_not_called()
    assert manager.pool is None
