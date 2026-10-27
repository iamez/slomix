-- Opt-in replacement for c0rnp0rn8.lua in lua_modules, NEVER an additional copy.
-- Operator must approve/install this entrypoint AND all required dependencies.
-- Trusted Lua search path required. No cvar auto-enable, tickets or discovery.
-- Every fresh VM, including Lua-only reload without InitGame, starts fenced.
-- A trusted bootstrap must capture and consume its in-VM InitGame lease.
-- Until then there is deliberately NO legacy stats fallback or source ACK.
require("c0rnp0rn8")
RequireRuntimeStatsInitLease()
local host_hooks = require("runtime_host_hooks").attach()
ConfigureRuntimeStatsHostHooks = host_hooks.configure
RuntimeStatsHostStatus = host_hooks.status
