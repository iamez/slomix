import os
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
import httpx
from dotenv import load_dotenv

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


@router.get("/login")
async def login():
    config = get_discord_config()
    if not config["client_id"]:
        raise HTTPException(status_code=500, detail="Discord Client ID not configured")

    return RedirectResponse(
        f"https://discord.com/api/oauth2/authorize?client_id={config['client_id']}&redirect_uri={config['redirect_uri']}&response_type=code&scope=identify"
    )


from website.backend.dependencies import get_db
from bot.core.database_adapter import DatabaseAdapter
from fastapi import Depends


@router.get("/callback")
async def callback(request: Request, code: str, db: DatabaseAdapter = Depends(get_db)):
    config = get_discord_config()
    if not config["client_id"] or not config["client_secret"]:
        raise HTTPException(
            status_code=500, detail="Discord credentials not configured"
        )

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
        print(f"[AUTH] Discord user logged in: {user_data.get('username')} (ID: {user_data.get('id')})")

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

        # Redirect to frontend home (use request host to be flexible)
        host = request.headers.get("host", "192.168.64.116:8000")
        return RedirectResponse(url=f"http://{host}/")


@router.get("/logout")
async def logout(request: Request):
    # Clear the entire session
    request.session.clear()
    host = request.headers.get("host", "192.168.64.116:8000")
    response = RedirectResponse(url=f"http://{host}/")
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
    
    # Search for players matching the query (case-insensitive)
    results = await db.fetch_all(
        """
        SELECT DISTINCT player_guid, player_name, clean_name
        FROM player_comprehensive_stats
        WHERE LOWER(player_name) LIKE LOWER($1) OR LOWER(clean_name) LIKE LOWER($1)
        ORDER BY player_name
        LIMIT 20
        """,
        (f"%{q}%",)
    )
    
    return [{"guid": r[0], "name": r[1], "clean_name": r[2]} for r in results]


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
        "SELECT id FROM player_links WHERE discord_id = $1",
        (discord_id,)
    )
    
    if existing:
        # Update existing link
        await db.execute(
            """
            UPDATE player_links 
            SET player_guid = $1, player_name = $2, linked_at = NOW()
            WHERE discord_id = $3
            """,
            (player_guid, player_name, discord_id)
        )
    else:
        # Insert new link
        await db.execute(
            """
            INSERT INTO player_links (player_guid, discord_id, discord_username, player_name, linked_at)
            VALUES ($1, $2, $3, $4, NOW())
            """,
            (player_guid, discord_id, discord_username, player_name)
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
    
    await db.execute(
        "DELETE FROM player_links WHERE discord_id = $1",
        (discord_id,)
    )
    
    # Update session
    user["linked_player"] = None
    request.session["user"] = user
    
    return {"success": True}
