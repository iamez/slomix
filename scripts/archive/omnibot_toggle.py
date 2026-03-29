#!/usr/bin/env python3
"""
Toggle Omni-bot via RCON using .env settings.

Examples:
  python scripts/omnibot_toggle.py on --min 6 --max 8
  python scripts/omnibot_toggle.py off
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
    parser = argparse.ArgumentParser(description="Toggle Omni-bot via RCON")
    parser.add_argument("mode", choices=["on", "off"], help="Enable or disable bots")
    parser.add_argument("--min", type=int, default=6, help="MinBots when enabling")
    parser.add_argument("--max", type=int, default=8, help="MaxBots when enabling")
    parser.add_argument("--balance", type=int, default=1, help="BalanceTeams 0/1")
    parser.add_argument("--bots-per-human", type=int, default=3, help="BotsPerHuman")
    parser.add_argument("--bot-team", type=int, default=-1, help="BotTeam (-1 off, 1 axis, 2 allies)")
    parser.add_argument("--human-team", type=int, default=1, help="HumanTeam (1 axis, 2 allies)")
    args = parser.parse_args()

    load_env(Path(".env"))

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


if __name__ == "__main__":
    raise SystemExit(main())
