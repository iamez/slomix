"""Load-time host composition, failure cleanup, no competing callback adoption."""
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = r'''
package.path=arg[1]..'/vps_scripts/?.lua;'..package.path
local mode=arg[2]
package.preload['socket.unix']=function() return {} end
local module=require('runtime_combined_host')
et={trap_Milliseconds=function() return 0 end}
local trace={}
local configured
local function stats()
    et_InitGame=function() trace[#trace+1]='stats-init' end
    et_RunFrame=function() trace[#trace+1]='stats-frame' end
    et_ShutdownGame=function() trace[#trace+1]='stats-stop' end
    return {configure=function(options) configured=options;return 'configured' end}
end
local function timing()
    et_InitGame=function() trace[#trace+1]='timing-init' end
    et_RunFrame=function() trace[#trace+1]='timing-frame' end
    et_ShutdownGame=function() trace[#trace+1]='timing-stop' end
    RequireRuntimeGametimeBinding=function() trace[#trace+1]='fenced' end
    BindRuntimeGametime=function() error('not called at load time') end
    if mode=='partial' then error('fixture partial loader') end
end
if mode=='existing' then et_InitGame=function() end end
local ok,value=pcall(module.configure,{source_id='fixture-server',socket_path='/private/stats',
    bootstrap_timeout_ms=1000,completion_timeout_ms=1000,producer_spool='/private/spool',
    timing_sockets={[1]=mode=='shared' and '/private/stats' or '/private/t1',
        [2]='/private/t2'}},{stats=stats,timing=timing})
if mode=='ok' then
    assert(ok and value=='configured' and type(configured.after_bound)=='function')
    et_InitGame();et_RunFrame();et_ShutdownGame()
    assert(table.concat(trace,',')=='fenced,stats-init,timing-init,stats-frame,timing-frame,stats-stop,timing-stop')
elseif mode=='partial' then
    assert(not ok and et_InitGame==nil and et_RunFrame==nil and et_ShutdownGame==nil)
elseif mode=='existing' then
    assert(not ok and type(et_InitGame)=='function' and configured==nil)
else
    assert(not ok and et_InitGame==nil and configured==nil)
end
assert(not pcall(module.configure,{},{}))
print('combined host '..mode..' OK')
'''


@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
@pytest.mark.parametrize('mode', ['ok', 'partial', 'existing', 'shared'])
def test_load_time_combined_host(tmp_path, lua, mode):
    script = tmp_path / 'host.lua'
    script.write_text(SCRIPT)
    result = subprocess.run([lua, str(script), str(ROOT), mode],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f'combined host {mode} OK' in result.stdout


@pytest.mark.parametrize('mode', ['ok', 'no-delivery'])
def test_whole_source_producers_share_callbacks_and_identity(tmp_path, mode):
    generation = tmp_path / ('a' * 32)
    generation.mkdir(mode=0o700)
    result = subprocess.run(
        ['lua5.4', str(ROOT / 'tests/lua/runtime_combined_source_harness.lua'),
         str(ROOT), str(tmp_path), mode], capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'WHOLE COMBINED SOURCE' in result.stdout
    if mode == 'no-delivery':
        assert 'no ticket, no ACK, no legacy files' in result.stdout
        assert list(tmp_path.iterdir()) == [generation]
        assert not list(generation.iterdir())
        return
    stats = (tmp_path / 'stats.txt').read_text()
    timing = json.loads(next(generation.glob('*.json')).read_text())
    assert 'slomix_round_v1:fixture-server:' in stats
    assert timing['meta']['runtime_identity'] in stats
    assert timing['meta']['actual_duration_seconds'] == 610
