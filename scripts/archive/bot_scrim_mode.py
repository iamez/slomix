#!/usr/bin/env python3
"""
Enable/disable bot-only scrim mode (3v3) via RCON.

Usage:
  python scripts/bot_scrim_mode.py on
  python scripts/bot_scrim_mode.py on --auto-ready
  python scripts/bot_scrim_mode.py off
"""

import argparse
import logging
import os
import socket
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def send_rcon(host: str, port: int, password: str, command: str) -> str:
    packet = f"\xFF\xFF\xFF\xFFrcon {password} {command}".encode()
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


def main() -> int:
    logger.info("Script started: %s", __file__)
    parser = argparse.ArgumentParser(description="Toggle bot-only scrim mode (3v3)")
    parser.add_argument("mode", choices=["on", "off"], help="Enable or disable bot scrim mode")
    parser.add_argument("--auto-ready", action="store_true", help="Attempt to auto-ready and restart the round")
    parser.add_argument("--map", default="", help="Optional map to load when enabling")
    parser.add_argument(
        "--keep-map",
        action="store_true",
        help="Do not force a map change when enabling",
    )
    args = parser.parse_args()

    load_env(Path(".env"))

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


if __name__ == "__main__":
    raise SystemExit(main())
