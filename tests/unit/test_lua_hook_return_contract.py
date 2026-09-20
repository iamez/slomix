"""ET:Legacy dispatches a hook to EVERY loaded module — unless one returns.

`G_LuaHook_Obituary` (src/game/g_lua.c) walks the loaded modules and stops at
the first one whose return value passes `lua_isstring(L, -1)`:

    if (!G_LuaCall(vm, "et_Obituary", 3, 1)) { continue; }
    if (lua_isstring(vm->L, -1)) { lua_pop(vm->L, 1); return qtrue; }
    lua_pop(vm->L, 1);

In the Lua C API `lua_isstring` is true for NUMBERS as well as strings, so a
plain `return 0` reads as "handled, stop here" and every module loaded after
that one is silently skipped. Returning nothing (or a bare `return`) leaves nil
on the stack, which does not stop the walk.

That is not hypothetical. stats_discord_webhook.lua ended its et_Obituary with
`return 0` and sits ahead of live_events.lua in `lua_modules`, so live_events
never received a single obituary from the day it shipped (2026-08-12) — the
Live page's K/D columns and alive dots were dead the whole time while damage
and DPM kept working, which is exactly why nobody noticed.

Measured on the local test server, 2026-08-20, module order UNCHANGED:
    before the fix: engine 28 kills -> 0 K lines
    after  the fix: engine 14 kills -> 14 K lines, aggregates 14/14

Hook groups below are from the engine source (2.85 master, same in 2.83/2.84).
Only the first group is dangerous: there, ANY returned value stops the chain.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Hooks that stop the module walk on ANY returned value (lua_isstring is true
# for numbers too). et_ClientConnect belongs here by design — a returned string
# is the rejection reason — so it is allowed to return, deliberately.
STOPS_ON_ANY_VALUE = ("et_Obituary", "et_ClientConnect")

# Hooks that only stop on one specific number; `return 0` is safe in these.
#   == 1:  et_ClientCommand, et_ConsoleCommand, et_Damage, et_Revive,
#          et_WeaponFire, et_AAGunFire, et_FixedMGFire, et_MountedMGFire
#   == -1: et_SetPlayerSkill, et_UpgradeSkill
# Everything else (et_InitGame, et_RunFrame, et_Print, …) ignores the return.

# The one hook our modules must never return from. Kept separate from
# STOPS_ON_ANY_VALUE so the intentional et_ClientConnect case stays readable.
FORBIDDEN_RETURN_HOOKS = ("et_Obituary",)

LUA_SOURCES = sorted(
    list((_REPO_ROOT / "vps_scripts").glob("*.lua"))
    + list((_REPO_ROOT / "proximity" / "lua").glob("*.lua"))
)


def _hook_body(path: Path, hook: str) -> list[tuple[int, str]]:
    """Lines of `function <hook>(...)` up to its closing top-level `end`."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = next(
        (i for i, ln in enumerate(lines) if re.match(rf"^function {hook}\b", ln)), None
    )
    if start is None:
        return []
    end = next(
        (i for i in range(start + 1, len(lines)) if re.match(r"^end\s*$", lines[i])),
        len(lines) - 1,
    )
    return [(i + 1, lines[i]) for i in range(start, end + 1)]


def test_lua_sources_are_discovered():
    """A glob that silently matches nothing would make every check below pass."""
    assert LUA_SOURCES, "no Lua modules found — the glob paths moved"


def _returns_a_value(line: str) -> bool:
    """Does this line return something the engine would read as "handled"?

    ⛔ A trailing comment is not a return value. The first version of this check
    was `^\\s*return\\s+\\S`, and `--` is a non-space character, so a perfectly
    safe `return  -- why` was reported as an offender (found 2026-09-04 on
    dots_arena_1v1.lua, whose three returns are all bare). A guard that cannot
    tell a comment from a value teaches people to work around it.
    """
    code = re.sub(r"--.*$", "", line).rstrip()
    return re.search(r"^\s*return\s+\S", code) is not None


