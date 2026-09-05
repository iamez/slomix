#!/usr/bin/env bash
# =============================================================================
# mutate_dots_arena.sh — deliberately break dots_arena_1v1.lua, one guard at a
# time, and check that the harness NOTICES.
#
# ⛔ A CHECKER NOBODY RUNS IS A CHECK THAT CANNOT FAIL. This repo already wrote
# that lesson down (tests/unit/test_manual_types_do_not_drift_further.py), and
# then the arena's own mutation battery spent two days living in a scratchpad
# where nobody but one session could run it. Forty-four mutations proving the
# guards are alive, and no way for the next person to re-run one of them.
#
# ⚠️ NOT part of CI, on purpose: this edits the working tree. It restores the
# original from a copy on every path, including failure, but a green CI run
# must never depend on that.
#
#   bash scripts/mutate_dots_arena.sh            # run them all
#   bash scripts/mutate_dots_arena.sh --list     # just name them
#
# A mutation that PASSES the harness is a finding, not a success: it means the
# guard it breaks is not actually watched by any case. Three of these were
# written, watched surviving, and the TEST was fixed — see the harness cases
# that cite "mutacija ... je prešla".
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."

LUA=vps_scripts/dots_arena_1v1.lua
ORIG="$(mktemp)"
cp "$LUA" "$ORIG"
trap 'cp "$ORIG" "$LUA"; rm -f "$ORIG"' EXIT

pass=0; fail=0

mutate() {  # name, old, new
    local name="$1" old="$2" new="$3"
    cp "$ORIG" "$LUA"
    # ⛔ A stale pattern counts as MISSED. It printed and returned without
    # touching `fail`, so the script exited 0 reporting "missed 0" while a
    # mutation had never run at all — the same defect its own header warns
    # about, one level up. Found by a review agent, not by running it.
    python3 - "$LUA" "$old" "$new" <<'PY' || { echo "⛔ ${name}: pattern no longer matches — the mutation is stale, not the guard"; fail=$((fail + 1)); return 1; }
import sys
path, old, new = sys.argv[1], sys.argv[2], sys.argv[3]
src = open(path, encoding="utf-8").read()
n = src.count(old)
assert n == 1, f"pattern occurs {n} times"
open(path, "w", encoding="utf-8").write(src.replace(old, new, 1))
PY
    # cmp proves the mutation reached the disk. Without it a no-op edit reads
    # as "the guard held".
    if cmp -s "$ORIG" "$LUA"; then
        echo "⛔ ${name}: mutation did not change the file"
        fail=$((fail + 1)); return
    fi
    if lua5.4 tests/lua/dots_arena_1v1_harness.lua >/dev/null 2>&1; then
        echo "⛔ ${name}: SURVIVED — no case watches this guard"
        fail=$((fail + 1))
    else
        echo "✅ ${name}"
        pass=$((pass + 1))
    fi
}

if [[ "${1:-}" == "--list" ]]; then
    grep -oE '^mutate "[^"]+"' "$0" | sed 's/mutate //'
    exit 0
fi

mutate "the map gate reads CS_SERVERINFO again (empty on a fresh map load)" \
'  local raw = et.trap_Cvar_Get("mapname")' \
'  local raw = ""'

mutate "et_Quit no longer restores g_forcerespawn" \
'function et_Quit()
  restore_forcerespawn()
end' \
'function et_Quit()
end'

mutate "leaving for spectator scores a point again" \
'  if victim == killer and mod == et.MOD_SWITCHTEAM then' \
'  if false then'

mutate "/kill stops costing the point (the escape hatch reopens)" \
'  ensure_pair(players)
  for _, cn in ipairs(players) do
    if cn ~= victim then
      score[cn] = (score[cn] or 0) + 1
    end
  end' \
'  ensure_pair(players)
  if victim ~= killer then
  for _, cn in ipairs(players) do
    if cn ~= victim then
      score[cn] = (score[cn] or 0) + 1
    end
  end
  end'

mutate "disconnect stops clearing the slot" \
'  forced[clientNum]       = nil
  spawn_shield[clientNum] = nil
  score[clientNum]        = nil
  last_cmd[clientNum]     = nil' \
'  local _ = clientNum'

mutate "the relevel flag outlives an empty arena" \
'  elseif #roster == 1 and roster[1] == clientNum then' \
'  elseif false then'

mutate "force_reset latches on an already-dead target" \
'  if not is_alive(cn) then
    log("FORCE   cn=%d why=%s SKIPPED — already dead, no obituary would fire", cn, why)
    return
  end' \
'  local _ = cn'

mutate "an uninvolved disconnect wipes the score again" \
'  if was_scored then
    score_pair = nil
  end' \
'  score_pair = nil'

mutate "a query charges the cooldown again" \
'  local function charge()
    last_cmd[clientNum] = now
  end' \
'  local function charge() end
  last_cmd[clientNum] = now'

mutate "/vampiric 0 turns lifesteal on again" \
'  if pool_arg == 0 then
    charge()
    vamp_pending = false' \
'  if false then
    charge()
    vamp_pending = false'

mutate "a shield gap too wide is silently skipped again" \
'        force_reset(other, et.MOD_SUICIDE, "shield-gap")' \
'        local _ = other'

mutate "a team change no longer arms the relevel" \
'    relevel_pending = true
    log("LEAVE   cn=%d — team change, relevel armed", victim)' \
'    log("LEAVE   cn=%d — team change, relevel armed", victim)'

mutate "refused damage no longer restores the shield" \
'    et.gentity_set(cn, "ps.powerups", et.PW_INVULNERABLE, shield)' \
'    local _ = shield'

mutate "arena_kill accepts any number again" \
'  if not valid_client(cn) then
    et.G_Print(MODNAME .. ": usage: arena_kill <clientnum 0.." ..' \
'  if cn == nil then
    et.G_Print(MODNAME .. ": usage: arena_kill <clientnum 0.." ..'

mutate "valid_client stops rejecting floats" \
'  if math.type(cn) ~= "integer" then return false end' \
'  if type(cn) ~= "number" then return false end'

mutate "sv_maxclients is trusted again" \
'  if n <= 0 or n > MAX_CLIENTS then n = MAX_CLIENTS end' \
'  if n <= 0 then n = MAX_CLIENTS end'

mutate "inf/nan reach nearest_preset again" \
'  if want ~= want or want == math.huge or want == -math.huge or want < 0 then
    return nil
  end' \
'  if false then return nil end'

mutate "the commands drop their team check" \
'  if team ~= et.TEAM_AXIS and team ~= et.TEAM_ALLIES then' \
'  if false then'

mutate "the commands drop their cooldown" \
'  if prev ~= nil and now >= prev and now - prev < CMD_COOLDOWN_MS then' \
'  if false then'

mutate "the cooldown stops surviving a clock wrap" \
'  if prev ~= nil and now >= prev and now - prev < CMD_COOLDOWN_MS then' \
'  if prev ~= nil and now - prev < CMD_COOLDOWN_MS then'

mutate "the log line loses its date again" \
'os.date("%Y-%m-%d %H:%M:%S ")' \
'os.date("%H:%M:%S ")'

mutate "the log stops rotating" \
'  if type(len) == "number" and len > LOG_MAX_BYTES then' \
'  if false then'

mutate "the log loses its per-map line cap" \
'  if log_writes >= LOG_MAX_LINES_PER_MAP then return end' \
'  if false then return end'

echo "─────────────────────────────────────────"
echo "caught ${pass}, missed ${fail}"
[[ $fail -eq 0 ]]
