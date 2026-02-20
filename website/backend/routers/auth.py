import base64
import hashlib
import json
import os
import secrets
import time
from collections import defaultdict, deque
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from bot.core.database_adapter import DatabaseAdapter
from website.backend.dependencies import get_db
from website.backend.logging_config import get_app_logger
from website.backend.routers.api import resolve_display_name

# Load .env file explicitly
load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

logger = get_app_logger("auth.router")
router = APIRouter()

OAUTH_STATE_TTL_SECONDS = max(60, int(os.getenv("DISCORD_OAUTH_STATE_TTL_SECONDS", "600")))
OAUTH_RATE_LIMIT_WINDOW_SECONDS = max(10, int(os.getenv("DISCORD_OAUTH_RATE_LIMIT_WINDOW_SECONDS", "60")))
OAUTH_RATE_LIMIT_MAX_REQUESTS = max(5, int(os.getenv("DISCORD_OAUTH_RATE_LIMIT_MAX_REQUESTS", "40")))

_oauth_rate_buckets: dict[str, deque[float]] = defaultdict(deque)


def _require_ajax_csrf_header(request: Request) -> None:
    """
    Lightweight CSRF hardening: require a non-simple AJAX header on
    state-changing session routes.
    """
    if request.headers.get("x-requested-with", "").lower() != "xmlhttprequest":
        raise HTTPException(status_code=403, detail="Missing required CSRF header")


def _normalize_redirect_uri(value: str) -> str:
    parsed = urlsplit(str(value or "").strip())
    if not parsed.scheme or not parsed.netloc:
        raise HTTPException(status_code=500, detail="Invalid DISCORD_REDIRECT_URI configuration")
    path = parsed.path or ""
    return f"{parsed.scheme.lower()}://{parsed.netloc}{path}"


def _redirect_allowlist(default_redirect_uri: str) -> set[str]:
    allowlist_raw = os.getenv("DISCORD_REDIRECT_URI_ALLOWLIST", "").strip()
    entries = [item.strip() for item in allowlist_raw.split(",") if item.strip()]
    if not entries:
        entries = [default_redirect_uri]
    normalized = {_normalize_redirect_uri(entry) for entry in entries}
    normalized.add(default_redirect_uri)
    return normalized


def get_discord_config() -> dict[str, Any]:
    """Get Discord config at runtime (after .env is loaded)."""
    redirect_uri = _normalize_redirect_uri(
        os.getenv("DISCORD_REDIRECT_URI", "http://localhost:8000/auth/callback")
    )
    allowlist = _redirect_allowlist(redirect_uri)
    if redirect_uri not in allowlist:
        raise HTTPException(status_code=500, detail="DISCORD_REDIRECT_URI is not allowlisted")

    return {
        "client_id": os.getenv("DISCORD_CLIENT_ID"),
        "client_secret": os.getenv("DISCORD_CLIENT_SECRET"),
        "redirect_uri": redirect_uri,
        "redirect_allowlist": allowlist,
    }


def get_frontend_origin(config: dict[str, Any]) -> str:
    """Return canonical frontend origin for post-auth redirects."""
    configured_origin = (
        os.getenv("FRONTEND_ORIGIN")
        or os.getenv("PUBLIC_FRONTEND_ORIGIN")
        or ""
    ).strip()
    if configured_origin:
        parsed = urlsplit(configured_origin)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"

    redirect_uri = str(config.get("redirect_uri") or "").strip()
    parsed_redirect = urlsplit(redirect_uri)
    if parsed_redirect.scheme and parsed_redirect.netloc:
        return f"{parsed_redirect.scheme}://{parsed_redirect.netloc}"

    return "http://localhost:8000"


def _oauth_bucket_key(request: Request, endpoint: str) -> str:
    client_host = request.client.host if request.client and request.client.host else "unknown"
    return f"{endpoint}:{client_host}"


