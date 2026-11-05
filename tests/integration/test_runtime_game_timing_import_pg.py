"""Packaged whole Lua -> actual supervisor capture -> helper -> SQL and replay.

CI's explicit disposable TCP transport replaces only the local proof target and
readiness admission. No production target rule is weakened or live service used.
"""
import asyncio
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot import runtime_timing_import_cli as cli
from scripts import runtime_game_import as helper
from shared.runtime_import_pool import TcpImportDatabaseConfig
from tests.integration.test_runtime_events_pg import connection_options
from tests.integration.test_runtime_full_import_pg import full_import_db as _full_import_db
from tests.integration.test_runtime_timing_driver_pg import clean_environment, snapshot
from tests.unit.test_runtime_game_bundle import inputs as _inputs
from tests.unit.test_runtime_timing_workspace import capture_packaged_pair
from tests.unit.test_runtime_timing_workspace import timed_placement as _timed_placement

full_import_db, inputs, timed_placement = _full_import_db, _inputs, _timed_placement


@pytest.mark.timeout(180)
async def test_packaged_supervisor_handoff_imports_and_replays(full_import_db, timed_placement, tmp_path, monkeypatch):
    _, reader = full_import_db
    options = connection_options()
    if options['host'].startswith('/'):
        pytest.skip('This proof uses the explicitly opted-in disposable CI TCP service')
    database = await reader.fetchval('SELECT current_database()')
    role = await reader.fetchval('SELECT current_user')
    assert database.startswith('slomix_fixture_')
    target = TcpImportDatabaseConfig(options['host'], database, role, options['password'], options['port'])
    captured = await asyncio.to_thread(capture_packaged_pair, timed_placement, monkeypatch, False, True)
    assert captured.timing_match is not None
    # No fake SQL operations/resources. Only CI transport/readiness differs
    # from the separately tested local peer-only production admission contract.
    monkeypatch.setattr(helper, 'preflight_import', AsyncMock())
    monkeypatch.setattr(helper, 'proof_database', lambda *args:
        SimpleNamespace(socket='/ci-explicit-transport', database=database, user=role))
    monkeypatch.setattr(cli, 'database_from_arguments', lambda args: target)
    clean = clean_environment(os.environ)
    for key in tuple(os.environ):
        if key not in clean:
            monkeypatch.delenv(key)
    lock = tmp_path / 'writer'
    lock.mkdir(mode=0o700)
    before = None
    for _ in range(2):
        result = await helper.import_live_timing_capture(captured.timing_match,
            socket=Path('/ci-explicit-transport'), database=database, lock_directory=lock,
            defer_team_assignment=True, writer_handover_confirmed=True, timing_writer_handover_confirmed=True)
        assert result['status'] == 'completed' and result['effect_state'] == 'observed_complete'
        assert result['source_acknowledged'] is False
        assert [row['observation'] for row in result['timing']] == ['applied', 'applied']
        current = await snapshot(reader)
        if before is None:
            before = current
            assert len(current['runtime_round_mappings']) == len(current['runtime_gametime_applications']) == 2
            assert len(current['runtime_events']) == 4
            assert await reader.fetchval('SELECT count(*) FROM player_comprehensive_stats WHERE round_number IN(1,2)') == 2
        else:
            assert current == before
    print('PACKAGED LUA/SUPERVISOR -> ACTUAL TIMING HELPER/SQL: both halves observed; full replay unchanged; CI transport explicit')
