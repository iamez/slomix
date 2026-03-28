# Vibe Coding Dry Run: Popoln načrt implementacije
**Datum**: 2026-03-28 | **Metoda**: 5 vzporednih ekip, Mandelbrot RCA | **Status**: TEORIJA — nič ni bilo spremenjeno

---

## SKUPNI PREGLED

| Prioriteta | Kategorija | Spremembe | Trud | Tveganje |
|------------|-----------|-----------|------|----------|
| **P0** | Security (gesla, deps) | 6 datotek | ~68 min | Nizko |
| **P1a** | Ruff razširitev + pre-commit | 2 config + ~90 auto-fix | ~1.5 ure | Nizko |
| **P1b** | print→logger (24 zamenjav) | 4 datoteke | ~20 min | Nizko |
| **P1c** | Tihe izjeme CRITICAL | 4 datoteke, 12 sprememb | ~2 uri | Srednje |
| **P1d** | Tihe izjeme HIGH | 5 datotek, 70+ sprememb | ~4 ure | Srednje |
| **P1e** | slowapi + deps sync | 2 datoteki | ~5 min | Nizko |
| **P2a** | Testi za servise | 3 nove test datoteke | ~6 ur | Nizko |
| **P2b** | mypy config | 1 config + dev deps | ~30 min | Nizko |
| **P2c** | CI pipeline update | 1 workflow | ~1 ura | Nizko |
| **P3a** | Duplikati izvleči | 5 datotek | ~1 ura | Nizko |
| **P3b** | Memory leak fix | 1 datoteka | ~30 min | Nizko |
| **P3c** | proximity_router split | 1→11 datotek | ~4-6 ur | Nizko |
| **P3d** | records_router split | 1→6 datotek | ~3-4 ure | Nizko |
| **P3e** | ultimate_bot decomp | 1→11 datotek | ~8-12 ur | VISOKO |
| **P3f** | shared/ package | ~16 datotek | ~4-6 ur | Srednje |
| | **SKUPAJ** | | **~35-45 ur** | |

---

# P0: TAKOJŠNJI POPRAVKI (~68 min)

## P0-1: Odstrani hardcoded gesla (32 min)

### 4 datoteke z geslom `etlegacy_secure_2025`:

**Datoteka 1: `scripts/backfill_player_track_metrics.py:21`**
```python
# BEFORE:
"password": "etlegacy_secure_2025"

# AFTER:
"password": os.getenv("DB_PASSWORD")
# Dodaj na vrh: import os
```

**Datoteka 2: `scripts/repair_endstats_round_assignments.py:156`**
```python
# BEFORE:
os.getenv("DB_PASSWORD", "etlegacy_secure_2025")

# AFTER:
os.getenv("DB_PASSWORD")  # brez fallback!
```

**Datoteka 3: `scripts/backfill_vs_stats_subjects.py:315`**
```python
# BEFORE:
os.getenv("DB_PASSWORD", "etlegacy_secure_2025")

# AFTER:
os.getenv("DB_PASSWORD")
```

**Datoteka 4: `scripts/reprocess_missing_endstats.py:188`**
```python
# BEFORE:
os.getenv("DB_PASSWORD", "etlegacy_secure_2025")

# AFTER:
os.getenv("DB_PASSWORD")
```

**Po popravku**: Rotacija DB gesla na produkciji (staro je v Git zgodovini za vedno).

## P0-2: SQL injection pregled — REZULTAT: ČIST (11 min za 2 manjša popravka)

**Ekipa je preverila celoten codebase. Rezultat:**
- 0 kritičnih SQL injection ranljivosti
- Vsi user-supplied values so pravilno parametrizirani (`$1`, `?`)
- F-string SQL se uporablja SAMO za hardkodirane table/column imena

**2 manjša popravka:**

1. `website/backend/routers/records_router.py:2300` — LIKE wildcard escape:
```python
# BEFORE:
WHERE player_name ILIKE $1", (f"%{safe_query}%",)

# AFTER:
WHERE player_name ILIKE $1", (f"%{escape_like_pattern(safe_query)}%",)
```