@pytest.mark.parametrize("path", LUA_SOURCES, ids=lambda p: p.name)
def test_obituary_never_returns_a_value(path: Path):
    """`return 0` here starves every module loaded after this one."""
    offenders = [
        (ln, txt.strip())
        for ln, txt in _hook_body(path, "et_Obituary")
        if _returns_a_value(txt)
    ]
    assert not offenders, (
        f"{path.name}: et_Obituary returns a value at "
        + ", ".join(f"line {ln} ({txt!r})" for ln, txt in offenders)
        + ". lua_isstring() is true for numbers, so this stops the engine's "
        "module walk and every module after this one stops receiving kills. "
        "Use a bare `return` instead — the engine ignores this hook's value."
    )


@pytest.mark.parametrize(
    ("line", "returns_value"),
    [
        ("    return", False),
        ("    return  -- not a 1v1 right now", False),
        ("\treturn -- why", False),
        ("    return 0", True),
        ("    return 0  -- handled", True),
        ("    return qtrue", True),
        ('    return "x"', True),
        ("    returnValue = 1", False),
    ],
)
def test_the_value_check_reads_code_not_comments(line: str, returns_value: bool):
    """Both directions. The comment case is why this exists; the `return 0 --`
    case is what must NOT be lost while fixing it."""
    assert _returns_a_value(line) is returns_value


def test_the_guard_knows_what_it_is_guarding():
    """The rule is worthless if the hook name drifts: at least one of our
    modules must actually define et_Obituary for the check above to mean
    anything."""
    definers = [p.name for p in LUA_SOURCES if _hook_body(p, "et_Obituary")]
    assert len(definers) >= 2, (
        f"expected several modules to define et_Obituary, found {definers} — "
        "if the hook was renamed engine-side this test is now checking nothing"
    )


# ── the map of the live server must not disagree with itself ──────────────────
_LUA_MAP = _REPO_ROOT / "docs" / "GAMESERVER_LIVE_LUA_MAP.md"


def _section(title: str) -> str:
    """The body of one `## <title>` section of the live Lua map."""
    text = _LUA_MAP.read_text(encoding="utf-8")
    start = text.index(f"## {title}")
    nxt = text.find("\n## ", start + 1)
    return text[start:nxt if nxt != -1 else len(text)]


def _modules_named_in(section: str) -> set[str]:
    return set(re.findall(r"([\w-]+\.lua)", section))


def test_the_live_module_lists_agree_with_each_other():
    """One list gaining a module and the others not is how the doc goes stale.

    live_events.lua joined lua_modules on 2026-08-12 and reached only the
    runtime line here; the Active modules list and the file mappings still
    omitted it eight days later, which is precisely the kind of gap an audit
    reads as "that module does not exist" (CodeRabbit review, #785).
    """
    active = _modules_named_in(_section("Live Lua Modules"))
    paths = _modules_named_in(_section("Live File Paths"))
    repo = _modules_named_in(_section("Repo Mapping"))
    assert active, "the Active modules list is empty — the section moved"

    missing_paths = sorted(active - paths)
    missing_repo = sorted(active - repo)
    assert not missing_paths, (
        "modules listed as active have no entry under Live File Paths: "
        + ", ".join(missing_paths)
    )
    assert not missing_repo, (
        "modules listed as active have no entry under Repo Mapping: "
        + ", ".join(missing_repo)
    )


def test_the_webhook_module_is_documented_at_the_path_that_runs():
    """fs_homepath overrides fs_basepath, and both copies exist on the server.

    A fix deployed to the basepath copy changes nothing and looks exactly like
    a fix that did not work — which is how an afternoon went on 2026-08-20.
    """
    paths = _section("Live File Paths")
    webhook = paths[paths.index("stats_discord_webhook.lua"):]
    webhook = webhook[:webhook.index("proximity_tracker.lua")]
    assert "/home/et/.etlegacy/legacy/luascripts/stats_discord_webhook.lua" in webhook, (
        "the live copy of stats_discord_webhook.lua is the one under "
        "fs_homepath; this document must name it, or the next deploy goes to "
        "the copy the engine ignores."
    )
