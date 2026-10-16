-- Explicit load-time factory for a trusted writer-close callback. One attempt
-- per instance, no ACK wait, retry or persistence inside the game VM. A separate
-- short connection AFTER writer close; not a bootstrap reconnect/reallocation.
local channel = require("runtime_host_channel")
local M = {}

local function encode(receipt, generation)
    assert(type(receipt) == "table", "writer-close receipt required")
    local allowed = {version=true, filename=true, bytes=true, state=true}
    for key in pairs(receipt) do assert(allowed[key], "unknown receipt field") end
    assert(receipt.version==1 and receipt.state=="writer_closed", "writer-close receipt required")
    local name, size = receipt.filename, receipt.bytes
    assert(type(generation)=="string" and #generation==32
        and generation:match("^[0-9a-f]+$"), "invalid completion generation")
    assert(type(name)=="string" and #name<=240 and not name:find("..",1,true)
        and name:match("^%d%d%d%d%-%d%d%-%d%d%-%d%d%d%d%d%d%-[A-Za-z0-9_.+%-]+%-round%-[12]%.txt$"),
        "invalid stats completion filename")
    assert(type(size)=="number" and size>=1 and size<=8388608 and size%1==0,
        "invalid stats completion size")
    return "slomix_stats_closed_v1|" .. generation .. "|" .. name .. "|" .. string.format("%.0f",size)
end

function M.sender(path, now, timeout_ms)
    assert(type(path)=="string" and path:sub(1,1)=="/" and #path<=107 and not path:find("%z"),
        "explicit local socket path required")
    assert(type(now)=="function" and type(timeout_ms)=="number" and timeout_ms>0 and timeout_ms<=10000,
        "bounded completion channel required")
    require("socket.unix") -- Preload outside callbacks; no dependency installation.
    local attempted, phase, reason = false, "ready", nil
    return {
        completed = function(receipt, generation)
            assert(not attempted, "writer completion already attempted")
            attempted, phase = true, "failed" -- Validation errors consume attempt too.
            local connection
            local ok, failure = pcall(function()
                local wire = encode(receipt, generation)
                connection = channel.open(path, now, timeout_ms)
                phase = "unconfirmed" -- A send error may still have delivered bytes.
                connection.send_line(wire)
                phase = "sent_unconfirmed" -- NOT host durable receipt or import ACK.
            end)
            if connection then connection.close() end
            if not ok then reason=tostring(failure); error(failure,0) end
        end,
        status = function() return phase, reason end,
    }
end

return M
