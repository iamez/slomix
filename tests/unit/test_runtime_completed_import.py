"""Real receipt/seal/parser composition with explicit stub or canonical preflight."""

import asyncio
import hashlib
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.community_stats_parser import C0RNP0RN3StatsParser
from bot.runtime_completed_import import CompletedRoundInput, MissingRoundOne, import_completed_round
from postgresql_database_manager import PostgreSQLDatabaseManager
from shared.runtime_completion_manifest import record_completion_once
from shared.runtime_source_reservation import reserve_source_generation
from shared.runtime_spool import publish_stats_file


@pytest.fixture
def inputs(tmp_path):
    """Two actual private generations with payloads and durable completion manifests."""
    tmp_path.chmod(0o700)
    result = []
    for number in (1, 2):
        generation = str(number) * 32
        name = f'2026-09-25-120000-supply-round-{number}.txt'
        raw = (f'x\\supply\\x\\{number}\\2\\1\\20:00\\10:00\n'
               '12345678\\^1Player\\1\\1\\1 1 1 1 1 1\n').encode()
        digest = hashlib.sha256(raw).hexdigest()
        directory = reserve_source_generation(tmp_path, generation)
        publish_stats_file(directory, name, [raw], expected_size=len(raw), expected_sha256=digest)
        record_completion_once(directory, {'version': 1, 'filename': name, 'bytes': len(raw),
                                           'state': 'writer_closed'}, expected_sha256=digest)
        result.append((CompletedRoundInput(tmp_path, generation, name, len(raw), digest), raw))
    return result


@pytest.mark.asyncio
@pytest.mark.parametrize('round_number', [1, 2])
async def test_inputs_survive_await_and_original_rewrite(inputs, round_number):
    """Awaiting does not close descriptors or cause a mutable-source reread."""
    current, raw = inputs[round_number - 1]
    retained = []
    async def process(path, *, input_source):
        retained.append(input_source)
        await asyncio.sleep(0)
        (current.root / current.generation / current.filename).write_bytes(b'changed')
        assert path.name == current.filename
        assert input_source.read_bytes() == input_source.read_bytes() == raw
        parsed = input_source.parse(None)
        assert parsed['success'] and parsed['round_num'] == round_number
        if round_number == 2:
            assert parsed['r1_filename'] == inputs[0][0].filename
            assert parsed['match_summary']['round_num'] == 0
        return (False, 'fixture result preserved')
    manager = SimpleNamespace(parser=C0RNP0RN3StatsParser(), process_file=process)
    before = set(os.listdir('/proc/self/fd'))
    result = await import_completed_round(manager, current, first=inputs[0][0] if round_number == 2 else None)
    assert result == (False, 'fixture result preserved')
    assert set(os.listdir('/proc/self/fd')) == before
    with pytest.raises(ValueError, match='closed'):
        retained[0].read_bytes()
    print(f'Completed R{round_number}: receipts -> sealed parse -> await; identity retained, descriptors closed')


@pytest.mark.asyncio
@pytest.mark.parametrize('round_number', [1, 2])
async def test_completed_input_reaches_canonical_duplicate_preflight(inputs, round_number):
    """Real receipt/parser/hash/importer composition; only DB methods are stubbed."""
    current, raw = inputs[round_number - 1]
    duplicate = f'existing-round-{round_number}.txt'
    manager = PostgreSQLDatabaseManager(config=SimpleNamespace(database_type='postgresql'))
    manager.is_file_processed = AsyncMock(return_value=False)
    manager.find_processed_by_hash = AsyncMock(return_value=duplicate)
    manager.mark_file_processed = AsyncMock()
    result = await import_completed_round(manager, current, first=inputs[0][0] if round_number == 2 else None)
    expected_hash = hashlib.sha256(b'\n'.join(raw.splitlines()[1:])).hexdigest()
    assert result == (True, f'Duplicate payload of {duplicate}')
    manager.find_processed_by_hash.assert_awaited_once_with(expected_hash, filename=current.filename)
    manager.mark_file_processed.assert_awaited_once_with(
        current.filename, success=True, error_msg=f'DUPLICATE_PAYLOAD_OF:{duplicate}',
        file_hash=expected_hash,
    )
    assert manager.pool is None
    print('Receipt -> sealed parser -> canonical payload hash and duplicate marker; SQL stubbed')


@pytest.mark.asyncio
async def test_missing_receipt_never_reaches_importer(inputs):
    """Correct payload bytes without a durable completion receipt are insufficient."""
    current, _ = inputs[0]
    receipt = current.root / current.generation / (current.filename + '.complete.json')
    receipt.rename(receipt.with_suffix('.held'))
    manager = SimpleNamespace(process_file=AsyncMock())
    before = set(os.listdir('/proc/self/fd'))
    with pytest.raises(ValueError, match='receipt/content'):
        await import_completed_round(manager, current)
    manager.process_file.assert_not_awaited()
    assert set(os.listdir('/proc/self/fd')) == before


@pytest.mark.asyncio
async def test_missing_r1_never_calls_manager(inputs):
    """An incomplete pair must remain retryable outside the canonical write path."""
    manager = SimpleNamespace(process_file=AsyncMock())
    with pytest.raises(MissingRoundOne):
        await import_completed_round(manager, inputs[1][0])
    manager.process_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancellation_closes_snapshots_and_keeps_sources(inputs):
    """Actual task cancellation closes ExitStack without deleting durable inputs."""
    current, _ = inputs[0]
    started = asyncio.Event()
    async def process(*args, **kwargs):
        started.set()
        await asyncio.Event().wait()
    manager = SimpleNamespace(parser=C0RNP0RN3StatsParser(), process_file=process)
    before = set(os.listdir('/proc/self/fd'))
    task = asyncio.create_task(import_completed_round(manager, current))
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert set(os.listdir('/proc/self/fd')) == before
    assert (current.root / current.generation / current.filename).exists()
    assert (current.root / current.generation / (current.filename + '.complete.json')).exists()
