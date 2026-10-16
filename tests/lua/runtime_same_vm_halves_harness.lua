-- Actual shipped hooks/bootstrap/lease/writer/completion in ONE Lua VM.
-- ET observations and local transport are synthetic; no actual engine is run.
local root, directory = arg[1], arg[2]
package.path = root .. '/vps_scripts/?.lua;' .. package.path
package.preload['socket.unix'] = function() return {} end
local half, state, counter, intermission = 1, '2', 1, ''
local opens, closes, completions, observations = 0, 0, {}, {}
local handle = nil
local process, lifecycle = string.rep('1',32), string.rep('2',32)
local match, first, second = string.rep('a',32), string.rep('b',32), string.rep('c',32)
local function generation() return string.rep(half==1 and 'd' or 'e',32) end
et = {CS_SERVERINFO=1, CS_MULTI_INFO=2, CS_MULTI_MAPWINNER=3, FS_WRITE=1,
      CS_REINFSEEDS=4, CS_INTERMISSION=5, GS_INTERMISSION=3, GS_WARMUP_COUNTDOWN=1}
function et.trap_GetConfigstring(key)
    if key==et.CS_REINFSEEDS then return '' end
    if key==et.CS_INTERMISSION then return intermission end
    return key
end
function et.Info_ValueForKey(_, key) return key=='mapname' and 'supply' or '0' end
function et.trap_Cvar_Get(key)
    if key=='g_currentRound' then return tostring(counter) end
    if key=='gamestate' then return state end
    if key=='g_gametype' then return '3' end
    if key=='sv_maxClients' then return '0' end
    if key=='timelimit' then return '20' end
    if key=='g_nextTimeLimit' then return '10' end
    return 'x'
end
function et.RegisterModname() end
function et.G_Print() end
function et.G_LogPrint() end
function et.trap_Milliseconds() return half*1000 end
function et.trap_FS_FOpenFile(path)
    if path=='proximity/frame_health.log' then return 0,-1 end
    assert(path=='gamestats/runtime-snapshots/'..generation()..'/2026-09-25-120000-supply-round-'..half..'.txt')
    opens=opens+1
    assert(opens==half, 'generation reopened')
    handle=assert(io.open(directory..'/round-'..half..'.txt','wb'))
    return 7,0
end
function et.trap_FS_Write(bytes,count,fd)
    assert(fd==7 and count==#bytes); assert(handle:write(bytes)); return count
end
function et.trap_FS_FCloseFile(fd)
    assert(fd==7); assert(handle:close()); handle=nil; closes=closes+1
end
-- Exercise the real bootstrap protocol and real completion sender, replacing
-- only the socket channel. Each bootstrap connection returns explicit pins.
package.loaded.runtime_host_channel={open=function()
    local queue, index = {},0
    return {send_line=function(wire)
        if wire:find('slomix_init_v1|',1,true)==1 then
            observations[#observations+1]=wire
            assert(wire=='slomix_init_v1|'..half*1000 ..'|supply|'..half, 'wrong ET start counter mapping')
            local identity=require('runtime_round_identity').encode({source_id='fixture',match_id=match,
                round_id=half==1 and first or second,first_round_id=first,round_number=half})
            queue={'slomix_bootstrap_context_v1|'..process..'|'..lifecycle..'|fixture',
                'slomix_stats_bind_v1|'..process..'|'..lifecycle..'|'..half*1000 ..'|'..identity..'|'..generation()..'|supply'}
        elseif wire:find('slomix_stats_closed_v1|',1,true)==1 then
            assert(handle==nil and closes==half, 'completion preceded writer close')
            completions[#completions+1]=wire
        else assert(wire:find('slomix_stats_ack_v1|',1,true)==1) end
    end,receive_line=function() index=index+1; return queue[index] end,close=function() end}
end}
local status=require('runtime_c0rn_host').configure({source_id='fixture',socket_path='/explicit/local',
    bootstrap_timeout_ms=1000,completion_timeout_ms=1000})
os.date=function() return '2026-09-25-120000-' end
for current=1,2 do
    half=current; counter=2-half; state='2'
    et_InitGame(half*1000-1,1,1)
    assert(status.bootstrap_status()=='waiting_playing_init')
    assert(not pcall(SaveStats), 'warmup inherited old ticket')
    state='0'
    et_InitGame(half*1000,1,1)
    et_RunFrame(1234); et_RunFrame(1235)
    assert(status.bootstrap_status()=='accepted', 'fresh half could not bind')
    assert(not pcall(CaptureRuntimeStatsHostInit), 'same init obtained another lease')
    max_clients=0; roundStart=1000; roundEnd=611000; pausedTime={[3]=10000}
    SaveStats()
    assert(status.completion_status()=='sent_unconfirmed')
    assert(not pcall(SaveStats), 'same generation retried')
    assert(opens==half and closes==half and #completions==half)
    et_ShutdownGame(1)
end
assert(#observations==2 and #completions==2 and opens==2 and closes==2)
assert(completions[1]:find(string.rep('d',32),1,true) and completions[2]:find(string.rep('e',32),1,true))
print('SAME VM: ET counter 1 -> R1 and 0 -> R2; warmup fenced; 2 bootstrap leases; 2 closed files; 2 distinct one-shot completions')
