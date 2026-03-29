#!/usr/bin/env python3
"""
Send a one-off RCON command using .env settings.

Usage:
  python scripts/rcon_command.py "lua_restart"
  python scripts/rcon_command.py "map_restart 0"
"""

import logging
import os
import socket
import sys
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


def main() -> int:
    logger.info("Script started: %s", __file__)
    if len(sys.argv) < 2:
        print("Usage: python scripts/rcon_command.py \"command\"")
        return 1

    load_env(Path(".env"))
    host = os.getenv("RCON_HOST")
    port = int(os.getenv("RCON_PORT", "27960"))
    password = os.getenv("RCON_PASSWORD")
    if not host or not password:
        print("[ERR] Missing RCON_HOST or RCON_PASSWORD in .env")
        return 1

    command = " ".join(sys.argv[1:])
    print(f"[INFO] Sending RCON: {command}")
    try:
        response = send_rcon(host, port, password, command)
        print("[OK] Response:")
        print(response)
        return 0
    except Exception as exc:
        print(f"[ERR] RCON failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
