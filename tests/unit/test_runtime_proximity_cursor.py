"""Real local checkpoint/restart/locking proof without application DB access."""

import asyncio
import json
import os
import subprocess
import sys
from unittest.mock import AsyncMock

import pytest

from shared import runtime_proximity_cursor as cursor
from shared.runtime_proximity_batch import ProximityBatchResult, ProximityDiscovery

CURSOR_FILE = '.proximity-cursor.json'


def root_with_generations(tmp_path):
    tmp_path.chmod(0o700)
    for number in (3, 1, 2):
        (tmp_path / f'{number:032x}').mkdir(mode=0o700)
    return tmp_path


async def run(root, **kwargs):
    return await cursor.process_proximity_checkpointed_batch(
        root, source_id='fixture', now=1000, adapter=None, observer=None,
        gametimes_dir=root, batch_size=1, **kwargs,
    )


@pytest.mark.asyncio
async def test_resume_in_fresh_process_and_wrap(tmp_path):
    root = root_with_generations(tmp_path)
    first = await run(root)
    assert first.discovery.generations == (f'{1:032x}',)
    assert first.items[0].result.reason == 'missing_admission'
    program = '''
import asyncio, json, sys
from pathlib import Path
from shared.runtime_proximity_cursor import process_proximity_checkpointed_batch
root = Path(sys.argv[1])
result = asyncio.run(process_proximity_checkpointed_batch(
    root, source_id='fixture', now=1001, adapter=None, observer=None,
    gametimes_dir=root, batch_size=1))
print(json.dumps(result.discovery.generations))
'''
    child = subprocess.run([sys.executable, '-c', program, str(root)],
                           check=True, capture_output=True, text=True, timeout=10)
    assert json.loads(child.stdout) == [f'{2:032x}']
    assert json.loads((root / CURSOR_FILE).read_text())['after'] == f'{2:032x}'
    assert (await run(root)).discovery.generations == (f'{3:032x}',)
    assert (await run(root)).discovery.generations == (f'{1:032x}',)
    assert len(list(root.iterdir())) == 4  # Three inputs + one bounded checkpoint.
    print('Runtime cursor proof: fresh process resumes 1 -> 2; then 3 -> 1, four entries retained')


@pytest.mark.asyncio
@pytest.mark.parametrize('error', [OSError('offline'), asyncio.CancelledError()])
async def test_failure_keeps_previous_cursor_and_releases_lock(tmp_path, monkeypatch, error):
    root = root_with_generations(tmp_path)
    await run(root)
    before = (root / CURSOR_FILE).read_bytes()
    with monkeypatch.context() as patch:
        patch.setattr(cursor, 'process_proximity_batch', AsyncMock(side_effect=error))
        with pytest.raises(type(error)):
            await run(root)
    assert (root / CURSOR_FILE).read_bytes() == before
    assert (await run(root)).discovery.generations == (f'{2:032x}',)


@pytest.mark.asyncio
async def test_concurrent_coroutine_cannot_enter_batch(tmp_path, monkeypatch):
    root = root_with_generations(tmp_path)
    entered, release = asyncio.Event(), asyncio.Event()
    original = cursor.process_proximity_batch

    async def blocked(*args, **kwargs):
        entered.set()
        await release.wait()
        return await original(*args, **kwargs)

    monkeypatch.setattr(cursor, 'process_proximity_batch', blocked)
    task = asyncio.create_task(run(root))
    try:
        await asyncio.wait_for(entered.wait(), timeout=2)
        with pytest.raises(BlockingIOError):
            await asyncio.wait_for(run(root), timeout=2)
    finally:
        release.set()
        await task


@pytest.mark.asyncio
@pytest.mark.parametrize('payload', [
    b'{', b'{"version":1,"version":1,"source_id":"fixture","after":null}',
    b'{"version":true,"source_id":"fixture","after":null}',
    b'{"version":1,"source_id":"other","after":null}',
    b'{"version":1,"source_id":"fixture","after":"bad"}',
    b'{"version":1,"source_id":"fixture","after":null,"extra":0}',
    b'x' * 4097,
])
async def test_corrupt_or_foreign_cursor_never_resets(tmp_path, monkeypatch, payload):
    root = root_with_generations(tmp_path)
    entry = root / CURSOR_FILE
    entry.write_bytes(payload)
    entry.chmod(0o600)
    work = AsyncMock()
    monkeypatch.setattr(cursor, 'process_proximity_batch', work)
    with pytest.raises(ValueError):
        await run(root)
    work.assert_not_called()
    assert entry.read_bytes() == payload


