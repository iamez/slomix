"""ET2.85 retained configstring regression; native Lua, synthetic engine API."""

import subprocess

import pytest

from tests.unit.test_runtime_identity_writer_path import ROOT, run_writer
from tests.unit.test_runtime_stats_dispatch import setup_pair


@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
def test_retained_intermission_allows_fresh_half_but_not_counter_flip(tmp_path, lua):
    _, spool, pair = setup_pair(tmp_path)
    result = run_writer(lua, spool, pair, 2, 'bound-stale-intermission')
    assert result.size > 0
    script = '''
package.path = arg[1] .. '/vps_scripts/?.lua;' .. package.path
local state, counter, flag = '0', '0', '1'
local context = {init_time=699500, map_name='supply', counter=0,
                 gamestate=0, exit_flag='1'}
local api = {CS_INTERMISSION=1, CS_SERVERINFO=2}
api.trap_GetConfigstring = function(k) return k==1 and flag or 'server' end
api.Info_ValueForKey = function() return 'supply' end
api.trap_Cvar_Get = function(k)
    return ({gamestate=state, g_currentRound=counter, g_gametype='3'})[k]
end
local lease = require('runtime_init_lease')
local wire, consume = lease.capture(api, function() return context end, function() return 'bound' end)
assert(wire=='slomix_init_v1|699500|supply|2')
assert(consume({}, function() end)=='bound')
local _, reject = lease.capture(api, function() return context end, function() error('must not bind') end)
counter='1' -- G_LogExit flips this even when the retained flag is already 1.
local ok, why = pcall(reject, {}, function() end)
assert(not ok and tostring(why):find('live context disagrees',1,true))
print('RETAINED FLAG admitted; new queued exit refused')
'''
    checked = subprocess.run([lua, '-', str(ROOT)], input=script, text=True,
                             capture_output=True, timeout=5)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert 'new queued exit refused' in checked.stdout
