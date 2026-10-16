-- Load the WHOLE shipped c0rn module; only ET bindings/game observations are fake.
-- Real temporary files, real SaveStats, real optional header/completion modules.
local root, directory, source, match, first, second, half_text, generation, scenario, wire = (table.unpack or unpack)(arg)
local expected_process, expected_lifecycle = string.rep("1",32), string.rep("2",32)
local unix_path = wire and wire:sub(1,6) == "@unix:" and wire:sub(7) or nil
local bootstrap_path = wire and wire:sub(1,11) == "@bootstrap:" and wire:sub(12) or nil
local hooks_path = wire and wire:sub(1,7) == "@hooks:" and wire:sub(8) or nil
local host_handshake = wire == "@stdin" or unix_path ~= nil
local observation_wire, init_configure
local observed_init_time = tonumber(arg[12] or "0")
local half = tonumber(half_text)
local required_entrypoint = arg[11] == "required-entrypoint"
local configured_host = arg[15] == "configured-host"
local legacy_scenario = scenario == "legacy" or scenario:sub(1,12) == "legacy-late-"
local bound = scenario:sub(1, 6) == "bound-"
local fault = bound and scenario:sub(7) or scenario
local state, counter, map, exit_flag, gametype = "0", half - 1, "supply", "", "3"
if scenario == "bound-stale-intermission" then exit_flag = "1" end
local opens = 0
local success = scenario == "ok" or scenario == "legacy" or scenario == "bound-frame"
    or scenario == "bound-shutdown" or scenario == "bound-mutate" or scenario == "bound-repeat"
    or scenario == "bound-ipc" or scenario == "bound-ipc-retry" or scenario == "bound-stale-intermission"
local ipc_sender, ipc_acks = nil, 0
package.path = root .. "/vps_scripts/?.lua;" .. package.path
local handle, writes, emitted, closed, opened = nil, 0, false, false, false
local ticket, hook_clock, completion_sender
et = {CS_SERVERINFO=1, CS_MULTI_INFO=2, CS_MULTI_MAPWINNER=3, FS_WRITE=1,
      CS_REINFSEEDS=4, CS_INTERMISSION=5, GS_INTERMISSION=3, GS_WARMUP_COUNTDOWN=1}
function et.trap_GetConfigstring(v)
    if v == et.CS_REINFSEEDS then return "" end
    if v == et.CS_INTERMISSION then return exit_flag end
    return v
end
function et.RegisterModname(_) end
function et.G_Print(_) end
function et.trap_Milliseconds() return 611000 end
function et.Info_ValueForKey(_, key)
    if key == "mapname" then return map end
    return key == "d" and "1" or "0"
end
function et.trap_Cvar_Get(key)
    -- Force the OPPOSITE completed-half value: explicit binding must win,
    -- including shutdown before a completed-half cvar flip.
    if key == "g_currentRound" then
        if bound then return tostring(counter) end
        if legacy_scenario then return half == 1 and "1" or "0" end
        return half == 1 and "0" or "1"
    end
    if key == "timelimit" then return "20" end
    if key == "g_nextTimeLimit" then return "10" end
    if key == "sv_maxClients" then return "0" end
    if key == "gamestate" then return state end
    if key == "g_gametype" then return gametype end
    return "x"
end
function et.trap_FS_FOpenFile(path)
    if path == "proximity/frame_health.log" then return 0, -1 end
    local expected = "gamestats/runtime-snapshots/" .. generation
        .. "/2026-09-25-120000-supply-round-" .. half .. ".txt"
    if legacy_scenario then expected = "gamestats/2026-09-25-120000-supply-round-" .. half .. ".txt" end
    opened = true
    opens = opens + 1
    assert(path == expected, "unexpected path or half (binding not honored)")
    assert(opens == 1, "runtime generation reopened")
    if fault == "open-error" or scenario == "legacy-late-open-error" then return 0, -1 end
    handle = assert(io.open(directory .. "/2026-09-25-120000-supply-round-" .. half .. ".txt", "wb"))
    return 7, 0
