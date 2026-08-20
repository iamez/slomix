"""Each server instance must write its gametimes into its own directory.

`stats_discord_webhook.lua` used to carry the output directory as a hardcoded
absolute path — `/home/et/.etlegacy/legacy/gametimes`, "to align with bot". One
instance, one directory, no problem. A second instance with its own
`fs_homepath` (the 2.85 test server) would have written its rounds into the
2.84 server's directory, where the bot ingests them as the first server's. It
never fired only because the write sits inside the webhook send path and the
test box has no webhook URL configured.

The obvious repair is a trap of its own. Simply dropping the hardcoded path
leaves the old fallback, which builds on **fs_basepath** — and on the
production server that cvar is the bare string ".", because the server starts
with `cd <gamedir> && ./etlded.x86_64`:

    fs_basepath=.  fs_homepath=/home/et/.etlegacy  fs_game=legacy   (puran, 2026-08-20)

so the path would resolve to "./legacy/gametimes", relative to wherever the
process was launched. The engine writes gamestats/, proximity/ and gametimes/
under the **homepath**; that is the cvar to derive from.

These cases run the shipped function itself against stubbed cvars.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE = _REPO_ROOT / "vps_scripts" / "stats_discord_webhook.lua"
_PROBE = _REPO_ROOT / "tests" / "fixtures" / "lua" / "gametimes_dir_probe.lua"

_LUA = shutil.which("lua5.4") or shutil.which("lua")
pytestmark = pytest.mark.skipif(_LUA is None, reason="lua interpreter not installed")


def resolve(homepath: str = "", basepath: str = "", fs_game: str = "legacy",
            configured: str = "") -> str:
    out = subprocess.run(
        [_LUA, str(_PROBE), str(_MODULE), homepath, basepath, fs_game, configured],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def test_probe_finds_the_function():
    """A silent extraction failure would make every case below meaningless."""
    assert resolve(homepath="/tmp/x").startswith("/tmp/x")


def test_production_path_is_unchanged():
    """The whole change is worthless if it moves the live server's output."""
    assert resolve(homepath="/home/et/.etlegacy", basepath=".") == \
        "/home/et/.etlegacy/legacy/gametimes"


def test_a_second_instance_gets_its_own_directory():
    """The bug this exists for: 2.85 must not write into 2.84's directory."""
    got = resolve(homepath="/home/et/.etlegacy-v2.85.0", basepath=".")
    assert got == "/home/et/.etlegacy-v2.85.0/legacy/gametimes"
    assert "/home/et/.etlegacy/legacy" not in got


def test_basepath_is_not_used_when_it_is_relative():
    """fs_basepath is "." in production — deriving from it escapes the tree."""
    got = resolve(homepath="", basepath=".", fs_game="legacy")
    assert not got.startswith("./"), f"resolved to a CWD-relative path: {got}"
    assert got.startswith("/")


def test_an_absolute_basepath_is_still_usable():
    assert resolve(basepath="/opt/et") == "/opt/et/legacy/gametimes"


def test_an_explicit_absolute_setting_wins():
    """An operator override must survive; it is the documented escape hatch."""
    assert resolve(homepath="/home/et/.etlegacy", configured="/srv/custom") == "/srv/custom"


def test_no_engine_paths_at_all_falls_back_but_stays_absolute():
    assert resolve() == "/home/et/.etlegacy/legacy/gametimes"


def test_the_hardcoded_path_is_not_the_default_any_more():
    """The config block must not pin the directory for every instance."""
    src = _MODULE.read_text(encoding="utf-8")
    block = src[src.index("gametimes_enabled"):src.index("gametimes_write_on_failure_only")]
    assert '"/home/et' not in block, (
        "gametimes_dir is hardcoded again in the configuration block; that makes "
        "every instance on the machine write into the first one's directory."
    )
