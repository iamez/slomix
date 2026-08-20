-- Runs the SHIPPED get_gametimes_dir() against stubbed engine cvars.
-- Extracted from the module rather than copied, so the test cannot drift away
-- from the code it is guarding.
local path, want_home, want_base, want_game, want_cfg = ...
local src = assert(io.open(path)):read("a")
local fn = src:match("(local function get_gametimes_dir%(%).-\nend)")
if not fn then io.stderr:write("get_gametimes_dir not found\n") os.exit(2) end

local cvars = {
    fs_homepath = (want_home ~= "" and want_home or nil),
    fs_basepath = (want_base ~= "" and want_base or nil),
    fs_game     = want_game,
}
local env = {
    string = string,
    configuration = { gametimes_dir = (want_cfg ~= "" and want_cfg or nil) },
    et = { trap_Cvar_Get = function(n) return cvars[n] end },
}
io.write(load(fn .. "\nreturn get_gametimes_dir", "probe", "t", env)()())