end
function et.trap_FS_Write(bytes, count, fd)
    assert(fd == 7 and not closed and count == #bytes)
    writes = writes + 1
    if fault == "write-error" then error("fixture write error") end
    if fault == "short-write" and writes == 2 then
        assert(handle:write(bytes:sub(1, 2)))
        return 2
    end
    assert(handle:write(bytes:sub(1, count)))
    return count
end
function et.trap_FS_FCloseFile(fd)
    assert(fd == 7 and not emitted)
    assert(handle:close()); closed = true
    if fault == "close-error" then error("fixture close error") end
end
function et.G_LogPrint(_) end
local host_adapter
if configured_host then
    assert(required_entrypoint and hooks_path and arg[13]==hooks_path)
    host_adapter = require("runtime_c0rn_host")
else
    dofile(root .. (required_entrypoint and "/vps_scripts/runtime_c0rn_entrypoint.lua" or "/vps_scripts/c0rnp0rn8.lua"))
end
if hooks_path then
    assert(required_entrypoint)
    hook_clock = require("socket")
    -- Test clock only; production adapter captures the actual ET monotonic API.
    et.trap_Milliseconds = function() return hook_clock.gettime()*1000 end
    if configured_host then
        local options = {source_id=source, socket_path=hooks_path,
            bootstrap_timeout_ms=5000, completion_timeout_ms=1000}
        local invalid = arg[16]
        if invalid then
            if invalid=="source" then options.source_id="bad source"
            elseif invalid=="path" then options.socket_path="relative"
            elseif invalid=="bootstrap-timeout" then options.bootstrap_timeout_ms=0
            elseif invalid=="completion-timeout" then options.completion_timeout_ms=0
            elseif invalid=="unknown" then options.extra=true
            elseif invalid=="missing" then options=nil
            elseif invalid=="clock" then et.trap_Milliseconds=nil
            elseif invalid=="late" then et_InitGame(observed_init_time,1,0)
            elseif invalid=="dependency" then
                package.loaded["socket.unix"]=nil
                package.preload["socket.unix"]=function() error("fixture missing LuaSocket") end
            else error("unknown invalid adapter fixture") end
            assert(not pcall(host_adapter.configure,options), "invalid host config accepted")
            assert(not pcall(host_adapter.configure,{source_id=source,socket_path=hooks_path,
                bootstrap_timeout_ms=5000,completion_timeout_ms=1000}), "failed config retried")
            assert(not pcall(SaveStats), "failed host adapter restored legacy writer")
            assert(opens==0 and not opened and not emitted)
            print("HOST ADAPTER configuration refused, writer fenced, no files")
            return
        end
        local status = host_adapter.configure(options)
        options.source_id="mutated"; options.socket_path="/wrong" -- Configuration is copied, not retained.
        completion_sender = {status=status.completion_status}
        assert(status.bootstrap_status()=="waiting_init")
        assert(not pcall(host_adapter.configure, {}), "host adapter configured twice")
    elseif arg[13] then
        completion_sender = require("runtime_host_completion").sender(arg[13], et.trap_Milliseconds, 1000)
    end
    if not configured_host then
        ConfigureRuntimeStatsHostHooks({source_id=source,socket_path=hooks_path,
            timeout_ms=fault=="hooks-timeout" and 50 or 5000,
            completed=function(...) return ticket.completed(...) end})
    end
    assert(RuntimeStatsHostStatus()=="waiting_init")
    local loaded_require = require
    require = function(name)
        assert(package.loaded[name], "dependency loaded inside engine callback: " .. name)
        return loaded_require(name)
    end
end
if bound and fault ~= "noinit" and fault ~= "ipc-noinit" and fault ~= "required-noinit"
    and fault ~= "ipc-lease-noinit" then
    if fault == "warmup-init" then state = "1" end
    if fault == "hooks-warmup" then
        state = "2"
        et_InitGame(observed_init_time - 1, 1, 0)
        assert(RuntimeStatsHostStatus() == "waiting_playing_init")
        state = "0"
        et_RunFrame(1234)
        assert(RuntimeStatsHostStatus() == "waiting_playing_init",
            "frame change incorrectly started host capture")
        print("WARMUP HELD UNTIL FRESH INIT"); io.stdout:flush()
    end
    et_InitGame(observed_init_time, 1, 0)
    state = "0"
end
max_clients=0; roundStart=1000; roundEnd=611000; pausedTime={[3]=10000}
os.date=function(_) return "2026-09-25-120000-" end

-- Supply synthetic player observations through the actual closure's stats table.
local found = false
for index = 1, 100 do
    local name, value = debug.getupvalue(SaveStats, index)
    if not name then break end
    if name == "stats" then
        value["12345678"] = "12345678\\Player\\1\\1\\1 "
            .. half .. " " .. half .. " " .. half .. " " .. half .. " " .. half .. "\n"
        found = true
    end
end
assert(found, "actual SaveStats stats upvalue missing")
local identity = {source_id=source, match_id=match, round_id=half == 1 and first or second,
                  round_number=half, first_round_id=first}
ticket = {identity=identity, generation=generation, map_name="supply", completed=function(receipt, returned_generation)
    assert(closed and writes == 2 and returned_generation == generation)
    if fault == "notify-error" then error("fixture notification error") end
    if completion_sender then completion_sender.completed(receipt, returned_generation) end
    emitted = true
    print(string.format('receipt {"generation":"%s","completion":{"version":1,"filename":"%s","bytes":%d,"state":"writer_closed"}}',
        returned_generation, receipt.filename, receipt.bytes))
end}
if hooks_path then
    local status, reason
    repeat
        et_RunFrame(1234)
        status, reason = RuntimeStatsHostStatus()
        if status == "context" or status == "delivery" then hook_clock.sleep(.001) end
    until status ~= "context" and status ~= "delivery"
    print("ENGINE HOOK BOOTSTRAP " .. status .. " " .. tostring(reason)); io.stdout:flush()
    if fault ~= "hooks-no-server" and fault ~= "hooks-timeout" then
        assert(io.read("*l") == "finish", "test host did not release child")
    end
    if status == "accepted" then
        round_started=true
        local wrote, failure = pcall(function()
            if fault=="hooks-shutdown" then et_ShutdownGame(0)
            else
                counter=1-counter; state="3"
                et_RunFrame(611000); et_RunFrame(614000)
            end
        end)
        if configured_host then emitted = completion_sender.status()=="sent_unconfirmed" end
        if arg[14]=="no-receiver" then
            assert(not wrote and tostring(failure):find("host channel connect failed",1,true))
            assert(opens==1 and closed and not emitted and completion_sender.status()=="failed")
            et_ShutdownGame(0); et_RunFrame(615000)
            assert(opens==1 and not pcall(SaveStats), "failed notification allowed rewrite")
            print("WRITER CLOSE failed; closed stats retained without receipt")
            return
        end
        assert(wrote, tostring(failure))
        assert(opens==1 and closed and emitted, "engine hooks did not finish actual stats writer")
        et_ShutdownGame(0); et_RunFrame(615000)
        assert(opens==1, "engine hooks wrote twice")
        print("ENGINE HOOK FULL WRITER completed opens=" .. opens)
        if completion_sender then
            assert(completion_sender.status()=="sent_unconfirmed")
            print("WRITER CLOSE sent_unconfirmed"); io.stdout:flush()
            assert(io.read("*l")=="receipt", "host did not finish authenticated receipt")
        end
    else
        assert((fault=="hooks-no-server" or fault=="hooks-timeout") and status=="failed")
        round_started=true; state="3"
        et_RunFrame(611000); et_RunFrame(614000); et_ShutdownGame(0)
        assert(opens==0 and not emitted, "failed engine bootstrap allowed stats IO")
    end
    return
end
if bootstrap_path then
    assert(required_entrypoint)
    local clock = require("socket")
    local host = require("runtime_host_channel")
    local bootstrap = require("runtime_host_bootstrap")
    local client = bootstrap.start(CaptureRuntimeStatsHostInit, function()
        local connection = host.open(bootstrap_path,function() return clock.gettime()*1000 end,5000)
        if fault == "host-ack-error" then
            local send = connection.send_line
            connection.send_line = function(message)
                if message:find("slomix_stats_ack_v1",1,true) then error("fixture ACK failure") end
                return send(message)
            end
        end
        return connection
    end, fault == "host-source" and "wrong-source" or source, ticket.completed)
    assert(not pcall(CaptureRuntimeStatsInit), "IPC lease bypassed host claim")
    assert(not pcall(CaptureRuntimeStatsHostInit), "host lease recaptured")
    if fault == "host-stale" then et_InitGame(observed_init_time,2,1) end
    if fault == "host-shutdown" then et_ShutdownGame(1) end
    local status, reason
    repeat
        status, reason = client.poll()
        if status == "context" or status == "delivery" then clock.sleep(.001) end
    until status ~= "context" and status ~= "delivery"
    assert(client.poll() == status, "terminal bootstrap retried")
    print("HOST BOOTSTRAP " .. status .. " " .. tostring(reason)); io.stdout:flush()
    assert(io.read("*l") == "finish", "test host did not release child")
    if status == "accepted" or fault == "host-ack-error" then
        assert(status == (fault == "host-ack-error" and "unconfirmed" or "accepted"))
        SaveStats()
        assert(opens==1 and closed and emitted, "accepted host bootstrap did not write")
        assert(not pcall(SaveStats), "host bootstrap allowed another write")
        print("HOST FULL MODULE wrote stats and completion")
    else
        assert(not pcall(SaveStats), "failed bootstrap allowed unbound write")
        assert(not opened and not emitted and opens==0)
    end
    return
end
if host_handshake then
    -- Actual source callback observation; keep its opaque lease in this Lua VM.
    -- Private test pipe only, NOT a deployed/authenticated ET transport.
    observation_wire, init_configure = CaptureRuntimeStatsInit()
    if unix_path then
        local clock = require("socket")
        -- Wall clock used ONLY in this short-lived fixture; engine adapter
        -- must supply et.trap_Milliseconds and fail closed on wrap/backwards.
        local channel = require("runtime_host_channel").open(unix_path,
            function() return clock.gettime()*1000 end, 5000)
        channel.send_line(observation_wire)
        local function read_host()
            while true do
                local line = channel.receive_line()
                if line then return line end
                clock.sleep(0.001) -- Test driver, NEVER a game callback.
            end
        end
        wire, expected_process, expected_lifecycle = read_host(), read_host(), read_host()
        channel.close()
        assert(io.read("*l") == "finish", "test parent did not release child")
    else
        print("HOST_READY"); print("INIT " .. observation_wire); io.stdout:flush()
        wire = assert(io.read("*l"), "host wire missing")
        expected_process = assert(io.read("*l"), "host process expectation missing")
        expected_lifecycle = assert(io.read("*l"), "host lifecycle expectation missing")
    end
end
if scenario == "bad-identity" then identity.round_number = 0 end
if scenario == "bad-ticket" then ticket.unexpected = true end
if scenario == "bad-map" then ticket.map_name = "radar" end
if scenario == "bad-generation" then ticket.generation = "../unsafe" end
if scenario == "bad-callback" then ticket.completed = nil end
if scenario == "legacy" then ticket = nil end
local ok, failure
if scenario:sub(1,12) == "legacy-late-" then
    assert(not required_entrypoint)
    local written = pcall(SaveStats)
    assert(written == (scenario ~= "legacy-late-open-error"))
    assert(opens==1 and not emitted)
    if scenario=="legacy-late-config" then
        assert(not pcall(ConfigureRuntimeStatsIPC,{},ticket.completed), "late IPC opt-in accepted")
    elseif scenario=="legacy-late-bind" then
        assert(not pcall(BindRuntimeStats,ticket), "late direct binding accepted")
    else
        assert(not pcall(RequireRuntimeStatsBinding), "late required-mode opt-in accepted")
    end
    assert(not pcall(SaveStats,ticket), "runtime write after legacy attempt accepted")
    assert(not pcall(SaveStats), "late opt-in failure restored legacy output")
    assert(opens==1 and not emitted, "late opt-in caused a second file open")
    print("LATE OPT-IN fenced " .. scenario .. " opens=" .. opens)
    return
end
if fault:sub(1,9) == "required-" then
    assert(required_entrypoint)
    if fault=="required-reinit" then et_InitGame(0,2,1) end
    if fault=="required-bind-failure" then
        ticket.map_name="wrong-map"
        assert(not pcall(BindRuntimeStats,ticket), "invalid direct binding accepted")
    end
    assert(not pcall(SaveStats), "required entrypoint allowed legacy output")
    assert(not pcall(SaveStats,ticket), "direct ticket bypassed required binding")
    assert(not opened and opens==0, "load-time fence allowed stats IO")
    RequireRuntimeStatsBinding() -- Check idempotence only AFTER the load-time fence.
    round_started=true; saved_stats=false; state="3"
    et_ShutdownGame(0); et_RunFrame(611000); et_RunFrame(614000)
    assert(not opened and not emitted and opens==0, "required callbacks attempted stats IO")
    assert(not et_IPCReceive(1,wire), "unconfigured entrypoint accepted IPC")
    print("REQUIRED ENTRYPOINT fenced " .. fault .. " opens=" .. opens)
    return
end
if bound then
    if fault == "warmup-now" then state = "1" end
    if fault == "queued" then exit_flag = "1" end
    if fault == "counter" then counter = 1 - counter end
    if fault == "map" then map = "radar" end
    if fault == "gametype" then gametype = "2" end
    local rejected = fault == "noinit" or fault == "warmup-init" or fault == "warmup-now"
        or fault == "queued" or fault == "counter" or fault == "map" or fault == "gametype"
    local accepted, id, gen
    if fault:sub(1,3) == "ipc" then
        local protocol = require("runtime_stats_delivery")
        local authority = {peer_slot=1, peer_name="authority", peer_signature=string.rep("a",40),
            process_epoch=expected_process, lifecycle_epoch=expected_lifecycle, init_time=observed_init_time, source_id=source}
        local consumer = {}
        for k,v in pairs(authority) do consumer[k]=v end
        consumer.peer_slot=2; consumer.peer_name="c0rn"; consumer.peer_signature=string.rep("b",40)
        function et.FindMod(slot)
            if slot==1 then return "authority", string.rep("a",40) end
            assert(slot==2); return "c0rn", string.rep("b",40)
        end
        function et.IPCSend(slot, message)
            if slot==2 then et_IPCReceive(1,message); return 1 end
            assert(slot==1); ipc_acks=ipc_acks+1
            assert(ipc_sender.receive(2,message)); return 1
        end
        if fault=="ipc-noinit" then
            assert(not pcall(ConfigureRuntimeStatsIPC,authority,ticket.completed), "IPC configured without InitGame")
            assert(not pcall(SaveStats), "failed IPC configuration fell back to legacy")
            assert(not opened and not emitted)
            return
        end
        if fault=="ipc-lease-noinit" then
            local available, reason = pcall(CaptureRuntimeStatsInit)
            assert(not available and tostring(reason):find("observation unavailable",1,true))
            assert(not pcall(SaveStats) and not opened and not emitted)
            return
        end
        if fault:sub(1,10)=="ipc-lease-" then
            assert(required_entrypoint)
            local observation, configure = CaptureRuntimeStatsInit()
            assert(observation == "slomix_init_v1|" .. observed_init_time .. "|supply|" .. half)
            assert(not pcall(CaptureRuntimeStatsInit), "second lease captured for same InitGame")
            assert(not pcall(ConfigureRuntimeStatsIPC,authority,ticket.completed), "direct config bypassed lease")
            assert(not pcall(BindRuntimeStats,ticket), "direct bind bypassed lease")
            local expected_error = "InitGame lease invalidated"
            if fault=="ipc-lease-stale" then et_InitGame(observed_init_time,2,1)
            elseif fault=="ipc-lease-shutdown" then et_ShutdownGame(1)
            elseif fault=="ipc-lease-bad-config" then authority.peer_slot=64; expected_error="invalid peer slot"
            elseif fault=="ipc-lease-duplicate" then
                configure(authority,ticket.completed)
                expected_error="InitGame lease already consumed"
            elseif fault=="ipc-lease-map" then map="radar"; expected_error="live context disagrees"
            elseif fault=="ipc-lease-half" then counter=1-counter; expected_error="live context disagrees"
            elseif fault=="ipc-lease-state" then state="1"; expected_error="live context disagrees"
            elseif fault=="ipc-lease-gametype" then gametype="2"; expected_error="live context disagrees"
            elseif fault=="ipc-lease-exit" then exit_flag="1"; expected_error="live context disagrees"
            else error("unknown lease fixture") end
            local configured, reason = pcall(configure,authority,ticket.completed)
            assert(not configured, "invalid or stale InitGame lease configured")
            assert(tostring(reason):find(expected_error,1,true), tostring(reason))
            authority.peer_slot=1; map="supply"; counter=half-1; state="0"; gametype="3"; exit_flag=""
            local retried, retry_error = pcall(configure,authority,ticket.completed)
            assert(not retried and tostring(retry_error):find("already consumed",1,true), "lease retry allowed")
            assert(not pcall(SaveStats) and not opened and not emitted)
            print("INIT LEASE " .. fault .. " rejected; opens=" .. opens)
            return
        end
        if fault:sub(1,12)=="ipc-invalid-" then
            local callback = ticket.completed
            if fault=="ipc-invalid-peer" then authority.peer_slot=64
            elseif fault=="ipc-invalid-init" then authority.init_time=1
            elseif fault=="ipc-invalid-callback" then callback=nil
            elseif fault=="ipc-invalid-module" then
                package.loaded.runtime_stats_delivery=nil
                package.preload.runtime_stats_delivery=function() error("fixture dependency unavailable") end
            else error("unknown invalid config fixture") end
            assert(not pcall(ConfigureRuntimeStatsIPC,authority,callback), "invalid config accepted")
            assert(not pcall(SaveStats), "failed IPC configuration fell back to legacy")
            assert(not opened, "failed IPC configuration attempted legacy file IO")
            round_started=true; state="3"
            et_ShutdownGame(0); et_RunFrame(611000); et_RunFrame(614000)
            assert(not opened and not emitted and ipc_acks==0, "failed config callback wrote stats")
            print("FAILED CONFIG fenced " .. fault .. " opens=" .. opens)
            return
        end
        if required_entrypoint and not init_configure then
            observation_wire, init_configure = CaptureRuntimeStatsInit()
            assert(observation_wire == "slomix_init_v1|" .. observed_init_time .. "|supply|" .. half)
            assert(not pcall(ConfigureRuntimeStatsIPC,authority,ticket.completed), "direct config bypassed lease")
        end
        (init_configure or ConfigureRuntimeStatsIPC)(authority, ticket.completed)
        assert(not pcall(ConfigureRuntimeStatsIPC, authority, ticket.completed), "reconfigured IPC pins")
        if fault=="ipc-missing" then
            round_started=true; state="3"
            et_ShutdownGame(0); et_RunFrame(611000); et_RunFrame(614000)
            assert(not pcall(SaveStats), "missing IPC binding fell back to legacy")
            assert(not opened and not emitted)
            return
        end
        ipc_sender=protocol.sender(et,consumer,wire)
        assert(ipc_sender.send() and ipc_sender.status()=="pending" and ipc_acks==0)
        if fault=="ipc-reset" then
            et_InitGame(0,2,1)
            assert(not et_IPCReceive(1,wire), "receiver survived unexpected InitGame")
            round_started=true; state="3"
            et_ShutdownGame(0); et_RunFrame(611000); et_RunFrame(614000)
            assert(not pcall(SaveStats), "invalidated IPC binding was used")
            assert(not opened and not emitted and ipc_acks==0)
            return
        end
        if fault=="ipc-retry" then assert(ipc_sender.send() and ipc_acks==0) end
        accepted,id,gen=true,identity.round_id,generation
    else
        accepted,id,gen=pcall(BindRuntimeStats,ticket)
    end
    assert(accepted == not rejected, tostring(id))
    if rejected then
        assert(not opened and not emitted)
        print("binding rejected " .. fault)
        return
    end
    assert(id == identity.round_id and gen == generation)
    assert(not pcall(BindRuntimeStats, ticket), "duplicate binding accepted")
    if fault == "mutate" then
        identity.round_number = 0
        ticket.generation = "../evil"
        ticket.map_name = "radar"
        ticket.completed = function() error("mutable callback leaked into binding") end
    end
    if fault == "reinit" then
        et_InitGame(0, 2, 1)
        assert(not pcall(SaveStats), "binding survived unexpected InitGame")
        round_started = true
        state = "3"
        et_ShutdownGame(0)
        et_RunFrame(611000)
        et_RunFrame(614000)
        assert(not opened and not emitted)
        return
    end
    -- Engine flips this before intermission; the frozen active-start half wins.
    counter = 1 - counter
    state = "3"
    round_started = true
    if fault == "shutdown" then
        ok, failure = pcall(et_ShutdownGame, 0)
    else
        et_RunFrame(611000)
        if ipc_sender then assert(ipc_acks==0 and ipc_sender.status()=="pending") end
        ok, failure = pcall(et_RunFrame, 614000)
        if ipc_sender then assert(ipc_acks==1 and ipc_sender.status()=="accepted") end
    end
    -- Both callback routes, including after a failed first attempt, are inert.
    et_ShutdownGame(0)
    et_RunFrame(620000)
    assert(opens == 1, "hook retried a consumed write")
    assert(not pcall(SaveStats), "direct call rewrote a consumed generation")
    assert(opens == 1, "direct call reopened a consumed generation")
else
    ok, failure = pcall(SaveStats, ticket)
    if scenario == "ok" then
        assert(not pcall(SaveStats, ticket), "explicit ticket rewrote a consumed generation")
        assert(not pcall(SaveStats), "explicit runtime attempt fell back to legacy")
        assert(opens == 1, "direct retry reopened a consumed generation")
    end
end
assert(ok == success, tostring(failure))
assert(emitted == (success and scenario ~= "legacy"))
if scenario == "legacy" then
    assert(closed and not package.loaded.runtime_round_identity and not package.loaded.runtime_completed_stats)
end
if scenario:find("bad-", 1, true) then assert(not opened) end
if fault == "write-error" or fault == "short-write" or fault == "close-error" then assert(closed) end
print("writer " .. tostring(ok) .. " opened " .. tostring(opened) .. " closed " .. tostring(closed))
if ipc_sender then print("IPC FULL MODULE accepted; close receipt is not import acknowledgement") end
