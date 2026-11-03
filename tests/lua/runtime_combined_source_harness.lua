-- Whole shipped producers in one VM; synthetic ET observations/host transport.
-- Real stats and timing files. No engine, listener, Discord or database.
local root, directory, mode = arg[1], arg[2], arg[3]
local native=mode=='native' or mode=='supervisor'
package.path=root..'/vps_scripts/?.lua;'..package.path
if arg[12] then package.path=arg[12]..'/?.lua;'..package.path end
local generation=string.rep('a',32)
local round=string.rep('b',32)
local identity={source_id='fixture-server',match_id=string.rep('c',32),
    round_id=round,first_round_id=round,round_number=1}
if native then identity.source_id=arg[7];identity.match_id=arg[8];identity.round_id=arg[9];identity.first_round_id=arg[9] end
local wire=require('runtime_round_identity').encode(identity)
local state,counter,clock='0','1',1000
local messages,logs={},{}
local values={mapname='supply',g_gametype='3',timelimit='20',g_nextTimeLimit='10',
    sv_maxClients='0',sv_maxclients='0',fs_homepath=directory}
if arg[13] then values.fs_homepath=arg[13] end
et={CS_SERVERINFO=1,CS_MULTI_INFO=2,CS_MULTI_MAPWINNER=3,CS_REINFSEEDS=4,
    CS_INTERMISSION=5,GS_INTERMISSION=3,GS_WARMUP_COUNTDOWN=1,FS_WRITE=1}
function et.trap_Cvar_Get(key)
    if key=='gamestate' then return state end
    if key=='g_currentRound' then return counter end
    return values[key] or ''
end
function et.trap_GetConfigstring(key)
    if key==et.CS_INTERMISSION or key==et.CS_REINFSEEDS then return '' end
    return key
end
function et.Info_ValueForKey(_,key)
    if key=='mapname' then return 'supply' end
    return key=='d' and '1' or '0'