def _enforce_oauth_rate_limit(request: Request, endpoint: str) -> None:
    """Additional guardrail for OAuth endpoints on top of global middleware."""
    now = time.monotonic()
    cutoff = now - OAUTH_RATE_LIMIT_WINDOW_SECONDS
    key = _oauth_bucket_key(request, endpoint)
    bucket = _oauth_rate_buckets[key]

    while bucket and bucket[0] <= cutoff:
        bucket.popleft()

    if len(bucket) >= OAUTH_RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail="OAuth rate limit exceeded",
        )

    bucket.append(now)


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _require_session_user(request: Request) -> dict[str, Any]:
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


async def _audit_link_event(
    db: DatabaseAdapter,
    *,
    user_id: int,
    discord_user_id: int,
    action: str,
    actor_discord_id: int,
    metadata: dict[str, Any] | None = None,
) -> None:
    payload = json.dumps(metadata or {}, ensure_ascii=True)
    try:
        await db.execute(
            """
            INSERT INTO account_link_audit_log
                (user_id, discord_user_id, action, actor_discord_id, metadata, created_at)
            VALUES ($1, $2, $3, $4, CAST($5 AS JSONB), CURRENT_TIMESTAMP)
            """,
            (user_id, discord_user_id, action, actor_discord_id, payload),
        )
    except Exception as exc:  # pragma: no cover - best effort audit
        logger.warning("Failed to write account link audit log: %s", exc)


