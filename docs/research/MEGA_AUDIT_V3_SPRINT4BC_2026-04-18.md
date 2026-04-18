# Mega Audit v3 — Sprint 4B + 4C (2026-04-18)

**Cilj:** Dokončanje Sprint 3 infrastrukture — aplicirati `short_guid()` in `ProximityQueryBuilder` na vse zelene kandidate iz research agenta.
**Branch:** `chore/audit-v3-sprint4bc-guid-query-builder`
**Trajanje:** ~45 min

## Sprint 4B — `short_guid()` migration (7 sites)

| Fajl | Vrstica | Pattern (prej) | Po |
|---|---|---|---|
| `bot/services/prediction_embed_builder.py` | 254 | `f"Player_{guid[:8]}"` | `f"Player_{short_guid(guid)}"` |
| `bot/services/matchup_analytics_service.py` | 544 | `guid[:8]` | `short_guid(guid)` |
| `bot/cogs/team_management_cog.py` | 202 | `f"{player_guid[:8]}..."` | `f"{short_guid(player_guid)}..."` |
| `bot/cogs/matchup_cog.py` | 45 | `guid[:8]` | `short_guid(guid)` |
| `bot/cogs/predictions_cog.py` | 682 | `f"Player_{guid[:8]}"` | `f"Player_{short_guid(guid)}"` |
| `bot/services/proximity_session_score_service.py` | 296 | `(guid or "?")[:8]` | `short_guid(guid)` |
| `bot/community_stats_parser.py` | 1300, 1302 | `f"{guid[:8]}{bot_hash}"` + `guid[:8]` | `f"{short_guid(guid)}{bot_hash}"` + `short_guid(guid)` |

**Ne migrirano** (rumen kandidat iz researcha):
- `bot/services/session_timing_shadow_service.py:135` uporablja `.lower()` + `.strip()` pred `[:8]`, kar `short_guid` ne naredi. Ohranjeno eksplicitno.

## Sprint 4C — `ProximityQueryBuilder` migration (3 endpoints)

| Fajl | Endpoint | Boilerplate pred → po |
|---|---|---|
| `proximity_objectives.py` | `/proximity/carrier-events` | 20 → 10 vrstic |
| `proximity_objectives.py` | `/proximity/carrier-kills` | 20 → 10 vrstic |
| `proximity_positions.py` | `/proximity/combat-position-stats` | 12 → 6 vrstic |

~40 vrstic boilerplatea izbrisanih skupno.

`with_raw(clause, value)` renumerira `$1` placeholderje glede na trenutni param count:
```python
qb = (ProximityQueryBuilder()
    .with_session_scope(session_date, range_days)
    .with_map_name(map_name))
if round_number is not None:
    qb.with_raw("round_number = $1", round_number)  # renumbers to $3
where_sql, params = qb.build()
```

## Config

- `pyproject.toml`: dodana `bot/tools/*` v T201 per-file-ignores (dev CLI skripti s `print()` — podobno kot `bot/diagnostics/*` v Sprint 3)

## Verifikacija

- `ruff check bot/ website/backend/` — 0 errors
- `pytest tests/` — **508 passed**, 45 skipped, 0 failed
- Route count unchanged: proximity_objectives=8, proximity_positions=7
- Smoke test: `ProximityQueryBuilder().with_session_scope('2026-04-17').with_map_name('battery').with_raw("round_number = $1", 2).build()` → `('WHERE session_date = $1 AND map_name = $2 AND round_number = $3', (date, 'battery', 2))` ✓

## Status Mega Audit v3

Vsi Sprint 3 infrastrukturni helperji (`@handle_router_errors`, `short_guid`, `ProximityQueryBuilder`, `StorytellingTiming`) so zdaj uporabljeni v praksi + dokumentirani. Skupaj od Sprint 3 do Sprint 4C:

| Helper | Uporabljeno v | Sprint |
|---|---|---|
| `@handle_router_errors` | 2 (demo) + 25 (4A) = **27 endpointov** | 3, 4A |
| `short_guid()` | 3 (demo) + 7 (4B) = **10 sites** | 3, 4B |
| `ProximityQueryBuilder` | 2 (demo) + 3 (4C) = **5 endpointov** | 3, 4C |
| `StorytellingTiming` konstante | **15+ mest** (vse magic ms) | 3 |

## Kar ostaja

**Deferred migration candidates:**
- 38 `except→HTTPException(500)` v `records_awards/overview/seasons`, `players_router`, `sessions_router` — zahtevajo per-site review (mixed business fallback)
- 77 proximity `where_parts` v remaining proximity routerjih — vsak endpoint preveri dodatne filterse pred migration
- 1 `guid[:8]` rumeni v `session_timing_shadow_service.py` (ima `.lower()` — zahteva nov helper ali explicit)

**Velike naloge iz Mega Audit Faze C (plan file):**
- P3f: `shared/` package (23 cross-imports `website→bot` → 0)
- P3e: `ultimate_bot.py` 6251 → <2500 vrstic (4 podfaze, 12-14 h)
- D.1: `storytelling_service.py` 3273 → 10 modulov (~4 h)

---

**Avtor:** Mega Audit v3 Sprint 4B + 4C (Claude Opus 4.7, 1M context)
**Datum:** 2026-04-18
