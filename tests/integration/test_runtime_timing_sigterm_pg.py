"""Real SIGTERM after a real R1 commit, only on the opted-in disposable CI DB."""

import asyncio
import json
import os
import signal
import sys
import time
from pathlib import Path

import pytest

from tests.integration.test_runtime_timing_driver_pg import (
    clean_environment,
    invoke,
    prepare_target,
    snapshot,
)
from tests.integration.test_runtime_timing_driver_pg import (
    full_import_db as _full_import_db,
)

full_import_db = _full_import_db


async def assert_original_backends(reader, sql, expected):
    """Allow bounded server-side socket teardown after the child has exited."""
    deadline = time.monotonic() + 3
    while True:
        observed = {row['pid'] for row in await reader.fetch(sql)}
        if observed == expected:
            return
        assert time.monotonic() < deadline, (observed, expected)
        await asyncio.sleep(0.02)


CHILD = r'''
import asyncio
import os
import sys
from pathlib import Path
from bot import runtime_timing_import_cli as cli

checkpoint = Path(sys.argv[1])
original = cli.import_completed_round
async def pause_before_r2(*args, **options):
    if options['expected_identity'].round_number == 2:
        temporary = checkpoint.with_suffix('.tmp')
        temporary.write_text(str(os.getpid()))
        temporary.rename(checkpoint)
        await asyncio.Event().wait()
    return await original(*args, **options)

cli.import_completed_round = pause_before_r2
raise SystemExit(cli.main(sys.argv[2:]))
'''


@pytest.mark.timeout(180)
async def test_real_sigterm_after_r1_commit_then_fresh_cli_replays(full_import_db, tmp_path):
    """Pause only scheduling at R2; imports, transactions and replay use real PG."""
    _, reader = full_import_db
    source = await prepare_target(reader, tmp_path)
    peers_sql = 'SELECT pid FROM pg_stat_activity WHERE datname=current_database()'
    before_peers = {row['pid'] for row in await reader.fetch(peers_sql)}
    checkpoint = tmp_path / 'r2-ready'
    child = await asyncio.create_subprocess_exec(
        sys.executable, '-c', CHILD, str(checkpoint), *source.args,
        cwd=Path(__file__).resolve().parents[2],
        env=clean_environment(os.environ),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 30
        while not checkpoint.exists() and child.returncode is None and time.monotonic() < deadline:
            await asyncio.sleep(0.01)
        assert checkpoint.exists(), 'Owned CLI child did not reach R2 after R1 commit'
        assert int(checkpoint.read_text()) == child.pid
        child.send_signal(signal.SIGTERM)
        stdout, stderr = await asyncio.wait_for(child.communicate(), 10)
        assert child.returncode == 130 and stderr == b'', (child.returncode, stdout, stderr)
        report = json.loads(stdout)
        assert report['status'] == 'interrupted'
        assert report['effect_state'] == 'possibly_partial'
        assert report['active_stage'] == 'stats_r2'
        assert [row['status'] for row in report['stats']] == ['accepted', 'unknown']
        assert [row['retention'] for row in report['timing']] == ['retained', 'retained']
        assert report['source_acknowledged'] is False
        # Backend disappearance is observed independently of the child's JSON.
        await assert_original_backends(reader, peers_sql, before_peers)
        partial = await snapshot(reader)
        assert len(partial['rounds']) == len(partial['processed_files']) == len(partial['runtime_events']) == 1
        assert len(partial['runtime_gametime_sources']) == 2
        assert partial['runtime_gametime_links'] == partial['runtime_gametime_applications'] == []
        first_id = partial['rounds'][0]['id']
        first_players = partial['player_comprehensive_stats']
        first_weapons = partial['weapon_comprehensive_stats']
        await invoke(source)
        completed = await snapshot(reader)
        assert len(completed['runtime_events']) == 4
        assert len(completed['runtime_gametime_applications']) == 2
        assert [row for row in completed['player_comprehensive_stats']
                if row['round_id'] == first_id] == first_players
        assert [row for row in completed['weapon_comprehensive_stats']
                if row['round_id'] == first_id] == first_weapons
        assert await reader.fetchval('SELECT count(*) FROM rounds WHERE round_number IN(1,2)') == 2
        await invoke(source)
        assert await snapshot(reader) == completed
        await assert_original_backends(reader, peers_sql, before_peers)
        for path, original in source.original.items():
            assert path.read_bytes() == original
        print('Real R1 PG commit -> actual owned CLI SIGTERM at R2 -> no child backends -> '
              'fresh CLI completes -> another CLI replay is unchanged; source bytes retained')
    finally:
        if child.returncode is None:
            child.terminate()  # Only the disposable CLI child owned by this test.
            await asyncio.wait_for(child.communicate(), 10)
