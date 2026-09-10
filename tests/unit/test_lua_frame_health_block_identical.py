"""The frame_health v6.13 block is one piece of code copied into six Lua
modules (the engine gives each module its own VM and no `require`), so the
only thing that keeps six copies one is this test: every copy must be
byte-identical to the tracker's, except the single `FH_MOD = "<name>"`
line; every module must call fh_init() from et_InitGame and carry the
run-frame hook AFTER its own et_RunFrame definition (a hook placed before
would wrap nil)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

MODULES = {
    "proximity/lua/proximity_tracker.lua": "proximity_tracker",
    "vps_scripts/team-lock.lua": "team-lock",
    "vps_scripts/c0rnp0rn8.lua": "c0rnp0rn8",
    "vps_scripts/endstats.lua": "endstats",
    "vps_scripts/stats_discord_webhook.lua": "stats_discord_webhook",
    "vps_scripts/live_events.lua": "live_events",
}

BLOCK = re.compile(r"-- BEGIN frame_health v6\.13 .*?\n(.*?)-- END frame_health v6\.13\n", re.S)
HOOK = re.compile(r"-- BEGIN frame_health hook v6\.13 .*?\n(.*?)-- END frame_health hook v6\.13\n", re.S)
MOD_LINE = re.compile(r'^local FH_MOD = "([^"]+)"$', re.M)


def _block(path: str) -> tuple[str, str, str]:
    text = (REPO / path).read_text(encoding="utf-8")
    blocks = BLOCK.findall(text)
    hooks = HOOK.findall(text)
    assert len(blocks) == 1, f"{path}: expected exactly one frame_health block, found {len(blocks)}"
    assert len(hooks) == 1, f"{path}: expected exactly one frame_health hook, found {len(hooks)}"
    names = MOD_LINE.findall(blocks[0])
    assert len(names) == 1, f"{path}: expected one FH_MOD line"
    return MOD_LINE.sub('local FH_MOD = "<mod>"', blocks[0]), hooks[0], names[0]


@pytest.mark.parametrize("path", list(MODULES))
def test_the_block_is_the_trackers_block_and_names_its_module(path: str) -> None:
    reference, ref_hook, _ = _block("proximity/lua/proximity_tracker.lua")
    block, hook, name = _block(path)
    assert name == MODULES[path]
    assert block == reference, f"{path}: frame_health block drifted from the tracker's copy"
    assert hook == ref_hook, f"{path}: frame_health hook drifted from the tracker's copy"


@pytest.mark.parametrize("path", list(MODULES))
def test_init_is_called_from_initgame_and_the_hook_follows_runframe(path: str) -> None:
    text = (REPO / path).read_text(encoding="utf-8")
    init = re.search(r"function et_InitGame\([^)]*\)\n(.*?)\nend", text, re.S)
    assert init and "fh_init()" in init.group(1), f"{path}: et_InitGame does not call fh_init()"
    run_frame_def = text.index("function et_RunFrame(levelTime)")
    hook = text.index("-- BEGIN frame_health hook v6.13")
    assert hook > run_frame_def, f"{path}: the hook must come after the module's own et_RunFrame"
    assert text.index("-- BEGIN frame_health v6.13") < run_frame_def, f"{path}: the block must precede et_RunFrame"


def test_the_check_can_fail() -> None:
    # A block with one changed byte is not the tracker's block.
    reference, _, _ = _block("proximity/lua/proximity_tracker.lua")
    assert reference.replace("self_threshold_ms = 50", "self_threshold_ms = 51") != reference
    assert len(MODULES) == 6
