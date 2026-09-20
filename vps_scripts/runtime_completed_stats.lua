-- Offline prototype only: not loaded by any game module or deployment script.
-- Trusted dispatcher must durably claim this generation BEFORE invoking write
-- exactly once; root maps to gamestats/runtime-snapshots. No claim is made here.
-- FS_WRITE is NOT exclusive creation. This helper does not solve collisions,
-- persistent receipts, fsync, source digest generation or consumer activation.
local M = {}

function M.write(api, generation, filename, chunks, completed)
    -- Validate the entire bounded payload before opening anything.
    assert(type(generation) == "string" and #generation == 32
        and generation:match("^[0-9a-f]+$"), "invalid source generation")
    assert(type(filename) == "string" and #filename <= 240
        and filename:match("^%d%d%d%d%-%d%d%-%d%d%-%d%d%d%d%d%d%-[%w_.+%-]+%-round%-[12]%.txt$")
        and not filename:find("..", 1, true), "invalid stats filename")
    assert(type(chunks) == "table" and type(completed) == "function", "invalid completion inputs")
    local count, size = 0, 0
    for key, chunk in pairs(chunks) do
        assert(type(key) == "number" and key % 1 == 0 and key >= 1 and key <= 4096,
            "invalid chunk index")
        assert(type(chunk) == "string", "invalid chunk")
        count = count + 1
        size = size + #chunk
        assert(size <= 8 * 1024 * 1024, "payload too large")
    end
    assert(count > 0 and size > 0, "empty payload")
    for index = 1, count do assert(chunks[index] ~= nil, "sparse chunks") end

    local path = "gamestats/runtime-snapshots/" .. generation .. "/" .. filename
    local fd, open_len = api.trap_FS_FOpenFile(path, api.FS_WRITE)
    assert(fd and fd ~= 0 and fd ~= -1 and open_len ~= -1, "stats open failed")
    local ok, failure = pcall(function()
        for index = 1, count do
            local chunk = chunks[index]
            local written = api.trap_FS_Write(chunk, #chunk, fd)
            assert(written == #chunk, "stats short write")
        end
    end)
    -- Attempt close even on write failure. Never emit completion on either error.
    local closed, close_failure = pcall(api.trap_FS_FCloseFile, fd)
    if not ok then error(failure, 0) end
    if not closed then error(close_failure, 0) end
    local receipt = {version = 1, filename = filename, bytes = size, state = "writer_closed"}
    -- Notification failure propagates; bytes may already exist. Never retry by
    -- overwriting them. A durable receipt/reconciliation protocol is still needed.
    -- Keep the v1 receipt scoped to its generation; never drop the second value
    -- when delivering/storing it. The generation is the enclosing directory.
    completed(receipt, generation)
    return receipt, generation
end

return M
