"""Actual Lua round result -> real file -> sealed reader, no ET/server/network."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from bot.runtime_gametime_source import parse_verified_gametime
from tests.unit.test_runtime_gametime_source import NAME

ROOT = Path(__file__).resolve().parents[2]


def run(tmp_path, *, enabled, target, capture=True, failure_only=False, mode='send',
        identity=None, binding_fault='none'):
    lua = shutil.which('lua5.4')
    assert lua is not None, 'Lua5.4 required for whole producer proof'
    result = subprocess.run(
        [lua, str(ROOT / 'tests/lua/gametime_independence_harness.lua'),
         str(ROOT / 'vps_scripts/stats_discord_webhook.lua'), str(tmp_path), mode,
         *[str(int(flag)) for flag in (enabled, target, capture, failure_only)],
         *([identity.encode(), binding_fault] if identity is not None else [])],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not result.stderr
    if binding_fault not in ('reset', 'end-half', 'end-map', 'end-counter', 'end-state', 'end-gametype'):
        assert 'crashed:' not in result.stdout, result.stdout
    assert 'frame_health end error:' not in result.stdout, result.stdout
    return result.stdout


def verify_file(tmp_path):
    path = tmp_path / NAME
    raw = path.read_bytes()
    payload = json.loads(raw)
    assert payload['meta']['actual_duration_seconds'] == 600
    assert payload['meta']['pause_seconds'] == 10
    with path.open('rb') as stream:
        timing = parse_verified_gametime(
            stream.fileno(), source_id='fixture-server', generation='a' * 32,
            filename=NAME, expected_size=len(raw), expected_sha256=hashlib.sha256(raw).hexdigest(),
        )
    assert timing.actual_duration_seconds == 600
    assert timing.total_pause_seconds == 10 and timing.pause_count == 1
    assert timing.round_end_unix - timing.round_start_unix == 610


@pytest.mark.parametrize(('enabled', 'target'), [(False, True), (True, False), (False, False)])
@pytest.mark.parametrize('failure_only', [False, True])
@pytest.mark.parametrize('mode', ['send', 'frame'])
def test_discord_off_retains_timing_once(tmp_path, enabled, target, failure_only, mode):
    output = run(tmp_path, enabled=enabled, target=target, failure_only=failure_only, mode=mode)
    assert 'COUNTS launches=0 opens=1 shell=1' in output, output
    assert 'local_saved=true, delivery_launched=false' in output
    verify_file(tmp_path)


@pytest.mark.parametrize('failure_only', [False, True])
@pytest.mark.parametrize('mode', ['send', 'launch-fail'])
def test_enabled_notification_policy_unchanged(tmp_path, failure_only, mode):
    output = run(tmp_path, enabled=True, target=True, failure_only=failure_only, mode=mode)
    saved = not failure_only or mode == 'launch-fail'
    assert f'COUNTS launches=1 opens={int(saved)} shell={int(saved)}' in output, output
    if saved:
        verify_file(tmp_path)
    else:
        assert not (tmp_path / NAME).exists()
    assert f'local_saved={str(saved).lower()}, delivery_launched={str(mode == "send").lower()}' in output


@pytest.mark.parametrize(('enabled', 'target'), [(False, True), (True, False), (False, False)])
def test_both_outputs_unavailable_no_io(tmp_path, enabled, target):
    output = run(tmp_path, enabled=enabled, target=target, capture=False)
    assert 'COUNTS launches=0 opens=0 shell=0' in output
    assert not (tmp_path / NAME).exists()


def test_disabled_local_capture_still_allows_notifications(tmp_path):
    output = run(tmp_path, enabled=True, target=True, capture=False)
    assert 'COUNTS launches=1 opens=0 shell=0' in output
    assert not (tmp_path / NAME).exists()


@pytest.mark.parametrize('mode', ['transport', 'sweep'])
@pytest.mark.parametrize(('enabled', 'target'), [(False, True), (True, False), (False, False)])
def test_disabled_transport_and_sweep_do_not_touch_pending_files(tmp_path, enabled, target, mode):
    pending = tmp_path / 'pending'
    pending.mkdir()
    payload = pending / 'fixture.json'
    marker = pending / 'fixture.exit'
    payload.write_bytes(b'{"fixture":"keep"}')
    marker.write_bytes(b'0\n')
    before = {path.name: path.read_bytes() for path in pending.iterdir()}
    output = run(tmp_path, enabled=enabled, target=target, mode=mode)
    assert 'COUNTS launches=0 opens=0 shell=0' in output
    assert {path.name: path.read_bytes() for path in pending.iterdir()} == before


def test_local_write_failure_never_claims_retention(tmp_path):
    output = run(tmp_path, enabled=False, target=True, mode='write-fail')
    assert 'fixture open failure' in output
    assert 'local_saved=false, delivery_launched=false' in output
    assert 'local_saved=true' not in output
    assert 'COUNTS launches=0 opens=1 shell=1' in output
    assert not (tmp_path / NAME).exists()


def test_provisioned_close_callback_runs_after_actual_writer_close(tmp_path):
    from tests.unit.test_runtime_stats_dispatch import setup_pair

    _, _, pair = setup_pair(tmp_path / 'rounds')
    output = run(tmp_path, enabled=False, target=False, mode='frame',
                 identity=pair.first, binding_fault='completion')
    assert 'BIND=true' in output
    assert output.count('TIMING_CLOSED_AFTER_READ bytes=') == 1
    verify_file(tmp_path)


@pytest.mark.parametrize(('capture', 'failure_only'), [(False, False), (True, True)])
def test_runtime_completion_requires_persistent_capture_policy(tmp_path, capture, failure_only):
    from tests.unit.test_runtime_stats_dispatch import setup_pair

    _, _, pair = setup_pair(tmp_path / 'rounds')
    output = run(tmp_path, enabled=False, target=False, capture=capture,
                 failure_only=failure_only, identity=pair.first, binding_fault='completion')
    assert 'BIND=false' in output
    assert 'TIMING_CLOSED_AFTER_READ' not in output
    assert not (tmp_path / NAME).exists()


def test_failed_checked_close_never_emits_completion(tmp_path):
    from tests.unit.test_runtime_stats_dispatch import setup_pair

    _, _, pair = setup_pair(tmp_path / 'rounds')
    output = run(tmp_path, enabled=False, target=False, mode='frame', identity=pair.first,
                 binding_fault='completion-close-fail')
    assert 'BIND=true' in output
    assert 'TIMING_CLOSED_AFTER_READ' not in output
    assert 'fixture close failure' in output


def test_same_vm_accepts_fresh_second_half_after_new_initgame(tmp_path):
    from tests.unit.test_runtime_stats_dispatch import setup_pair

    _, _, pair = setup_pair(tmp_path / 'rounds')
    result = subprocess.run([
        shutil.which('lua5.4'), str(ROOT / 'tests/lua/gametime_independence_harness.lua'),
        str(ROOT / 'vps_scripts/stats_discord_webhook.lua'), str(tmp_path), 'send',
        '0', '0', '1', '0', pair.first.encode(), 'two-halves', pair.second.encode(),
    ], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'TWO_HALVES_REBOUND' in result.stdout
    for half, expected in ((1, pair.first), (2, pair.second)):
        raw = (tmp_path / NAME.replace('R1', f'R{half}')).read_bytes()
        assert json.loads(raw)['meta']['runtime_identity'] == expected.encode()
