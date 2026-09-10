#!/usr/bin/env python3
"""slomix_rcon.py — Unified RCON/server-control tool for Slomix.

Consolidates RCON scripts into a single CLI with subcommands:
  slomix_rcon.py cmd "lua_restart"
  slomix_rcon.py omnibot on --min 6 --max 8
  slomix_rcon.py omnibot off
  slomix_rcon.py scrim on [--auto-ready] [--map oasis]
  slomix_rcon.py scrim off
  slomix_rcon.py testmode on [--map supply]
  slomix_rcon.py testmode off
  slomix_rcon.py testmode status
  slomix_rcon.py botnames [--limit 24] [--prefix "^o[BOT]^7"] [--output path]

All scripts use .env for RCON configuration (RCON_HOST, RCON_PORT, RCON_PASSWORD).
The botnames subcommand also uses DB_HOST, DB_USER, etc. for database access.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import socket
import sys
from pathlib import Path
from typing import Iterable, List

# Setup sys.path and load .env
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

import asyncpg

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# SHARED RCON HELPERS
# ============================================================================

def send_rcon(host: str, port: int, password: str, command: str) -> str:
    packet = b"\xff\xff\xff\xffrcon " + f"{password} {command}".encode("utf-8")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5.0)
    try:
        sock.sendto(packet, (host, port))
        response, _ = sock.recvfrom(4096)
        decoded = response.decode("utf-8", errors="ignore")
        return decoded.split("\n", 1)[1] if "\n" in decoded else decoded
    finally:
        sock.close()


def run_commands(commands: list[str]) -> None:
    host = os.getenv("RCON_HOST")
    port = int(os.getenv("RCON_PORT", "27960"))
    password = os.getenv("RCON_PASSWORD")
    if not host or not password:
        raise RuntimeError("Missing RCON_HOST or RCON_PASSWORD in .env")

    for cmd in commands:
        print(f"[RCON] {cmd}")
        response = send_rcon(host, port, password, cmd)
        if response:
            print(response.strip())

# ============================================================================
# SUBCOMMAND: cmd
# ============================================================================

def cmd_cmd(args) -> int:
    host = os.getenv("RCON_HOST")
    port = int(os.getenv("RCON_PORT", "27960"))
    password = os.getenv("RCON_PASSWORD")
    if not host or not password:
        print("[ERR] Missing RCON_HOST or RCON_PASSWORD in .env")
        return 1

    command = " ".join(args.rcon_cmd)
    print(f"[INFO] Sending RCON: {command}")
    try:
        response = send_rcon(host, port, password, command)
        print("[OK] Response:")
        print(response)
        return 0
    except Exception as exc:
        print(f"[ERR] RCON failed: {exc}")
        return 1

# ============================================================================
# SUBCOMMAND: omnibot
# ============================================================================

def cmd_omnibot(args) -> int:
    if args.mode == "on":
        commands = [
            "set omnibot_enable 1",
            f"bot MinBots {args.min}",
            f"bot MaxBots {args.max}",
            f"bot BalanceTeams {args.balance}",
            f"bot BotTeam {args.bot_team}",
            f"bot HumanTeam {args.human_team}",
            f"bot BotsPerHuman {args.bots_per_human}",
        ]
    else:
        commands = [
            "bot MinBots -1",
            "bot MaxBots -1",
            "bot BotTeam -1",
            "set omnibot_enable 0",
        ]

    try:
        run_commands(commands)
        return 0
    except Exception as exc:
        print(f"[ERR] {exc}")
        return 1

# ============================================================================
# SUBCOMMAND: scrim
# ============================================================================

def cmd_scrim(args) -> int:
    if args.mode == "on":
        commands = [
            "set omnibot_enable 1",
            "bot MinBots 6",
            "bot MaxBots 6",
            "bot BalanceTeams 1",
            "bot BotTeam -1",
            "bot HumanTeam 1",
            "bot BotsPerHuman 0",
            "set match_readypercent 0",
            "set match_minplayers 0",
        ]
        commands.append("exec bot_scrim_mapcycle.cfg")
        if args.map:
            commands.append(f"map {args.map}")
        elif not args.keep_map:
            commands.append("vstr scrim_d1")
        if args.auto_ready:
            commands.extend([
                "ref allready",
                "map_restart 0",
            ])
    else:
        commands = [
            "bot MinBots -1",
            "bot MaxBots -1",
            "bot BotTeam -1",
            "set omnibot_enable 0",
            "set match_readypercent 100",
            "set match_minplayers 2",
        ]

    try:
        run_commands(commands)
        return 0
    except Exception as exc:
        print(f"[ERR] {exc}")
        return 1

# ============================================================================
# SUBCOMMAND: testmode
# ============================================================================

def cmd_testmode(args) -> int:
    """Switch between production and test (Omni-bot) server configuration."""
    host = os.getenv("RCON_HOST")
    port = int(os.getenv("RCON_PORT", "27960"))
    password = os.getenv("RCON_PASSWORD")
    if not host or not password:
        print("[ERR] Missing RCON_HOST or RCON_PASSWORD in .env")
        return 1

    if args.mode == "status":
        try:
            for cvar in ("omnibot_enable", "sv_hostname", "g_gametype", "timelimit"):
                resp = send_rcon(host, port, password, cvar)
                print(f"  {cvar}: {resp.strip()}")
            return 0
        except Exception as exc:
            print(f"[ERR] {exc}")
            return 1

    if args.mode == "on":
        commands = ["exec seareal.cfg"]
        if args.map:
            commands.append(f"map {args.map}")
        print("[INFO] Activating test mode (seareal.cfg)...")
        print("[INFO] Server auto-restores to production on 20:00 cron restart")
    else:
        commands = [
            # Same as: exec vektor.cfg — but without the map command
            "exec vektor.cfg",
        ]
        print("[INFO] Deactivating test mode (exec vektor.cfg)...")

    try:
        run_commands(commands)
        if args.mode == "on":
            print("\n[OK] Test mode active. Bots will populate and play automatically.")
            print("[OK] Monitor: ssh et@puran.hehe.si ls ~/.etlegacy/legacy/proximity/")
        else:
            print("\n[OK] Production settings restored.")
        return 0
    except Exception as exc:
        print(f"[ERR] {exc}")
        return 1

# ============================================================================
# SUBCOMMAND: botnames
# ============================================================================

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


def sanitize_name(raw: str, max_len: int) -> str:
    cleaned = COLOR_CODE_RE.sub("", raw)
    cleaned = CONTROL_RE.sub("", cleaned)
    cleaned = cleaned.replace('"', "").replace("\\", "")
    cleaned = cleaned.strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rstrip()
    return cleaned


async def fetch_recent_aliases(limit: int) -> List[str]:
    host = os.getenv("DB_HOST")
    port = int(os.getenv("DB_PORT", "5432"))
    database = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    if not (host and database and user and password):
        raise RuntimeError("Missing DB_* settings in .env")

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


def dedupe(items: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        key = item.lower()
        if key in seen or not item:
            continue
        seen.add(key)
        result.append(item)
    return result


def assign_names(names: List[str]) -> tuple[dict[str, List[str]], dict[str, List[str]]]:
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


def ensure_class_coverage(axis: dict[str, List[str]], allies: dict[str, List[str]], fallback: List[str]) -> None:
    fallback_iter = iter(fallback)
    for cls, _ in CLASSES:
        if not axis[cls]:
            axis[cls].append(next(fallback_iter))
        if not allies[cls]:
            allies[cls].append(next(fallback_iter))


def gm_escape(name: str) -> str:
    return name.replace("\\", "").replace('"', "")


def render_botnames(axis: dict[str, List[str]], allies: dict[str, List[str]], prefix: str, extra: List[str]) -> str:
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


async def _run_botnames(args) -> int:
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


def cmd_botnames(args) -> int:
    return asyncio.run(_run_botnames(args))

# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Unified RCON/server-control tool for Slomix",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/slomix_rcon.py cmd "lua_restart"
  python tools/slomix_rcon.py cmd "map_restart 0"
  python tools/slomix_rcon.py omnibot on --min 6 --max 8
  python tools/slomix_rcon.py omnibot off
  python tools/slomix_rcon.py scrim on --auto-ready
  python tools/slomix_rcon.py scrim off
  python tools/slomix_rcon.py botnames --limit 24 --output server/omnibot/et_botnames_ext.gm
        """
    )

    subs = parser.add_subparsers(dest='command', required=True, help='RCON subcommand')

    # CMD subcommand
    sub = subs.add_parser('cmd', help='Send a one-off RCON command')
    sub.add_argument('rcon_cmd', nargs='+', help='RCON command to send')
    sub.set_defaults(func=cmd_cmd)

    # OMNIBOT subcommand
    sub = subs.add_parser('omnibot', help='Toggle Omni-bot via RCON')
    sub.add_argument('mode', choices=['on', 'off'], help='Enable or disable bots')
    sub.add_argument('--min', type=int, default=6, help='MinBots when enabling')
    sub.add_argument('--max', type=int, default=8, help='MaxBots when enabling')
    sub.add_argument('--balance', type=int, default=1, help='BalanceTeams 0/1')
    sub.add_argument('--bots-per-human', type=int, default=3, help='BotsPerHuman')
    sub.add_argument('--bot-team', type=int, default=-1, help='BotTeam (-1 off, 1 axis, 2 allies)')
    sub.add_argument('--human-team', type=int, default=1, help='HumanTeam (1 axis, 2 allies)')
    sub.set_defaults(func=cmd_omnibot)

    # SCRIM subcommand
    sub = subs.add_parser('scrim', help='Enable/disable bot-only scrim mode (3v3)')
    sub.add_argument('mode', choices=['on', 'off'], help='Enable or disable bot scrim mode')
    sub.add_argument('--auto-ready', action='store_true', help='Attempt to auto-ready and restart the round')
    sub.add_argument('--map', default='', help='Optional map to load when enabling')
    sub.add_argument('--keep-map', action='store_true', help='Do not force a map change when enabling')
    sub.set_defaults(func=cmd_scrim)

    # TESTMODE subcommand
    sub = subs.add_parser('testmode', help='Switch between production and test (Omni-bot) mode')
    sub.add_argument('mode', choices=['on', 'off', 'status'], help='Enable/disable test mode or check status')
    sub.add_argument('--map', default='', help='Override starting map (default: supply from seareal.cfg)')
    sub.set_defaults(func=cmd_testmode)

    # BOTNAMES subcommand
    sub = subs.add_parser('botnames', help='Generate et_botnames_ext.gm from recent player aliases')
    sub.add_argument('--limit', type=int, default=24, help='Max recent aliases to pull from DB')
    sub.add_argument('--max-name-len', type=int, default=20, help='Max bot name length (prefix not included)')
    sub.add_argument(
        '--prefix',
        default='^o[BOT]^7',
        help='Bot name prefix (color codes allowed), default "^o[BOT]^7"',
    )
    sub.add_argument(
        '--output',
        default='server/omnibot/et_botnames_ext.gm',
        help='Output GM file path',
    )
    sub.set_defaults(func=cmd_botnames)

    args = parser.parse_args()
    logger.info("Script started: %s with command: %s", __file__, args.command)

    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
