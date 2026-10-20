"""Explicit source hooks: bounded polling and preserved engine callback behavior."""

import socket
import subprocess
import tempfile
from pathlib import Path

import pytest

from tests.unit.test_runtime_stats_dispatch import prepare, setup_pair

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
@pytest.mark.parametrize('fault', [
    'ok', 'no-init', 'reinit', 'init-error', 'frame-error', 'shutdown-error',
    'dependency', 'invalid', 'late-init', 'late-frame', 'late-shutdown', 'capture-error',
    'state--1', 'state-1', 'state-2', 'state-4', 'state-5', 'state-3', 'state-bad',
])
def test_hooks_preserve_callbacks_and_bound_io(lua, fault):
    result = subprocess.run(
        [lua, str(ROOT / 'tests/lua/runtime_host_hooks_harness.lua'), str(ROOT), fault],
        capture_output=True, text=True, timeout=5,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
@pytest.mark.parametrize('fault', ['hooks-no-server', 'hooks-timeout'])
def test_unavailable_host_keeps_full_stats_writer_fenced(tmp_path, lua, fault):
    authority, spool, pair = setup_pair(tmp_path)
    dispatch = prepare(authority, spool, pair)
    directory = spool / dispatch.generation
    with tempfile.TemporaryDirectory(prefix='slomix-hooks-', dir='/tmp') as local:
        path = str(Path(local) / 'host.sock')
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            if fault == 'hooks-timeout':
                server.bind(path)
                server.listen(1)  # Real local peer deliberately sends no answer.
            result = subprocess.run([
                lua, str(ROOT / 'tests/lua/runtime_identity_writer_harness.lua'), str(ROOT),
                str(directory), pair.first.source_id, pair.first.match_id, pair.first.round_id,
                pair.second.round_id, '1', dispatch.generation, 'bound-' + fault,
                '@hooks:' + path, 'required-entrypoint', '1234',
            ], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'ENGINE HOOK BOOTSTRAP failed' in result.stdout
    assert ('host channel connect failed' if fault == 'hooks-no-server'
            else 'host channel deadline expired') in result.stdout
    assert not list(directory.glob('*.txt'))
