"""Actual OS cancellation of the timing caller, with database stages stubbed."""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from shared.runtime_writer_lock import local_import_writer
from tests.unit.test_runtime_timing_import_cli import source as _source

source = _source

CHILD = r'''
import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from bot import runtime_timing_import_cli as cli
from shared.runtime_writer_lock import ImportWriterBusy, local_import_writer

root = Path(sys.argv[1])
lock = Path(sys.argv[sys.argv.index('--lock-directory') + 1])
fds = []

@asynccontextmanager
async def resources(database):
    try:
        yield object(), object(), object()
    finally:
        # Cleanup must still hold the writer lease and timing descriptors.
        try:
            with local_import_writer(lock):
                raise AssertionError('Writer lease released before cleanup')
        except ImportWriterBusy:
            pass  # The caller must retain its cooperative lease until cleanup.
        for fd in fds:
            os.fstat(fd)
        (root / 'cleanup').write_text('closed')

async def retain(adapter, fd, **binding):
    assert os.fstat(fd).st_size == binding['expected_size']
    fds.append(fd)

async def stats(manager, current, **binding):
    if binding['expected_identity'].round_number == 1:
        return True, 'stubbed stage; no database commit is claimed'
    marker = root / 'ready.tmp'
    marker.write_text(str(os.getpid()))
    marker.rename(root / 'ready')  # Publish only the complete PID.
    await asyncio.Event().wait()

cli.timing_import_resources = resources
cli.retain_gametime_source = retain
cli.import_completed_round = stats
code = cli.main(sys.argv[2:])
assert (root / 'cleanup').read_text() == 'closed'
for fd in fds:
    try:
        os.fstat(fd)
    except OSError:
        continue
    raise AssertionError('Timing descriptor leaked after cancellation')
with local_import_writer(lock):
    pass  # The same process must be able to reacquire the released lease.
raise SystemExit(code)
'''


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux SIGTERM contract')
def test_real_sigterm_preserves_progress_sources_and_cleanup(source, tmp_path):
    """No app/PG service: signal only the child created by this test."""
    root = Path(__file__).resolve().parents[2]
    child = subprocess.Popen(
        [sys.executable, '-c', CHILD, str(tmp_path), *source.args],
        cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env={key: value for key, value in os.environ.items()
             if not key.startswith(('POSTGRES_', 'RUNTIME_EVENTS_TEST_', 'DB_'))},
    )
    stdout = stderr = ''
    try:
        ready = tmp_path / 'ready'
        deadline = time.monotonic() + 10
        while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ready.exists(), 'Owned test child did not reach the R2 wait point'
        assert int(ready.read_text()) == child.pid
        child.send_signal(signal.SIGTERM)
        stdout, stderr = child.communicate(timeout=5)
    finally:
        if child.poll() is None:
            child.terminate()  # Only this test-owned disposable child, never a service.
            stdout, stderr = child.communicate(timeout=5)
    assert child.returncode == 130, (child.returncode, stdout, stderr)
    assert stderr == ''
    report = json.loads(stdout)
    assert report['status'] == 'interrupted'
    assert report['effect_state'] == 'possibly_partial'
    assert report['active_stage'] == 'stats_r2'
    assert report['stats'] == [dict(round_number=1, status='accepted'),
                               dict(round_number=2, status='unknown')]
    assert [row['retention'] for row in report['timing']] == ['retained', 'retained']
    assert all(row['application'] == 'not_attempted' for row in report['timing'])
    assert report['source_acknowledged'] is False
    assert (tmp_path / 'cleanup').read_text() == 'closed'
    with local_import_writer(source.lock):
        pass  # Also verify the lease is available in the independent parent.
    for path, original in source.original.items():
        assert path.read_bytes() == original
    print('Actual owned-child SIGTERM: exit130, R2 unknown, cleanup/FD/lease checks pass; '
          'four real Lua source files retained; database stages stubbed')