2. `website/backend/routers/proximity_router.py:96-100` — defensivni allowlist za column name (že safe, ampak krhko):
```python
# BEFORE:
order_col = sort_map.get(sort_by, "total_kills")
query += f" ORDER BY {order_col} DESC"

# AFTER:
ALLOWED_SORT = {"total_kills", "avg_distance", "kdr", ...}
order_col = sort_map.get(sort_by, "total_kills")
if order_col not in ALLOWED_SORT:
    order_col = "total_kills"
query += f" ORDER BY {order_col} DESC"
```

## P0-3: Dependency sync (25 min)

### website/requirements.txt je drastično za root:

| Paket | website/ | root/ | Akcija |
|-------|----------|-------|--------|
| `fastapi` | 0.110.3 | 0.133.1 | UPDATE |
| `uvicorn` | 0.29.0 | 0.41.0 | UPDATE |
| `python-dotenv` | 1.0.1 | 1.2.1 | UPDATE |
| `asyncpg` | 0.29.0 | 0.31.0 | UPDATE |
| `httpx` | 0.27.2 | 0.28.1 | UPDATE |

**Fix**: Sinhroniziraj website/requirements.txt z root verzijami.

---

# P1a: RUFF RAZŠIRITEV (~1.5 ure)

## Sprememba pyproject.toml

```toml
# BEFORE:
[tool.ruff.lint]
select = ["E", "F", "W"]
ignore = ["E501", "E402"]

# AFTER:
[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "S", "T20", "SIM", "C4"]
ignore = [
    "E501",   # line-too-long
    "E402",   # module-level-import-not-at-top
    "S110",   # try-except-pass (namerni bot stability pattern)
    "S603",   # subprocess-without-shell (false positive na asyncio)
    "S607",   # start-process-with-partial-path
    "S601",   # paramiko-call (core SSH funkcionalnost)
    "S105",   # hardcoded-password-string (env fallback defaults)
]

[tool.ruff.lint.per-file-ignores]
"bot/endstats_parser.py" = ["T201"]       # CLI __main__ block
"website/backend/init_db.py" = ["T201"]   # Standalone seed script
"postgresql_database_manager.py" = ["T201"] # Interactive CLI tool

[tool.ruff.lint.isort]
known-first-party = ["bot", "website"]
```

## Sprememba .pre-commit-config.yaml

```yaml
# BEFORE:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.0
    hooks:
      - id: ruff
        args: ['--select', 'E,F,W', '--ignore', 'E501,E402', '--fix']

# AFTER:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.4
    hooks:
      - id: ruff
        args: ['--fix']
```

## Ocena vpliva novih pravil

| Pravilo | Kategorija | Približno kršitev | Auto-fix? |
|---------|-----------|-------------------|-----------|
| `I` | isort | 50-80 | DA (100%) |
| `UP` | pyupgrade | 500-900 | DA (95%) — `Optional[X]`→`X \| None`, `Dict`→`dict` |
| `B` | bugbear | 5-15 | Delno (50%) |
| `S` | security | 700+ | NE — ampak večina ignorirana z zgornjimi pravili |
| `T20` | print | 39 | NE — ročno (24 zamenjav) |
| `SIM` | simplify | 30-50 | Delno (40%) |
| `C4` | comprehensions | 10-20 | DA (90%) |

**Postopek**: `ruff check --fix` avtomatsko popravi I, UP, C4. Nato ročno T20 (print→logger).

---

# P1b: PRINT→LOGGER (20 min, 24 zamenjav)

**Vse 4 datoteke ŽE imajo logger konfiguriran — samo zamenjaj print() z logger.error():**

### `website/backend/routers/players_router.py` (10 zamenjav)
Logger: `get_app_logger("api.players")` — že obstaja na vrstici 23.
```python
# BEFORE (linije 196, 243, 261, 279, 299, 312, 397, 951, 1022, 1101):
print(f"Error fetching player stats: {e}")

# AFTER:
logger.error(f"Error fetching player stats: {e}")
```

### `website/backend/routers/records_router.py` (9 zamenjav)
Logger: `get_app_logger("api.records")` — že obstaja na vrstici 26.
```python
# Linije 614, 621, 696, 1082, 1138, 1242, 1342, 1486, 1660
# 696 posebej: logger.warning() (ima fallback, ni fatalno)
```

### `website/backend/routers/sessions_router.py` (3 zamenjave)
Logger: `get_app_logger("api.sessions")` — že obstaja na vrstici 26.
```python
# Linije 512, 601, 732
```

