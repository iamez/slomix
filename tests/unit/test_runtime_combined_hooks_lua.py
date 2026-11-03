"""Same-VM composition preserves lifecycle observers and command ownership."""
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = r'''
local m=dofile(arg[1]..'/vps_scripts/runtime_combined_hooks.lua')
local calls={}
local function event(name,fail)
    return function() calls[#calls+1]=name;if fail then error('fixture '..name) end end
end
local c=m.compose({et_InitGame=event('stats-init'),et_RunFrame=event('stats-frame',true),
                   et_ShutdownGame=event('stats-stop')},
                  {et_InitGame=event('timing-init'),et_RunFrame=event('timing-frame'),
                   et_ShutdownGame=event('timing-stop')})
c.et_InitGame();assert(not pcall(c.et_RunFrame));c.et_ShutdownGame()
assert(table.concat(calls,',')=='stats-init,timing-init,stats-frame,timing-frame,stats-stop,timing-stop')
local n=0
local commands=m.compose({et_ClientCommand=function() return 1 end},
                         {et_ClientCommand=function() n=n+1;return 0 end})
assert(commands.et_ClientCommand()==1 and n==0)
local second_claim=m.compose({et_ClientCommand=function() return 0 end},
                             {et_ClientCommand=function() return 1 end})
assert(second_claim.et_ClientCommand()==1)
assert(not pcall(m.capture,{et_Unknown=function() end}))
local func=function() end
assert(not pcall(m.compose,{et_RunFrame=func},{et_RunFrame=func}))
assert(not pcall(m.compose,{not_a_callback=func},{}))
local a={et_Print=function() return 'frozen' end}
local frozen=m.compose(a,{et_Print=function() return 'other' end})
a.et_Print=function() return 'changed' end
assert(frozen.et_Print()=='frozen')
local single=m.compose({et_Damage=function() return nil,7 end},{})
local x,y=single.et_Damage();assert(x==nil and y==7)
print('same-VM hook composition contract OK')
'''


@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
def test_combined_hooks_preserve_callbacks(tmp_path, lua):
    script = tmp_path / 'combined.lua'
    script.write_text(SCRIPT)
    result = subprocess.run([lua, str(script), str(ROOT)], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'same-VM hook composition contract OK' in result.stdout
