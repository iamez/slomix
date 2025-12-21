# Session Notes - December 21, 2025

## What We Accomplished ✅

### 1. Discord OAuth2 Login Implementation
- **Configured Discord Application**: Client ID `1174388516004835419`
- **Set up OAuth2 flow**: Login → Discord Auth → Callback → Session
- **Created `.env` file** with Discord credentials
- **Fixed environment variable loading**: Added `load_dotenv()` to auth.py (env vars weren't loading because `os.getenv()` runs at import time)
- **Fixed redirect URLs**: Changed hardcoded localhost to use `request.headers.get("host")` for dynamic host detection

### 2. Player Linking API
- **Added `/auth/players/search?q=<name>`** - Search for ET players by name
- **Added `POST /auth/link`** - Link Discord account to ET player GUID
- **Added `DELETE /auth/link`** - Unlink Discord from ET player
- **Updated frontend** `js/app.js` to use new auth endpoints instead of old `/api/player/search`

### 3. Session/Logout Fix
- **Improved logout**: Changed from `session.pop()` to `session.clear()` + delete cookie
- **Added debug logging** to auth callback to see which Discord user actually logs in

---

## What Didn't Work / Known Issues ⚠️

### Discord Login Shows Wrong User
- **Issue**: User logs in as "seareal" on Discord but website shows "BAMBAM"
- **Suspected Cause**: Session/cookie not being properly cleared between logins
- **Debug Added**: Server now logs `[AUTH] Discord user logged in: <username> (ID: <id>)` to `/tmp/uvicorn.log`
- **To Debug**: 
  1. Clear ALL browser cookies for `192.168.64.116`
  2. Use incognito/private window
  3. Check server logs after login: `tail -50 /tmp/uvicorn.log | grep AUTH`

### Player Linking UI
- **Status**: Backend API complete, frontend modal exists
- **Not Tested**: Couldn't test because login was showing wrong user

---

## Files Modified This Session

| File | Changes |
|------|---------|
| `website/.env` | Added `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DISCORD_REDIRECT_URI` |
| `website/backend/routers/auth.py` | Fixed env loading, added player search/link endpoints, improved logout, added debug logging |
| `website/js/app.js` | Updated `searchPlayer()` and `searchHeroPlayer()` to use `/auth/players/search` endpoint |

---

## Server Information

- **Server**: `192.168.64.116`
- **SSH**: `samba@192.168.64.116` (password: `Deljeno2x`)
- **Website URL**: `http://192.168.64.116:8000`
- **Uvicorn Logs**: `/tmp/uvicorn.log`
- **Project Path**: `/home/samba/share/slomix_discord`

### Running Services
```bash
# Check if website is running
curl http://192.168.64.116:8000/api/stats/overview

# View server logs
tail -f /tmp/uvicorn.log

# Restart server (if needed)
cd /home/samba/share/slomix_discord
pkill -f "uvicorn website.backend.main"
source venv/bin/activate
nohup python -m uvicorn website.backend.main:app --host 0.0.0.0 --port 8000 --reload > /tmp/uvicorn.log 2>&1 &
```

---

## Database Information

- **Database**: `etlegacy` on PostgreSQL
- **Website User**: `website_readonly` / `WebsiteReadOnly2024`
- **Player Links Table**: `player_links` (empty, ready for use)

```sql
-- Check player links
SELECT * FROM player_links;

-- Search for players
SELECT DISTINCT player_guid, player_name FROM player_comprehensive_stats WHERE LOWER(player_name) LIKE '%seareal%';
```

---

## Discord OAuth Configuration

### Discord Developer Portal
- **Application**: Already configured
- **OAuth2 Redirect URL**: `http://192.168.64.116:8000/auth/callback`
- **Scopes**: `identify`

### Environment Variables (in `.env`)
```
DISCORD_CLIENT_ID=1174388516004835419
DISCORD_CLIENT_SECRET=fRU1vL4GmoKWBB8cqPcxix4JaEdoTokU
DISCORD_REDIRECT_URI=http://192.168.64.116:8000/auth/callback
```

---

## Next Session TODO

1. **Fix Discord login issue** - Debug why wrong user appears after authorization
   - Check server logs for actual Discord username returned
   - May need to add `prompt=consent` to Discord OAuth URL to force re-auth

2. **Test player linking** - Once login works correctly

3. **Show linked player stats on dashboard** - Personalized stats for logged-in users

4. **Add "Switch Account" button** - Allow users to re-authenticate with different Discord account

---

## Quick Debug Commands

```bash
# SSH to server
ssh samba@192.168.64.116

# Check who actually logged in (after login attempt)
tail -50 /tmp/uvicorn.log | grep AUTH

# Test player search API
curl "http://192.168.64.116:8000/auth/players/search?q=fl0w"

# Check session cookie
# In browser console:
document.cookie
```

---

## Potential Fix for Discord Login Issue

If the issue persists, add `prompt=consent` to force Discord to show account picker:

```python
# In auth.py login route, change:
f"...&scope=identify"
# To:
f"...&scope=identify&prompt=consent"
```

This forces Discord to show the authorization screen every time, preventing cached authorization.
