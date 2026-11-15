"""Compile real pinned ET2.85 functions with small, explicitly fake dependencies.

Opt in with ETLEGACY_SOURCE=/path/to/git/checkout. Never downloads or starts a
server. This characterizes dispatch and the stopwatch branch, not complete engine
initialization, Lua execution, live callback order, disk durability or ID trust.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REVISION = '489f1c4f142903aa9d1619f1c107d00b554d0dd6'


def function(source, name):
    found = re.findall(rf'^(?:static )?(?:int|void) {name}\([^\n]*\)\n\{{.*?^\}}',
                       source, flags=re.MULTILINE | re.DOTALL)
    assert len(found) == 1, f'Expected one pinned function {name}'
    return found[0]


@pytest.fixture(scope='module')
def engine_sources():
    directory = os.environ.get('ETLEGACY_SOURCE')
    if not directory:
        pytest.skip('Set ETLEGACY_SOURCE for pinned external-source proof')

    def source(path):
        return subprocess.run(['git', '-C', directory, 'show', f'{REVISION}:{path}'],
                              capture_output=True, text=True, check=True, timeout=15).stdout

    return source('src/game/g_lua.c'), source('src/game/g_main.c')


@pytest.fixture(scope='module')
def observations(engine_sources, tmp_path_factory):
    lua, main = engine_sources
    functions = '\n'.join(function(lua, name) for name in (
        '_et_IPCSend', 'G_LuaRestart', 'G_LuaHook_InitGame',
        'G_LuaHook_ShutdownGame', 'G_LuaHook_RunFrame'))
    log_exit = function(main, 'G_LogExit')
    opening = '\tif (g_gametype.integer == GT_WOLF_STOPWATCH)\n\t{'
    ending = '\n\telse if (g_gametype.integer == GT_WOLF_CAMPAIGN)'
    assert log_exit.count(opening) == log_exit.count(ending) == 1
    block = log_exit[log_exit.index(opening):log_exit.index(ending)]
    functions += '\nvoid finish_stopwatch(void) { char cs[64];\n' + block + '\n}\n'
    template = (ROOT / 'tests/fixtures/runtime_engine_identity_probe.c').read_text()
    marker = '/* EXTRACTED_ENGINE_FUNCTIONS */'
    assert template.count(marker) == 1
    compiler = shutil.which('cc')
    assert compiler, 'C compiler required when external source proof is requested'
    directory = tmp_path_factory.mktemp('engine-identity-probe')
    code, executable = directory / 'probe.c', directory / 'probe'
    code.write_text(template.replace(marker, functions))
    built = subprocess.run([compiler, '-std=c99', '-Wall', '-Wextra', '-Werror',
                            str(code), '-o', str(executable)], capture_output=True, text=True, timeout=20)
    assert built.returncode == 0, built.stdout + built.stderr
    run = subprocess.run([str(executable)], capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stdout + run.stderr
    print(f'PINNED ENGINE {REVISION}; dependency stubs; NOT a running game\n{run.stdout}')
    return [line.split() for line in run.stdout.splitlines()]


def row(observations, name):
    matches = [values[1:] for values in observations if values[0] == name]
    assert len(matches) == 1
    return tuple(map(int, matches[0]))


def test_lua_reload_does_not_dispatch_qagame_lifecycle_hooks(observations):
    assert row(observations, 'qagame_init') == (1, 2)
    # Reload orchestrator reinitializes VMs, but calls neither lifecycle hook.
    # Frame dispatch still reaches the reloaded VMs: no init is synthesized.
    assert row(observations, 'lua_reload') == (2, 1, 2, 0, 2)
    assert row(observations, 'qagame_restart') == (4, 2, 1)


@pytest.mark.parametrize('half', [0, 1])
def test_completed_half_counter_is_not_playing_half_counter(observations, half):
    cases = [tuple(map(int, values[1:])) for values in observations if values[0] == 'half']
    assert len(cases) == 4
    assert [case for case in cases if case[0] == half] == [
        (half, 0, 1 - half, half), (half, 1, 1 - half, half)]
    for current, _, after_exit, _ in cases:
        started_half = current + 1
        file_half = 2 if after_exit == 0 else 1
        assert started_half == file_half
        assert after_exit + 1 != started_half
    assert row(observations, 'xp') == (4,)


def test_ipc_delivery_is_not_application_acknowledgement(observations):
    assert row(observations, 'ipc_ok') == (1, 1, 0, 0, 1)


def test_ipc_failures_do_not_become_success(observations):
    assert row(observations, 'ipc_missing') == (0, 1)
    assert row(observations, 'ipc_error') == (0, 2)
    assert row(observations, 'ipc_errored_vm') == (0, 2)
    assert row(observations, 'ipc_missing_vm') == (0, 3)


def test_successful_ipc_can_have_unknown_sender(observations):
    assert row(observations, 'ipc_unknown_sender') == (1, 1, -1)
