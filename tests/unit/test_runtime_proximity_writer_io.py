"""Whole tracker frame/shutdown, real files, explicit write/close fault proof."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from proximity.parser.parser import ProximityParserV4

ROOT = Path(__file__).resolve().parents[2]
NAME = '2026-10-08-120000-supply-round-1_engagements.txt'


def run(tmp_path, fault='none', fail_at=1):
    lua = shutil.which('lua5.4')
    assert lua, 'Lua5.4 required for actual tracker proof'
    result = subprocess.run([lua, 'tests/lua/proximity_writer_io_harness.lua', str(tmp_path), fault, str(fail_at)],
                            cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not result.stderr
    match = re.search(r'RESULT written=(\w+) attempted=(\w+) in_progress=(\w+) '
                      r'opens=(\d+) writes=(\d+) closes=(\d+) bytes=(\d+)', result.stdout)
    assert match, result.stdout
    written, attempted, progress, *counts = match.groups()
    assert attempted == 'true' and progress == 'false', result.stdout
    return written == 'true', tuple(map(int, counts)), result.stdout


def test_actual_complete_file_written_once_and_parsed(tmp_path):
    written, (opens, writes, closes, size), output = run(tmp_path)
    assert written and opens == closes == 1 and writes > 5, output
    raw = (tmp_path / NAME).read_bytes()
    assert len(raw) == size and '# PLAYER_TRACKS' in raw.decode()
    assert '[PROX v5] Saved: 1 tracks (1 samples)' in output
    parser = ProximityParserV4(output_dir=str(tmp_path), gametimes_dir=str(tmp_path / 'absent'))
    assert parser.parse_file(str(tmp_path / NAME), source_bytes=raw)
    assert parser.metadata['map_name'] == 'supply' and parser.metadata['round_num'] == 1
    assert len(parser.player_tracks) == 1
    print('WHOLE TRACKER FRAME -> CLOSED REAL FILE -> CANONICAL PARSER: 1 track/1 sample, no repeat open')


@pytest.mark.parametrize('fault', ['empty', 'open-nil', 'open-zero', 'open-negative', 'open-length'])
def test_empty_or_failed_open_never_claims_written(tmp_path, fault):
    written, (opens, writes, closes, size), output = run(tmp_path, fault)
    assert not written and opens == (0 if fault == 'empty' else 1)
    assert writes == closes == size == 0
    assert '[PROX v5] Saved:' not in output
    assert not (tmp_path / NAME).exists()


@pytest.mark.parametrize('fail_at', [1, 5])
@pytest.mark.parametrize('fault', ['short', 'nil-write', 'throw-write'])
def test_failed_write_closes_once_retains_partial_file_and_blocks_reopen(tmp_path, fault, fail_at):
    written, (opens, writes, closes, size), output = run(tmp_path, fault, fail_at)
    assert not written and opens == closes == 1 and writes == fail_at, output
    assert '[PROX] ERROR in outputData:' in output
    assert '[PROX v5] Saved:' not in output
    assert len((tmp_path / NAME).read_bytes()) == size


@pytest.mark.parametrize('fault', ['format', 'close'])
def test_exception_does_not_leak_or_retry_ambiguous_output(tmp_path, fault):
    written, (opens, writes, closes, size), output = run(tmp_path, fault)
    assert not written and opens == closes == 1 and writes > 1, output
    assert '[PROX v5] Saved:' not in output
    assert len((tmp_path / NAME).read_bytes()) == size