### `website/backend/routers/diagnostics_router.py` (2 zamenjavi)
Logger: `get_app_logger("api.diagnostics")` — že obstaja na vrstici 22.
```python
# Liniji 821, 1100
```

---

# P1c: TIHE IZJEME — CRITICAL TIER (2 uri, 12 sprememb)

## Popoln census: 220 tihih izjem, 85 datotek

| Tier | Štetje | Čas | Opis |
|------|--------|-----|------|
| CRITICAL | 12 | 2 uri | DB operacije, parser, data pipeline |
| HIGH | 70+ | 4 ure | API endpointi, servisi |
| MEDIUM | 30+ | 3 ure | Bot komande, paginacija |
| LOW | 28 | 1 ura | Samo anotacije (intentional suppression) |
| INTENTIONAL | ~80 | 0 | Pusti (ImportError, CancelledError, CLI) |

## CRITICAL popravki (teh 12 takoj):

### Fix 1: `bot/services/monitoring_service.py` (4 metode brez logiranja)
```python
# BEFORE (linije 203, 218, 231, 241):
except Exception:
    return False

# AFTER:
except Exception:
    logger.warning("DB error checking table %s", table_name, exc_info=True)
    return False
```

### Fix 2: `bot/community_stats_parser.py` (napačen tip izjeme)
```python
# BEFORE (safe_int, safe_float):
except Exception:
    return default

# AFTER:
except (ValueError, TypeError, IndexError):
    return default
```
Brez logiranja (kličejo se tisočkrat), ampak zoži tip da ne maskira pravih bugov.

### Fix 3: `bot/services/round_correlation_service.py:120`
```python
# BEFORE:
except Exception as e:
    return False, f"schema_preflight_query_failed:{type(e).__name__}"

# AFTER:
except Exception as e:
    logger.error("Schema preflight query failed: %s", e, exc_info=True)
    return False, f"schema_preflight_query_failed:{type(e).__name__}"
```

### Fix 4: `bot/automation/file_tracker.py` (4 DB operacije)
Že popravljeno v Deep RCA auditu, ampak preveri da so vsi poti pokriti.

## HIGH popravki — najhujši krivec:

### `proximity_router.py`: 53 bare `except Exception:` blokov
Trije pod-vzorci:
- **20x** že logira z `exc_info=True` → zoži tip izjeme
- **30x** posodobi payload ampak ne logira → dodaj `logger.exception()`
- **3x** (linije 468, 940, 964) POPOLNOMA tiho → dodaj `logger.debug()` z kontekstom

---

# P1e: SLOWAPI + PYTEST-ASYNCIO FIX (5 min)

### requirements.txt — dodaj slowapi:
```
# Na konec requirements.txt:
slowapi==0.1.9
```

### website/requirements.txt — dodaj slowapi:
```
slowapi==0.1.9
```

### requirements-dev.txt — fix pytest-asyncio:
```
# BEFORE:
pytest-asyncio==1.3.0   # TA VERZIJA NE OBSTAJA!

# AFTER:
pytest-asyncio==0.24.0
```

---

# P2a: TESTI ZA SERVISE (~6 ur, 3 nove datoteke)

## Stanje: 82 test datotek, coverage samo za `bot/`, 0% za website servise

### Nova datoteka 1: `tests/unit/test_storytelling_service.py`
- Največja netestirana datoteka (~2200 vrstic)
- **Pure funkcije** (brez mockov): `_to_date`, `_strip_et_colors`, `_format_time_ms`, `_weapon_name` — 12 testov
- **_score_kill** multiplier logika: carrier_kill, gibbed outcome, medic class, push bonus — 8 testov
- **_classify_archetype**: vsak arhetip (Slayer, Medic, Engineer...) — 7 testov
- **compute_session_kis**: cached result, no data, fresh compute — 3 async testov
- **detect_moments**: empty, diverse types — 2 async testov
- **Edge cases**: prazni podatki, NULL, GUID dolžina 8 vs 32
- **FakeDB** pattern: `_FakeStorytellingDB` z query routing
- **Ocena**: ~40 testov, ~300 vrstic

