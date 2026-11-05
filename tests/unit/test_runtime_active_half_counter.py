"""Native ET starts R1 at counter0 and flips the counter in G_LogExit."""
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('counter,half', [(0, 1), (1, 2)])
def test_init_lease_uses_active_not_intermission_counter(counter, half):
    script = r'''
package.path=arg[1]..'/vps_scripts/?.lua;'..package.path
local counter,half=tonumber(arg[2]),tonumber(arg[3])
local context={init_time=10450,map_name='supply',counter=counter,gamestate=0,exit_flag=''}
local api={CS_INTERMISSION=1,CS_SERVERINFO=2}
api.trap_GetConfigstring=function(k) return k==1 and '' or 'server' end
api.Info_ValueForKey=function() return 'supply' end
api.trap_Cvar_Get=function(k) return tostring(({gamestate=0,g_currentRound=counter,g_gametype=3})[k]) end
local wire=require('runtime_init_lease').capture(api,function() return context end,function() end)
assert(wire=='slomix_init_v1|10450|supply|'..half,wire)
'''
    result = subprocess.run(['lua5.4', '-', str(ROOT), str(counter), str(half)],
                            input=script, text=True, capture_output=True, timeout=5)
    assert result.returncode == 0, result.stderr
