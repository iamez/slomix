"""Missing rows and incorrect totals must not claim validation success."""

from unittest.mock import AsyncMock

import pytest

from bot.runtime_import_validation import validate_import_totals
from postgresql_database_manager import PostgreSQLDatabaseManager


@pytest.mark.parametrize('field', [None, 'players', 'weapons', 'kills', 'deaths'])
async def test_each_total_is_checked(field):
    actual = dict(players=2, weapons=3, kills=7, deaths=5)
    if field:
        actual[field] = 0
    conn = AsyncMock()
    conn.fetchrow.return_value = actual
    ok, message = await validate_import_totals(conn, 42, 2, 3, 7, 5)
    assert ok is (field is None)
    if field:
        assert f'{field}: expected ' in message and 'stored 0' in message
    assert conn.fetchrow.await_args.args[1:] == (42,)


async def test_empty_expected_round_is_not_missing_data():
    conn = AsyncMock()
    conn.fetchrow.return_value = dict.fromkeys(('players', 'weapons', 'kills', 'deaths'), 0)
    assert await validate_import_totals(conn, 1, 0, 0, 0, 0) == (True, 'Import totals match')


async def test_canonical_validator_reports_query_failure():
    conn = AsyncMock()
    conn.fetchrow.side_effect = RuntimeError('fixture unavailable')
    manager = object.__new__(PostgreSQLDatabaseManager)
    assert await manager._validate_round_data(conn, 1, 1, 1, 1, 1, 'round-1.txt') == (  # noqa: SLF001
        False, 'Validation error: fixture unavailable',
    )


@pytest.mark.parametrize('negative', [False, True])
async def test_existing_negative_value_check_is_preserved(negative):
    conn = AsyncMock()
    conn.fetchrow.return_value = dict(players=1, weapons=1, kills=1, deaths=1)
    conn.fetch.return_value = [{'player_name': 'Fixture', 'kills': 1, 'deaths': 1}] if negative else []
    manager = object.__new__(PostgreSQLDatabaseManager)
    ok, message = await manager._validate_round_data(conn, 42, 1, 1, 1, 1, 'round-2.txt')  # noqa: SLF001
    assert ok is (not negative)
    assert ('Negative values' in message) is negative
    conn.fetch.assert_awaited_once()