### Nova datoteka 2: `tests/unit/test_rivalries_service.py`
- **Pure funkcije**: `_classify`, `_weapon_name` — 8 testov
- **get_player_rivalries**: empty, nemesis+prey found — 3 async testov
- **get_head_to_head**: weapon breakdown, map breakdown — 2 async testov
- **Edge cases**: OMNIBOT filtriranje, self-kill, color code stripping
- **Ocena**: ~20 testov, ~200 vrstic

### Nova datoteka 3: `tests/unit/test_skill_rating_service.py`
- **Pure funkcije**: `get_tier`, `_percentile`, `_row_to_stats` — 15 testov
- **calculate_et_rating**: average player, missing percentiles, component structure, clamping — 4 testov
- **Edge cases**: zero rounds, division by zero, boundary values
- **Ocena**: ~25 testov, ~250 vrstic

---

# P2b: MYPY CONFIG (30 min)

### Dodaj v pyproject.toml:
```toml
[tool.mypy]
python_version = "3.11"
warn_return_any = false
warn_unused_configs = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
show_error_codes = true

[[tool.mypy.overrides]]
module = [
    "asyncpg.*", "discord.*", "paramiko.*", "scp.*",
    "trueskill.*", "PIL.*", "matplotlib.*", "watchdog.*",
    "redis.*", "prometheus_client.*", "slowapi.*", "websockets.*",
]
ignore_missing_imports = true
```

### Dodaj v requirements-dev.txt:
```
mypy==1.15.0
```

**Ocena napak**: ~450-730 na prvem zagonu. Faza 1 je informativna (non-blocking).

---

# P2c: CI PIPELINE UPDATE (1 ura)

### Obstoječi `.github/workflows/tests.yml` je dobra osnova. Dodaj:

1. **Ruff z razširjenimi pravili** (zamenjaj obstoječ korak)
2. **Bandit security scan** (nov korak, non-blocking)
3. **pip-audit** (nov korak, non-blocking)
4. **mypy** (nov korak, non-blocking z `|| true`)
5. **Coverage threshold**: `--cov-fail-under=15` (začetna meja)
6. **Coverage za website**: dodaj `--cov=website/backend`

**Kaj bi failalo na prvem zagonu:**
- `pytest-asyncio==1.3.0` — ne obstaja (fix zgoraj)
- `ruff format --check` — nikoli formatirano (preskoči zaenkrat)
- mypy — ~500+ napak (non-blocking)
- bandit — ~30 medium/low (non-blocking)

---

# P3a: IZVLEČI DUPLIKATE (1 ura)

### Nova datoteka: `website/backend/utils/et_constants.py`

```python
"""ET:Legacy shared constants and utility functions."""
import re

KILL_MOD_NAMES = {
    3: "Knife", 4: "Luger", 5: "Colt", 6: "Luger", 7: "Colt",
    8: "MP40", 9: "Thompson", 10: "Sten", 11: "Garand",
    12: "Silenced", 13: "FG42", 14: "FG42 Scope", 15: "Panzerfaust",
    16: "Grenade", 17: "Flamethrower", 18: "Grenade",
    22: "Dynamite", 23: "Airstrike", 26: "Artillery",
    37: "Carbine", 38: "K98", 39: "GPG40", 40: "M7",
    41: "Landmine", 42: "Satchel", 44: "Mobile MG42",
    45: "Silenced Colt", 46: "Garand Scope",
    50: "K43", 51: "K43 Scope", 52: "Mortar",
    53: "Akimbo Colt", 54: "Akimbo Luger",
    55: "Akimbo Silenced Colt", 56: "Akimbo Silenced Luger",
    60: "Sten", 66: "Backstab",
}

def strip_et_colors(name: str) -> str:
    if not name:
        return ""
    return re.sub(r'\^[0-9a-zA-Z]', '', name)

def weapon_name(kill_mod) -> str:
    if kill_mod is None:
        return "Unknown"
    return KILL_MOD_NAMES.get(int(kill_mod), f"MOD_{kill_mod}")
```

### Spremembe v obstoječih datotekah:
- `storytelling_service.py`: izbriši vrstice 58-72, 90-93, 107-109. Dodaj import.
- `rivalries_service.py`: izbriši vrstice 19-47. Dodaj import.
- `replay_service.py`: izbriši vrstice 18-22. Dodaj import.
- `storytelling_router.py`: spremeni import source.

---

