"""Full c0rn module required-mode proofs; no live ET or service activation."""

import pytest

from tests.unit.test_runtime_identity_writer_path import run_writer
from tests.unit.test_runtime_stats_dispatch import setup_pair


@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
@pytest.mark.parametrize('fault', ['peer', 'init', 'callback', 'module'])
def test_failed_configuration_never_reverts_to_legacy_io(tmp_path, lua, fault):
    _, spool, pair = setup_pair(tmp_path)
    directory = run_writer(lua, spool, pair, 1, 'bound-ipc-invalid-' + fault)
    assert not list(directory.glob('*.txt'))
    assert not list(directory.glob('*.complete.json'))


@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
@pytest.mark.parametrize('state', ['noinit', 'unbound', 'reinit', 'bind-failure'])
def test_required_entrypoint_blocks_unbound_fresh_vm_and_hooks(tmp_path, lua, state):
    _, spool, pair = setup_pair(tmp_path)
    directory = run_writer(lua, spool, pair, 1, 'bound-required-' + state, entrypoint=True)
    assert not list(directory.glob('*.txt'))
    assert not list(directory.glob('*.complete.json'))


@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
@pytest.mark.parametrize('half', [1, 2])
def test_required_entrypoint_still_writes_with_valid_ipc_binding(tmp_path, lua, half):
    _, spool, pair = setup_pair(tmp_path)
    completed = run_writer(lua, spool, pair, half, 'bound-ipc', entrypoint=True)
    assert (spool / completed.generation / completed.filename).stat().st_size == completed.size


@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
@pytest.mark.parametrize('action', ['config', 'bind', 'require', 'open-error'])
def test_late_opt_in_after_legacy_attempt_never_writes_again(tmp_path, lua, action):
    _, spool, pair = setup_pair(tmp_path)
    directory = run_writer(lua, spool, pair, 1, 'legacy-late-' + action)
    assert len(list(directory.glob('*.txt'))) == (0 if action == 'open-error' else 1)
    assert not list(directory.glob('*.complete.json'))
