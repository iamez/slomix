"""A `setl` cvar that changes at runtime unloads the whole config, every time.

`G_ConfigCheckLocked` (src/game/g_config.c:516-547) runs once per frame from
`G_RunFrame` (g_main.c:4636) and compares every cvar the config declared with
`setl` against its live value:

    trap_Cvar_VariableStringBuffer(config->setl[i].name, temp, 256);
    if (Q_stricmp(config->setl[i].value, temp))
    {
        trap_SetConfigstring(CS_CONFIGNAME, "");
        trap_SendServerCommand(-1, va("cp \"^7Config '%s^7' ^1WAS UNLOADED DUE TO
                                       EXTERNAL MANIPULATION\"", config->name));
        Com_Memset(&level.config, 0, sizeof(config_t));
        break;
    }

It does not restore the value — it forgets the config. So any cvar that the
Lua module or a player writes at runtime must be declared with plain `set`,
which records nothing (g_config.c, `G_ParseSettings`: the `set` branch only
calls `trap_Cvar_Set`, the `setl` branch also appends to `config->setl[]`).

`dots_arena_1v1.lua` writes exactly two cvars at runtime:

    arena_hp          from set_pool(), i.e. every /arenahp a player types
    g_forcerespawn    "-1" at every InitGame, restored at ShutdownGame

Either of them declared with `setl` in the shipped config would unload that
config within one frame of the arena arming — on somebody else's server, where
nobody knows to look for it. That is what this test exists to prevent, and it
is a contract between two files that no single-file check could see.

The second half pins the ordering rule. `G_ParseMapSettings` (g_config.c:290)
applies a `map default` block UNCONDITIONALLY — it does not check whether a
more specific block also matched:

    if (!Q_stricmp(token.string, "default"))
    {
        return G_ParseSettings(handle, qtrue, config);
    }

so `map default { setl lua_modules "" }` placed AFTER `map dots_arena` would
wipe the module back out and the arena would never arm.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
README = REPO / "vps_scripts" / "dots_arena" / "README.md"
LUA = REPO / "vps_scripts" / "dots_arena_1v1.lua"
CONFIG = REPO / "vps_scripts" / "dots_arena" / "dots_arena_1v1.config"

# The tokens G_ParseSettings and G_configLoadAndSet accept. Anything else is a
# hard parse error at the recipient ("unknown/unexpected token"), which is a
# broken bundle rather than a warning.
OUTER_TOKENS = {"configname", "version", "init", "map", "signature", "public"}
INNER_TOKENS = {"set", "setl", "command", "mapscripthash"}


def _strip_comments(text: str) -> str:
    return "\n".join(line.split("//", 1)[0] for line in text.splitlines())


def runtime_written_cvars(lua_source: str) -> set[str]:
    """Cvars the module writes while the server runs."""
    body = "\n".join(
        re.sub(r"--.*$", "", line) for line in lua_source.splitlines()
    )
    return set(re.findall(r'trap_Cvar_Set\(\s*"([A-Za-z0-9_]+)"', body))


def locked_cvars(config_source: str) -> set[str]:
    return set(re.findall(r'^\s*setl\s+([A-Za-z0-9_]+)', _strip_comments(config_source), re.M))


def plain_set_cvars(config_source: str) -> set[str]:
    return set(re.findall(r'^\s*set\s+([A-Za-z0-9_]+)', _strip_comments(config_source), re.M))


def test_the_extractor_actually_finds_the_writes() -> None:
    """An empty set would pass every assertion below without measuring anything.

    This is the half that has been wrong before: a guard whose subject comes
    back empty agrees with everything.
    """
    written = runtime_written_cvars(LUA.read_text(encoding="utf-8"))
    assert written == {"arena_hp", "g_forcerespawn"}, (
        "the set of cvars the module writes at runtime changed; the shipped "
        f"config has to be re-checked against it. Found: {sorted(written)}"
    )


def test_no_runtime_written_cvar_is_locked() -> None:
    written = runtime_written_cvars(LUA.read_text(encoding="utf-8"))
    locked = locked_cvars(CONFIG.read_text(encoding="utf-8"))
    clash = written & locked
    assert not clash, (
        f"{sorted(clash)} declared with `setl` in {CONFIG.name}. The engine "
        "re-checks every setl cvar once per frame and unloads the entire "
        "config when one changes (g_config.c:516). Use plain `set`."
    )


def test_the_pool_is_actually_declared_so_the_guard_is_not_vacuous() -> None:
    """`arena_hp` absent from the config would also satisfy the test above."""
    plain = plain_set_cvars(CONFIG.read_text(encoding="utf-8"))
    assert "arena_hp" in plain, (
        "arena_hp is not declared with `set` in the config — either it is "
        "missing (players get no configured default) or it moved to `setl` "
        "(the config will unload itself)."
    )


def test_map_default_comes_before_the_arena_block() -> None:
    text = _strip_comments(CONFIG.read_text(encoding="utf-8"))
    default_at = text.find("map default")
    arena_at = text.find("map dots_arena")
    assert default_at != -1, "the `map default` block is missing; lua_modules would leak onto other maps"
    assert arena_at != -1, "the `map dots_arena` block is missing; nothing arms the module"
    assert default_at < arena_at, (
        "`map default` must come first: G_ParseMapSettings applies it "
        "unconditionally (g_config.c:290), so a later default block wipes "
        "lua_modules back out and the arena never arms."
    )


def test_map_default_does_not_touch_lua_modules() -> None:
    """A `default` block applies unconditionally, so setting the module list
    there would disarm the arena on its own map and take every other module the
    admin runs down with it, on every map. Measured on a server that had six
    Lua modules loaded: this config took it to one, which is why the merge
    warning in `init` exists and why nothing clears the list here.
    """
    text = _strip_comments(CONFIG.read_text(encoding="utf-8"))
    start = text.index("map default")
    end = text.index("map dots_arena")
    assert "lua_modules" not in text[start:end], (
        "the `map default` block sets lua_modules; it is applied on every map "
        "including dots_arena (g_config.c:290) and will disarm the arena."
    )


def test_config_uses_only_tokens_the_engine_parses() -> None:
    """The engine hard-errors on an unknown token; a typo is a dead bundle."""
    text = _strip_comments(CONFIG.read_text(encoding="utf-8"))
    depth = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line == "{":
            depth += 1
            continue
        if line == "}":
            depth -= 1
            continue
        head = line.split()[0]
        if line.endswith("{"):
            depth += 1
            head = line.split()[0]
            assert head in OUTER_TOKENS, f"unknown outer token {head!r}"
            continue
        expected = INNER_TOKENS if depth else OUTER_TOKENS
        assert head in expected, f"unknown token {head!r} at depth {depth}: {line!r}"
    assert depth == 0, "unbalanced braces in the config"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ('et.trap_Cvar_Set("arena_hp", "1")', {"arena_hp"}),
        ('-- et.trap_Cvar_Set("commented", "1")', set()),
        ('  et.trap_Cvar_Set(  "spaced"  , x)', {"spaced"}),
    ],
)
def test_extractor_self_check(source: str, expected: set[str]) -> None:
    assert runtime_written_cvars(source) == expected


def readme_documented_cvars() -> set[str]:
    """Every cvar the README's own table presents as a knob.

    Rows look like `| `arena_vamp` | `0` | lifesteal |` and appear once per
    language section; the set is the union.
    """
    text = README.read_text(encoding="utf-8")
    return set(re.findall(r"^\|\s*`(arena_[A-Za-z0-9_]+)`\s*\|", text, re.M))


def test_the_readme_table_is_actually_parsed() -> None:
    """The vacuous half: an empty set would satisfy the contract below."""
    documented = readme_documented_cvars()
    assert len(documented) >= 10, (
        f"only {len(documented)} cvars parsed out of the README table — the "
        "row format changed and the contract below is measuring nothing"
    )


def test_every_cvar_the_readme_calls_a_knob_is_set_not_setl() -> None:
    """We shipped a README describing twelve runtime knobs, eleven of which
    were `setl` in the config we shipped beside it.

    `G_ConfigCheckLocked` (g_config.c:516) compares every `setl` cvar against
    its live value once per frame from `G_RunFrame` and, on the first
    difference, blanks CS_CONFIGNAME and memsets `level.config` — the whole
    ruleset gone, the cvar not restored. So a reader who followed our own
    instruction and typed `arena_1v1 0` destroyed the config that was making
    the arena work, on somebody else's server, with a message that names
    neither us nor the cvar.

    This is a contract across three files: the module writes some of these
    cvars, the README calls all of them adjustable, and the config decides
    whether adjusting one is a knob or a landmine.
    """
    locked = locked_cvars(CONFIG.read_text(encoding="utf-8"))
    clash = readme_documented_cvars() & locked
    assert not clash, (
        f"{sorted(clash)} are documented as runtime knobs but declared `setl`; "
        "changing one unloads the entire config (g_config.c:516)"
    )
