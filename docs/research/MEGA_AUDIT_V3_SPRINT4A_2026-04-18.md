# Mega Audit v3 — Sprint 4A (2026-04-18)

**Cilj:** Uporabiti `@handle_router_errors` dekorator (iz Sprint 3) na vse "clean wrapper" endpoint-e v 5 routerjih.
**Branch:** `chore/audit-v3-sprint4a-error-decorator`
**Trajanje:** ~1.5 h

## Izvedeno

25 endpointov dobilo `@handle_router_errors()` dekorator, ~150 vrstic boilerplatea izbrisanih:

| Router | Endpointov | Metoda |
|---|---|---|
| `proximity_positions.py` | **7** | hit-regions, /by-weapon, /headshot-rates, combat-positions/heatmap, /kill-lines, /danger-zones, combat-position-stats |
| `proximity_objectives.py` | **8** | carrier-events, carrier-kills, carrier-returns, vehicle-progress, escort-credits, construction-events, objective-runs, objective-focus |
| `proximity_teamplay.py` | **6** | spawn-timing, cohesion, crossfire-angles, pushes, lua-trades, focus-fire (teamplay **preskočen** — payload fallback) |
| `records_trends.py` | **1** | /stats/trends (retro-viz preskočen — fallback `images=[]`) |
| `records_weapons.py` | **2** | /stats/weapons, /stats/weapons/by-player (hall-of-fame **preskočen** — fallback `{"leaders": {}}`) |

**Agent je sprva našel 11 zelenih** (plitek grep). Read-verification razkrila še 14 dodatnih clean wrapperjev, ki jih je agent zgrešil. Vsi imajo identičen pattern `except Exception: logger.error/exception + raise HTTPException(500)` brez business-logic fallback-a.

## Pristop

1. Batch transformation z Python skriptom:
   - Najdi vsak `@router.get(...)` → `async def ...`
   - Če blok vsebuje `except Exception: logger + raise HTTPException(500)` → dodaj `@handle_router_errors("msg")` + odstrani `try:` + de-indent body + odstrani except blok
   - Ohrani `raise HTTPException(400)` v bloku (validation) — `handle_router_errors` jih ne wrapa
2. Dodaj `from website.backend.routers.api_helpers import handle_router_errors` v imports
3. Ruff `--fix` za import organizing
4. Manual cleanup razdvojenih imports (ruff isort občasno razbije `from X import (a,)` v ločene bloke)

## Ne aplicirano (business-logic fallback)

Research agent je pravilno označil kot ROdeče:
- `records_weapons.py /hall-of-fame` — vrne `{"period": period, "leaders": {}}` fallback
- `records_trends.py /retro-viz/gallery` — vrne `{"images": []}` fallback
- `proximity_teamplay.py /teamplay` — `payload.update({"error": ...})` fallback
- `records_awards.py /records`, `/leaderboard`, `/hall-of-fame` — schema negotiation fallback queries
- `records_overview.py` — nested schema fallback
- `records_seasons.py` — fallback queries
- `players_router.py` (18 except) — mešanica, agent označil rdeče

## Verifikacija

- `ruff check bot/ website/backend/`: 0 errors
- `pytest tests/`: **508 passed**, 45 skipped, 0 failed (brez regresij)
- Route count: positions=7, objectives=8, teamplay=7, trends=2, weapons=4 (brez sprememb)
- Import sanity: vsi 5 routerji naložijo brez `NameError: handle_router_errors`

## Kar ostaja za Sprint 4B/4C

- **4B short_guid** — 7 mest v bot/services + bot/cogs (agent seznam)
- **4C ProximityQueryBuilder** — 3 mesta v proximity_objectives + proximity_positions (agent seznam)

---

**Avtor:** Mega Audit v3 Sprint 4A (Claude Opus 4.7, 1M context, Python batch transform)
**Datum:** 2026-04-18
