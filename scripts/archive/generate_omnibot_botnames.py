#!/usr/bin/env python3
"""
Generate an Omni-bot name list from most recently active players.

Output: a full et_botnames_ext.gm file that sets BotPrefix + per-class names.
Default output: server/omnibot/et_botnames_ext.gm

Requires .env with POSTGRES_* settings (or set env vars explicitly).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
from pathlib import Path
from typing import Iterable

import asyncpg

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

COLOR_CODE_RE = re.compile(r"\^(?:[0-9a-zA-Z])")
CONTROL_RE = re.compile(r"[\x00-\x1F\x7F]")

FALLBACK_NAMES = [
    "SuperBoyy",
    "Olympus",
    "lagger",
    "carniee",
    "wajs",
    "bronze",
    "vid",
    "endekk",
    "olz",
    "Proner2026",
    "KomandantVarga",
]

CLASSES = [
    ("COVERTOPS", "Covert Ops"),
    ("ENGINEER", "Engineers"),
    ("FIELDOPS", "Field Ops"),
    ("MEDIC", "Medics"),
    ("SOLDIER", "Soldiers"),
]


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def sanitize_name(raw: str, max_len: int) -> str:
    cleaned = COLOR_CODE_RE.sub("", raw)
    cleaned = CONTROL_RE.sub("", cleaned)
    cleaned = cleaned.replace('"', "").replace("\\", "")
    cleaned = cleaned.strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rstrip()
    return cleaned


async def fetch_recent_aliases(limit: int) -> list[str]:
    host = os.getenv("POSTGRES_HOST")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    database = os.getenv("POSTGRES_DATABASE")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    if not (host and database and user and password):
        raise RuntimeError("Missing POSTGRES_* settings in .env")

    conn = await asyncpg.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )
    try:
        rows = await conn.fetch(
            """
            WITH latest AS (
                SELECT DISTINCT ON (guid)
                    guid,
                    alias,
                    last_seen
                FROM player_aliases
                WHERE alias IS NOT NULL
                  AND alias <> ''
                ORDER BY guid, last_seen DESC
            )
            SELECT alias
            FROM latest
            ORDER BY last_seen DESC
            LIMIT $1
            """,
            limit,
        )
        return [r["alias"] for r in rows]
    finally:
        await conn.close()


def dedupe(items: Iterable[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        key = item.lower()
        if key in seen or not item:
            continue
        seen.add(key)
        result.append(item)
    return result


def assign_names(names: list[str]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    axis = {cls: [] for cls, _ in CLASSES}
    allies = {cls: [] for cls, _ in CLASSES}
    axis_idx = 0
    allies_idx = 0

    for idx, name in enumerate(names):
        if idx % 2 == 0:
            cls = CLASSES[axis_idx % len(CLASSES)][0]
            axis[cls].append(name)
            axis_idx += 1
        else:
            cls = CLASSES[allies_idx % len(CLASSES)][0]
            allies[cls].append(name)
            allies_idx += 1

    return axis, allies


def ensure_class_coverage(axis: dict[str, list[str]], allies: dict[str, list[str]], fallback: list[str]) -> None:
    fallback_iter = iter(fallback)
    for cls, _ in CLASSES:
        if not axis[cls]:
            axis[cls].append(next(fallback_iter))
        if not allies[cls]:
            allies[cls].append(next(fallback_iter))


def gm_escape(name: str) -> str:
    return name.replace("\\", "").replace('"', "")


def render_botnames(axis: dict[str, list[str]], allies: dict[str, list[str]], prefix: str, extra: list[str]) -> str:
    lines = []
    lines.append("/////////////////////////////////////////////////////////////////////")
    lines.append("// initialize the team tables")
    lines.append("AxisBots = {};")
    lines.append("AlliedBots = {};")
    lines.append("")
    lines.append("/////////////////////////////////////////////////////////////////////")
    lines.append("// USER CONFIG STARTS HERE")
    lines.append("/////////////////////////////////////////////////////////////////////")
    lines.append("")
    lines.append("/////////////////////////////////////////////////////////////////////")
    lines.append("// Register default profiles for the game classes.")
    lines.append("foreach (cls in Util.PlayerClassTable)")
    lines.append("{")
    lines.append('\tRegisterDefaultProfile(cls, "def_bot.gm");')
    lines.append("}")
    lines.append("")
    lines.append("/////////////////////////////////////////////////////////////////////")
    lines.append("// optionally assign a prefix for the bot name. set to \"\" for no prefix")
    lines.append(f'global BotPrefix = "{prefix}";')
    lines.append("global AxisBotPrefix = BotPrefix;")
    lines.append("global AlliedBotPrefix = BotPrefix;")
    lines.append("")

    lines.append("/////////////////////////////////////////////////////////////////////")
    lines.append("// Axis Bots")
    for cls, label in CLASSES:
        lines.append("")
        lines.append(f"// {label}")
        lines.append(f't = {{ class=CLASS.{cls}, weapon=0, profile="" }};')
        for name in axis[cls]:
            lines.append(f'AxisBots["{gm_escape(name)}"] = t;')

    lines.append("")
    lines.append("/////////////////////////////////////////////////////////////////////")
    lines.append("// Allied Bots")
    for cls, label in CLASSES:
        lines.append("")
        lines.append(f"// {label}")
        lines.append(f't = {{ class=CLASS.{cls}, weapon=0, profile="" }};')
        for name in allies[cls]:
            lines.append(f'AlliedBots["{gm_escape(name)}"] = t;')

    lines.append("")
    lines.append("/////////////////////////////////////////////////////////////////////")
    lines.append("// Overflow bots - used if no bots left for team / class desired")
    lines.append("global ExtraBots =")
    lines.append("{")
    for name in extra:
        lines.append(f'\t"{gm_escape(name)}",')
    lines.append("};")
    lines.append("")
    lines.append("/////////////////////////////////////////////////////////////////////")
    lines.append("// END USER CONFIG. DO NOT EDIT BELOW")
    lines.append("/////////////////////////////////////////////////////////////////////")
    lines.append("")
    lines.append("/////////////////////////////////////////////////////////////////////")
    lines.append("// initialize some global tables for external reference")
    lines.append("// the previous tables are set up for user friendliness")
    lines.append("global _AxisBots = {};")
    lines.append("global _AlliedBots = {};")
    lines.append("global _PreferredWeapon = {};")
    lines.append("global _OverFlowBotNumber = 0;")
    lines.append("")
    lines.append("/////////////////////////////////////////////////////////////////////")
    lines.append("// register the bot names and set up tables for OnBotAutoJoin reference")
    lines.append("")
    lines.append("InitNames = function ( tbl1, tbl2, prefix)")
    lines.append("{")
    lines.append("\tforeach ( botName and loadout in tbl1 ) {")
    lines.append("\t\tname = prefix + botName;")
    lines.append("\t\tNames[ name ] = loadout.profile;")
    lines.append("\t\tif (!tbl2[ loadout.class ]) {")
    lines.append("\t\t\ttbl2[ loadout.class ] = {};")
    lines.append("\t\t}")
    lines.append("\t\t// add the name to the list")
    lines.append("\t\tUtil.AddToTable(tbl2[ loadout.class ], name);")
    lines.append("")
    lines.append("\t\tif (loadout.weapon) {")
    lines.append("\t\t\t_PreferredWeapon[ name ] = loadout.weapon;")
    lines.append("\t\t}")
    lines.append("\t}")
    lines.append("};")
    lines.append("")
    lines.append("InitNames(AxisBots, _AxisBots, AxisBotPrefix);")
    lines.append("InitNames(AlliedBots, _AlliedBots, AlliedBotPrefix);")
    lines.append("")
    lines.append("/////////////////////////////////////////////////////////////////////")
    lines.append("// pick a bot to add based on team / class needed")
    lines.append("global OnBotAutoJoin = function()")
    lines.append("{")
    lines.append("\tdesiredTeam = TEAM.AXIS;")
    lines.append("\tif ( tableCount(Server.Team)>0 && (Server.Team[TEAM.AXIS].NumPlayers > Server.Team[TEAM.ALLIES].NumPlayers")
    lines.append("\t\t|| Server.Team[TEAM.AXIS].NumPlayers == Server.Team[TEAM.ALLIES].NumPlayers && Server.Team[TEAM.AXIS].NumBots > Server.Team[TEAM.ALLIES].NumBots)")
    lines.append('\t\t|| GetModName() == "infected") {')
    lines.append("\t\tdesiredTeam = TEAM.ALLIES;")
    lines.append("\t}")
    lines.append("")
    lines.append("\tdesiredClass = ClassManager.EvalClassByTeam(desiredTeam);")
    lines.append("")
    lines.append("\tteamTable = _AxisBots;")
    lines.append("\tif ( desiredTeam == TEAM.ALLIES ) {")
    lines.append("\t\tteamTable = _AlliedBots;")
    lines.append("\t}")
    lines.append("")
    lines.append("\t// find a bot for the team and class. sequential lookup for now.")
    lines.append("\t// cs: note: gm tables are actually randomized, so bots will vary")
    lines.append("\t// from game to game.")
    lines.append("\tbotName = null;")
    lines.append("\tif ( teamTable[ desiredClass ] ) {")
    lines.append("\t\tforeach ( name in teamTable[ desiredClass ] ) {")
    lines.append("\t\t\t// make sure this name is not already used")
    lines.append("\t\t\tif ( !Util.GetBotByName(name) ) {")
    lines.append("\t\t\t\tbotName = name;")
    lines.append("\t\t\t\tbreak;")
    lines.append("\t\t\t}")
    lines.append("\t\t}")
    lines.append("\t}")
    lines.append("")
    lines.append("\tif ( !botName && _OverFlowBotNumber < tableCount(ExtraBots) ) {")
    lines.append("\t\tbotName = ExtraBots[_OverFlowBotNumber];")
    lines.append("\t\tglobal _OverFlowBotNumber = _OverFlowBotNumber + 1;")
    lines.append("")
    lines.append("\t\tif ( desiredTeam == TEAM.ALLIES ) {")
    lines.append("\t\t\tbotName = AlliedBotPrefix + botName;")
    lines.append("\t\t} else {")
    lines.append("\t\t\tbotName = AxisBotPrefix + botName;")
    lines.append("\t\t}")
    lines.append("\t}")
    lines.append("")
    lines.append("\treturn { class = desiredClass, team = desiredTeam, name = botName };")
    lines.append("};")
    lines.append("")
    return "\n".join(lines)


async def main() -> int:
    logger.info("Script started: %s", __file__)
    parser = argparse.ArgumentParser(description="Generate et_botnames_ext.gm from recent player aliases")
    parser.add_argument("--limit", type=int, default=24, help="Max recent aliases to pull from DB")
    parser.add_argument("--max-name-len", type=int, default=20, help="Max bot name length (prefix not included)")
    parser.add_argument(
        "--prefix",
        default="^o[BOT]^7",
        help='Bot name prefix (color codes allowed), default "^o[BOT]^7"',
    )
    parser.add_argument(
        "--output",
        default="server/omnibot/et_botnames_ext.gm",
        help="Output GM file path",
    )
    args = parser.parse_args()

    load_env(Path(".env"))

    try:
        recent = await fetch_recent_aliases(args.limit)
    except Exception as exc:
        print(f"[WARN] Could not fetch recent aliases from DB: {exc}")
        recent = []

    sanitized = [sanitize_name(name, args.max_name_len) for name in recent]
    sanitized = [name for name in sanitized if name]
    sanitized = dedupe(sanitized)

    fallback = [sanitize_name(name, args.max_name_len) for name in FALLBACK_NAMES]
    fallback = dedupe(fallback)

    combined = dedupe(sanitized + fallback)
    if len(combined) < 10:
        combined = dedupe(combined + [f"Bot{idx}" for idx in range(1, 16)])

    axis, allies = assign_names(combined)
    ensure_class_coverage(axis, allies, fallback + combined)

    extra = [name for name in combined if name not in sum(axis.values(), []) + sum(allies.values(), [])]
    if not extra:
        extra = ["ExtraOne", "ExtraTwo", "ExtraThree"]

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_botnames(axis, allies, args.prefix, extra), encoding="utf-8")

    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
