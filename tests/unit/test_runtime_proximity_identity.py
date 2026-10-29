"""Actual tracker files retain shared IDs and cannot fall back to clock linking."""

import hashlib
import shutil
import subprocess
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest

from proximity.parser.parser import ProximityParserV4
from shared.proximity_import import import_proximity_file
from shared.runtime_proximity_identity import proximity_header_identity
from shared.runtime_round_identity import RoundIdentity, stats_header_identity
from tests.unit.test_runtime_gametime_independence import run as run_timing
from tests.unit.test_runtime_gametime_source import NAME as TIMING_NAME
from tests.unit.test_runtime_gametime_source import parse as parse_timing
from tests.unit.test_runtime_stats_dispatch import dispatched_pair

ROOT = Path(__file__).resolve().parents[2]


def identity(half=1):
    return RoundIdentity('fixture', 'a' * 32, ('b' if half == 1 else 'c') * 32, half, 'b' * 32)


def name(half=1):
    return f'2026-10-08-120000-supply-round-{half}_engagements.txt'


def document(half=1):
    return f'# map=supply\n# round={half}\n# runtime_identity={identity(half).encode()}\n'


def run(tmp_path, half=1, scenario='normal', declared=None):
    lua = shutil.which('lua5.4')
    assert lua, 'Lua5.4 required'
    result = subprocess.run([lua, 'tests/lua/proximity_writer_io_harness.lua',
                             str(tmp_path), 'none', '1', (declared or identity(half)).encode(), scenario],
                            cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not result.stderr
    return result.stdout


def test_dispatched_stats_timing_and_proximity_share_both_halves(tmp_path):
    artifacts = dispatched_pair(tmp_path / 'stats', ipc=True)
    assert len(artifacts) == 2
    for half, artifact in enumerate(artifacts, 1):
        with (artifact.root / artifact.generation / artifact.filename).open() as stream:
            declared = stats_header_identity(stream.readline())
        timing, proximity = tmp_path / f'timing{half}', tmp_path / f'proximity{half}'
        timing.mkdir()
        proximity.mkdir()
        run_timing(timing, enabled=False, target=False, mode='frame', identity=declared)
        timing_name = TIMING_NAME.replace('R1', f'R{half}')
        admitted = parse_timing(timing, (timing / timing_name).read_bytes(),
                                filename=timing_name, expected_identity=declared)
        run(proximity, half, declared=declared)
        observed = proximity_header_identity((proximity / name(half)).read_text().splitlines(), name(half))
        assert observed == admitted.declared_identity == declared
    print('HOST DISPATCH -> FULL STATS IPC + TIMING + PROXIMITY: 6 real files, matching R1/R2 IDs')


@pytest.mark.parametrize('half', [1, 2])
@pytest.mark.parametrize('scenario', ['normal', 'mutate'])
def test_real_whole_tracker_file_and_parser_agree_on_frozen_id(tmp_path, half, scenario):
    output = run(tmp_path, half, scenario)
    assert 'written=true' in output and 'opens=1' in output
    path = tmp_path / name(half)
    raw = path.read_bytes()
    assert proximity_header_identity(raw.decode().splitlines(), path.name) == identity(half)
    parser = ProximityParserV4(gametimes_dir=str(tmp_path))
    # Even a conflicting neighboring gametime must not overwrite a declared half.
    (tmp_path / f'gametime-supply-R{3-half}-1700000610.json').touch()
    assert parser.parse_file(str(path), source_bytes=raw)
    assert parser.metadata['runtime_identity'] == identity(half).encode()
    assert parser.metadata['round_num'] == half and len(parser.player_tracks) == 1
    print(f'WHOLE LUA -> REAL FILE -> PYTHON DECLARATION/PARSER: R{half}, 1 track, exact ID')


@pytest.mark.parametrize('scenario', ['no-init', 'warmup', 'wrong-map', 'wrong-half', 'wrong-gametype'])
def test_binding_requires_observed_matching_active_context(tmp_path, scenario):
    assert 'BIND_REJECTED' in run(tmp_path, scenario=scenario)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('half', [1, 2])
@pytest.mark.parametrize('scenario', ['reset', 'end-map', 'end-half', 'end-gametype'])
def test_invalidated_or_conflicting_end_never_opens_output(tmp_path, half, scenario):
    output = run(tmp_path, half, scenario)
    assert 'written=false' in output and 'opens=0' in output
    assert '[PROX] ERROR in outputData:' in output
    assert not list(tmp_path.iterdir())


def test_same_vm_second_live_cannot_reuse_id_or_truncate_first_file(tmp_path):
    output = run(tmp_path, scenario='second-live')
    assert 'written=false' in output and 'opens=1' in output
    assert 'binding invalidated' in output
    assert proximity_header_identity((tmp_path / name()).read_text().splitlines(), name()) == identity()


@pytest.mark.parametrize('edit', [
    lambda s: s + '# runtime_identity=' + identity().encode() + '\n',
    lambda s: s + '# map=supply\n',
    lambda s: s + '# round=1\n',
    lambda s: s.replace('# map=supply\n', ''),
    lambda s: s.replace('# round=1\n', ''),
    lambda s: s.replace('# round=1', '# round=2'),
    lambda s: s.replace('# map=supply', '# map=oasis'),
    lambda s: s.replace(identity().encode(), ''),
    lambda s: s.replace('slomix_round_v1', 'slomix_round_v2'),
    lambda s: s.replace('# runtime_identity=', '# runtime_identity '),
])
def test_malformed_declaration_never_becomes_legacy(tmp_path, edit):
    raw = edit(document())
    with pytest.raises(ValueError):
        proximity_header_identity(raw.splitlines(), name())
    parser = ProximityParserV4(gametimes_dir=str(tmp_path))
    assert not parser.parse_file(name(), source_bytes=raw.encode())


@pytest.mark.parametrize('filename', ['supply.txt', name(2), name().replace('supply', 'oasis')])
def test_declared_filename_must_agree(filename):
    with pytest.raises(ValueError):
        proximity_header_identity(document().splitlines(), filename)


async def test_declared_file_cannot_enter_legacy_import_or_touch_database(tmp_path):
    run(tmp_path)
    raw = (tmp_path / name()).read_bytes()
    adapter = Mock()
    parser = ProximityParserV4(db_adapter=adapter, gametimes_dir=str(tmp_path))
    assert not await parser.import_file(name(), date(2026, 10, 8), source_bytes=raw)
    assert adapter.mock_calls == []


@pytest.mark.parametrize('strict', [False, True])
async def test_runtime_reports_mapping_pending_before_receipt_or_db(tmp_path, strict):
    run(tmp_path)
    path = tmp_path / name()
    path.chmod(0o600)  # Model transfer into the private verified runtime spool.
    raw = path.read_bytes()
    adapter = Mock()
    result = await import_proximity_file(path, adapter=adapter, session_date=date(2026, 10, 8),
        gametimes_dir=tmp_path, expected_size=len(raw), expected_sha256=hashlib.sha256(raw).hexdigest(),
        require_linked_parent=strict)
    assert not result.success and result.pending_reason == 'declared_identity_mapping_pending'
    assert result.round_id is None and result.parsed_stats is None
    assert adapter.mock_calls == [] and path.read_bytes() == raw


def test_unbound_legacy_and_parser_reuse_do_not_invent_identity(tmp_path):
    parser = ProximityParserV4(gametimes_dir=str(tmp_path))
    assert parser.parse_file(name(), source_bytes=document().encode())
    assert parser.metadata['runtime_identity'] == identity().encode()
    legacy = b'# map=supply\n# round=1\n'
    assert parser.parse_file(name(), source_bytes=legacy)
    assert parser.metadata['runtime_identity'] is None
    assert proximity_header_identity(legacy.decode().splitlines(), name()) is None
