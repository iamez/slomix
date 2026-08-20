-- Runs the SHIPPED get_gametimes_dir() against stubbed engine cvars.
-- Extracted from the module rather than copied, so the test cannot drift away
-- from the code it is guarding.
local path, want_home, want_base, want_game, want_cfg = ...
local src = assert(io.open(path)):read("a")
local fn = src:match("(local function get_gametimes_dir%(%).-\nend)")
if not fn then io.stderr:write("get_gametimes_dir not found\n") os.exit(2) end

-- "NIL" means "the cvar/key is absent"; "" means "present but empty", which is
-- the shipped default for gametimes_dir and behaves differently in Lua (an
-- empty string is truthy). The two cases must stay distinguishable here.
local function arg_or_nil(v) if v == "NIL" then return nil end return v end
local cvars = {
    fs_homepath = arg_or_nil(want_home),
    fs_basepath = arg_or_nil(want_base),
    fs_game     = arg_or_nil(want_game),
}
local env = {
    string = string,
    configuration = { gametimes_dir = arg_or_nil(want_cfg) },
    et = { trap_Cvar_Get = function(n) return cvars[n] end },
}
io.write(load(fn .. "\nreturn get_gametimes_dir", "probe", "t", env)()())
