# Mega Audit v3 — Sprint 2 (2026-04-17)

**Cilj:** Security fixes iz Sprint 1 audit report-a (SEC-02, SEC-05, SEC-08).
**Branch:** `chore/audit-v3-sprint2-security`
**Trajanje:** ~1.5 h

---

## Izvedeno

### SEC-02 — Admin auth na diagnostics endpointih ✅

**Problem:** 11 endpointov v `website/backend/routers/diagnostics_router.py` je bilo dostopnih **brez kakršne koli avtentikacije**. Razkrivali so: število vrstic v tabelah, čase zadnjih zapisov, Lua webhook konfiguracijo, timing audit, spawn audit, monitoring status, historijo player aktivnosti, voice channel aktivnost, itd. Posneti za recon.

**Fix:**
- Nov FastAPI dependency `require_admin_user` v `website/backend/dependencies.py`
- Uporablja iste env vars (`WEBSITE_ADMIN_DISCORD_IDS`, `ADMIN_DISCORD_IDS`, `OWNER_USER_ID`) kot `availability.py::_is_admin_user` in `planning.py` — **single source of truth** za admin gate
- 401 na manjkajočo sejo, 403 na non-admin sejo
- Dodan `_user: dict = Depends(require_admin_user)` na **10 od 11** endpointov:
  - `/diagnostics`, `/diagnostics/lua-webhook`, `/diagnostics/round-linkage`
  - `/diagnostics/time-audit`, `/diagnostics/spawn-audit`
  - `/monitoring/status`, `/live-status`
  - `/server-activity/history`, `/voice-activity/history`, `/voice-activity/current`
- `/status` (health check `{"status": "online", "database": "ok"}`) **ostaja javen** — brez občutljivih podatkov, uporabniki monitoring tool ga potrebujejo.

### SEC-05 — Centralizirano stripanje ET color kod ✅

**Problem:** Več kot 10 routerjev je pošiljalo raw `player_name` z barvnimi kodami (`^1Dmon^7`) v JSON responses. Samo `sessions_router.py` in `storytelling_router.py` sta stripala po Sprint 1.5 popravku. React frontend auto-escape-a HTML, a **ne stripa color kod** → UX regresija.

**Fix:**
- Modificiran `website/backend/routers/api_helpers.py::resolve_display_name` (en osrednji helper, uporabljen v >10 mestih): uporablja `strip_et_colors()` na vseh 4 vrnjenih poteh (`player_links` display_name, `player_links` player_name, `player_aliases`, `player_comprehensive_stats`, pa tudi fallback).
- `batch_resolve_display_names()`: final dict comprehension stripa vsako vrednost — pokriva 7 callerjev iz `records_awards.py`.
- Edini import dodatek: `from website.backend.utils.et_constants import strip_et_colors`.

**Pokriva:** `records_player.py`, `records_awards.py`, `records_seasons.py`, `proximity_player.py`, `proximity_objectives.py`, `proximity_support.py`, `proximity_scoring.py`, `greatshot_topshots.py` — vsi posredno prek `resolve_display_name`.

### SEC-08 — Discord ID PII log masking ✅

**Problem:** `website/backend/routers/auth.py:406` je logiral `discord_id=%s username=%s` na **INFO** level. Discord ID je PII (direktno povezljivo z uporabniško identiteto). Production INFO logi shranjeni za analizo/debugging → potencialni leak če logi nepazljivo deljeni.

**Fix:**
- INFO linija: `discord_id=<first 4 chars>****` (maskirano)
- Polno vrednost (ID + username) logiraj **samo na DEBUG** (audit level, ne shrani production)

---

## Verifikacija

- `ruff check website/backend/ bot/` — 0 errors
- `pytest tests/` — 496 passed, 45 skipped, 0 failed (no regression)
- Import sanity check: `require_admin_user`, `resolve_display_name`, `batch_resolve_display_names`, `auth_router`, `diagnostics_router` — vsi naložijo brez napake.

## Kar ostaja za prihodnje sprinte

Iz Sprint 1 review dokumenta (`SESSION_DETAIL_V2_REVIEW_2026-04-17.md`):

**Sprint 2.5 ali 3:**
- **CR-02** — Dual rendering React ↔ legacy JS feature parity. Glavni tehnični dolg iz PR #79. Dve implementaciji z različnim feature-setom (3 vs 7 metrik, heatmap samo v legacy, drill-down samo v legacy).
- **CR-04** — Extract `SessionMatrixService` (300-line `build_team_matrix` v `sessions_router.py` → servis modul).
- **CR-05** — `UTILITY_WEAPONS` v `et_constants.py` (hardcoded seznam v SQL subquery).
- **CR-07** — Unit testi za `build_team_matrix` (substitution, stopwatch swap, edge cases).

**Sprint 3 (arhitektura):**
- **ARCH-01** — `@handle_router_errors` dekorator za 22 routerjev (duplicirana try/except logika).
- **CQ-03** — `bot/core/guid_utils.py::normalize_guid()` za 3 stile GUID normalizacije.
- **CQ-04** — `ProximityQueryBuilder` fluent API.
- **REFAC-01** — `StorytellingTiming` constants class.

**Veliko delo iz Mega Audit Faze C:**
- **P3f** — `shared/` package (21 cross-imports `website→bot` → 0), 3-4 h.
- **P3e** — `bot/ultimate_bot.py` 6251 → <2500 vrstic (12 servisov), 12-14 h.
- **D.1** — `storytelling_service.py` 3273 → 10 modulov, 4 h.
- **D.2** — GUID canonical migration verify (30 min read-only).

---

## Commit plan

```
chore(security): sprint 2 — admin auth on diagnostics + centralized color strip + PII log masking

- require_admin_user dependency in dependencies.py (reuses existing
  WEBSITE_ADMIN_DISCORD_IDS / ADMIN_DISCORD_IDS / OWNER_USER_ID env vars)
- 10 diagnostics endpoints now require admin session (/status stays public
  as a health check)
- resolve_display_name + batch_resolve_display_names now strip ET color
  codes at the helper level, covering 10+ consumer routers
- auth.py OAuth success log masks Discord ID at INFO; full value moves to
  DEBUG only
```

---

**Avtor:** Mega Audit v3 Sprint 2 (Claude Opus 4.7, 1M context)
**Datum:** 2026-04-17