async def _sync_website_identity(
    db: DatabaseAdapter,
    *,
    discord_id: int,
    username: str,
    display_name: str,
    avatar: str | None,
) -> dict[str, Any]:
    """
    Sync Discord identity into website account tables and bridge legacy link table.

    `website_users.id` intentionally mirrors Discord ID to avoid a breaking user-id
    migration while still giving us explicit website account rows.
    """
    user_id = int(discord_id)
    linked_player_guid = None
    linked_player_name = None

    identity_tables_ready = True
    try:
        await db.execute(
            """
            INSERT INTO website_users (id, created_at, updated_at, last_login_at)
            VALUES ($1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (id) DO UPDATE SET
                updated_at = CURRENT_TIMESTAMP,
                last_login_at = CURRENT_TIMESTAMP
            """,
            (user_id,),
        )

        await db.execute(
            """
            INSERT INTO discord_accounts
                (user_id, discord_user_id, username, display_name, avatar, linked_at, last_refreshed_at)
            VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (discord_user_id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                username = EXCLUDED.username,
                display_name = EXCLUDED.display_name,
                avatar = EXCLUDED.avatar,
                last_refreshed_at = CURRENT_TIMESTAMP
            """,
            (user_id, discord_id, username, display_name, avatar),
        )

        row = await db.fetch_one(
            """
            SELECT player_guid, player_name
            FROM user_player_links
            WHERE user_id = $1
            LIMIT 1
            """,
            (user_id,),
        )
        if row:
            linked_player_guid = row[0]
            linked_player_name = row[1]
    except Exception as exc:
        identity_tables_ready = False
        logger.warning("Website identity tables unavailable, using legacy fallback: %s", exc)

    # Legacy compatibility bridge for existing player_links consumers.
    legacy_row = await db.fetch_one(
        "SELECT player_guid, player_name FROM player_links WHERE discord_id = $1 LIMIT 1",
        (discord_id,),
    )
    if legacy_row and not linked_player_guid:
        linked_player_guid = legacy_row[0]
        linked_player_name = legacy_row[1]
        if identity_tables_ready:
            try:
                await db.execute(
                    """
                    INSERT INTO user_player_links
                        (user_id, player_guid, player_name, linked_at, updated_at)
                    VALUES ($1, $2, $3, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id) DO UPDATE SET
                        player_guid = EXCLUDED.player_guid,
                        player_name = EXCLUDED.player_name,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (user_id, linked_player_guid, linked_player_name),
                )
            except Exception as exc:
                logger.warning("Failed syncing legacy player link into user_player_links: %s", exc)

    if linked_player_guid and not legacy_row:
        # Keep legacy table populated for bot/cog compatibility.
        try:
            await db.execute(
                """
                INSERT INTO player_links (player_guid, discord_id, discord_username, player_name, linked_at)
                VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
                ON CONFLICT (discord_id) DO UPDATE SET
                    player_guid = EXCLUDED.player_guid,
                    discord_username = EXCLUDED.discord_username,
                    player_name = EXCLUDED.player_name,
                    linked_at = CURRENT_TIMESTAMP
                """,
                (linked_player_guid, discord_id, username, linked_player_name),
            )
        except Exception as exc:
            logger.warning("Failed syncing user_player_links into player_links: %s", exc)

    return {
        "user_id": user_id,
        "linked_player_guid": linked_player_guid,
        "linked_player_name": linked_player_name,
    }


def _build_session_user(
    *,
    discord_id: int,
    username: str,
    display_name: str,
    avatar: str | None,
    website_user_id: int,
    linked_player_guid: str | None,
    linked_player_name: str | None,
) -> dict[str, Any]:
    return {
        "id": str(discord_id),
        "username": username,
        "display_name": display_name,
        "avatar": avatar,
        "website_user_id": website_user_id,
        "linked_player": linked_player_name,
        "linked_player_guid": linked_player_guid,
    }


def _discord_identity(payload: dict[str, Any]) -> tuple[int, str, str, str | None]:
    discord_id = _safe_int(payload.get("id"))
    if discord_id is None:
        raise HTTPException(status_code=400, detail="Discord user payload missing id")

    username = str(payload.get("username") or f"discord-{discord_id}").strip()[:100]
    display_name = str(payload.get("global_name") or username).strip()[:100]
    avatar = payload.get("avatar")
    avatar_text = str(avatar).strip()[:200] if avatar else None

    return discord_id, username, display_name, avatar_text


@router.get("/login")
async def login(request: Request):
    _enforce_oauth_rate_limit(request, "login")

    config = get_discord_config()
    if not config["client_id"]:
        raise HTTPException(status_code=500, detail="Discord Client ID not configured")

    state = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = _pkce_challenge(code_verifier)

    request.session["oauth_state"] = state
    request.session["oauth_state_issued_at"] = int(time.time())
    request.session["oauth_pkce_verifier"] = code_verifier

    auth_query = urlencode(
        {
            "client_id": config["client_id"],
            "redirect_uri": config["redirect_uri"],
            "response_type": "code",
            "scope": "identify",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    return RedirectResponse(f"https://discord.com/api/oauth2/authorize?{auth_query}")


@router.get("/callback")
async def callback(
    request: Request,
    code: str,
    state: str | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    _enforce_oauth_rate_limit(request, "callback")

    config = get_discord_config()
    if not config["client_id"] or not config["client_secret"]:
        raise HTTPException(status_code=500, detail="Discord credentials not configured")

    expected_state = request.session.pop("oauth_state", None)
    state_issued_at = _safe_int(request.session.pop("oauth_state_issued_at", None)) or 0
    code_verifier = request.session.pop("oauth_pkce_verifier", None)

    state_is_valid = bool(
        state
        and expected_state
        and secrets.compare_digest(str(state), str(expected_state))
    )
    state_not_expired = (int(time.time()) - state_issued_at) <= OAUTH_STATE_TTL_SECONDS

    if not state_is_valid or not state_not_expired or not code_verifier:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    async with httpx.AsyncClient(timeout=20.0) as client:
        token_resp = await client.post(
            "https://discord.com/api/oauth2/token",
            data={
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": config["redirect_uri"],
                "code_verifier": code_verifier,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if token_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get token from Discord")

        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="Discord token payload missing access token")

        user_resp = await client.get(
            "https://discord.com/api/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if user_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get user info")

        user_data = user_resp.json()

    discord_id, username, display_name, avatar = _discord_identity(user_data)

    website_user_id = discord_id
    linked_player_guid = None
    linked_player_name = None
    if db is not None:
        state_payload = await _sync_website_identity(
            db,
            discord_id=discord_id,
            username=username,
            display_name=display_name,
            avatar=avatar,
        )
        website_user_id = int(state_payload["user_id"])
        linked_player_guid = state_payload.get("linked_player_guid")
        linked_player_name = state_payload.get("linked_player_name")

    request.session["user"] = _build_session_user(
        discord_id=discord_id,
        username=username,
        display_name=display_name,
        avatar=avatar,
        website_user_id=website_user_id,
        linked_player_guid=linked_player_guid,
        linked_player_name=linked_player_name,
    )

    frontend_origin = get_frontend_origin(config)
    if linked_player_name:
        return RedirectResponse(url=f"{frontend_origin}/")
    return RedirectResponse(url=f"{frontend_origin}/#/profile")


@router.post("/logout")
async def logout(request: Request):
    _require_ajax_csrf_header(request)
    request.session.clear()
    frontend_origin = get_frontend_origin(get_discord_config())
    response = JSONResponse({"ok": True, "redirect_url": f"{frontend_origin}/"})
    response.delete_cookie("session")
    return response


@router.get("/me")
async def get_current_user(request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


@router.get("/link/start")
async def start_link_flow(request: Request):
    """Entry point used by CTA buttons to start/continue account linking."""
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/auth/login")

    frontend_origin = get_frontend_origin(get_discord_config())
    return RedirectResponse(url=f"{frontend_origin}/#/profile")


@router.get("/link/status")
async def get_link_status(request: Request, db: DatabaseAdapter = Depends(get_db)):
    user = request.session.get("user")
    if not user:
        return {
            "authenticated": False,
            "discord_linked": False,
            "player_linked": False,
        }

    discord_id = _safe_int(user.get("id"))
    website_user_id = _safe_int(user.get("website_user_id")) or discord_id
    linked_player_guid = None
    linked_player_name = user.get("linked_player")

    if website_user_id and db is not None:
        try:
            row = await db.fetch_one(
                """
                SELECT player_guid, player_name
                FROM user_player_links
                WHERE user_id = $1
                LIMIT 1
                """,
                (int(website_user_id),),
            )
            if row:
                linked_player_guid = row[0]
                linked_player_name = row[1]
        except Exception:
            # Backward-compatible fallback while migration rolls out.
            if discord_id:
                row = await db.fetch_one(
                    "SELECT player_guid, player_name FROM player_links WHERE discord_id = $1 LIMIT 1",
                    (int(discord_id),),
                )
                if row:
                    linked_player_guid = row[0]
                    linked_player_name = row[1]

    return {
        "authenticated": True,
        "discord_linked": bool(discord_id),
        "player_linked": bool(linked_player_guid or linked_player_name),
        "discord_user_id": discord_id,
        "website_user_id": website_user_id,
        "linked_player": {
            "guid": linked_player_guid,
            "name": linked_player_name,
        },
    }


@router.get("/players/search")
async def search_players(q: str, db: DatabaseAdapter = Depends(get_db)):
    """Search for players by name to link to Discord account."""
    if not q or len(q) < 2:
        return []

    like_query = f"%{q}%"
    advanced_query = """
        WITH candidates AS (
            SELECT DISTINCT player_guid
            FROM player_comprehensive_stats
            WHERE LOWER(player_name) LIKE LOWER($1)
               OR LOWER(clean_name) LIKE LOWER($1)
            UNION
            SELECT DISTINCT guid
            FROM player_aliases
            WHERE LOWER(alias) LIKE LOWER($1)
        )
        SELECT
            c.player_guid,
            MAX(p.player_name) as player_name,
            MAX(p.clean_name) as clean_name
        FROM candidates c
        LEFT JOIN player_comprehensive_stats p
            ON p.player_guid = c.player_guid
        GROUP BY c.player_guid
        ORDER BY MAX(p.player_name) NULLS LAST
        LIMIT 20
    """
    fallback_query = """
        SELECT
            player_guid,
            MAX(player_name) as player_name,
            MAX(clean_name) as clean_name
        FROM player_comprehensive_stats
        WHERE LOWER(player_name) LIKE LOWER($1)
           OR LOWER(clean_name) LIKE LOWER($1)
        GROUP BY player_guid
        ORDER BY MAX(player_name)
        LIMIT 20
    """

    try:
        rows = await db.fetch_all(advanced_query, (like_query,))
    except Exception:
        rows = await db.fetch_all(fallback_query, (like_query,))

    results = []
    for guid, player_name, clean_name in rows:
        fallback_name = player_name or clean_name or guid
        display_name = await resolve_display_name(db, guid, fallback_name)
        results.append(
            {
                "guid": guid,
                "name": display_name,
                "clean_name": clean_name,
                "canonical_name": player_name or clean_name or display_name,
            }
        )
    return results


@router.get("/players/suggestions")
async def suggested_players_for_me(request: Request, db: DatabaseAdapter = Depends(get_db)):
    user = _require_session_user(request)

    terms: list[str] = []
    for raw_term in [user.get("display_name"), user.get("username")]:
        token = str(raw_term or "").strip()
        if len(token) < 2:
            continue
        lowered = token.lower()
        if lowered in {term.lower() for term in terms}:
            continue
        terms.append(token)

    suggestions = []
    seen_guids: set[str] = set()
    for term in terms:
        matches = await search_players(term, db)
        for match in matches:
            guid = str(match.get("guid") or "")
            if not guid or guid in seen_guids:
                continue
            seen_guids.add(guid)
            suggestions.append(match)
            if len(suggestions) >= 12:
                break
        if len(suggestions) >= 12:
            break

    return {
        "terms": terms,
        "suggestions": suggestions,
        "ambiguous": len(suggestions) > 1,
    }


@router.post("/link")
async def link_player(request: Request, db: DatabaseAdapter = Depends(get_db)):
    """Link logged-in Discord user to an ET player."""
    _require_ajax_csrf_header(request)
    user = _require_session_user(request)

    body = await request.json()
    player_guid = str(body.get("player_guid") or "").strip()
    player_name = str(body.get("player_name") or "").strip()

    if not player_guid:
        raise HTTPException(status_code=400, detail="player_guid is required")

    discord_id = _safe_int(user.get("id"))
    website_user_id = _safe_int(user.get("website_user_id")) or discord_id
    if discord_id is None or website_user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user session")

    previous = None
    try:
        previous = await db.fetch_one(
            "SELECT player_guid, player_name FROM user_player_links WHERE user_id = $1 LIMIT 1",
            (int(website_user_id),),
        )
    except Exception:
        previous = None

    existing_owner = None
    try:
        existing_owner = await db.fetch_one(
            "SELECT user_id FROM user_player_links WHERE player_guid = $1 LIMIT 1",
            (player_guid,),
        )
    except Exception:
        existing_owner = None

    if existing_owner and int(existing_owner[0]) != int(website_user_id):
        raise HTTPException(status_code=409, detail="Player profile is already linked to another user")

    existing_legacy = await db.fetch_one(
        "SELECT discord_id FROM player_links WHERE player_guid = $1 LIMIT 1",
        (player_guid,),
    )
    if existing_legacy and int(existing_legacy[0]) != int(discord_id):
        raise HTTPException(status_code=409, detail="Player profile is already linked to another Discord account")

    try:
        await db.execute(
            """
            INSERT INTO user_player_links (user_id, player_guid, player_name, linked_at, updated_at)
            VALUES ($1, $2, $3, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE SET
                player_guid = EXCLUDED.player_guid,
                player_name = EXCLUDED.player_name,
                linked_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            """,
            (int(website_user_id), player_guid, player_name or player_guid),
        )
    except Exception as exc:
        logger.warning("user_player_links upsert failed, continuing with legacy link table: %s", exc)

    discord_username = str(user.get("username") or "")
    existing = await db.fetch_one(
        "SELECT id FROM player_links WHERE discord_id = $1",
        (int(discord_id),),
    )

    if existing:
        await db.execute(
            """
            UPDATE player_links
            SET player_guid = $1, player_name = $2, linked_at = NOW()
            WHERE discord_id = $3
            """,
            (player_guid, player_name or player_guid, int(discord_id)),
        )
    else:
        await db.execute(
            """
            INSERT INTO player_links (player_guid, discord_id, discord_username, player_name, linked_at)
            VALUES ($1, $2, $3, $4, NOW())
            """,
            (player_guid, int(discord_id), discord_username, player_name or player_guid),
        )

    user["linked_player"] = player_name or player_guid
    user["linked_player_guid"] = player_guid
    user["website_user_id"] = int(website_user_id)
    request.session["user"] = user

    action = "player_linked"
    if previous and str(previous[0]) != player_guid:
        action = "player_changed"

    await _audit_link_event(
        db,
        user_id=int(website_user_id),
        discord_user_id=int(discord_id),
        action=action,
        actor_discord_id=int(discord_id),
        metadata={"player_guid": player_guid, "player_name": player_name or player_guid},
    )

    return {
        "success": True,
        "linked_player": player_name or player_guid,
        "linked_player_guid": player_guid,
    }


@router.delete("/link")
async def unlink_player(request: Request, db: DatabaseAdapter = Depends(get_db)):
    """Unlink the logged-in Discord user from their ET player mapping."""
    _require_ajax_csrf_header(request)
    user = _require_session_user(request)

    discord_id = _safe_int(user.get("id"))
    website_user_id = _safe_int(user.get("website_user_id")) or discord_id
    if discord_id is None or website_user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user session")

    try:
        await db.execute("DELETE FROM user_player_links WHERE user_id = $1", (int(website_user_id),))
    except Exception as exc:
        logger.warning("user_player_links delete failed during unlink: %s", exc)

    await db.execute("DELETE FROM player_links WHERE discord_id = $1", (int(discord_id),))

    user["linked_player"] = None
    user["linked_player_guid"] = None
    request.session["user"] = user

    await _audit_link_event(
        db,
        user_id=int(website_user_id),
        discord_user_id=int(discord_id),
        action="player_unlinked",
        actor_discord_id=int(discord_id),
        metadata={},
    )

    return {"success": True}


@router.post("/discord/unlink")
async def unlink_discord_account(request: Request, db: DatabaseAdapter = Depends(get_db)):
    """
    Fully unlink Discord account from website user.

    Since Discord is the auth provider, this also logs the user out.
    """
    _require_ajax_csrf_header(request)
    user = _require_session_user(request)

    discord_id = _safe_int(user.get("id"))
    website_user_id = _safe_int(user.get("website_user_id")) or discord_id
    if discord_id is None or website_user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user session")

    try:
        await db.execute("DELETE FROM user_player_links WHERE user_id = $1", (int(website_user_id),))
    except Exception as exc:
        logger.warning("user_player_links delete failed during discord unlink: %s", exc)

    await db.execute("DELETE FROM player_links WHERE discord_id = $1", (int(discord_id),))

    try:
        await db.execute("DELETE FROM discord_accounts WHERE discord_user_id = $1", (int(discord_id),))
    except Exception as exc:
        logger.warning("discord_accounts delete failed during discord unlink: %s", exc)

    await _audit_link_event(
        db,
        user_id=int(website_user_id),
        discord_user_id=int(discord_id),
        action="discord_unlinked",
        actor_discord_id=int(discord_id),
        metadata={},
    )

    request.session.clear()
    frontend_origin = get_frontend_origin(get_discord_config())
    response = JSONResponse(
        {
            "success": True,
            "redirect_url": f"{frontend_origin}/",
        }
    )
    response.delete_cookie("session")
    return response
