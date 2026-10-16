"""Exercise the actual canonical preflight/error path, with no application DB."""

import hashlib
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from bot.runtime_round_mapping import StatsRoundBinding
from postgresql_database_manager import PostgreSQLDatabaseManager
from shared.runtime_round_identity import RoundIdentity
from shared.runtime_sealed_snapshot import sealed_stats_snapshot

NAME = '2026-09-25-120000-supply-round-1.txt'
RAW = b'header\nverified player payload\n'
PAYLOAD_HASH = hashlib.sha256(b'verified player payload').hexdigest()


@pytest.fixture
def boundary(tmp_path, monkeypatch):
    """No pool; canonical manager may only invoke explicitly stubbed DB methods."""
    manager = PostgreSQLDatabaseManager(config=SimpleNamespace(database_type='postgresql'))
    manager.is_file_processed = AsyncMock(return_value=False)
    manager.find_processed_by_hash = AsyncMock(return_value=None)
    manager.mark_file_processed = AsyncMock()
    manager.parser.parse_stats_file = Mock(side_effect=AssertionError('mutable path parser used'))
    monkeypatch.setattr(Path, 'read_bytes', Mock(side_effect=AssertionError('mutable path hash used')))
    source = SimpleNamespace(read_bytes=Mock(return_value=RAW),
                             parse=Mock(return_value={'success': False, 'error': 'fixture invalid stats'}))
    return manager, tmp_path / NAME, source


@pytest.mark.asyncio
async def test_canonical_error_path_hashes_and_parses_explicit_source(boundary):
    """Actual process_file preserves logical marker identity and canonical payload hash."""
    manager, path, source = boundary
    success, message = await manager.process_file(path, input_source=source)
    assert not success and message == 'Parse error: fixture invalid stats'
    source.read_bytes.assert_called_once_with()
    source.parse.assert_called_once_with(manager.parser)
    manager.find_processed_by_hash.assert_awaited_once_with(PAYLOAD_HASH, filename=NAME)
    manager.mark_file_processed.assert_awaited_once_with(
        NAME, success=False, error_msg='fixture invalid stats', file_hash=PAYLOAD_HASH,
    )
    assert manager.pool is None
    print('Canonical boundary: injected bytes hashed; logical filename retained; parser error unchanged; no pool')


@pytest.mark.asyncio
async def test_duplicate_short_circuit_keeps_parser_unused(boundary):
    """Existing dedup semantics still stop before parsing the explicit source."""
    manager, path, source = boundary
    manager.find_processed_by_hash.return_value = 'existing-round.txt'
    success, message = await manager.process_file(path, input_source=source)
    assert success and message == 'Duplicate payload of existing-round.txt'
    source.parse.assert_not_called()
    manager.mark_file_processed.assert_awaited_once_with(
        NAME, success=True, error_msg='DUPLICATE_PAYLOAD_OF:existing-round.txt', file_hash=PAYLOAD_HASH,
    )


@pytest.mark.asyncio
async def test_default_path_still_uses_existing_parser(tmp_path):
    """Without opt-in, legacy callers follow the same file/parser contract."""
    manager = PostgreSQLDatabaseManager(config=SimpleNamespace(database_type='postgresql'))
    path = tmp_path / NAME
    path.write_bytes(RAW)
    manager.is_file_processed = AsyncMock(return_value=False)
    manager.find_processed_by_hash = AsyncMock(return_value=None)
    manager.mark_file_processed = AsyncMock()
    manager.parser.parse_stats_file = Mock(return_value={'success': False, 'error': 'fixture invalid stats'})
    await manager.process_file(path)
    manager.parser.parse_stats_file.assert_called_once_with(str(path))
    manager.find_processed_by_hash.assert_awaited_once_with(PAYLOAD_HASH, filename=NAME)


@pytest.mark.asyncio
@pytest.mark.parametrize('bound', [False, True])
async def test_explicit_hash_failure_is_retryable_before_database_preflight(boundary, bound):
    """Unlike legacy best-effort hashing, explicit input never proceeds without a hash."""
    manager, path, source = boundary
    source.read_bytes.side_effect = OSError('fixture closed snapshot')
    binding = StatsRoundBinding(
        RoundIdentity('fixture', 'a' * 32, 'b' * 32, 1, 'b' * 32),
        'c' * 32, NAME, len(RAW), hashlib.sha256(RAW).hexdigest(), 'supply',
    ) if bound else None
    result = await manager.process_file(path, input_source=source, runtime_binding=binding)
    assert result == (False, 'Explicit input could not be hashed') and result.retryable
    manager.is_file_processed.assert_not_awaited()
    manager.find_processed_by_hash.assert_not_awaited()
    manager.mark_file_processed.assert_not_awaited()
    source.parse.assert_not_called()


@pytest.mark.asyncio
async def test_real_sealed_bytes_reach_canonical_hash_and_parser(tmp_path):
    """Actual sealed FD and actual parser enter canonical error handling with no DB."""
    path = tmp_path / NAME
    path.write_bytes(RAW)
    manager = PostgreSQLDatabaseManager(config=SimpleNamespace(database_type='postgresql'))
    manager.is_file_processed = AsyncMock(return_value=False)
    manager.find_processed_by_hash = AsyncMock(return_value=None)
    manager.mark_file_processed = AsyncMock()
    with path.open('rb') as original, sealed_stats_snapshot(
        original.fileno(), expected_size=len(RAW), expected_sha256=hashlib.sha256(RAW).hexdigest(),
    ) as view:
        path.write_bytes(b'changed after sealing')
        source = SimpleNamespace(
            read_bytes=lambda: os.pread(view.fileno(), len(RAW), 0),
            parse=lambda parser: parser.parse_regular_stats_file(f'/proc/self/fd/{view.fileno()}'),
        )
        result = await manager.process_file(path, input_source=source)
    assert result == (False, 'Parse error: invalid header format')
    manager.find_processed_by_hash.assert_awaited_once_with(PAYLOAD_HASH, filename=NAME)
    assert manager.mark_file_processed.await_args.args == (NAME,)
    print('Sealed canonical proof: actual hash/parser read unchanged bytes; invalid header refused; no SQL')
