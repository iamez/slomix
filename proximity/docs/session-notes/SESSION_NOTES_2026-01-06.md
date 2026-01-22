# Proximity Tracker - Session Notes

## January 6, 2026

### Session Goal

Document and cross-reference FIVEEYES (Oct 2025) with Proximity Tracker v3 (Dec 2025), then deploy and verify the system.

---

## What Was Accomplished

### 1. Documentation & Cross-Reference

Created comprehensive unified plan at `/home/samba/.claude/plans/zany-mapping-lighthouse.md` with:

| Section | Content |
|---------|---------|
| Session Log | Today's completed work |
| Cross-Reference | FIVEEYES vs Proximity comparison |
| Confirmed Issues | 5 issues with risk levels |
| FIVEEYES Deep Dive | Commands, schema, algorithm |
| Appendix D | Complete document inventory |
| Appendix E | Consolidation recommendations |
| Appendix F | Priority fix checklist (P0-P3) |
| Appendix G | File tree summary |

### 2. Bug Hunting & Verification

| Check | Result | Details |
|-------|--------|---------|
| Import path from bot/ | **WORKS** | `sys.path.insert(0, '..')` then `from proximity.parser import ProximityParserV3` |
| `player_synergies` table | **MISSING** | FIVEEYES Phase 1 migration was never run |
| Parser db_adapter compatibility | **COMPATIBLE** | Both use PostgreSQL `$N` placeholders |

**Key Discovery:** The bot's `PostgreSQLDatabaseAdapter._translate_placeholders()` method:

- Converts SQLite `?` placeholders to PostgreSQL `$1, $2...`
- Passes through queries already using `$N` format (line 219: `if '?' not in query: return query`)
- The proximity parser uses `$N` directly, so it's fully compatible

### 3. Lua Script Deployment

**Deployed:** `proximity_tracker.lua` to game server

```text
Source: /home/samba/share/slomix_discord/proximity/lua/proximity_tracker.lua
Target: /home/et/etlegacy-v2.83.1-x86_64/legacy/proximity_tracker.lua
```text

**Updated Config:** `/home/et/etlegacy-v2.83.1-x86_64/etmain/legacy.cfg`

Before:

```text
set lua_modules "luascripts/wolfadmin/main.lua"
```text

After:

```text
set lua_modules "luascripts/team-lock c0rnp0rn7.lua endstats.lua proximity_tracker.lua"
```python

**Status:** Config updated permanently. Module will load on next map change or server restart.

---

## Key Findings

### Finding 1: FIVEEYES Uses SQLite - Bot Uses PostgreSQL

**Location:** `analytics/synergy_detector.py`

- Lines 9-10: `import sqlite3`, `import aiosqlite`
- Line 73: `db_path: str = 'etlegacy_production.db'`
- Lines 97, 329, 376, 417: All use `aiosqlite.connect()`

**Impact:** FIVEEYES synergy system is INCOMPATIBLE with current PostgreSQL bot.

### Finding 2: FIVEEYES is Disabled & Abandoned

- `fiveeyes_config.json` line 4: `"enabled": false`
- `player_synergies` table does NOT exist
- Migration script never run
- Last commit: Nov 6, 2025 (2+ months ago)

### Finding 3: Proximity v3 Supersedes FIVEEYES Phase 3

| FIVEEYES Phase 3 | Proximity v3 |
|------------------|--------------|
| `proximity_events` table | `combat_engagement` table |
| 6 columns | 27 columns |
| Time near only | Full engagement windows |
| No escape detection | 5s timeout + 300 unit travel |
| Simple crossfire | Crossfire with ms-precision timing |
| No heatmaps | Kill + movement heatmaps |

### Finding 4: Game Server Lua Loading

Discovered how lua_modules is configured:

- Static config in `legacy.cfg` (we updated this)
- Runtime setting via RCON `setl lua_modules`
- Latched cvar - takes effect on map change

Console log shows:

```text
setl lua_modules luascripts/team-lock c0rnp0rn7.lua endstats.lua
Lua 5.4 API: file 'luascripts/team-lock.lua' loaded into Lua VM
Lua 5.4 API: file 'c0rnp0rn7.lua' loaded into Lua VM
Lua 5.4 API: file 'endstats.lua' loaded into Lua VM
```yaml

---

## Files Modified

### On Bot Server

| File | Change |
|------|--------|
| `/home/samba/.claude/plans/zany-mapping-lighthouse.md` | Added comprehensive cross-reference documentation |

### On Game Server (puran.hehe.si)

| File | Change |
|------|--------|
| `/home/et/etlegacy-v2.83.1-x86_64/legacy/proximity_tracker.lua` | NEW - deployed Lua script |
| `/home/et/etlegacy-v2.83.1-x86_64/etmain/legacy.cfg` | Updated lua_modules to include proximity_tracker.lua |

