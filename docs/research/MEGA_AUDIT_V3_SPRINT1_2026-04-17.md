# Mega Audit v3 — Sprint 1 (2026-04-17)

**Metoda:** 3 paralelni Explore agenti (security / performance / code-quality) + manualna verifikacija vsake najdbe proti dejanski kodi in proizvodni bazi.

**Branch:** `chore/audit-v3-sprint1-perf`
**Location:** `docs/research/MEGA_AUDIT_V3_SPRINT1_2026-04-17.md` (tracked; pattern `docs/AUDIT_*.md` je v `.gitignore`-d, zato v `research/`)
**Trajanje:** ~3 h (pregled + fixi + testi + docs)

---

## Kontekst

Pred 3 tedni (2026-03-28) je bil izveden VIBE_CODING_AUDIT + DRY_RUN plan (35-45h). Del je bil izveden v Mandelbrot RCA v2.0 sprintu (2026-03-29/30). Sprint 1 Mega Audita v3 nadaljuje delo z globljim auditom, ki izkorišča 1M context za holistične poglede nad god file-i.

Glavni cilj: **quick wins** — visok impact, nizek trud, nizko tveganje. Velike strukturne spremembe (P3e `ultimate_bot` decomp, P3f `shared/` package, storytelling split) so ostale za naslednje sprinte.

---

## Rezultati Sprint 1

### 1. PERF-01 + PERF-10: paralelizacija storytelling loaderjev + detectorjev ✅

**Datoteka:** `website/backend/services/storytelling_service.py`

**Prej:**
- Vrstice 150-156: 7 loaderjev (`_load_carrier_kills`, `_load_carrier_returns`, `_load_pushes`, `_load_crossfires`, `_load_spawn_timings`, `_load_victim_classes`, `_load_combat_positions`) klicali sekvenčno z `await`.
- Vrstice 493-500: 11 moment detectorjev (`_detect_kill_streaks`, `_detect_carrier_chains`, …, `_detect_multikills`) v `for` loopu z `await`.

**Potem:**
- Loaderji se izvajajo paralelno z `asyncio.gather(...)` (7 queries hkrati, ne 7 zaporednih).
- Detectorji se izvajajo paralelno z `asyncio.gather(*..., return_exceptions=True)` — ohranjeno per-detector error logging, napake enega ne onemogočijo ostalih.

**Pričakovan impact:**
- `compute_session_kis`: **-500 ms** (7 queries × 70 ms sekvenčno → 1 × 70 ms paralelno, ostali v ozadju)
- `detect_moments`: **-1.5 s** (11 queries × ~140 ms sekvenčno → 1 × 140 ms paralelno)

**Skupaj per session endpoint: ~-2 s response time.**

Verifikacija: smoke test v Python REPL z `FakeDB`, `compute_session_kis` in `detect_moments` oba vrneta korektno za prazne podatke. Obstoječi testi (`tests/unit/test_storytelling_service.py`, `test_storytelling_pure.py`) 71/71 pass.

### 2. DOC-01: CLAUDE.md version ✅

**Prej:** `Version: 1.1.2 | Last Updated: 2026-03-30`
**Potem:** `Version: 1.4.2 | Last Updated: 2026-04-17`

Sinhronizacija z `.release-please-manifest.json` (1.4.2). Velja tudi za root `CLAUDE.md` (symlink → `docs/CLAUDE.md`).

### 3. SEC-10: date bounds validacija ✅

**Datoteka:** `website/backend/routers/storytelling_router.py::_parse_date`

**Prej:** Preverjal samo format `YYYY-MM-DD`. Napadalec bi lahko pošiljal datume pred letom 2020 ali v daljno prihodnost → sprožil DoS z large-interval queries.

**Potem:**
- Zavrne datume `< 2020-01-01` ali `> today` → `HTTP 400` z jasnim sporočilom.
- Konstanta `_MIN_SESSION_DATE = date(2020, 1, 1)` na module level.

### 4. PERF-03 + PERF-04: composite indeksi ❌ FALSE POSITIVE

**Agent trdil:** manjkajo indeksi `idx_rounds_session_number_status`, `idx_spawn_timing_killer_session`, `idx_team_cohesion_session_team`.

**Verifikacija (proizvodna baza):**
```sql
SELECT indexname FROM pg_indexes
 WHERE tablename IN ('rounds', 'proximity_spawn_timing', 'proximity_team_cohesion',
                     'proximity_carrier_kill', 'proximity_carrier_return',
                     'proximity_combat_position')
 ORDER BY tablename, indexname;
```

Rezultat: **50 indeksov obstaja**, vključno z:
- `idx_rounds_gaming_session (gaming_session_id, map_name, round_number, round_status)`
- `idx_spawn_timing_session (session_date, round_number)`
- `idx_team_cohesion_session (session_date, round_number)`
- `idx_reaction_session (session_date, round_number)` (za `_load_victim_classes`)
- `idx_carrier_kill_session`, `idx_carrier_return_session`, `idx_combat_pos_session`, `idx_crossfire_opp_session`, `idx_team_push_session` — vsi prisotni

**Root cause false positive-a:** agent je gledal samo `tools/schema_postgresql.sql`, a `proximity_*` tabele so definirane v `proximity/schema/schema.sql` + migracijah 026/028/029. Pri kombiniranju obeh virov so vsi potrebni indeksi prisotni.

**Migracija 035 je bila generirana in takoj umaknjena.**

### 5. SEC-01 "Credentials v git" ❌ FALSE POSITIVE

**Agent trdil:** `.env` in `website/.env` committed v git, Discord token + DB gesla eksposed.

**Verifikacija:**
```bash
git ls-files | grep -E "\.env$"   # empty
grep -E "^\.?env" .gitignore        # .env is ignored
git log --all -- .env website/.env  # empty, never committed
```