# P3b: MEMORY LEAK FIX (30 min)

### `storytelling_service.py:23`

```python
# BEFORE:
_compute_locks: dict[str, asyncio.Lock] = {}

# AFTER:
from collections import OrderedDict

class _BoundedLockDict:
    """Bounded dict of asyncio.Lock. Evicts oldest when full."""
    def __init__(self, maxsize: int = 64):
        self._locks: OrderedDict[str, asyncio.Lock] = OrderedDict()
        self._maxsize = maxsize

    def get(self, key: str) -> asyncio.Lock:
        if key in self._locks:
            self._locks.move_to_end(key)
            return self._locks[key]
        if len(self._locks) >= self._maxsize:
            self._locks.popitem(last=False)
        lock = asyncio.Lock()
        self._locks[key] = lock
        return lock

_compute_locks = _BoundedLockDict()
```

Uporaba: `async with _compute_locks.get(lock_key):` namesto ročnega if/create.

---

# P3c: PROXIMITY_ROUTER SPLIT (4-6 ur)

### 5497 vrstic → 11 datotek

| Nova datoteka | Endpointov | Vrstic | Vsebina |
|---------------|-----------|--------|---------|
| `proximity_helpers.py` | 0 | ~600 | Shared pomožne funkcije |
| `proximity_combat_router.py` | 10 | ~1000 | Core combat analytics |
| `proximity_trades_router.py` | 3 | ~200 | Trade kill analytics |
| `proximity_teamplay_router.py` | 5 | ~400 | Teamplay v5 |
| `proximity_events_router.py` | 2 | ~300 | Event detail |
| `proximity_player_router.py` | 5 | ~500 | Player profiles, round deep-dive |
| `proximity_scoring_router.py` | 6 | ~640 | Weapons, revives, scores, leaderboards |
| `proximity_kill_analysis_router.py` | 5 | ~380 | Kill outcomes, hit regions |
| `proximity_positions_router.py` | 4 | ~320 | Combat positions, movement |
| `proximity_objectives_router.py` | 7 | ~620 | v6 objective intelligence |
| `proximity_support_router.py` | 4 | ~380 | Focus, support |

**Tveganje**: NIZKO. Čisti split, brez spremembe logike. Vsak sub-router dobi svoj `APIRouter()`.

---

# P3d: RECORDS_ROUTER SPLIT (3-4 ure)

### 3163 vrstic → 6 datotek

| Nova datoteka | Endpointov | Vrstic |
|---------------|-----------|--------|
| `overview_router.py` | 2 | ~540 |
| `seasons_router.py` | 3 | ~640 |
| `weapons_router.py` | 3 | ~310 |
| `awards_router.py` | 6 | ~640 |
| `records_router.py` (ohranjen) | 5 | ~640 |
| `rounds_router.py` | 3 | ~310 |

---

# P3e: ULTIMATE_BOT DEKOMPOZICIJA (8-12 ur) ⚠️ VISOKO TVEGANJE

### 6229 vrstic → ~350 vrstic + 10 novih modulov

| Nov modul | Vrstic | Izvor |
|-----------|--------|-------|
| `bot/services/admin_alert_service.py` | ~100 | Vrstice 340-438 |
| `bot/services/stats_import_service.py` | ~600 | 1045-1211, 1799-2636 |
| `bot/services/round_metadata_service.py` | ~400 | 1213-1612 |
| `bot/services/lua_data_service.py` | ~400 | 1615-1798, 4181-4516 |
| `bot/services/webhook_handler_service.py` | ~600 | 3212-3810 |
| `bot/services/stats_ready_service.py` | ~200 | 3834-3930, 4517-4701 |
| `bot/services/gametimes_service.py` | ~300 | 3932-4180 |
| `bot/services/endstats_pipeline_service.py` | ~1300 | 4703-6005 |
| `bot/tasks/monitoring_tasks.py` | ~300 | 2658-3208 |
| `bot/services/live_achievement_service.py` | ~120 | 1337-1447 |

**V ultimate_bot.py ostane** (~350 vrstic):
- `__init__()` (vitko — samo instantiate services)
- `setup_hook()` (vitko — cog loading loop)
- `on_ready()`, `on_message()` (tanki dispatcherji)
- `on_command()`, `on_command_completion()`, `on_command_error()`
- `close()`, `main()`

