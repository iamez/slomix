"""Bounded traversal, round-robin progress and explicit per-item failure states."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from shared import runtime_proximity_batch as batch
from shared.runtime_proximity_admission import publish_proximity_admission
from shared.runtime_proximity_queue import ProximityQueueResult
from shared.runtime_source_reservation import reserve_source_generation
from tests.unit.test_runtime_proximity_admission import OPTIONS, SOURCE


def populate(root, numbers):
    root.chmod(0o700)
    for number in numbers:
        generation = f'{number:032x}'
        directory = reserve_source_generation(root, generation)
        publish_proximity_admission(directory, **(OPTIONS | dict(generation=generation)))


def test_selection_counts_all_names_and_rotates_without_starvation(tmp_path):
    populate(tmp_path, [5, 1, 4, 3, 2])
    (tmp_path / 'unrelated').write_text('not a generation')
    cursor = None
    visited = []
    for _ in range(3):
        result = batch.discover_proximity_batch(tmp_path, after=cursor, batch_size=2)
        assert (result.entries_seen, result.ignored_entries, result.total_generations) == (6, 1, 5)
        visited.extend(result.generations)
        cursor = result.next_cursor
    assert visited == [f'{n:032x}' for n in (1, 2, 3, 4, 5, 1)]
    assert len(set(visited)) == 5
    print('Discovery proof: 6 entries = 5 candidates +1 ignored; three batches '
          'visit 1,2 /3,4 /5,1 irrespective of creation order')


def test_missing_cursor_continues_at_successor_and_wraps(tmp_path):
    populate(tmp_path, [2, 4])
    assert batch.discover_proximity_batch(tmp_path, after=f'{3:032x}').generations == (f'{4:032x}', f'{2:032x}')
    assert batch.discover_proximity_batch(tmp_path, after='f' * 32).generations == (f'{2:032x}', f'{4:032x}')


@pytest.mark.parametrize('options', [dict(batch_size=True), dict(batch_size=0), dict(batch_size=33),
    dict(max_entries=0), dict(max_entries=4097), dict(max_entries=True), dict(after='../unsafe'), dict(after=0)])
def test_invalid_bounds_or_cursor_refused(tmp_path, options):
    with pytest.raises(ValueError):
        batch.discover_proximity_batch(tmp_path, **options)


def test_overflow_including_ignored_entries_never_returns_partial_batch(tmp_path):
    populate(tmp_path, [1])
    (tmp_path / 'ignored').write_text('counts against the cap')
    with pytest.raises(ValueError, match='exceeds entry cap'):
        batch.discover_proximity_batch(tmp_path, max_entries=1)


def test_empty_root_and_nonprivate_root_are_distinct(tmp_path):
    tmp_path.chmod(0o700)
    result = batch.discover_proximity_batch(tmp_path)
    assert result.generations == () and result.next_cursor is None and result.entries_seen == 0
    tmp_path.chmod(0o755)
    with pytest.raises(ValueError, match='0700'):
        batch.discover_proximity_batch(tmp_path)


async def run(root, **kwargs):
    return await batch.process_proximity_batch(root, source_id=SOURCE, now=1000,
        adapter=object(), observer=object(), gametimes_dir=root, **kwargs)


async def test_malformed_entry_does_not_block_next_item_or_follow_symlink(tmp_path, monkeypatch):
    populate(tmp_path, [2, 3])
    (tmp_path / f'{1:032x}').symlink_to(tmp_path / f'{2:032x}', target_is_directory=True)
    (tmp_path / f'{2:032x}' / '.proximity-admission.json').write_text('{')
    worker = AsyncMock(return_value=ProximityQueueResult('retry', 'missing_manifest'))
    monkeypatch.setattr(batch, 'process_proximity_once', worker)
    result = await run(tmp_path)
    assert [item.result.reason for item in result.items] == ['admission_unavailable', 'invalid_admission', 'missing_manifest']
    worker.assert_awaited_once()
    assert worker.call_args.args[0].name == f'{3:032x}'
    assert result.discovery.next_cursor == f'{3:032x}'


async def test_missing_admission_never_reaches_worker(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    reserve_source_generation(tmp_path, '0' * 32)
    worker = AsyncMock()
    monkeypatch.setattr(batch, 'process_proximity_once', worker)
    assert (await run(tmp_path)).items[0].result.reason == 'missing_admission'
    worker.assert_not_awaited()


async def test_invalid_queue_state_does_not_hide_other_work(tmp_path, monkeypatch):
    populate(tmp_path, [1, 2])
    worker = AsyncMock(side_effect=[ValueError('private malformed state'), ProximityQueueResult('retry', 'parent_missing')])
    monkeypatch.setattr(batch, 'process_proximity_once', worker)
    result = await run(tmp_path)
    assert [item.result.reason for item in result.items] == ['invalid_queue_state', 'parent_missing']


@pytest.mark.parametrize('error', [OSError('DB unavailable'), RuntimeError('connection broken'), asyncio.CancelledError()])
async def test_global_failure_propagates_without_advancing_to_next_item(tmp_path, monkeypatch, error):
    populate(tmp_path, [1, 2])
    worker = AsyncMock(side_effect=error)
    monkeypatch.setattr(batch, 'process_proximity_once', worker)
    with pytest.raises(type(error)):
        await run(tmp_path)
    assert worker.await_count == 1


async def test_overflow_before_any_worker_call(tmp_path, monkeypatch):
    populate(tmp_path, [1, 2])
    worker = AsyncMock()
    monkeypatch.setattr(batch, 'process_proximity_once', worker)
    with pytest.raises(ValueError, match='exceeds entry cap'):
        await run(tmp_path, max_entries=1)
    worker.assert_not_awaited()


async def test_later_items_use_elapsed_time_not_stale_batch_start(tmp_path, monkeypatch):
    populate(tmp_path, [1, 2])
    ticks = iter([50.0, 50.0, 140.0])
    monkeypatch.setattr(batch, 'monotonic', lambda: next(ticks))
    worker = AsyncMock(return_value=ProximityQueueResult('retry', 'parent_missing'))
    monkeypatch.setattr(batch, 'process_proximity_once', worker)
    await run(tmp_path)
    assert [call.kwargs['now'] for call in worker.await_args_list] == [1000, 1090]
