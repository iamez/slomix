-- Deterministic hook order/fault proof. Native socket/full writer proof is separate.
local root, fault = arg[1], arg[2]
package.path = root .. "/vps_scripts/?.lua;" .. package.path
local events, polls, connects, closes, captures = {}, 0, 0, 0, 0
local current, tick, state = nil, 100, "0"
local reports = {}
local function event(name) events[#events+1] = name end
et = {G_Print=function(message) reports[#reports+1] = message end,
    trap_Milliseconds=function() return tick end,
    trap_Cvar_Get=function(key) assert(key=="gamestate"); return state end}
function et_InitGame(time, seed, restart)
    event("init")
    assert(time == 7 and seed == 8 and restart == 9)
    if fault == "init-error" then error("original init error",0) end
    current = {}
end
function et_RunFrame(time)
    event("frame")
    assert(time == 123)
    if fault == "frame-error" then error("original frame error",0) end
    return "frame-result"
end
function et_ShutdownGame(restart)
    event("shutdown")
    assert(restart == 1 and closes == connects)
    if fault == "shutdown-error" then error("original shutdown error",0) end
    current = nil
    return "shutdown-result"
end
function CaptureRuntimeStatsHostInit()
    assert(current, "no init")
    if fault == "capture-error" then
        error("live context disagrees with InitGame observation PRIVATE_PAYLOAD", 0)
    end
    captures = captures + 1
    return "observation", function() end
end
package.preload["socket.unix"] = function()
    event("preload")
    if fault == "dependency" then error("dependency unavailable") end
    return {}
end
package.loaded.runtime_host_channel = {open=function(path, now, timeout)
    assert(path == "/explicit/socket" and now() == tick and timeout == 250)
    connects = connects + 1
    event("open")
    return {}
end}
package.loaded.runtime_host_bootstrap = {start=function(capture, open, source, completed)
    assert(source == "test-source" and type(completed) == "function")
    event("capture")
    capture()
    open()
    local closed = false
    return {
        poll=function() assert(not closed); polls=polls+1; event("poll"); return "context" end,
        status=function() return "context" end,
        close=function() assert(not closed); closed=true; closes=closes+1; event("close") end,
    }
end}
local hooks = require("runtime_host_hooks").attach()
local options = {source_id="test-source",socket_path="/explicit/socket",timeout_ms=250,completed=function() end}
if fault:sub(1,5) == "late-" then
    local what = fault:sub(6)
    if what == "init" then et_InitGame(7,8,9)
    elseif what == "frame" then et_RunFrame(123)
    else et_ShutdownGame(1) end
    assert(not pcall(hooks.configure, options), "late configuration accepted")
    assert(connects==0 and captures==0)
    return
end
if fault == "invalid" then options.extra = true end
local configured = pcall(hooks.configure, options)
assert(configured == (fault~="invalid" and fault~="dependency"))
assert(not pcall(hooks.configure, options), "configuration retried")
if not configured then
    assert(hooks.status()=="configuration_failed")
    et_InitGame(7,8,9); et_RunFrame(123); et_ShutdownGame(1)
    assert(connects==0 and captures==0)
    return
end
options.source_id="mutated"; options.socket_path="/wrong"; options.timeout_ms=100000
assert(hooks.status()=="waiting_init")
if fault:sub(1,6)=="state-" then
    state = fault:sub(7)
    et_InitGame(7,8,9)
    local expected = (state=="3" or state=="bad") and "failed" or "waiting_playing_init"
    assert(hooks.status()==expected, "non-playing InitGame misclassified")
    assert(connects==0 and captures==0, "non-playing InitGame consumed host lease")
    state="0"
    for _=1,10 do et_RunFrame(123) end
    assert(connects==0 and captures==0, "frame state change forged InitGame")
    et_InitGame(7,8,9)
    assert(connects==1 and captures==1 and hooks.status()=="context")
    et_ShutdownGame(1)
    assert(closes==1)
    print("NONPLAYING INIT FENCED " .. fault .. " -> fresh playing InitGame")
    return
end
if fault == "no-init" then
    for _=1,100 do et_RunFrame(123) end
    assert(hooks.status()=="waiting_init" and connects==0 and captures==0)
    return
end
local ok, result = pcall(et_InitGame,7,8,9)
if fault == "capture-error" then
    assert(ok and hooks.status()=="failed")
    for _=1,100 do et_RunFrame(123) end
    assert(#reports==1, "failure diagnostic missing or repeated")
    assert(reports[1]=="Slomix runtime host: failed live_context_mismatch\n",
        "unsafe or incorrect failure diagnostic")
    assert(connects==0)
    print(reports[1])
    return
end
assert(ok == (fault~="init-error"))
if not ok then
    assert(result=="original init error" and hooks.status()=="init_failed")
    et_RunFrame(123); assert(connects==0 and polls==0); return
end
assert(table.concat(events,",")=="preload,init,capture,open", "bootstrap started before init/preload")
ok, result = pcall(et_RunFrame,123)
assert(ok == (fault~="frame-error"))
assert(result == (ok and "frame-result" or "original frame error"))
assert(polls==1, "more than one poll per frame")
assert(events[#events-1]=="poll" and events[#events]=="frame")
if fault == "reinit" then
    et_InitGame(7,8,9)
    assert(closes==1 and connects==2 and captures==2)
    assert(table.concat(events,",",#events-3)=="close,init,capture,open")
end
ok, result = pcall(et_ShutdownGame,1)
assert(ok == (fault~="shutdown-error"))
assert(result == (ok and "shutdown-result" or "original shutdown error"))
assert(hooks.status()=="stopped" and closes==connects)
local count=polls
if fault~="frame-error" then for _=1,10 do et_RunFrame(123) end end
assert(polls==count, "shutdown left polling active")
print("HOOK ORDER " .. fault .. " " .. table.concat(events,","))