**⚠️ Glavna tveganja:**
- Deljeno mutable stanje (`processed_files`, `processed_endstats_files`, rate limit dicts)
- `self.config`, `self.db_adapter` referencirani globoko v call chain
- Task loops reference bot state direktno

---

# P3f: SHARED PACKAGE (4-6 ur)

### Razbitje bot/↔website/ sklopitve

**14 cross-importov website→bot, 2 cross-importov bot→website**

### Nova `shared/` struktura:
```
shared/
  database/
    adapter.py           # DatabaseAdapter + create_adapter()
    config.py            # load_config() — skupna DB/env config
  season_manager.py      # SeasonManager (čista logika)
  utils.py               # escape_like_pattern(), validate_stats_filename()
  crypto/
    contact_handle_crypto.py
  game_server/
    query.py
  services/
    session_data_service.py
    session_stats_aggregator.py
    stopwatch_scoring_service.py
    round_linkage_anomaly_service.py
    proximity_session_score_service.py
```

**~16 datotek spremenjenih** (import poti).

---

# PRIPOROČEN VRSTNI RED IMPLEMENTACIJE

```
Teden 1 (P0 + P1 quick wins):
  Dan 1: P0-1 gesla (32 min) + P1e slowapi/pytest fix (5 min)
  Dan 1: P1a ruff razširitev (1.5 ure) — ruff --fix auto popravi ~600 datotek
  Dan 1: P1b print→logger (20 min)
  Dan 2: P0-2 SQL popravka (11 min) + P0-3 dep sync (25 min)
         ─── skupaj dan 1-2: ~4 ure, 90+ datotek, OGROMEN ROI ───

Teden 2 (P1c-d tihe izjeme):
  Dan 3-4: P1c CRITICAL izjeme (2 uri) — 4 datoteke
  Dan 5-7: P1d HIGH izjeme (4 ure) — proximity_router 53x, ostali routerji

Teden 3 (P2 testing + tooling):
  Dan 8: P2b mypy config (30 min) + P2c CI update (1 ura)
  Dan 9-12: P2a testi za servise (6 ur) — 3 nove test datoteke, ~85 testov

Teden 4+ (P3 arhitektura):
  P3b memory leak (30 min) → P3a duplikati (1 ura)
  P3c proximity split (4-6 ur) → P3d records split (3-4 ure)
  P3f shared/ package (4-6 ur)
  P3e ultimate_bot decomp (8-12 ur) — ZADNJE, ko je shared/ na mestu
```

---

# ORODJA ZA NAMESTITEV

```bash
# Dev tools (dodaj v requirements-dev.txt):
pip install bandit[toml] mypy pip-audit vulture

# Skeniranje (enkratno):
bandit -r bot/ website/backend/ -ll                    # security
pip-audit -r requirements.txt                          # CVE check
vulture bot/ website/ --min-confidence 80              # dead code
mypy bot/core/ --ignore-missing-imports                # type check
ruff check bot/ website/ --select I,UP,B,S,T20,SIM,C4 # expanded lint
pytest --cov=bot --cov=website/backend --cov-report=term-missing  # coverage
```

---

# METRIKE USPEHA

| Metrika | Pred | Po P0-P1 | Po P2 | Po P3 |
|---------|------|----------|-------|-------|
| Hardcoded gesel | 4 | 0 | 0 | 0 |
| print() v prod routerjih | 24 | 0 | 0 | 0 |
| Ruff pravil | 3 (E,F,W) | 10 | 10 | 10 |
| Tihe izjeme CRITICAL | 12 | 0 | 0 | 0 |
| Tihe izjeme HIGH | 70+ | 70+ | 0 | 0 |
| Test datotek za servise | 0 | 0 | 3 | 3 |
| Test coverage (est.) | ~15% | ~15% | ~30% | ~35% |
| God files >3000 vrstic | 3 | 3 | 3 | 0 |
| Cross-imports bot↔web | 16 | 16 | 16 | 0 |
| mypy errors (est.) | 700 | 700 | 500 | 300 |
| Max datoteka (vrstic) | 6229 | 6229 | 6229 | ~1300 |

---

**Ta dokument je TEORIJA. Nič ni bilo spremenjeno. Pregledaj in odloči se kje začeti.**
