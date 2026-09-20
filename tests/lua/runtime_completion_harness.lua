-- Real temporary filesystem with ET-shaped bindings, never a running server.
local module_path, directory, scenario, generation = arg[1], arg[2], arg[3], arg[4]
if scenario == "unsafe-generation" then generation = "../" .. generation end
if scenario == "uppercase-generation" then generation = string.upper(generation) end
local writer = dofile(module_path)
local name = "2026-09-20-120000-oasis-round-1.txt"
if scenario == "unsafe-name" then name = "../" .. name end
if scenario == "round-zero" then name = "2026-09-20-120000-oasis-round-0.txt" end
local opened, closed, emitted, writes = false, false, false, 0
local handle
local api = {
    FS_WRITE = 1,
    trap_FS_FOpenFile = function(path)
        assert(path == "gamestats/runtime-snapshots/" .. generation .. "/" .. name)
        if scenario == "open-fail" then return 0, -1 end
        opened = true
        handle = assert(io.open(directory .. "/" .. name, "wb"))
        return 7, 0
    end,
    trap_FS_Write = function(data, length, fd)
        assert(fd == 7 and not closed and length == #data)
        writes = writes + 1
        if scenario == "write-error" then error("fixture write failure") end
        if scenario == "short-write" and writes == 2 then
            assert(handle:write(data:sub(1, 2)))
            return 2
        end
        assert(handle:write(data))
        if scenario == "missing-count" then return nil end
        return length
    end,
    trap_FS_FCloseFile = function(fd)
        assert(fd == 7 and not emitted)
        assert(handle:close())
        closed = true
        if scenario == "close-error" then error("fixture close failure") end
    end,
}
local chunks = {"header\n", "player-row\n"}
if scenario == "sparse" then chunks = {[1] = "x", [3] = "z"} end
if scenario == "empty" then chunks = {} end
if scenario == "oversize" then chunks = {string.rep("x", 8 * 1024 * 1024 + 1)} end
local ok = pcall(writer.write, api, generation, name, chunks, function(receipt, receipt_generation)
    assert(receipt_generation == generation, "completion lost generation identity")
    assert(closed and writes == 2, "completion preceded payload close")
    if scenario == "notify-error" then error("fixture notification failure") end
    assert(receipt.version == 1 and receipt.filename == name and receipt.bytes == 18)
    assert(receipt.state == "writer_closed")
    emitted = true
end)
assert(ok == (scenario == "ok"), "unexpected writer outcome: " .. scenario)
assert(emitted == (scenario == "ok"), "unexpected completion: " .. scenario)
if opened then assert(closed, "writer handle leaked") end
print("completion-proof " .. scenario .. " emitted=" .. tostring(emitted))