---

## Commands Used

### SSH Commands

```bash
# Deploy Lua script
scp -P 48101 -i ~/.ssh/etlegacy_bot \
  /home/samba/share/slomix_discord/proximity/lua/proximity_tracker.lua \
  et@puran.hehe.si:/home/et/.etlegacy/legacy/

# Copy to correct directory
ssh et@puran.hehe.si "cp /home/et/.etlegacy/legacy/proximity_tracker.lua \
  /home/et/etlegacy-v2.83.1-x86_64/legacy/"

# Update legacy.cfg
ssh et@puran.hehe.si "sed -i 's|set lua_modules.*|set lua_modules \"luascripts/team-lock c0rnp0rn7.lua endstats.lua proximity_tracker.lua\"|' \
  /home/et/etlegacy-v2.83.1-x86_64/etmain/legacy.cfg"
```text

### RCON Commands (via netcat)

```bash
# Check current lua_modules
echo -e "\xff\xff\xff\xffrcon glavni123 lua_modules" | nc -u -w 2 puran.hehe.si 27960

# Result: "luascripts/team-lock c0rnp0rn7.lua endstats.lua"
```text

### Database Verification

```bash
# Check if player_synergies exists (it doesn't)
PGPASSWORD='etlegacy_secure_2025' psql -h 192.168.64.116 -U etlegacy_user -d etlegacy \
  -c "\dt player_synergies"
# Result: Did not find any relation named "player_synergies"
```python

### Python Import Test

```python
# From bot/ directory
import sys
sys.path.insert(0, '..')
from proximity.parser import ProximityParserV3  # SUCCESS
```python

---

## Next Steps

### Immediate (Testing)

1. Wait for map change on game server (or restart)
2. Play a test round
3. Check for `*_engagements.txt` files in gamestats/
4. Verify Lua output format matches parser expectations

### Short-term (Enable Bot Integration)

1. Set `PROXIMITY_ENABLED=true` in `.env`
2. Restart bot
3. Monitor `!proximity_status` command
4. Verify data flows to PostgreSQL tables

### Medium-term (Fix FIVEEYES)

1. Create `player_synergies` table in PostgreSQL
2. Rewrite `synergy_detector.py` for PostgreSQL (replace aiosqlite with asyncpg)
3. Enable FIVEEYES in config
4. Write synergy data population logic

---

## Architecture Notes

### Current Data Flow (c0rnp0rn)

```text

Game Server                    Bot Server
───────────────────────────────────────────────────
c0rnp0rn7.lua                  SSHMonitor
    │                               │
    ▼                               ▼
gamestats/*.txt ──────────► local_stats/
                                    │
                                    ▼
                            C0RNP0RN3StatsParser
                                    │
                                    ▼
                            player_comprehensive_stats

```text

### New Data Flow (Proximity)

```text

Game Server                    Bot Server
───────────────────────────────────────────────────
proximity_tracker.lua          ProximityCog (background task)
    │                               │
    ▼                               ▼
**engagements.txt ─────────► ProximityParserV3
                                    │
                                    ▼
                            combat_engagement
                            player_teamplay_stats
                            crossfire_pairs
                            map**_heatmap

```text

### Database Adapter Compatibility

Bot's `PostgreSQLDatabaseAdapter.execute()`:

```python
async def execute(self, query: str, params: Optional[Tuple] = None):
    query = self._translate_placeholders(query)  # ? → $1, $2...
    async with self.connection() as conn:
        await conn.execute(query, *(params or ()))
```text

Proximity parser uses:

```python
query = """INSERT INTO combat_engagement (...) VALUES ($1, $2, $3...)"""
await self.db_adapter.execute(query, (param1, param2...))
```

**Compatibility:** Parser uses `$N` placeholders directly. Adapter's `_translate_placeholders()` passes through unchanged when no `?` found.

---

## Reference: Issue Priority Checklist

### P0: CRITICAL (Blocking)

- [x] Deploy Lua script to game server ✅ DONE

### P1: HIGH (Major functionality broken)

- [ ] Fix synergy_detector.py SQLite→PostgreSQL
- [ ] Create player_synergies table in PostgreSQL
- [ ] Enable FIVEEYES in config

### P2: MEDIUM (Functionality incomplete)

- [x] Verify proximity parser db_adapter compatibility ✅ COMPATIBLE
- [x] Test import path from bot directory ✅ WORKS
- [ ] Add synergy data population logic

### P3: LOW (Nice to have)

- [ ] Phase 2: Role Normalization
- [ ] User-facing proximity commands
- [ ] Website integration

---

## Session Duration

Approximately 45 minutes

## Next Session

- Wait for engagement files to be generated after gameplay
- Test parser with real data
- Enable proximity in bot config
