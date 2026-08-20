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

import os
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE = _REPO_ROOT / "vps_scripts" / "stats_discord_webhook.lua"
_PROBE = _REPO_ROOT / "tests" / "fixtures" / "lua" / "gametimes_dir_probe.lua"
_CFG_PROBE = _REPO_ROOT / "tests" / "fixtures" / "lua" / "config_table_probe.lua"

_LUA = shutil.which("lua5.4") or shutil.which("lua")
_ON_CI = os.environ.get("CI", "").lower() == "true"

# Skipping is fine on a laptop without Lua. On CI it is not: a skipped guard
# looks green while checking nothing, which is how the bug below could come
# back through a required check. The workflow installs lua5.4 in the Python
# job for exactly this reason, and test_ci_actually_has_lua below fails if
# that step is ever dropped.
pytestmark = pytest.mark.skipif(
    _LUA is None and not _ON_CI,
    reason="no lua interpreter (local run; CI installs one and must have it)",
)


def test_ci_actually_has_lua():
    """The step that makes every other test here real."""
    if not _ON_CI:
        pytest.skip("only meaningful on CI")
    assert _LUA is not None, (
        "CI has no lua interpreter, so every test in this module would have "
        "skipped and the cross-instance path guard would be inert. Restore the "
        "'Install Lua' step in .github/workflows/tests.yml (python job)."
    )


#: what the probe reads as "this key/cvar is absent"
ABSENT = "NIL"


def resolve(homepath: str = ABSENT, basepath: str = ABSENT, fs_game: str = "legacy",
            configured: str = "") -> str:
    """`configured=""` is the shipped default: present, empty, meaning derive."""
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
    got = resolve(homepath=ABSENT, basepath=".", fs_game="legacy")
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


def config_defaults() -> dict[str, tuple[str, str]]:
    """The module's own `configuration` table, loaded as Lua, not regexed."""
    out = subprocess.run(
        [_LUA, str(_CFG_PROBE), str(_MODULE)],
        capture_output=True, text=True, check=True,
    )
    parsed: dict[str, tuple[str, str]] = {}
    for line in out.stdout.splitlines():
        key, kind, value = line.split("\t", 2)
        parsed[key] = (kind, value)
    return parsed


def test_gametimes_dir_stays_visible_to_the_override_loader():
    """A nil default would silently disable the documented escape hatch.

    `apply_config_overrides()` rejects any key that is not already present in
    `configuration` — "unknown key '<k>' ignored" — and in Lua a nil value IS
    absence. The first version of this change set `gametimes_dir = nil`, which
    left the config-file override unreachable while every path test still
    passed, because the probe injects `configuration` directly instead of going
    through the loader (Codex review on #788). The default is "" instead:
    present, type string, and read as "derive it".
    """
    defaults = config_defaults()
    assert "gametimes_dir" in defaults, (
        "gametimes_dir is absent from the configuration table, so "
        "apply_config_overrides() will reject an operator's setting as an "
        "unknown key and the documented override cannot be used at all."
    )
    kind, value = defaults["gametimes_dir"]
    assert kind == "string", (
        f"gametimes_dir defaults to a {kind}; the loader also requires the "
        "override's type to match, so only a string default accepts a path."
    )
    assert not value.startswith("/"), (
        f"gametimes_dir is pinned to {value!r} again — every instance on the "
        "machine would write into the first one's directory."
    )


def test_the_empty_default_still_resolves_somewhere_sane():
    """"" is truthy in Lua, so `dir or "gametimes"` does not catch it."""
    got = resolve(homepath="/home/et/.etlegacy", configured="")
    assert got == "/home/et/.etlegacy/legacy/gametimes"
    assert not got.endswith("/")