@pytest.mark.asyncio
async def test_empty_inventory_binds_source(tmp_path):
    tmp_path.chmod(0o700)
    assert not (await run(tmp_path)).items
    assert json.loads((tmp_path / CURSOR_FILE).read_text()) == dict(
        version=1, source_id='fixture', after=None)
    with pytest.raises(ValueError, match='configured source'):
        await cursor.process_proximity_checkpointed_batch(
            tmp_path, source_id='other', now=1000, adapter=None, observer=None,
            gametimes_dir=tmp_path)


@pytest.mark.asyncio
async def test_checkpoint_counts_against_capacity(tmp_path):
    root = root_with_generations(tmp_path)
    with pytest.raises(ValueError, match='entry cap'):
        await run(root, max_entries=3)
    assert json.loads((root / CURSOR_FILE).read_text())['after'] is None


@pytest.mark.asyncio
async def test_symlink_is_not_followed_or_replaced(tmp_path):
    root = root_with_generations(tmp_path)
    target = root / 'unrelated'
    target.write_bytes(b'untouched')
    (root / CURSOR_FILE).symlink_to(target)
    with pytest.raises(OSError):
        await run(root)
    assert target.read_bytes() == b'untouched'
    assert (root / CURSOR_FILE).is_symlink()


@pytest.mark.asyncio
async def test_sync_failure_propagates_and_retains_temp(tmp_path, monkeypatch):
    root = root_with_generations(tmp_path)
    await run(root)
    before = (root / CURSOR_FILE).read_bytes()
    def fail(_fd):
        raise OSError('simulated cursor sync failure')
    monkeypatch.setattr(cursor.os, 'fsync', fail)
    with pytest.raises(OSError, match='simulated cursor sync failure'):
        await run(root)
    assert (root / CURSOR_FILE).read_bytes() == before
    assert len(list(root.glob('.proximity-cursor-next-*'))) == 1


@pytest.mark.asyncio
async def test_bad_bounds_do_not_create_state(tmp_path):
    tmp_path.chmod(0o700)
    with pytest.raises(ValueError):
        await run(tmp_path, max_entries=True)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_checkpoint_is_private(tmp_path):
    await run(root_with_generations(tmp_path))
    assert os.stat(tmp_path / CURSOR_FILE).st_mode & 0o777 == 0o600


@pytest.mark.asyncio
async def test_empty_scan_keeps_previous_position(tmp_path, monkeypatch):
    root = root_with_generations(tmp_path)
    await run(root)
    before = (root / CURSOR_FILE).read_bytes()
    empty = ProximityBatchResult(ProximityDiscovery((), None, 1, 1, 0), ())
    monkeypatch.setattr(cursor, 'process_proximity_batch', AsyncMock(return_value=empty))
    assert await run(root) == empty
    assert (root / CURSOR_FILE).read_bytes() == before


@pytest.mark.asyncio
async def test_directory_sync_failure_is_not_reported_as_success(tmp_path, monkeypatch):
    root = root_with_generations(tmp_path)
    await run(root)
    original = os.fsync
    count = 0

    def fail_second(fd):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError('simulated directory sync failure')
        original(fd)

    monkeypatch.setattr(cursor.os, 'fsync', fail_second)
    with pytest.raises(OSError, match='simulated directory sync failure'):
        await run(root)
    # Visible new hint is NOT evidence of crash durability or successful return.
    assert json.loads((root / CURSOR_FILE).read_text())['after'] == f'{2:032x}'


@pytest.mark.asyncio
async def test_initial_binding_sync_failure_prevents_batch_work(tmp_path, monkeypatch):
    root = root_with_generations(tmp_path)
    work = AsyncMock()
    monkeypatch.setattr(cursor, 'process_proximity_batch', work)
    def fail(_fd):
        raise OSError('initial binding failure')
    monkeypatch.setattr(cursor.os, 'fsync', fail)
    with pytest.raises(OSError, match='initial binding failure'):
        await run(root)
    work.assert_not_called()
    assert not (root / CURSOR_FILE).exists()
