-- Trusted same-VM composition; no hooks/config activation. Preload this module
-- and approved dependencies before game callbacks. Channel authenticates host
-- via protected pathname; all loaded modules/callbacks must be trusted.
local delivery = require("runtime_stats_delivery")
local M = {}

local function source(value)
    return type(value) == "string" and #value >= 1 and #value <= 64
        and value:match("^[a-z0-9][a-z0-9_.%-]*$")
end

local function context(wire, expected_source)
    local process, lifecycle, name = wire:match("^slomix_bootstrap_context_v1|([0-9a-f]+)|([0-9a-f]+)|([^|]+)$")
    assert(process and #process == 32 and #lifecycle == 32 and process ~= lifecycle
        and name == expected_source, "invalid bootstrap context")
    return process, lifecycle
end

function M.start(capture, open_channel, expected_source, completed)
    assert(type(capture) == "function" and type(open_channel) == "function"
        and type(completed) == "function" and source(expected_source), "invalid bootstrap adapter")
    -- Claim source context BEFORE connection; failed connect cannot be retried
    -- with another lease for the same InitGame. No timestamp identity.
    local observed, consume = capture()
    local init, map, half = observed:match("^slomix_init_v1|([0-9]+)|([^|]+)|([12])$")
    assert(init and type(consume) == "function", "invalid captured InitGame")
    local channel, phase, reason, process, lifecycle = nil, "context", nil, nil, nil
    local binding_attempted = false
    local function close() if channel then channel.close() end end
    local function fail(error)
        phase = binding_attempted and "unconfirmed" or "failed"
        reason = tostring(error)
        close()
    end
    local opened, error = pcall(function()
        channel = open_channel()
        channel.send_line(observed)
    end)
    if not opened then fail(error) end
    return {
        poll = function()
            if phase ~= "context" and phase ~= "delivery" then return phase, reason end
            local ok, failure = pcall(function()
                local wire = channel.receive_line()
                if wire == nil then return end
                if phase == "context" then
                    process, lifecycle = context(wire, expected_source)
                    phase = "delivery"
                    return -- At most one line and one bounded receive per poll.
                end
                local value = delivery.decode(wire)
                assert(value.process_epoch == process and value.lifecycle_epoch == lifecycle
                    and value.identity.source_id == expected_source and value.init_time == tonumber(init)
                    and value.map_name == map and value.identity.round_number == tonumber(half),
                    "bootstrap delivery disagrees with independent context")
                binding_attempted = true -- A raising callback may have changed state.
                local round, generation = consume(value, completed)
                assert(round == value.identity.round_id and generation == value.generation,
                    "bootstrap binding not confirmed")
                channel.send_line("slomix_stats_ack_v1" .. wire:sub(#"slomix_stats_bind_v1" + 1))
                phase = "accepted" -- Local bind + ACK sent, NOT host durability or writer completion.
                close()
            end)
            if not ok then fail(failure) end
            return phase, reason
        end,
        status = function() return phase, reason end,
        close = function()
            if phase == "context" or phase == "delivery" then phase = "cancelled" end
            close()
        end,
    }
end

return M
