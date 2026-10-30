"""Isolation admission and deadline forwarding; native behavior has PG proof."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from shared import runtime_proximity_isolation as module
from shared.runtime_proximity_main import ProximityProcessConfig


def test_rejects_arbitrary_task_or_missing_config(monkeypatch):
    spawn = Mock()
    monkeypatch.setattr(module, 'run_bounded_owned_task', spawn)
    with pytest.raises(TypeError):
        module.run_bounded_proximity_batch(None)
    spawn.assert_not_called()


def test_passes_only_configuration_not_live_resources(monkeypatch):
    config = ProximityProcessConfig(Path('/proof'), 'fixture', Path('/proof'),
                                    '/tmp/proof', 5432, 'proof', 'fixture', 'proof', '')
    spawn = Mock(return_value='outcome')
    monkeypatch.setattr(module, 'run_bounded_owned_task', spawn)
    assert module.run_bounded_proximity_batch(config, timeout_seconds=17, shutdown_grace=0.5) == 'outcome'
    args, kwargs = spawn.call_args
    assert args[0].args == (config,)
    assert kwargs == dict(timeout_seconds=17, shutdown_grace=0.5)