end
function et.RegisterModname() end
function et.G_Print(text) logs[#logs+1]=text end
function et.G_LogPrint() end
function et.gentity_get() return 0 end
local timer=native and require('socket') or nil
local started=timer and timer.gettime() or 0
function et.trap_Milliseconds() return clock+(timer and math.floor((timer.gettime()-started)*1000) or 0) end
local handle,stats_closed,opens=nil,false,0
function et.trap_FS_FOpenFile(path)
    if path=='proximity/frame_health.log' then return 0,-1 end
    local gen,name=path:match('^gamestats/runtime%-snapshots/([0-9a-f]+)/([^/]+)$')
    assert(gen and #gen==32 and name=='2026-09-25-120000-supply-round-'..identity.round_number..'.txt',path)
    if not native then assert(gen==generation) end
    opens=opens+1;assert(opens==1,'stats reopened')
    handle=assert(io.open(native and directory..'/'..gen..'/'..name or directory..'/stats.txt','wb'));return 7,0
end
function et.trap_FS_Write(bytes,count,fd)
    assert(fd==7 and not stats_closed and count==#bytes)
    assert(handle:write(bytes));return count
end
function et.trap_FS_FCloseFile(fd)
    assert(fd==7);assert(handle:close());stats_closed=true
end
local delivery='slomix_stats_bind_v1|'..string.rep('1',32)..'|'..string.rep('2',32)
    ..'|100|'..wire..'|'..generation..'|supply'
-- Only the transport boundary is synthetic. Bootstrap/lease/binding are real.
if not native then package.loaded['runtime_host_channel']={open=function(path)
    local replies={'slomix_bootstrap_context_v1|'..string.rep('1',32)..'|'
        ..string.rep('2',32)..'|fixture-server',mode~='no-delivery' and delivery or nil}
    local index=0
    return {send_line=function(message)
        if message:match('^slomix_stats_closed') then assert(stats_closed) end
        messages[#messages+1]={path=path,wire=message}
    end,receive_line=function() index=index+1;return replies[index] end,close=function() end}
end}
package.preload['socket.unix']=function() return {} end end
if native and arg[14]=='missing-first-timing' then
    local channel=require('runtime_host_channel')
    local open=channel.open
    channel.open=function(path,...)
        if path==arg[5] then error('fixture timing transport unavailable') end
        return open(path,...)
    end
end
local function locate(fn,key,seen)
    seen=seen or {};if seen[fn] then return end;seen[fn]=true
    local children={}
    for index=1,100 do
        local name,value=debug.getupvalue(fn,index);if not name then break end
        if name==key then return value end
        if type(value)=='function' then children[#children+1]=value end
    end
    for _,child in ipairs(children) do local value=locate(child,key,seen);if value~=nil then return value end end
end
local status
if arg[11] then status=dofile(arg[11]) else
status=require('runtime_combined_host').configure({source_id=identity.source_id,
    socket_path=native and arg[4] or '/private/stats',bootstrap_timeout_ms=5000,completion_timeout_ms=1000,
    producer_spool=directory,timing_sockets={[1]=native and arg[5] or '/private/t1',[2]=native and arg[6] or '/private/t2'}}, {
    stats=function() return require('runtime_c0rn_host') end,
    timing=function()
        dofile(root..'/vps_scripts/stats_discord_webhook.lua')
        local config=assert(locate(et_RunFrame,'configuration'))
        config.enabled=false;config.discord_webhook_urls={};config.debug=false
    end})
end
local wall=1700000000
os.time=function() return wall end
os.date=function() return '2026-09-25-120000-' end
os.execute=function() error('unexpected shell execution') end
io.popen=function() error('unexpected legacy queue scan') end
if native then
    print('READY');io.stdout:flush()
    assert(io.read('*l')==(mode=='supervisor' and 'map supply' or 'start'),'host did not release init')
    for half=1,2 do
        identity.round_number=half;counter=tostring(2-half);state='0'
        clock=1000;wall=1700000000+(half-1)*1200;started=timer.gettime()
        opens=0;stats_closed=false
        et_InitGame(half*100,1,half-1)
        local phase,reason
        repeat
            et_RunFrame(1000)
            phase,reason=status.bootstrap_status()
            if phase=='context' or phase=='delivery' then timer.sleep(.001) end
        until phase~='context' and phase~='delivery'
        assert(phase=='accepted',tostring(phase)..':'..tostring(reason))
        if mode~='supervisor' then assert(io.read('*l')=='finish','host did not release writer') end
        clock=611000;wall=wall+610;state='3';counter=tostring(half-1)
        et_RunFrame(611000);et_RunFrame(614000);et_ShutdownGame(0)
        assert(opens==1 and stats_closed and status.completion_status()=='sent_unconfirmed')
        print('NATIVE WHOLE SOURCE half '..half..' closed');io.stdout:flush()
        if mode~='supervisor' or half==2 then
            assert(io.read('*l')==(half==1 and 'next' or 'done'),'host did not complete half')
        end
    end
    for _,message in ipairs(logs) do assert(not message:find('crashed:',1,true),message) end
    return
end
et_InitGame(100,1,0)
et_RunFrame(1000);et_RunFrame(1050)
local phase,reason=status.bootstrap_status()
if mode=='no-delivery' then
    assert(phase=='delivery',tostring(phase)..':'..tostring(reason))
    clock=611000;wall=1700000610;state='3';counter='0'
    et_RunFrame(611000);et_RunFrame(614000);et_ShutdownGame(0)
    assert(opens==0 and #messages==1,'unbound producer escaped runtime fence')
    print('WHOLE COMBINED SOURCE: no ticket, no ACK, no legacy files')
    return
end
assert(phase=='accepted',tostring(phase)..':'..tostring(reason))
assert(messages[2].wire==delivery:gsub('^slomix_stats_bind_v1','slomix_stats_ack_v1'))
-- Real callback transition and both real writers; no extracted function bodies.
clock=611000;wall=1700000610;state='3';counter='0'
et_RunFrame(611000);et_RunFrame(614000);et_ShutdownGame(0)
assert(opens==1 and stats_closed and status.completion_status()=='sent_unconfirmed')
local stats_notice,timing_notice=0,0
for _,message in ipairs(messages) do
    if message.wire:match('^slomix_stats_closed_v1|') then
        assert(message.path=='/private/stats');stats_notice=stats_notice+1
    elseif message.wire:match('^slomix_timing_closed_v1|') then
        assert(message.path=='/private/t1');timing_notice=timing_notice+1
    end
end
assert(stats_notice==1 and timing_notice==1,'missing or duplicate completion')
for _,message in ipairs(logs) do assert(not message:find('crashed:',1,true),message) end
print('WHOLE COMBINED SOURCE: bootstrap accepted, stats/timing closed once')
