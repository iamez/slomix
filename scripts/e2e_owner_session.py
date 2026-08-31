#!/usr/bin/env python3
"""Mint a signed session cookie for the Playwright `owner` project.

The site's only login is Discord OAuth, which a headless run cannot walk —
so the owner storage state is minted the same way the backend itself would:
the session payload `_build_session_user` produces, base64-encoded and
signed with the SAME `SESSION_SECRET` starlette's SessionMiddleware uses
(TimestampSigner over b64(json), which is starlette's own cookie format).
This is a local test rig, not an auth bypass: it only works on a machine
that already holds the backend's secret, i.e. the machine running the
backend under test.

Prints the cookie VALUE to stdout and nothing else. Never prints the
secret; never writes a file. The caller (e2e/owner.setup.ts) turns it into
a gitignored storageState.

Identity: the values are read from the environment so nothing personal is
hard-coded in the repo — E2E_OWNER_DISCORD_ID and E2E_OWNER_GUID, with a
neutral local fallback that exercises "logged in" without claiming to be
anyone (auth surfaces gate on the session's existence, not on a specific
id).
"""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load_env() -> None:
    # SESSION_SECRET lives in website/.env (the backend's own env file);
    # the repo-root .env holds the bot's. Read both, backend first.
    for env in (REPO / "website" / ".env", REPO / ".env"):
        if env.exists():
            _load_env_file(env)


def _load_env_file(env: Path) -> None:
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def main() -> int:
    _load_env()
    secret = os.getenv("SESSION_SECRET")
    if not secret or secret == "super-secret-key-change-me":
        print("SESSION_SECRET is not configured; cannot mint a session", file=sys.stderr)
        return 1

    import itsdangerous

    discord_id = os.getenv("E2E_OWNER_DISCORD_ID", "1")
    guid = os.getenv("E2E_OWNER_GUID")
    user = {
        "id": str(discord_id),
        "username": "e2e-owner",
        "display_name": "e2e-owner",
        "avatar": None,
        "website_user_id": int(os.getenv("E2E_OWNER_WEBSITE_USER_ID", "1")),
        "linked_player": os.getenv("E2E_OWNER_PLAYER_NAME"),
        "linked_player_guid": guid,
    }
    payload = base64.b64encode(json.dumps({"user": user}).encode("utf-8"))
    signer = itsdangerous.TimestampSigner(secret)
    sys.stdout.write(signer.sign(payload).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
