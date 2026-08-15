"""The Lua webhook must be able to feed both bots.

One game server, two bots: production and dev listen in different Discord
channels. Until 2026-08-15 the script could only reach one, so the dev bot
dropped every trigger as "channel mismatch" and never imported a round at the
moment it ended — which is what left its Lua captures unlinkable.

There is no Lua test harness in this repo, so this extracts the two real
functions out of `vps_scripts/stats_discord_webhook.lua` and runs them under
the interpreter the game server uses (5.4). It tests the shipped text, not a
copy of it. Skipped when no lua5.4 is installed, e.g. in CI.
"""
from __future__ import annotations

import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "vps_scripts" / "stats_discord_webhook.lua"
LUA = shutil.which("lua5.4") or shutil.which("lua")

pytestmark = pytest.mark.skipif(LUA is None, reason="lua5.4 not installed")

HARNESS = """
local function shell_escape(s) return "'" .. tostring(s):gsub("'", "'\\\\''") .. "'" end
configuration = { curl_connect_timeout = 5, curl_max_time = 10, curl_retry = 2,
                  curl_retry_delay = 1, curl_retry_max_time = 20 }
"""


def _functions_under_test() -> str:
    """The real source of configured_webhook_urls + build_curl_command."""
    src = SCRIPT.read_text(encoding="utf-8")
    start = src.index("local function configured_webhook_urls()")
    end = src.index("local function pending_buffer_count()")
    return src[start:end]


def _run_lua(body: str) -> str:
    program = HARNESS + _functions_under_test() + textwrap.dedent(body)
    result = subprocess.run(
        [LUA, "-"], input=program, capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_script_parses_under_the_game_servers_lua():
    """The script uses 5.4 bitwise operators; a 5.1 luac rejects them by
    design, so parse with the same runtime ET:Legacy 2.83.1 ships."""
    luac = shutil.which("luac5.4")
    if luac is None:
        pytest.skip("luac5.4 not installed")
    result = subprocess.run([luac, "-p", str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_placeholder_is_not_a_target():
    out = _run_lua("""
        configuration.discord_webhook_url = "REPLACE_WITH_YOUR_WEBHOOK_URL"
        print(#configured_webhook_urls(),
              build_curl_command("/tmp/p.json", "/tmp/p.exit") == nil)
    """)
    assert out == "0\ttrue"


def test_single_url_still_works():
    """An untouched deployment must keep behaving exactly as before."""
    out = _run_lua("""
        configuration.discord_webhook_url = "https://discord.com/api/webhooks/1/AAA"
        local cmd = build_curl_command("/tmp/p.json", "/tmp/p.exit")
        print(#configured_webhook_urls(), select(2, cmd:gsub("curl ", "")))
    """)
    assert out == "1\t1"


def test_url_list_takes_precedence_and_sends_to_every_target():
    out = _run_lua("""
        configuration.discord_webhook_url = "https://discord.com/api/webhooks/1/SINGLE"
        configuration.discord_webhook_urls = {
            "https://discord.com/api/webhooks/1/PROD",
            "https://discord.com/api/webhooks/2/DEV",
        }
        local cmd = build_curl_command("/tmp/p.json", "/tmp/p.exit")
        print(#configured_webhook_urls(),
              select(2, cmd:gsub("curl ", "")),
              cmd:find("PROD", 1, true) ~= nil,
              cmd:find("DEV", 1, true) ~= nil,
              cmd:find("SINGLE", 1, true) == nil)
    """)
    assert out == "2\t2\ttrue\ttrue\ttrue"


def test_one_exit_marker_carries_the_worst_exit_code():
    """The retry buffer reads a single marker per payload: it must see a
    failure if ANY target failed, or a missed round would look delivered."""
    out = _run_lua("""
        configuration.discord_webhook_urls = {
            "https://discord.com/api/webhooks/1/A",
            "https://discord.com/api/webhooks/2/B",
        }
        local cmd = build_curl_command("/tmp/p.json", "/tmp/p.exit")
        print(cmd:find("rc=0", 1, true) ~= nil,
              select(2, cmd:gsub("|| rc=%$%?", "")),
              cmd:find("echo $rc >", 1, true) ~= nil)
    """)
    assert out == "true\t2\ttrue"


def test_empty_and_placeholder_entries_are_skipped():
    out = _run_lua("""
        configuration.discord_webhook_url = "REPLACE_WITH_YOUR_WEBHOOK_URL"
        configuration.discord_webhook_urls = {
            "", "REPLACE_WITH_YOUR_WEBHOOK_URL",
            "https://discord.com/api/webhooks/3/OK",
        }
        print(#configured_webhook_urls())
    """)
    assert out == "1"


def test_config_declares_the_list_key_so_the_override_loader_accepts_it():
    """The loader only takes a key when `configuration[key] ~= nil` AND the
    types match. Declaring the default as nil made the live server reject the
    secret config with "unknown key 'discord_webhook_urls' ignored" — the unit
    tests missed it because they set the field directly, bypassing the loader.
    """
    src = SCRIPT.read_text(encoding="utf-8")
    config_block = src[src.index("local configuration = {"):src.index("-- Enable/disable the webhook")]
    assert "discord_webhook_urls = {}" in config_block, (
        "the key must default to an empty TABLE: nil is rejected as unknown, "
        "and a non-table default would fail the loader's type check"
    )


def test_empty_list_falls_back_to_the_single_url():
    out = _run_lua("""
        configuration.discord_webhook_url = "https://discord.com/api/webhooks/1/AAA"
        configuration.discord_webhook_urls = {}
        print(#configured_webhook_urls())
    """)
    assert out == "1"
