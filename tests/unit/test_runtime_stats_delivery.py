"""Host/Lua IPC contract and bounded acknowledgement state machine."""

import json
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from bot.community_stats_parser import C0RNP0RN3StatsParser
from bot.runtime_completed_import import import_completed_round
from shared.runtime_round_identity import RoundIdentity
from shared.runtime_stats_delivery import StatsDelivery, decode_stats_delivery
from shared.runtime_stats_dispatch import StatsDispatch
from tests.unit.test_runtime_identity_writer_path import run_writer
from tests.unit.test_runtime_stats_dispatch import dispatched_pair, setup_pair

ROOT = Path(__file__).resolve().parents[2]
DELIVERY = StatsDelivery('1' * 32, '2' * 32, 1234,
    StatsDispatch(RoundIdentity('fixture-server', '3' * 32, '4' * 32, 1, '4' * 32), '5' * 32, 'supply'))


@pytest.mark.parametrize('init_time', [0, 1, 2147483647])
@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
def test_python_wire_decodes_in_real_lua(lua, init_time):
    value = replace(DELIVERY, init_time=init_time)
    wire = value.encode()
    assert decode_stats_delivery(wire) == value
    script = f'package.path={json.dumps(str(ROOT / "vps_scripts/?.lua") + ";")}..package.path\n'
    script += f'local d=require("runtime_stats_delivery").decode({json.dumps(wire)})\n'
    script += 'print(d.init_time); print(d.identity.round_id); print(d.generation)\n'
    result = subprocess.run([lua, '-'], input=script, text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [str(init_time), '4' * 32, '5' * 32]


@pytest.mark.parametrize('change', [dict(init_time=True), dict(init_time=-1), dict(init_time=2147483648),
    dict(process_epoch='x'), dict(lifecycle_epoch='1' * 32), dict(dispatch=None),
    dict(process_epoch='3' * 32), dict(lifecycle_epoch='5' * 32)])
def test_invalid_host_delivery(change):
    with pytest.raises(ValueError):
        replace(DELIVERY, **change).encode()


@pytest.mark.parametrize('time', ['01', '0.0', '1e3', '-1', '2147483648', 'nan', 'inf', ''])
@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
def test_noncanonical_time_rejected_by_both(lua, time):
    wire = DELIVERY.encode().replace('|1234|', f'|{time}|')
    with pytest.raises(ValueError):
        decode_stats_delivery(wire)
    script = f'package.path={json.dumps(str(ROOT / "vps_scripts/?.lua") + ";")}..package.path\n'
    script += f'print(pcall(require("runtime_stats_delivery").decode,{json.dumps(wire)}))\n'
    result = subprocess.run([lua, '-'], input=script, text=True, capture_output=True, timeout=10)
    assert result.returncode == 0 and result.stdout.startswith('false\t'), result.stderr


@pytest.mark.parametrize('scenario', ['ok', 'wrong-peer', 'reused-slot', 'stale', 'malformed',
    'pins-frozen', 'conflict', 'bind-error', 'send-error', 'ack-drop', 'ack-error', 'wrong-ack',
    'stale-lifecycle', 'wrong-init', 'wrong-source'])
@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
def test_real_protocol_state_machine(lua, scenario):
    result = subprocess.run([lua, str(ROOT / 'tests/lua/runtime_stats_delivery_harness.lua'),
                             str(ROOT), DELIVERY.encode(), scenario],
                            text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.startswith('IPC ' + scenario)
    print(result.stdout.strip())


@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
async def test_host_dispatch_ipc_full_lua_callbacks_and_strict_import(lua, tmp_path):
    first, second = dispatched_pair(tmp_path, lua, ipc=True)
    parsed = []
    async def process(path, *, input_source):
        parsed.append(input_source.parse(None))
        return True, path.name
    manager = SimpleNamespace(parser=C0RNP0RN3StatsParser(), process_file=process)
    assert (await import_completed_round(manager, first, require_declared_identity=True))[0]
    assert (await import_completed_round(manager, second, first=first, require_declared_identity=True))[0]
    assert [item['round_num'] for item in parsed] == [1, 2]
    assert parsed[1]['r1_filename'] == first.filename
    print(f'CONNECTED IPC {lua}: host claims -> whole c0rn receive/ack/frame -> closed files '
          '-> receipt/sealed strict pair -> canonical manager boundary; ET synthetic, no DB')


@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
@pytest.mark.parametrize('scenario', ['bound-ipc-noinit', 'bound-ipc-missing', 'bound-ipc-reset'])
def test_full_module_ipc_unavailable_never_falls_back(lua, scenario, tmp_path):
    _, spool, pair = setup_pair(tmp_path)
    directory = run_writer(lua, spool, pair, 1, scenario)
    assert not list(directory.glob('*.txt'))


@pytest.mark.parametrize('slot', ['-1', '64', '100000', 'nil', 'true', '0/0', '1.5'])
@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
def test_invalid_peer_slot_never_reaches_engine(lua, slot):
    script = f'package.path={json.dumps(str(ROOT / "vps_scripts/?.lua") + ";")}..package.path\n'
    script += '''
local protocol=require("runtime_stats_delivery")
local called=false
local api={FindMod=function() called=true; error("unsafe engine lookup") end}
local options={peer_slot=SLOT, peer_name="authority", peer_signature=string.rep("a",40),
    process_epoch=string.rep("1",32), lifecycle_epoch=string.rep("2",32), init_time=0, source_id="fixture"}
assert(not pcall(protocol.receiver, api, options, function() end, function() end))
assert(not called)
'''.replace('SLOT', slot)
    result = subprocess.run([lua, '-'], input=script, text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
