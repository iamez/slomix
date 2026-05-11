"""Auth + CSRF + admin/promoter resolver helpers.

Extracted from ``website/backend/routers/availability.py`` to drop ~60 LOC
from that god file and let other routers share the same auth-resolution
contract without re-declaring private helpers.

Every function is a pure resolver over ``request.session`` or environment
variables — no DB, no IO — so they are safe to import from any router.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any

from fastapi import HTTPException, Request


def require_user(request: Request) -> dict[str, Any]:
    """Return the authenticated session user or raise 401."""
    user = request.session.get("user")
    if not user or "id" not in user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def optional_user(request: Request) -> dict[str, Any] | None:
    """Return the session user if logged in, otherwise None."""
    user = request.session.get("user")
    if not user or "id" not in user:
        return None
    return user


def optional_user_id(request: Request) -> int | None:
    """Return the session user's numeric id if logged in, otherwise None."""
    user = optional_user(request)
    if not user:
        return None
    try:
        return int(user["id"])
    except (TypeError, ValueError):
        return None


def require_ajax_csrf_header(request: Request) -> None:
    """Require a non-simple AJAX header on state-changing session routes."""
    if request.headers.get("x-requested-with", "").lower() != "xmlhttprequest":
        raise HTTPException(status_code=403, detail="Missing required CSRF header")


def configured_admin_ids() -> set[int]:
    """Read admin Discord IDs from env (multi-key compatible)."""
    ids: set[int] = set()
    for env_name in ("WEBSITE_ADMIN_DISCORD_IDS", "ADMIN_DISCORD_IDS", "OWNER_USER_ID"):
        raw = os.getenv(env_name, "")
        if not raw:
            continue
        for token in raw.split(","):
            token = token.strip()
            if token.isdigit():
                ids.add(int(token))
    return ids


def is_admin_user(request: Request) -> bool:
    """Return True iff the session user is in the configured admin set."""
    user_id = optional_user_id(request)
    if user_id is None:
        return False
    return user_id in configured_admin_ids()


def configured_promoter_ids() -> set[int]:
    """Read promoter Discord IDs from env (single-key)."""
    raw = os.getenv("PROMOTER_DISCORD_IDS", "")
    if not raw:
        return set()
    values: set[int] = set()
    for token in raw.split(","):
        token = token.strip()
        if token.isdigit():
            values.add(int(token))
    return values


def website_user_id_from_user(user: dict[str, Any]) -> int | None:
    """Return the canonical website-user id (preferring `website_user_id`)."""
    for key in ("website_user_id", "id"):
        raw = user.get(key)
        try:
            return int(raw)
        except (TypeError, ValueError):
            continue
    return None


def link_token_hash(raw_token: str) -> str:
    """SHA-256 of a raw verification token (channel-link flow)."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
