"""Bounded host vocabulary and full Lua callback/opaque-lease proofs."""

from dataclasses import replace

import pytest

from shared.runtime_init_observation import InitGameObservation, decode_init_observation
from shared.runtime_process_authority import prepare_observed_process_delivery, reserve_process_epoch
from tests.unit import test_runtime_process_pin as process_fixtures
from tests.unit.test_runtime_identity_writer_path import run_writer
from tests.unit.test_runtime_process_authority import pin as pin_fixture
from tests.unit.test_runtime_stats_dispatch import prepare, setup_pair

approved, child, pin = process_fixtures.approved, process_fixtures.child, pin_fixture


@pytest.mark.parametrize('time', [0, 1234, 2147483647])
@pytest.mark.parametrize('half', [1, 2])
def test_canonical_observation_roundtrip(time, half):
    value = InitGameObservation(time, 'supply', half)
    assert decode_init_observation(value.encode()) == value


@pytest.mark.parametrize('wire', [None, '', 'x' * 129, 'slomix_init_v2|0|supply|1',
    'slomix_init_v1|00|supply|1', 'slomix_init_v1|0.0|supply|1', 'slomix_init_v1|-1|supply|1',
    'slomix_init_v1|2147483648|supply|1', 'slomix_init_v1|0|supply|0',
    'slomix_init_v1|0|../map|1', 'slomix_init_v1|0|supply|1\n', 'slomix_init_v1|0|supply|1|extra'])
def test_untrusted_observation_rejected(wire):
    with pytest.raises(ValueError):
        decode_init_observation(wire)


@pytest.mark.parametrize('change', [dict(init_time=True), dict(init_time=float('nan')),
    dict(map_name=''), dict(map_name='a' * 65), dict(round_number=True), dict(round_number=3)])
def test_invalid_typed_observation_is_not_a_shortcut(change):
    with pytest.raises(ValueError):
        replace(InitGameObservation(1234, 'supply', 1), **change).encode()


@pytest.mark.parametrize('change', [dict(map_name='radar'), dict(round_number=2)])
def test_host_refuses_dispatch_observation_mismatch_before_process_io(tmp_path, change):
    authority, spool, pair = setup_pair(tmp_path)
    dispatch = prepare(authority, spool, pair)
    observed = replace(InitGameObservation(1234, 'supply', 1), **change)
    with pytest.raises(ValueError, match='map or half'):
        prepare_observed_process_delivery(authority, None, None, lifecycle_epoch='2' * 32,
                                          observation=observed, dispatch=dispatch)


def test_observed_time_is_used_with_native_process_authority(tmp_path, pin):
    host = tmp_path / 'host'
    host.mkdir(mode=0o700)
    expected = reserve_process_epoch(host, pin, source_id='fixture-server')
    authority, spool, pair = setup_pair(tmp_path / 'rounds')
    dispatch = prepare(authority, spool, pair)
    observation = decode_init_observation('slomix_init_v1|4321|supply|1')
    delivery = prepare_observed_process_delivery(host, pin, expected, lifecycle_epoch='2' * 32,
                                                 observation=observation, dispatch=dispatch)
    assert delivery.init_time == 4321 and delivery.process_epoch == expected.process_epoch


@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
@pytest.mark.parametrize('fault', ['stale', 'shutdown', 'bad-config', 'duplicate', 'map',
    'half', 'state', 'gametype', 'exit', 'noinit'])
def test_actual_module_rejects_stale_or_reused_init_lease(tmp_path, lua, fault):
    _, spool, pair = setup_pair(tmp_path)
    directory = run_writer(lua, spool, pair, 1, 'bound-ipc-lease-' + fault, entrypoint=True)
    assert not list(directory.glob('*.txt'))
    assert not list(directory.glob('*.complete.json'))
