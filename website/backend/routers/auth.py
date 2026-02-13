import os
import secrets
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
import httpx
from dotenv import load_dotenv
from urllib.parse import urlencode, urlsplit

# Load .env file explicitly
load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

router = APIRouter()


def get_discord_config():
    """Get Discord config at runtime (after .env is loaded)"""
    return {
        "client_id": os.getenv("DISCORD_CLIENT_ID"),
        "client_secret": os.getenv("DISCORD_CLIENT_SECRET"),
        "redirect_uri": os.getenv(
            "DISCORD_REDIRECT_URI", "http://localhost:8000/auth/callback"
        ),
    }


def get_frontend_origin(config: dict) -> str:
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


@router.get("/login")
async def login(request: Request):
    config = get_discord_config()
    if not config["client_id"]:
        raise HTTPException(status_code=500, detail="Discord Client ID not configured")

    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state

    auth_query = urlencode(
        {
            "client_id": config["client_id"],
            "redirect_uri": config["redirect_uri"],
            "response_type": "code",
            "scope": "identify",
            "state": state,
        }
    )
    return RedirectResponse(
        f"https://discord.com/api/oauth2/authorize?{auth_query}"
    )


from website.backend.dependencies import get_db
from bot.core.database_adapter import DatabaseAdapter
from fastapi import Depends
from website.backend.routers.api import resolve_display_name


@router.get("/callback")
async def callback(
    request: Request,
    code: str,
    state: str | None = None,
    db: DatabaseAdapter = Depends(get_db),
):
    config = get_discord_config()
    if not config["client_id"] or not config["client_secret"]:
        raise HTTPException(
            status_code=500, detail="Discord credentials not configured"
        )

    expected_state = request.session.pop("oauth_state", None)
    if not state or not expected_state or not secrets.compare_digest(state, expected_state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    async with httpx.AsyncClient() as client:
        # Exchange code for token
        token_resp = await client.post(
            "https://discord.com/api/oauth2/token",
            data={
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": config["redirect_uri"],
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if token_resp.status_code != 200:
            raise HTTPException(
                status_code=400, detail="Failed to get token from Discord"
            )

        token_data = token_resp.json()
        access_token = token_data["access_token"]

        # Get User Info
        user_resp = await client.get(
            "https://discord.com/api/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if user_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get user info")

        user_data = user_resp.json()

        # Debug: Log who actually logged in
        print(
            f"[AUTH] Discord user logged in: {user_data.get('username')} (ID: {user_data.get('id')})"
        )

        # Check for existing player link
        try:
            discord_id = int(user_data["id"])
            # Use $1 placeholder for Postgres
            link = await db.fetch_one(
                "SELECT player_name FROM player_links WHERE discord_id = $1",
                (discord_id,),
            )

            if link:
                user_data["linked_player"] = link[0]
                print(f"[AUTH] Found linked player: {link[0]}")
            else:
                user_data["linked_player"] = None
                print(f"[AUTH] No linked player for discord_id {discord_id}")
        except Exception as e:
            print(f"Error fetching player link: {e}")
            user_data["linked_player"] = None

        # Store user info in session
        request.session["user"] = user_data

        frontend_origin = get_frontend_origin(config)
        return RedirectResponse(url=f"{frontend_origin}/")


@router.get("/logout")
async def logout(request: Request):
    # Clear the entire session
    request.session.clear()
    frontend_origin = get_frontend_origin(get_discord_config())
    response = RedirectResponse(url=f"{frontend_origin}/")
    # Also delete the session cookie
    response.delete_cookie("session")
    return response


@router.get("/me")
async def get_current_user(request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


@router.get("/players/search")
async def search_players(q: str, db: DatabaseAdapter = Depends(get_db)):
    """Search for players by name to link to Discord account"""
    if not q or len(q) < 2:
        return []

    like_query = f"%{q}%"
    # Prefer unique GUIDs to avoid duplicate aliases showing as separate players
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


@router.post("/link")
async def link_player(request: Request, db: DatabaseAdapter = Depends(get_db)):
    """Link logged-in Discord user to an ET player"""
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    body = await request.json()
    player_guid = body.get("player_guid")
    player_name = body.get("player_name")

    if not player_guid:
        raise HTTPException(status_code=400, detail="player_guid is required")

    discord_id = int(user["id"])
    discord_username = user.get("username", "")

    # Check if user already has a link
    existing = await db.fetch_one(
        "SELECT id FROM player_links WHERE discord_id = $1", (discord_id,)
    )

    if existing:
        # Update existing link
        await db.execute(
            """
            UPDATE player_links 
            SET player_guid = $1, player_name = $2, linked_at = NOW()
            WHERE discord_id = $3
            """,
            (player_guid, player_name, discord_id),
        )
    else:
        # Insert new link
        await db.execute(
            """
            INSERT INTO player_links (player_guid, discord_id, discord_username, player_name, linked_at)
            VALUES ($1, $2, $3, $4, NOW())
            """,
            (player_guid, discord_id, discord_username, player_name),
        )

    # Update session with linked player
    user["linked_player"] = player_name
    request.session["user"] = user

    return {"success": True, "linked_player": player_name}


@router.delete("/link")
async def unlink_player(request: Request, db: DatabaseAdapter = Depends(get_db)):
    """Unlink the logged-in Discord user from their ET player"""
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    discord_id = int(user["id"])

    await db.execute("DELETE FROM player_links WHERE discord_id = $1", (discord_id,))

    # Update session
    user["linked_player"] = None
    request.session["user"] = user

    return {"success": True}
