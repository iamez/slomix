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
    # the repo-root .env holds the bot's. Read both, backend first — and
    # with the SAME loader the backend uses: a hand parser kept quotes,
    # `export` prefixes and inline comments in the value, so the cookie
    # was signed with a different secret and /auth/me answered 401
    # (Codex on #855, round four).
    from dotenv import dotenv_values

    for env in (REPO / "website" / ".env", REPO / ".env"):
        if not env.exists():
            continue
        for key, value in dotenv_values(env).items():
            if value is not None:
                os.environ.setdefault(key, value)


def mint_session_cookie() -> str:
    """The signed cookie VALUE for the sentinel identity (E2E_OWNER_* env),
    or '' with the reason on stderr. Importable: scripts/record_api_corpus.py
    --sentinel calls this instead of spawning the script, so the recorder
    and the Playwright rig cannot drift apart on how the cookie is minted."""
    _load_env()
    secret = os.getenv("SESSION_SECRET")
    if not secret or secret == "super-secret-key-change-me":  # noqa: S105 — the known placeholder, not a credential (same check as main.py)
        print("SESSION_SECRET is not configured; cannot mint a session", file=sys.stderr)
        return ""

    import itsdangerous

    # ⛔ The identity defaults are SENTINELS that cannot collide with a real
    # account (Codex on #855, round seven): website user ids are positive
    # serials and Discord snowflakes are non-zero, so -1 / "0" can never
    # address the first real user on a populated database. Authenticated
    # availability/planning routes trust website_user_id from the session —
    # a default of 1 would have made every owner spec read (and potentially
    # mutate) the first human's data. Real ids come only from explicit
    # E2E_OWNER_* configuration.
    discord_id = os.getenv("E2E_OWNER_DISCORD_ID", "0")
    guid = os.getenv("E2E_OWNER_GUID")
    user = {
        "id": str(discord_id),
        "username": "e2e-owner",
        "display_name": "e2e-owner",
        "avatar": None,
        "website_user_id": int(os.getenv("E2E_OWNER_WEBSITE_USER_ID", "-1")),
        "linked_player": os.getenv("E2E_OWNER_PLAYER_NAME"),
        "linked_player_guid": guid,
    }
    payload = base64.b64encode(json.dumps({"user": user}).encode("utf-8"))
    signer = itsdangerous.TimestampSigner(secret)
    return signer.sign(payload).decode("utf-8")


def main() -> int:
    cookie = mint_session_cookie()
    if not cookie:
        return 1
    sys.stdout.write(cookie)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
