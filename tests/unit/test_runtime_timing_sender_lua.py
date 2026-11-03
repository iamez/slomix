"""Lua5.1/5.4 timing sender wire, attempts and protocol separation."""
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = r'''
package.path = arg[1] .. '/vps_scripts/?.lua;' .. package.path
package.preload['socket.unix'] = function() return {} end
local wires={}
package.loaded['runtime_host_channel']={open=function()
    return {send_line=function(wire) table.insert(wires,wire) end,close=function() end}
end}
local module=require('runtime_host_timing_completion')
local receipt={version=1,state='writer_closed',filename='gametime-supply-R1-123.json',bytes=42}
local function sender() return module.sender('/private/socket',function() return 0 end,1000) end
local channel=sender()
channel.completed(receipt,string.rep('a',32))
assert(wires[1]=='slomix_timing_closed_v1|'..string.rep('a',32)..'|gametime-supply-R1-123.json|42')
assert(channel.status()=='sent_unconfirmed')
assert(not pcall(channel.completed,receipt,string.rep('a',32)))
for _,name in ipairs({'../x.json','/x.json','x.txt','x|y.json'}) do
    local bad=sender()
    assert(not pcall(bad.completed,{version=1,state='writer_closed',filename=name,bytes=42},string.rep('a',32)))
    assert(bad.status()=='failed')
    assert(not pcall(bad.completed,receipt,string.rep('a',32)))
end
assert(#wires==1)
print('timing-only wire and one-attempt sender OK')
'''


@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
def test_timing_sender_lua_versions(tmp_path, lua):
    script = tmp_path / 'timing.lua'
    script.write_text(SCRIPT)
    result = subprocess.run([lua, str(script), str(ROOT)], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'timing-only wire and one-attempt sender OK' in result.stdout
