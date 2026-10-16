-- Deterministic IO faults. Actual Unix/Lua integration is tested separately.
local root, scenario = arg[1], arg[2]
package.path = root .. "/vps_scripts/?.lua;" .. package.path
local tick, closed, reads, writes, connected = 100, false, 0, 0, false
local queue = {}
local socket = {}
function socket:settimeout(value) assert(value == 0); return 1 end
function socket:connect(path) assert(path == "/fixture.sock"); connected=true; return 1 end
function socket:close() closed=true; return 1 end
function socket:send(value)
    writes = writes+1
    assert(#value <= 513)
    if scenario == "partial-send" then return nil,"timeout",2 end
    return #value
end
function socket:receive(size)
    reads=reads+1
    assert(size >= 1 and size <= 513, "unbounded receive")
    local next = table.remove(queue,1)
    if not next then return nil,"timeout","" end
    return next[1],next[2],next[3]
end
package.loaded["socket.unix"] = {stream=function() return socket end}
local module = require("runtime_host_channel")
local channel = module.open("/fixture.sock",function() return tick end,1000)
assert(connected and not closed)
local function rejected(callback, expected)
    local ok, reason = pcall(callback)
    assert(not ok and tostring(reason):find(expected,1,true), "expected " .. expected .. ": " .. tostring(reason))
    assert(closed, "failure did not close socket")
    assert(not pcall(channel.receive_line), "failed channel reusable")
end
if scenario == "fragments" then
    queue = {{nil,"timeout","hel"},{nil,"timeout","lo\nnext\n"}}
    local value, state = channel.receive_line()
    assert(value == nil and state == "pending" and reads==1)
    assert(channel.receive_line()=="hello" and reads==2)
    assert(channel.receive_line()=="next" and reads==2)
elseif scenario == "boundary" then
    queue={{nil,"timeout",string.rep("a",512)},{nil,"timeout","\n"}}
    assert(channel.receive_line()==nil)
    assert(channel.receive_line()==string.rep("a",512))
elseif scenario == "full-eof" then
    queue={{nil,"closed","complete\n"}}
    assert(channel.receive_line()=="complete")
    rejected(channel.receive_line,"ended before complete line")
elseif scenario == "partial-eof" then
    queue={{nil,"closed","incomplete"}}
    rejected(channel.receive_line,"ended before complete line")
elseif scenario == "oversize" then
    queue={{string.rep("a",513)}}
    rejected(channel.receive_line,"line exceeds bound")
elseif scenario == "empty" then
    queue={{nil,"timeout","\n"}}
    rejected(channel.receive_line,"invalid host channel line")
elseif scenario == "control" then
    queue={{nil,"timeout","a\000b\n"}}
    rejected(channel.receive_line,"invalid host channel line")
elseif scenario == "partial-send" then
    rejected(function() channel.send_line("payload") end,"send failed")
    assert(writes==1, "ambiguous send retried")
elseif scenario == "invalid-send" then
    rejected(function() channel.send_line("a\nb") end,"invalid host channel line")
    assert(writes==0)
elseif scenario == "deadline" then
    tick=1099; assert(channel.receive_line()==nil)
    tick=1100; rejected(channel.receive_line,"deadline expired")
    assert(reads==1, "deadline reset after pending poll")
elseif scenario == "backward" then
    tick=99; rejected(channel.receive_line,"clock invalid")
elseif scenario == "nan" then
    tick=0/0; rejected(channel.receive_line,"clock invalid")
else error("unknown fixture") end
channel.close()
assert(closed)
print("BOUNDED LUA CHANNEL " .. scenario .. " reads=" .. reads .. " writes=" .. writes)
