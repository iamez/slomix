import os
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
import httpx

router = APIRouter()

# TODO: Load these from environment variables or config
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv(
    "DISCORD_REDIRECT_URI", "http://localhost:8000/auth/callback"
)


@router.get("/login")
async def login():
    if os.getenv("DATABASE_TYPE") == "mock":
        return RedirectResponse(url="/auth/dev_login")

    if not DISCORD_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Discord Client ID not configured")

    return RedirectResponse(
        f"https://discord.com/api/oauth2/authorize?client_id={DISCORD_CLIENT_ID}&redirect_uri={DISCORD_REDIRECT_URI}&response_type=code&scope=identify"
    )


@router.get("/dev_login")
async def dev_login(request: Request):
    """Simulate a login for local development"""
    if os.getenv("DATABASE_TYPE") != "mock":
        raise HTTPException(status_code=403, detail="Dev login only available in mock mode")
    
    # Create dummy user
    user_data = {
        "id": "123456789",
        "username": "DevUser",
        "discriminator": "0000",
        "avatar": None,
        "linked_player": "BAMBAM" # Pre-link to a player in our mock DB
    }
    
    request.session["user"] = user_data
    return RedirectResponse(url="/")


from website.backend.dependencies import get_db
from bot.core.database_adapter import DatabaseAdapter
from fastapi import Depends


@router.get("/callback")
async def callback(request: Request, code: str, db: DatabaseAdapter = Depends(get_db)):
    if not DISCORD_CLIENT_ID or not DISCORD_CLIENT_SECRET:
        raise HTTPException(
            status_code=500, detail="Discord credentials not configured"
        )

    async with httpx.AsyncClient() as client:
        # Exchange code for token
        token_resp = await client.post(
            "https://discord.com/api/oauth2/token",
            data={
                "client_id": DISCORD_CLIENT_ID,
                "client_secret": DISCORD_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": DISCORD_REDIRECT_URI,
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

        # Check for existing player link
        try:
            discord_id = int(user_data["id"])
            # Use ? placeholder, adapter handles translation to $1 for Postgres
            link = await db.fetch_one(
                "SELECT player_name FROM player_links WHERE discord_id = ?",
                (discord_id,),
            )

            if link:
                user_data["linked_player"] = link[0]
            else:
                user_data["linked_player"] = None
        except Exception as e:
            print(f"Error fetching player link: {e}")
            user_data["linked_player"] = None

        # Store user info in session
        request.session["user"] = user_data

        # Redirect to frontend dashboard or home
        return RedirectResponse(url="http://localhost:8000/dashboard")


@router.get("/logout")
async def logout(request: Request):
    request.session.pop("user", None)
    return RedirectResponse(url="http://localhost:8000")


@router.get("/me")
async def get_current_user(request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
