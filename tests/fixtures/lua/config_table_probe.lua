-- Loads the module's `configuration = { ... }` table literal for real and
-- prints "<key>\t<type>\t<value>" per requested key, so a test can ask what
-- apply_config_overrides() will see rather than guess from a regex.
local path = ...
local src = assert(io.open(path)):read("a")
local body = src:match("\nlocal configuration = (%b{})")
if not body then io.stderr:write("configuration table not found\n") os.exit(2) end
local cfg = load("return " .. body, "cfg", "t", {})()
local keys = {}
for k in pairs(cfg) do keys[#keys + 1] = k end
table.sort(keys)
for _, k in ipairs(keys) do
    io.write(string.format("%s\t%s\t%s\n", k, type(cfg[k]), tostring(cfg[k])))
end
