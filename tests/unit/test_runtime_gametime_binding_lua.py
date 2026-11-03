"""Trusted bridge freezes operator paths and forwards exact accepted ticket."""
import subprocess
from pathlib import Path

import pytest

from shared.runtime_stats_delivery import StatsDelivery
from tests.unit.test_runtime_stats_dispatch import prepare, setup_pair

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = r'''
package.path=arg[1]..'/vps_scripts/?.lua;'..package.path
local ticket=require('runtime_stats_delivery').decode(arg[2])
package.preload['socket.unix']=function() return {} end
local sent={}
package.loaded['runtime_host_timing_completion']={sender=function(path,now,timeout)
    assert(path=='/private/t1' and timeout==1000 and now()==17)
    return {completed=function(receipt,generation) sent[#sent+1]=generation end}
end}
local module=require('runtime_gametime_binding')
local options={source_id=ticket.identity.source_id,producer_spool='/private/spool',
               timing_sockets={[1]='/private/t1',[2]='/private/t2'},timeout_ms=1000}
local calls=0
local bridge=module.prepare(options,function(id,map,close)
    calls=calls+1
    assert(id.round_id==ticket.identity.round_id and map=='supply')
    assert(close.directory=='/private/spool/'..ticket.generation)
    close.completed({},close.generation)
    return require('runtime_round_identity').encode(id)
end,function() return 17 end)
options.producer_spool='/mutated';options.timing_sockets[1]='/mutated'
bridge(ticket)
assert(calls==1 and sent[1]==ticket.generation)
ticket.identity.source_id='other-source'
assert(not pcall(bridge,ticket) and calls==1)
print('trusted timing binding bridge OK')
'''


@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
def test_trusted_binding_bridge(tmp_path, lua):
    authority, spool, pair = setup_pair(tmp_path / 'rounds')
    dispatch = prepare(authority, spool, pair)
    ticket = StatsDelivery('1' * 32, '2' * 32, 1234, dispatch)
    script = tmp_path / 'bridge.lua'
    script.write_text(SCRIPT)
    result = subprocess.run([lua, str(script), str(ROOT), ticket.encode()],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'trusted timing binding bridge OK' in result.stdout
