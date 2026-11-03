"""One actual standalone caller for Lua stats/timing, only on disposable CI PG."""

import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

from bot import runtime_timing_import_cli as cli
from tests.integration.test_runtime_events_pg import connection_options
from tests.integration.test_runtime_full_import_pg import full_import_db as _full_import_db
from tests.unit.test_runtime_timing_import_cli import pipeline_inputs

full_import_db = _full_import_db
TABLES = ('rounds', 'player_comprehensive_stats', 'weapon_comprehensive_stats', 'runtime_events',
          'processed_files', 'runtime_round_mappings', 'lua_correction_inputs', 'runtime_gametime_sources',
          'runtime_gametime_identities', 'runtime_gametime_links', 'runtime_gametime_applications')


def clean_environment(values):
    return {key: value for key, value in values.items()
            if not key.startswith(('POSTGRES_', 'DB_', 'PG', 'DATABASE_'))
            and key not in {'PYTHONPATH', 'PYTHONHOME', 'LD_PRELOAD', 'LD_LIBRARY_PATH', 'LD_AUDIT',
                            'BOT_ENVIRONMENT'}}


async def prepare_target(reader, tmp_path):
    options = connection_options()
    if options['host'].startswith('/'):
        pytest.skip('Actual TCP pipeline proof requires the opted-in disposable CI service')
    source = pipeline_inputs(tmp_path)
    database = await reader.fetchval('SELECT current_database()')
    user = await reader.fetchval('SELECT current_user')
    assert database.startswith('slomix_fixture_')
    config = tmp_path / 'pipeline.env'
    raw = ''.join(f'{key}={value}\n' for key, value in {
        'POSTGRES_HOST': options['host'], 'POSTGRES_PORT': options['port'],
        'POSTGRES_DATABASE': database, 'POSTGRES_USER': user, 'POSTGRES_PASSWORD': options['password'],
    }.items()).encode()
    config.write_bytes(raw)
    config.chmod(0o600)
    for flag in ('--socket', '--database', '--user'):
        offset = source.args.index(flag)
        del source.args[offset:offset + 2]
    source.args.extend(['--env-file', str(config.resolve()), '--config-sha256', hashlib.sha256(raw).hexdigest(),
                        '--expected-target', options['host'], str(options['port']), database, user,
                        '--writer-handover-confirmed'])
    return source


async def invoke(source):
    process = await asyncio.create_subprocess_exec(
        sys.executable, '-m', 'bot.runtime_timing_import_cli', *source.args,
        cwd=Path(__file__).resolve().parents[2], env=clean_environment(os.environ),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), 60)
    finally:
        if process.returncode is None:
            process.kill()  # Only this owned disposable CLI child; never a service.
            await process.communicate()
    assert stderr == b''
    report = json.loads(stdout)
    assert process.returncode == 0, report
    assert report['status'] == 'completed' and report['effect_state'] == 'observed_complete'
    assert report['active_stage'] == 'finished' and report['source_acknowledged'] is False
    assert [row['observation'] for row in report['timing']] == ['applied', 'applied']
    return report


async def snapshot(reader):
    result = {}
    for table in TABLES:
        rows = await reader.fetch(f'SELECT * FROM {table} ORDER BY 1,2')
        assert len(rows) == await reader.fetchval(f'SELECT count(*) FROM {table}')
        result[table] = rows
    return result


@pytest.mark.timeout(180)
@pytest.mark.parametrize('generation_layout', [False, True])
async def test_actual_cli_complete_declared_pair_and_fresh_process_replay(full_import_db, tmp_path, generation_layout):
    _, reader = full_import_db
    source = await prepare_target(reader, tmp_path)
    if generation_layout:
        root = Path(source.args[source.args.index('--timing-directory') + 1])
        for half in (1, 2):
            offset = source.args.index(f'--timing-r{half}')
            generation, filename = source.args[offset + 1:offset + 3]
            directory = root / generation
            directory.mkdir(mode=0o700)
            payload = (root / filename).read_bytes()
            path = directory / filename
            path.write_bytes(payload)
            path.chmod(0o600)
            source.original[path] = payload
        source.args.append('--timing-generation-directories')
    await invoke(source)
    committed = await snapshot(reader)
    assert [row['round_number'] for row in committed['rounds']].count(0) == 1
    assert await reader.fetchval('SELECT count(*) FROM rounds WHERE round_number IN (1,2)') == 2
    for table in ('processed_files', 'runtime_round_mappings', 'runtime_gametime_sources',
                  'runtime_gametime_identities', 'runtime_gametime_links', 'runtime_gametime_applications'):
        assert len(committed[table]) == 2, table
    assert len(committed['runtime_events']) == 4
    rows = await reader.fetch('SELECT actual_duration_seconds,total_pause_seconds,pause_count,round_start_unix '
                             'FROM rounds WHERE round_number IN(1,2) ORDER BY round_number')
    assert [tuple(row) for row in rows] == [(600, 10, 1, None), (600, 10, 1, None)]
    assert await reader.fetchval('SELECT count(*) FROM runtime_consumer_receipts') == 0
    assert await reader.fetchval("SELECT count(*) FROM runtime_events WHERE event_type='round_timing_reconciled'") == 2
    replay = await invoke(source)
    assert [row['application'] for row in replay['timing']] == ['already_applied', 'already_applied']
    assert await snapshot(reader) == committed
    for path, raw in source.original.items():
        assert path.read_bytes() == raw
    print('Two actual CLI lifetimes, actual emitted Lua R1/R2 + timing -> one writer slot + separate observer; '
          '2 stats + 2 timing events/receipts, full replay unchanged, sources retained, no Discord/web/consumers')


@pytest.mark.timeout(180)
async def test_r2_interruption_retains_r1_and_timing_then_cli_resumes(full_import_db, tmp_path, monkeypatch):
    _, reader = full_import_db
    source = await prepare_target(reader, tmp_path)
    original = cli.import_completed_round

    async def interrupted(manager, current, **options):
        if current.filename.endswith('-round-2.txt'):
            raise asyncio.CancelledError()
        return await original(manager, current, **options)

    progress = cli.initial_progress()
    with monkeypatch.context() as patch:
        patch.setattr(cli, 'import_completed_round', interrupted)
        clean = clean_environment(os.environ)
        for key in set(os.environ) - set(clean):
            patch.delenv(key)
        with pytest.raises(asyncio.CancelledError):
            await cli.execute(cli.parser().parse_args(source.args), progress)
    partial = await snapshot(reader)
    assert len(partial['rounds']) == len(partial['processed_files']) == len(partial['runtime_events']) == 1
    assert len(partial['runtime_gametime_sources']) == 2
    assert partial['runtime_gametime_links'] == partial['runtime_gametime_applications'] == []
    assert progress['active_stage'] == 'stats_r2' and progress['effect_state'] == 'possibly_partial'
    assert progress['stats'][1]['status'] == 'unknown'
    await invoke(source)
    final = await snapshot(reader)
    assert len(final['runtime_events']) == 4 and len(final['runtime_gametime_applications']) == 2
    old_id = partial['rounds'][0]['id']
    assert [row for row in final['player_comprehensive_stats'] if row['round_id'] == old_id] == partial['player_comprehensive_stats']
    for path, raw in source.original.items():
        assert path.read_bytes() == raw
    print('Actual R1 committed + both timing sources retained, cancellation at R2 propagated with unknown stage; '
          'resources closed, second CLI lifetime resumes without duplicate stats/player effects')
