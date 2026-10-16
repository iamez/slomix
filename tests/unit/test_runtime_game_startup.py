"""Startup recipe is read-only; console tests use native peers, never ET."""

import json
import os
import subprocess
import sys

import pytest

from scripts.prepare_runtime_game_workspace import prepare
from scripts.runtime_game_startup import startup_recipe
from shared.runtime_game_console import map_release
from shared.runtime_process_pin import pin_process
from tests.unit.test_runtime_game_bundle import inputs  # noqa: F401
from tests.unit.test_runtime_game_workspace import placement  # noqa: F401
from tests.unit.test_runtime_process_pin import approved, child  # noqa: F401


def test_verified_recipe_is_mapless_and_local(placement, monkeypatch):  # noqa: F811
    prepare(**placement)
    monkeypatch.setenv('LD_PRELOAD', '/must/not/inherit.so')
    monkeypatch.setenv('LUA_PATH', '/must/not/inherit')
    result = startup_recipe(placement['destination'])
    settings = result['settings']
    assert result['activation_ready'] is False
    assert result['argv'][0] == str(placement['executable'])
    assert '+map' not in result['argv'] and '+exec' not in result['argv']
    assert settings['net_ip'] == '127.0.0.1' and settings['net_enabled'] == '1'
    assert settings['dedicated'] == '1' and settings['sv_advert'] == '0'
    assert settings['lua_modules'] == 'slomix_runtime_entry.lua'
    assert settings['g_luaModuleList'] == '' and settings['lua_allowedModules'] == ''
    assert settings['g_gametype'] == '3' and settings['g_currentRound'] == '0'
    assert settings['g_customConfig'] == ''
    assert settings['omnibot_enable'] == '0' and settings['g_nextTimeLimit'] == '0'
    assert result['round_fixture']['players'] == 'not_provisioned'
    assert settings['com_watchdog'] == '300' and settings['com_watchdog_cmd'] == 'quit'
    assert result['env'] == {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C',
                             'HOME': str(placement['destination'] / 'home')}
    assert result['console_release'] == 'map supply\n'
    # Independently parse ET's reconstructed console text, including empty args.
    import shlex
    wire = ''.join(arg + ' ' for arg in result['argv'][1:])
    parsed = shlex.split(wire)
    assert len(wire.encode('ascii')) < 1024
    assert len(settings) < 32
    assert {parsed[i + 1]: parsed[i + 2] for i in range(0, len(parsed), 3)} == settings
    assert all(parsed[i] == '+set' for i in range(0, len(parsed), 3))
    # No launch API is involved; verify the real inventory again.
    from scripts.prepare_runtime_game_workspace import verify
    assert verify(placement['destination']) == result['workspace']


@pytest.mark.parametrize('kwargs', [{'port': 80}, {'port': True}, {'port': 65536},
                                   {'idle_seconds': 0}, {'idle_seconds': 601}])
def test_bad_policy_refused_before_workspace_read(kwargs, tmp_path):
    with pytest.raises(ValueError):
        startup_recipe(tmp_path / 'absent', **kwargs)


def test_cli_recipe_and_drift_refusal(placement):  # noqa: F811
    prepare(**placement)
    command = [sys.executable, 'scripts/runtime_game_startup.py',
               '--directory', str(placement['destination'])]
    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['status'] == 'startup_recipe_only'
    (placement['destination'] / 'home/legacy/autoexec.cfg').write_text('map supply\n')
    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert result.returncode == 1 and json.loads(result.stderr)['status'] == 'refused'


def test_console_rejects_wrong_pipe(child, approved):  # noqa: F811
    read_fd, write_fd = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        with (pin_process(child.pid, **approved) as pin,
              pytest.raises(ValueError, match='pipe'), map_release(pin, write_fd)):
            pytest.fail('Wrong stdin admitted')
        with pytest.raises(BlockingIOError):
            os.read(read_fd, 20)
    finally:
        os.close(read_fd)
        os.close(write_fd)


def test_console_requires_nonblocking_writer(child, approved):  # noqa: F811
    with (pin_process(child.pid, **approved) as pin,
          pytest.raises(ValueError, match='nonblocking'), map_release(pin, child.stdin.fileno())):
        pytest.fail('Blocking writer admitted')


def test_console_failure_consumes_callback_and_preserves_original_fd(child, approved):  # noqa: F811
    fd = child.stdin.fileno()
    os.set_blocking(fd, False)
    with pin_process(child.pid, **approved) as pin:
        with map_release(pin, fd) as release:
            pin.invalidate()
            with pytest.raises(ValueError, match='invalidated'):
                release()
            with pytest.raises(ValueError, match='consumed'):
                release()
        os.fstat(fd)
        with pytest.raises(ValueError, match='consumed|closed'):
            release()


def test_console_context_exit_without_release_closes_capability(child, approved):  # noqa: F811
    os.set_blocking(child.stdin.fileno(), False)
    with pin_process(child.pid, **approved) as pin:
        with map_release(pin, child.stdin.fileno()) as release:
            pass
        with pytest.raises(ValueError, match='closed'):
            release()


def test_full_native_pipe_refuses_without_retry(approved):  # noqa: F811
    gate_read, gate_write = os.pipe()
    # Wait on a DIFFERENT pipe, leaving stdin unread until the test closes gate.
    # No signals: every exit path releases the child by EOF and collects output.
    code = 'import os,sys; print("READY",flush=True); os.read(int(sys.argv[1]),1)'
    try:
        with subprocess.Popen([sys.executable, '-c', code, str(gate_read)],
                              pass_fds=(gate_read,), stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE) as running:
            try:
                assert running.stdout.readline() == b'READY\n'
                fd = running.stdin.fileno()
                os.set_blocking(fd, False)
                # Linux pipe capacity is finite; refuse a broken fixture rather
                # than running an unbounded fill loop.
                for _ in range(1024):
                    try:
                        os.write(fd, b'x' * 4096)
                    except BlockingIOError:
                        break
                else:
                    pytest.fail('Pipe did not fill within 4 MiB')
                with pin_process(running.pid, **approved) as pin, map_release(pin, fd) as release:
                    with pytest.raises(BlockingIOError):
                        release()
                    with pytest.raises(ValueError, match='consumed'):
                        release()
            finally:
                os.close(gate_write)
                gate_write = None
                running.stdin.close()
                running.wait(timeout=5)
                assert running.stdout.read() == b''
                assert running.stderr.read() == b''
    finally:
        os.close(gate_read)
        if gate_write is not None:
            os.close(gate_write)
