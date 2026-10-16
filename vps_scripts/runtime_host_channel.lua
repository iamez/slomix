-- Explicit local client only. Caller supplies trusted protected socket pathname
-- (and ancestors), approved LuaSocket installation/search path and monotonic ms
-- clock. A socket path is NOT learned from a cvar/message. No listener, reconnect,
-- lifecycle IDs or game hooks. No blocking operations or unbounded line reads.
local M = {}

local function valid_line(value)
    return type(value) == "string" and #value >= 1 and #value <= 512
        and not value:find("[^ -~]")
end

function M.open(path, now, timeout_ms)
    assert(type(path) == "string" and path:sub(1,1) == "/" and #path <= 107
        and not path:find("%z"), "explicit local socket path required")
    assert(type(now) == "function" and type(timeout_ms) == "number"
        and timeout_ms > 0 and timeout_ms <= 10000, "bounded channel deadline required")
    local socket = require("socket.unix").stream()
    local closed, ended, buffer, last, deadline = false, false, "", nil, nil
    local client = {}
    function client.close()
        closed, buffer = true, ""
        socket:close()
    end
    local function fail(reason)
        client.close()
        error(reason, 0)
    end
    local function check()
        if closed then error("host channel closed",0) end
        local ok, tick = pcall(now)
        if not ok or type(tick) ~= "number" or tick ~= tick or math.abs(tick) == math.huge
            or (last and tick < last) then fail("host channel clock invalid") end
        last = tick
        deadline = deadline or tick + timeout_ms
        if tick >= deadline then fail("host channel deadline expired") end
    end
    check()
    local bounded, bound_error = socket:settimeout(0)
    if not bounded then fail("host channel timeout setup failed: " .. tostring(bound_error)) end
    local connected, connect_error = socket:connect(path)
    if not connected then fail("host channel connect failed: " .. tostring(connect_error)) end
    check()
    function client.send_line(value)
        check()
        if not valid_line(value) then fail("invalid host channel line") end
        local sent, reason = socket:send(value .. "\n")
        -- Partial/ambiguous send is terminal. Do not resend prefix or reconnect.
        if sent ~= #value + 1 then fail("host channel send failed: " .. tostring(reason)) end
        check()
    end
    function client.receive_line()
        check()
        local stop = buffer:find("\n",1,true)
        if not stop then
            if ended then fail("host channel ended before complete line") end
            -- At most one nonblocking bounded receive per poll. LuaSocket
            -- returns available prefix on timeout; never use receive('*l').
            local data, reason, partial = socket:receive(513 - #buffer)
            buffer = buffer .. (data or partial or "")
            if not data and reason == "closed" then
                ended = true -- Complete buffered frames remain valid; partial tail does not.
            elseif not data and reason ~= "timeout" then
                fail("host channel receive failed: " .. tostring(reason))
            end
            check()
            stop = buffer:find("\n",1,true)
        end
        if not stop then
            if #buffer > 512 then fail("host channel line exceeds bound") end
            if ended then fail("host channel ended before complete line") end
            return nil, "pending"
        end
        local value = buffer:sub(1,stop-1)
        buffer = buffer:sub(stop+1)
        if not valid_line(value) then fail("invalid host channel line") end
        return value
    end
    return client
end

return M
