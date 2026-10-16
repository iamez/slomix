-- Bounded ET IPC adapter, explicit provisioning only. Pins are supplied by the
-- trusted host bootstrap, NOT learned from a received message. ET's module name
-- and SHA1 identify a loaded peer, not a cryptographic trust boundary against
-- hostile same-process Lua/native code. All installed game modules are trusted.
local identity = require("runtime_round_identity")
local M = {}
local BIND, ACK = "slomix_stats_bind_v1", "slomix_stats_ack_v1"

local function token(value)
    return type(value) == "string" and #value == 32 and value:match("^[0-9a-f]+$")
end

local function integer(value, maximum)
    return type(value) == "number" and value >= 0 and value <= maximum and value % 1 == 0
end

function M.decode(wire)
    assert(type(wire) == "string" and #wire <= 512, "invalid delivery wire")
    local f = {}
    for value in (wire .. "|"):gmatch("(.-)|") do f[#f + 1] = value end
    assert(#f == 7 and f[1] == BIND, "invalid delivery wire")
    assert(token(f[2]) and token(f[3]) and f[2] ~= f[3] and token(f[6]), "invalid delivery token")
    local init_time = tonumber(f[4])
    assert(#f[4] <= 10 and (f[4] == "0" or f[4]:match("^[1-9][0-9]*$"))
        and integer(init_time, 2147483647) and tostring(init_time) == f[4], "invalid InitGame levelTime")
    assert(#f[7] >= 1 and #f[7] <= 64 and f[7]:match("^[A-Za-z0-9_.+%-]+$")
        and not f[7]:find("..", 1, true), "invalid delivery map")
    local decoded = identity.decode(f[5])
    for _, value in ipairs({decoded.match_id, decoded.round_id, decoded.first_round_id, f[6]}) do
        assert(value ~= f[2] and value ~= f[3], "epoch reused as round/artifact identity")
    end
    return {process_epoch=f[2], lifecycle_epoch=f[3], init_time=init_time,
        identity=decoded, generation=f[6], map_name=f[7]}
end

local function pins(options)
    assert(type(options) == "table", "explicit peer/context pins required")
    local allowed = {peer_slot=true, peer_name=true, peer_signature=true,
        process_epoch=true, lifecycle_epoch=true, init_time=true, source_id=true}
    for key in pairs(options) do assert(allowed[key], "unknown delivery pin") end
    -- ET2.85 _et_FindMod indexes lVM directly. Reject all out-of-range slots
    -- BEFORE calling it; LUA_NUM_VM is64 in the pinned source.
    assert(integer(options.peer_slot, 63), "invalid peer slot")
    assert(type(options.peer_name) == "string" and #options.peer_name >= 1
        and #options.peer_name <= 128, "invalid peer name")
    assert(type(options.peer_signature) == "string" and #options.peer_signature == 40
        and options.peer_signature:match("^[0-9a-fA-F]+$"), "invalid peer signature")
    assert(token(options.process_epoch) and token(options.lifecycle_epoch)
        and options.process_epoch ~= options.lifecycle_epoch, "invalid pinned epochs")
    assert(integer(options.init_time, 2147483647), "invalid pinned InitGame levelTime")
    assert(type(options.source_id) == "string" and #options.source_id <= 64
        and options.source_id:match("^[a-z0-9][a-z0-9_.%-]*$"), "invalid pinned source")
    local frozen = {}
    for key, value in pairs(options) do frozen[key] = value end
    return frozen
end

local function peer_matches(api, expected, sender)
    if sender ~= expected.peer_slot then return false end
    local ok, name, signature = pcall(api.FindMod, sender)
    return ok and name == expected.peer_name and signature == expected.peer_signature
end

local function context_matches(expected, value)
    return value.process_epoch == expected.process_epoch
        and value.lifecycle_epoch == expected.lifecycle_epoch
        and value.init_time == expected.init_time and value.identity.source_id == expected.source_id
end

function M.receiver(api, options, bind, completed)
    local expected = pins(options)
    assert(type(bind) == "function" and type(completed) == "function", "invalid receiver callbacks")
    local accepted, pending, attempts = nil, false, 0
    local defer_flush = false
    local poisoned = false
    return {
        receive = function(sender, wire)
            if poisoned or not peer_matches(api, expected, sender) then return false end
            local ok, value = pcall(M.decode, wire)
            if not ok or not context_matches(expected, value) then return false end
            if accepted ~= nil then
                if accepted ~= wire then return false end
                if not pending then defer_flush = true end
                pending = true -- Exact retry: acknowledgement only, NEVER rebind.
                return true
            end
            -- A callback could have changed state before raising. Never invoke
            -- it twice after an ambiguous failure, even with the same message.
            poisoned = true
            local bound, round_id, generation = pcall(bind, {identity=value.identity,
                generation=value.generation, map_name=value.map_name, completed=completed})
            if not bound or round_id ~= value.identity.round_id or generation ~= value.generation then return false end
            accepted, pending, poisoned, defer_flush = wire, true, false, true
            return true
        end,
        flush = function()
            -- Call on a later frame, never recursively inside et_IPCReceive.
            if poisoned or not pending or attempts >= 3 then return false end
            -- Skip the first frame callback after reception regardless of VM
            -- callback ordering. Wall milliseconds do not identify a game frame.
            if defer_flush then defer_flush = false; return false end
            if not peer_matches(api, expected, expected.peer_slot) then return false end
            attempts = attempts + 1
            local ok, sent = pcall(api.IPCSend, expected.peer_slot, ACK .. accepted:sub(#BIND + 1))
            if ok and sent == 1 then pending = false end
            return ok and sent == 1
        end,
    }
end

function M.sender(api, options, wire)
    local expected = pins(options)
    local value = M.decode(wire)
    assert(context_matches(expected, value), "sender context mismatch")
    local attempts, acknowledged = 0, false
    local exact_ack = ACK .. wire:sub(#BIND + 1)
    return {
        send = function()
            if acknowledged or attempts >= 3 then return false end
            if not peer_matches(api, expected, expected.peer_slot) then return false end
            attempts = attempts + 1
            local ok, sent = pcall(api.IPCSend, expected.peer_slot, wire)
            return ok and sent == 1 -- Delivery is NOT acceptance; inspect status().
        end,
        receive = function(sender, message)
            if attempts == 0 or not peer_matches(api, expected, sender) or message ~= exact_ack then return false end
            acknowledged = true
            return true
        end,
        status = function() return acknowledged and "accepted" or (attempts >= 3 and "unconfirmed" or "pending") end,
    }
end

return M