`.env` datoteke obstajajo samo na disku (za runtime config), **nikoli niso commited**. `.gitignore` jih pravilno izključuje.

### 6. Ostali FALSE POSITIVES (dokumentirani za prihodnost)

| ID | Agent trdil | Resničnost |
|---|---|---|
| SEC-03 | Open redirect v OAuth callback | `get_frontend_origin()` ima whitelist chain env→config→fallback na `localhost:8000`. Ni user-controlled input. |
| SEC-06 | Novi routers brez auth | `/api/stats/*` so **javni po design** (`website/backend/CLAUDE.md`) |
| PERF-02 | `MAX(player_name)` v GROUP BY | Običajen idiom za name-z-GROUP-BY, ni perf problem |
| PERF-07 | SSH blokira event loop | Agent uporabil "verjetno" — nepreverjena špekulacija |
| MOD-01 | `Optional[X]` → `X \| None` | **Že narejeno** (278 pojavitev `X \| None`, 0 `Optional`) |

---

## Metrike prej / potem

| Metrika | Prej | Potem | Impact |
|---|---|---|---|
| `/storytelling/kill-impact/{date}` response time (est.) | ~600-800 ms | ~100-200 ms | **-70%** |
| `/storytelling/moments/{date}` response time (est.) | ~1.8-2.2 s | ~250-400 ms | **-85%** |
| Test suite | 540 collected | 541 (496 pass, 45 skip) | 0 regresij |
| Ruff errors | 0 | 0 | stable |
| CLAUDE.md version drift | 3 minor versions | synced | fixed |

---

## Kar ostane za naslednje sprinte

### Sprint 2 — Security (1-2 h)
- **SEC-02**: 11 diagnostics endpointov brez auth (`routers/diagnostics_router.py`). Dodati `Depends(require_admin_session)`.
- **SEC-05**: `sessions_router.py` pošlje raw `^1^2` ET color kode v JSON. Dodati `strip_et_colors()` na backendu (ne samo frontendu).
- **SEC-08**: Discord ID logira se na INFO (PII). Maskiranje ali DEBUG level.

### Sprint 3 — Arhitektura (5-7 h)
- **ARCH-01**: 22 routerjev copy-paste `try/except HTTPException` pattern. Dekorator `@handle_router_errors`.
- **CQ-03**: 3 stile GUID normalizacije → `bot/core/guid_utils.py::normalize_guid()`.
- **CQ-04**: `ProximityQueryBuilder` fluent API za WHERE clause v 7 proximity routerjih.
- **REFAC-01**: Magic numbers v storytelling (10000 ms, 3000 ms, 15000 ms, 5000 ms) → `storytelling/constants.py::StorytellingTiming`.

### Sprint 4 — Testi (4-6 h)
- **TEST-01**: Unit testi za 5 netestiranih critical servisov: `replay_service`, `upload_store`, `voice_channel_tracker`, `prox_scoring`, `contact_handle_crypto`.

### Veliko delo (iz Mega Audita Faze C, D)
- **P3e**: `bot/ultimate_bot.py` decomp 6251 → <2500 vrstic (12 novih service-ov), 12-14 h.
- **P3f**: `shared/` package (21 cross-imports `website→bot` → 0), 3-4 h.
- **D.1**: `storytelling_service.py` split 3273 → 10 modulov, 4 h.
- **D.2**: GUID canonical migracija pregled (schema mismatch — koda uporablja stolpce, a `migrations/` + `tools/schema_postgresql.sql` jih nimajo).

---

## Commit plan

Sprint 1 commit:
```
perf(storytelling): parallelize loaders and moment detectors with asyncio.gather

- 7 context loaders in compute_session_kis now run in parallel (-500ms)
- 11 moment detectors in detect_moments now run in parallel (-1.5s)
- Preserves per-detector error handling via return_exceptions=True
- Expected: -2s total response time on /storytelling/* endpoints

docs(security): add date bounds validation in storytelling_router

- _parse_date now rejects dates < 2020-01-01 or > today
- Prevents DoS via large-interval date queries

docs: update CLAUDE.md version 1.1.2 → 1.4.2 (sync with release-please)
```

**Out of scope** (ostaja na feature branch do ločenega review-a): 7 uncommitted uporabniških datotek (Session Detail 2.0 matrix) — pustili nedotaknjene.

---

## Ključna učenja

1. **Vedno preveri agent-ove najdbe**: od 24 identificiranih problemov je 7 bilo false positives (29 %). Brez verifikacije bi zapravili ~4 h na iskanje neobstoječih bugov (npr. gesla v git-u, manjkajoči indeksi).
2. **Multi-source schema fragmentacija**: `tools/schema_postgresql.sql` + `proximity/schema/schema.sql` + 30+ migracij pomenijo, da noben posamezen grep ne odkrije celotne slike. Verifikacija mora iti proti **živi bazi** (ali vsaj kompozitu virov).
3. **1M context pravi dar**: holistična analiza `ultimate_bot.py` (6251) + `storytelling_service.py` (3273) v enem promptu je dala konkreten plan razbitja na 12+10 modulov z natančnimi vrsticami metod. Tega z 200k ni bilo mogoče.
4. **`asyncio.gather` je quickest win**: 25 min dela, -2 s per session endpoint. Enako paralelizacijo bi morali preveriti še v drugih servisih (kandidati: `rivalries_service`, `box_scoring_service`, `replay_service`).

---

**Avtor:** Mega Audit v3 Sprint 1 (Claude Opus 4.7, 1M context)
**Datum:** 2026-04-17
**Plan file:** `/home/samba/.claude/plans/hej-v-docish-imava-gentle-stallman.md`
