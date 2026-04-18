# Mega Audit v3 — Sprint 5 (P3f shared/ package, 2026-04-18)

**Cilj:** Razblini 25 cross-imports `website/backend → bot/` skozi `shared/` re-export paket.
**Branch:** `chore/audit-v3-sprint5-shared-package`
**Trajanje:** ~30 min

## Pristop — re-export shim (minimalno tveganje)

Nova `shared/` mapa vsebuje **samo re-exports** iz `bot/`. Canonical implementacija ostane v `bot/` (brez premika fajlov, brez regresije). Website importa iz `shared/`.

Prednosti:
- **Minimalno tveganje**: nobena koda ni premaknjena
- **Eksplicitna surface area**: `shared/` je točen seznam kar website potrebuje iz bot-a
- **Temelj za prihodnost**: če bot gre v svoj repo, samo premaknemo canonical iz `bot/` v `shared/`

**Alternativa (dejanski premik)** bi bila 3-4h dela z 508-testnim suite za verifikacijo in višjim tveganjem. Shim rešuje 80% value pri 20% tveganja.

## Struktura

```
shared/
├── __init__.py
├── config.py                 → load_config
├── database_adapter.py       → DatabaseAdapter, create_adapter
├── season_manager.py         → SeasonManager
├── utils.py                  → escape_like_pattern
├── guid_utils.py             → short_guid, name_or_short_guid, GUID_SHORT_LEN, GUID_MISSING_PLACEHOLDER
└── services/
    ├── __init__.py
    ├── session_data_service.py        → SessionDataService
    ├── session_stats_aggregator.py    → SessionStatsAggregator
    ├── stopwatch_scoring_service.py   → StopwatchScoringService, normalize_side
    └── round_linkage_anomaly_service.py → assess_round_linkage_anomalies
```

Vsak modul je **eksplicitni** re-export (ne `from X import *`), tako statični analizatori vidijo simbole.

## Migration

Python batch script zamenjal vsak `from bot.X import Y` v `website/backend/` → `from shared.X import Y`:

| Izvor | Cilj | Pojavitev |
|---|---|---|
| `bot.config` | `shared.config` | 3 |
| `bot.core.database_adapter` | `shared.database_adapter` | 5 |
| `bot.core.season_manager` | `shared.season_manager` | 4 |
| `bot.core.utils` | `shared.utils` | 3 |
| `bot.core.guid_utils` | `shared.guid_utils` | 3 |
| `bot.services.session_data_service` | `shared.services.session_data_service` | 1 |
| `bot.services.session_stats_aggregator` | `shared.services.session_stats_aggregator` | 1 |
| `bot.services.stopwatch_scoring_service` | `shared.services.stopwatch_scoring_service` | 2 |
| `bot.services.round_linkage_anomaly_service` | `shared.services.round_linkage_anomaly_service` | 1 |

**16 fajlov** spremenjenih. **0 cross-imports** ostalo.

## Verifikacija

- `ruff check bot/ website/backend/ shared/` — 0 errors
- `pytest tests/` — **508 passed**, 45 skipped, 0 failed
- `grep -rn "^from bot\.\|^import bot\." website/backend/` — **0 hits**
- Vseh 9 re-exports naložijo brez napake

## Za prihodnost

### P3e (ultimate_bot decomp)
- `shared/` je predpogoj za ekstrakcijo servisov iz `ultimate_bot.py` če bo cross-call potreba
- Novi `bot/services/*.py` lahko uvažajo prosto iz drugih `bot/` modulov

### Bodoč micro-service split
1. Premakni koda iz `bot/X.py` → `shared/X.py`
2. V `bot/X.py` dodaj `from shared.X import *` shim (za kompat)
3. Po 2 release-ah: zbriši bot shim
4. `shared/` postane samostojen package

---

**Avtor:** Mega Audit v3 Sprint 5 / P3f (Claude Opus 4.7, 1M context)
**Datum:** 2026-04-18
