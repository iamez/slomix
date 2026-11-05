"""Run the shipped frame callback with independent engine clock origins.

ET v2.85 G_MILLISECONDS returns Sys_Milliseconds (sv_game.c); GAME_RUN_FRAME
receives sv.time, which sv_init.c may reset. No HTTP/file delivery is exercised.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _run(delay, wall, level):
    lua = shutil.which("lua5.4")
    assert lua, "lua5.4 is required for the engine clock contract"
    source = (ROOT / "vps_scripts/stats_discord_webhook.lua").read_text()
    start = source.index("function et_RunFrame(levelTime)")
    stop = source.index("\n-- ============================================================================", start)
    # Execute the whole shipped callback. Stub its external collaborators only;
    # scheduling, transition flags and comparisons are not copied into the test.
    program = f"""
local wall, level = {wall}, {level}
local sends = 0
local function noop() end
local env = {{
    string=string, tonumber=tonumber, os={{time=function() return 200 end}},
    configuration={{send_delay_seconds={delay}, pending_retry_interval_seconds=30}},
    last_pending_retry_unix=200, round_start_unix=100,
    GS_PLAYING=0, GS_INTERMISSION=3,
    intermission_handled=false, round_end_emitted=false,
    et={{trap_Milliseconds=function() return wall end,
        trap_Cvar_Get=function(name) assert(name == 'gamestate'); return '3' end}},
    handle_gamestate_change=noop, log=noop, fh_section=noop,
    fh_now=function() return wall end,
    collect_team_data=function() return {{}}, {{}} end,
    format_player_json=function() return '[]' end,
    format_player_names=function() return '' end,
    send_webhook=function() sends=sends+1 end,
}}
local callback = [====[{source[start:stop]}]====]
assert(load(callback, '@shipped-webhook-frame', 't', env))()
env.et_RunFrame(level)
if {delay} <= 0 then
    assert(sends == 1, 'immediate path must send once')
else
    assert(sends == 0, 'different level origin must not send early')
    assert(env.scheduled_send_time == wall + {delay} * 1000)
    wall = wall + {delay} * 1000 - 1
    env.et_RunFrame(level + 1)
    assert(sends == 0, 'must not send before the monotonic deadline')
    wall = wall + 1
    -- A frame-clock discontinuity must not delay a monotonic deadline.
    env.et_RunFrame(0)
    assert(sends == 1, 'deadline reached on monotonic clock must send')
    assert(env.send_pending == false, 'completed pending flag must clear')
end
wall = wall + 5000
env.et_RunFrame(level + 5000)
assert(sends == 1, 'later frames must not send twice')
print('DEADLINE PROOF: sends='..sends..' delay='..tostring({delay})..' wall='..wall)
"""
    result = subprocess.run(
        [lua, "-"], input=program, cwd=ROOT, text=True,
        capture_output=True, timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


@pytest.mark.parametrize("wall,level", [(1000000, 100), (100, 1000000)])
def test_delayed_send_uses_its_own_deadline_clock(wall, level):
    assert "sends=1 delay=2" in _run(2, wall, level)


@pytest.mark.parametrize("delay", [0, -1])
def test_immediate_send_remains_once(delay):
    assert "sends=1" in _run(delay, 1000000, 100)
