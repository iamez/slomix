-- Opt-in wire contract; stats/timing/proximity load it only for runtime binding.
-- Trusted authority supplies unique match/half IDs and the correct R1 dependency.
-- This module does not allocate IDs, persist lifecycle state, send IPC, write
-- artifacts or authenticate callers. No clock/randomSeed-derived identity.
local M = {}
local keys = {source_id=true, match_id=true, round_id=true,
              round_number=true, first_round_id=true}

local function token(value)
    return type(value) == "string" and #value == 32 and value:match("^[0-9a-f]+$")
end

function M.encode(identity)
    assert(type(identity) == "table", "explicit identity required")
    for key in pairs(identity) do assert(keys[key], "unknown identity field") end
    local source = identity.source_id
    assert(type(source) == "string" and #source >= 1 and #source <= 64
        and source:match("^[a-z0-9][a-z0-9_.%-]*$"), "invalid identity source")
    assert(token(identity.match_id) and token(identity.round_id)
        and token(identity.first_round_id), "invalid identity token")
    local half = identity.round_number
    assert(type(half) == "number" and (half == 1 or half == 2), "invalid half")
    assert((identity.round_id == identity.first_round_id) == (half == 1),
        "invalid first-half dependency")
    return table.concat({"slomix_round_v1", source, identity.match_id,
        identity.round_id, half == 1 and "1" or "2", identity.first_round_id}, ":")
end

function M.append_stats_header(header, identity)
    -- Preserve all existing fields and measured-playtime units. Only the shipped
    -- nine-field producer shape can opt in; no invented ninth-field default.
    assert(type(header) == "string" and #header <= 3800, "invalid stats header")
    local line = header:gsub("\r?\n$", "")
    assert(not line:find("[\r\n]"), "expected single header line")
    local _, separators = line:gsub("\\", "")
    assert(separators == 8, "expected nine-field stats header")
    local fields = {}
    for field in (line .. "\\"):gmatch("(.-)\\") do fields[#fields + 1] = field end
    local encoded = M.encode(identity)
    assert(fields[4] == (identity.round_number == 1 and "1" or "2"), "half mismatch")
    return line .. "\\" .. encoded .. "\n"
end

function M.decode(wire)
    assert(type(wire) == "string" and #wire <= 200, "invalid identity wire")
    local fields = {}
    for value in (wire .. ":"):gmatch("(.-):") do fields[#fields + 1] = value end
    assert(#fields == 6 and fields[1] == "slomix_round_v1"
        and (fields[5] == "1" or fields[5] == "2"), "invalid identity wire")
    local identity = {source_id=fields[2], match_id=fields[3], round_id=fields[4],
        round_number=tonumber(fields[5]), first_round_id=fields[6]}
    assert(M.encode(identity) == wire, "noncanonical identity wire")
    return identity
end

return M
