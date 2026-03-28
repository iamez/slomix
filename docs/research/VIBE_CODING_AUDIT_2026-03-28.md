# Vibe Coding Audit: Slomix Discord Bot
**Datum**: 2026-03-28 | **Metoda**: Mandelbrot RCA (5 WHYs fraktalno kopanje) | **3 ekipe vzporedno**

---

## PREGLED

| Ekipa | Naloga | Rezultat |
|-------|--------|----------|
| Ekipa 1 - Raziskava | 40+ člankov, akademske študije, varnostna poročila | 55 najdb v 7 kategorijah |
| Ekipa 2 - Revizija kode | Celoten Slomix codebase audit | 22 najdb (1 CRITICAL, 3 HIGH, 10 MEDIUM, 8 LOW) |
| Ekipa 3 - Rešitve | Konkretni načrti popravkov, orodja, CI/CD | 8 kategorij z akcijskimi načrti |

---

# DEL 1: RAZISKAVA - Vibe Coding napake v industriji

## Ključne statistike

| Metrika | Vrednost | Vir |
|---------|----------|-----|
| AI koda z varnostnimi ranljivostmi | 45% | Veracode |
| AI PR-ji z vsaj 1 ranljivostjo | 87% | Tenzai |
| XSS failure rate across AI tools | 86% | Tenzai |
| CSRF/security headers present | 0% | Tenzai |
| SSRF prisoten pri vseh orodjih | 100% | Tenzai |
| Podvajanje kode (povečanje) | 48% | Codepanion |
| Podvojeni bloki (AI vs človek) | 8x več | Codepanion |
| Refactoring aktivnost (padec) | 60% | Codepanion |
| Hardcoded secrets v GitHub (2025) | 28.65M | GitGuardian |
| Secrets iz hardcoded vrednosti (vibe apps) | 78% | Replit |
| Deploymenti z izpostavljenimi sekreti | 20-40% | Raziskave |
| CTO-ji s produkcijskimi katastrofami od AI | 89% | BayTech |
| Startupi, ki potrebujejo rebuild | 8,000+ | BayTech |

## Top 10 najnevarnejših anti-vzorcev (po pogostosti in resnosti)

### 1. Tiho požiranje napak (Silent Exception Swallowing)
- **SIMPTOM**: Koda teče, ampak tiho ne dela kar mora
- **ZAKAJ #1**: AI generira prazne catch bloke, da koda "deluje"
- **ZAKAJ #2**: AI je treniran na javnih repozitorijih, kjer je `except: pass` pogost
- **ZAKAJ #3**: AI prioritizira "zagonljivo" kodo pred "pravilno" kodo
- **ZAKAJ #4**: Razvijalci testirajo samo happy path in ne opazijo tihih napak
- **ZAKAJ #5**: Ni avtomatiziranih orodij (bandit B110) v CI, ki bi to ujela
- **Pogostost**: #1 vzorec napak po Columbia DAPLab študiji

### 2. Hardcoded sekreti
- **SIMPTOM**: API ključi, gesla, tokeni direktno v kodi
- **ZAKAJ #1**: AI se je naučil iz javnih repozitorijev, kjer so sekreti pogosti v primerih
- **ZAKAJ #2**: Sekreti v Git zgodovini so permanentni tudi po brisanju
- **ZAKAJ #3**: Razvijalec zaupa AI outputu in ne pregleda vsake vrstice
- **ZAKAJ #4**: Ni avtomatiziranega pre-commit skeniranja ali rotacije sekretov
- **Realni primer**: $82,000 račun po kraji Google Cloud API ključa; Moltbook izpostavil 1.5M auth tokenov

### 3. Zlomljena avtentikacija/avtorizacija
- **SIMPTOM**: Manjkajoče ali obhodljive varnostne kontrole
- **ZAKAJ #1**: AI "preskoči" auth logiko ker je kompleksna
- **ZAKAJ #2**: Tenzai študija: avtorizacija je NAJBOLJ KRITIČNA varnostna vrzel
- **ZAKAJ #3**: Privzeta gesla (`user@example.com:password123`) ostanejo v produkciji
- **ZAKAJ #4**: Ni rate limitinga na občutljivih endpointih

### 4. Brez verzijskega nadzora ali rollback strategije
- **SIMPTOM**: Ni Git-a, ni save pointov, ni rollback možnosti
- **ZAKAJ**: Replit incident: "no rollback features - everything was lost"

### 5. Popravljanje simptomov namesto vzrokov
- **SIMPTOM**: AI popravlja izhod namesto vhodnega problema
- **ZAKAJ #1**: AI kaže "fix-it-where-you-see-it" pristranskost
- **ZAKAJ #2**: Lokalni popravki namesto sistemskih
- **ZAKAJ #3**: Vsak popravek uvede nove buge - spirala "fixes that break fixes"
- **ZAKAJ #4**: "The answer isn't better prompts - it's stepping back and understanding the structure"

### 6. Brez testov
- **SIMPTOM**: Prvo obvestilo o bugu je crash v produkciji
- **ZAKAJ**: AI-generirane test suite so "nestabilne, nepopolne in neusklajene"

### 7. Podvajanje kode / bloat
- **SIMPTOM**: 8x več dupliciranih blokov kot človeška koda
- **ZAKAJ**: AI obravnava vsak prompt izolirano, generira duplikate

### 8. Supply chain poisoning (slopsquatting)
- **SIMPTOM**: AI hallucinira imena paketov, ki ne obstajajo
- **ZAKAJ**: Napadalci registrirajo te fantomske pakete z zlonamerno kodo
- **Realni primer**: CanisterWorm napad 2026 - razširil se čez 47 npm paketov

### 9. Manjkajoča validacija vnosa
- **SIMPTOM**: AI predpostavlja, da so vsi vnosi pravilni
- **ZAKAJ**: Brez validacije negativnih števil, prekomerne dolžine, specialnih znakov

### 10. Razvoj brez arhitekture
- **SIMPTOM**: Cursor CEO: "shaky foundations... things start to crumble"
- **ZAKAJ**: "The agent is looking to create something that works, rather than adhering to principles of systemic design"

## Columbia DAPLab: 9 kritičnih vzorcev napak

Iz analize stotih napak čez 15+ aplikacij zgrajenih s Cline, Claude, Cursor, Replit, V0:

1. **Error Handling Failures** -- agenti potlačijo napake za tekoč program (NAJPOGOSTEJŠI)
2. **Business Logic Failures** -- koda deluje, ampak krši domenska pravila (NAJRESNEJŠI)
3. **Silent Failures** -- app teče brez crasha, ampak ne naredi zahtevane naloge
4. **State Management Issues** -- nepravilno upravljanje stanja med interakcijami
5. **Data Handling Errors** -- napačne transformacije, manjkajoče validacije
6. **UI/UX Implementation Gaps** -- manjkajoči loading states, error displays, accessibility
7. **Integration Failures** -- API klici brez error handleja ali retry logike
8. **Security Oversights** -- manjkajoč auth, izpostavljeni endpointi
9. **Performance Anti-Patterns** -- N+1 queries, neomejeni fetchi, memory leaki

---

# DEL 2: REVIZIJA KODE - Najdbe v Slomix codebase

## Povzetek po resnosti

| Resnost | Št. | Ključni problemi |
|---------|-----|-----------------|
| **CRITICAL** | 1 | Hardcoded DB geslo v scriptih |
| **HIGH** | 3 | God files (6229, 5497, 3163 vrstic), tesna sklopitev bot↔website |
| **MEDIUM** | 10 | Tihe izjeme, print logging, duplicirana koda, manjkajoč slowapi, migracije, brez testov za servise, izpostavljeni diagnostics, f-string SQL, fat controllers |
| **LOW** | 8 | CORS defaults, magic numbers, memory leak, placeholder nedoslednost, tranzitivne odvisnosti, input validacija, env validacija |

## CRITICAL najdbe

### SEC-01: Hardcoded DB geslo v scriptih
- **KAJ**: Geslo `etlegacy_secure_2025` hardkodirano v 4 Python scriptih
- **KJE**:
  - `scripts/backfill_player_track_metrics.py:21` - direktno hardkodirano
  - `scripts/repair_endstats_round_assignments.py:156` - kot os.getenv fallback
  - `scripts/backfill_vs_stats_subjects.py:315` - kot os.getenv fallback
  - `scripts/reprocess_missing_endstats.py:188` - kot os.getenv fallback
- **ZAKAJ #1**: Scripte so bile pisane hitro za one-off naloge, brez varnostnega pregleda
- **ZAKAJ #2**: Geslo je v Git zgodovini - tudi če ga odstraniš, ostane za vedno
- **ZAKAJ #3**: `detect-secrets` pre-commit hook bi moral to ujeti, ampak scripta morda niso šla skozi hook
- **ZAKAJ #4**: Brez rotacije gesel - isto geslo od 2025
- **ZAKAJ #5**: To je VZOREC - 4 različne datoteke, isti problem = sistemska vrzel v skriptah

## HIGH najdbe

### CQ-01: God File - `bot/ultimate_bot.py` (6,229 vrstic)
- **KAJ**: Ena datoteka vsebuje main bot class, task loops, stats import, schema validation, admin notifications
- **ZAKAJ #1**: Nastalo z inkrementalnim dodajanjem funkcionalnosti brez refaktoriranja
- **ZAKAJ #2**: AI dodaja kodo v obstoječo datoteko namesto ustvarjanja novih modulov
- **ZAKAJ #3**: Zelo težko za vzdrževanje - sprememba v enem delu lahko zlomi drugega
- **ZAKAJ #4**: Ni testov za posamezne komponente znotraj datoteke
- **ZAKAJ #5**: To je VZOREC - tudi `proximity_router.py` (5,497) in `records_router.py` (3,163)

### ARCH-01: Tesna dvosmerna sklopitev med `bot/` in `website/`
- **KAJ**: Website backend importira 10+ modulov iz `bot/`, bot importira 2 modula iz `website/`
- **ZAKAJ #1**: Deljeni `database_adapter` namesto skupnega paketa
- **ZAKAJ #2**: Ni možno deployati bot ali website neodvisno
- **ZAKAJ #3**: Sprememba v bot/core/ lahko zlomi website in obratno
- **ZAKAJ #4**: Krožna odvisnost onemogoča čist modularni razvoj

## MEDIUM najdbe

### ERR-01: Tihe `except Exception: pass` izjeme v kritičnih poteh
- **KJE**:
  - `bot/ultimate_bot.py:3191-3202` - RCON cleanup
  - `bot/core/lazy_pagination_view.py:185-186` - paginacija
  - `bot/core/endstats_pagination_view.py:148-149` - paginacija
  - `bot/core/pagination_view.py:117-118` - paginacija
  - `website/backend/main.py:394-395` - shutdown
  - `website/backend/routers/uploads.py:384-385` - upload
  - `bot/cogs/availability_poll_cog.py:1144-1145` - polling
- **ZAKAJ #1**: AI generira `pass` v except blokih ker prioritizira "delujočo" kodo
- **ZAKAJ #2**: Ni bandit B110 pravila v CI, ki bi to ujelo
- **ZAKAJ #3**: Napake v paginaciji in uploadu so nevidne za uporabnika - tiha degradacija
- **ZAKAJ VZOREC**: 435 širokih `except Exception:` ujemov v 64 datotekah v `bot/`

### ERR-02: `print()` namesto `logger` v produkcijskih routerjih
- **KJE**: 21 pojavitev v 4 routerjih:
  - `players_router.py` (8x)
  - `sessions_router.py` (3x)
  - `records_router.py` (6x)
  - `diagnostics_router.py` (2x)
- **ZAKAJ #1**: `print()` gre na stdout brez log levelov, timestampov ali log routinga
- **ZAKAJ #2**: Ne pojavi se v strukturiranih logih
- **ZAKAJ #3**: Logging audit (Feb 2027) je ocenil projekt 6.1/10, ampak print-i niso bili popravljeni

### SEC-02: F-string SQL konstrukcija (kontrolirano tveganje)
- **KJE**: `records_router.py:1635`, `diagnostics_router.py:219`, `proximity_cog.py:680`, `database_adapter.py:496`
- **ZAKAJ**: Interpolirane vrednosti prihajajo iz hardkodiranih slovarjev (ne user input), AMPAK vzorec je krhek - prihodnji maintainer lahko pomotoma interpolira user input
- **ZAKAJ VZOREC**: `# nosec B608` anotacija prizna tveganje

### SEC-03: Diagnostics endpointi brez avtentikacije
- **KJE**: `diagnostics_router.py` - vseh 11 endpointov brez auth
- **KAJ**: `/status`, `/diagnostics`, `/diagnostics/lua-webhook`, `/diagnostics/round-linkage`, `/monitoring/status`, `/live-status` ipd.
- **ZAKAJ**: Ne razkrivajo sekretov, AMPAK razkrivajo operativne podrobnosti (štetje tabel, čase zadnjih zapisov, server status, vzorce aktivnosti igralcev)

### CQ-04: Duplicirana koda - KILL_MOD_NAMES slovar
- **KJE**: Identičen 30-vnosni slovar v:
  - `website/backend/services/storytelling_service.py:58-72`
  - `website/backend/services/rivalries_service.py:19-33`
- **KAJ**: Tudi `_strip_et_colors()` in `_weapon_name()` funkciji sta duplicirani
- **ZAKAJ #1**: AI generira kodo izolirano za vsak prompt, ne ve za obstoječe implementacije
- **ZAKAJ #2**: Ni skupnega `constants.py` ali `utils.py` modula za deljene vrednosti

### DEP-01: `slowapi` manjka v requirements.txt
- **KJE**: `rate_limit.py` in `storytelling_router.py` importirata slowapi
- **KAJ**: Koda ima `try/except ImportError` fallback - no-op stub
- **ZAKAJ**: Rate limiting je VARNOSTNA funkcija, ki TIHO degradira v "nič" če paket ni nameščen
- **ZAKAJ VZOREC**: Tiha degradacija varnostne funkcije je hujša kot crash

### DB-01: Nedosledne migracije
- **KJE**: `migrations/` direktorij
- **KAJ**: Dva sistema poimenovanja (numbered vs unnamed), duplikat `008_` prefix
- **ZAKAJ**: Merge conflict ali oversight, ni migration runnerja

### TEST-02/03: Brez testov za website backend servise
- **KJE**: `storytelling_service.py`, `rivalries_service.py` - brez testov
- **KAJ**: Kompleksna poslovna logika (KIS scoring, synergy, rivalry detection) brez pokritja
- **ZAKAJ**: Coverage konfiguriran samo za `bot/` paket (`--cov=bot`)

### ARCH-02: Poslovna logika v route handlerjih
- **KJE**: `records_router.py`, `sessions_router.py`, `players_router.py`
- **KAJ**: Scoring kalkulacije, data agregacija, team detection direktno v endpoint handlerjih
- **ZAKAJ**: AI generira "vse v enem mestu" namesto ločevanja plasti

## LOW najdbe

### CFG-04: Postgres geslo defaults to prazen string
- **KJE**: `bot/config.py:78` - `postgres_password` defaults to `''`
- **ZAKAJ**: Bot poskuša connect z praznim geslom namesto fail-fast z jasno napako

### CQ-05: Magic numbers v storytelling service
- **KJE**: `storytelling_service.py` - `10000`, `3000`, `15000`, `5000` vgrajeni v metode

### CQ-06: Memory leak v storytelling service
- **KJE**: `storytelling_service.py:23` - `_compute_locks` dict raste neomejeno
- **KAJ**: Nov `asyncio.Lock()` za vsak unikaten session date, nikoli počiščen

### ARCH-03: Nedosleden SQL placeholder stil
- **KAJ**: `?` (bot/core) vs `$1` (PostgreSQL native) - database_adapter prevaja, ampak avtor mora vedeti kateri uporabiti kje

### DEP-02/03: Tranzitivne odvisnosti
- **KAJ**: `starlette` in `cryptography` se uporabljata direktno ampak nista eksplicitno v requirements.txt

---

# DEL 3: NAČRT POPRAVKOV

## Prioritetna matrika

| Prioriteta | Kategorija | Trud | Vpliv | Prva akcija |
|------------|-----------|------|-------|-------------|
| **P0** | SQL injection audit | Nizek | Kritičen | `bandit -t B608` na bot/ in website/ |
| **P0** | Skeniranje sekretov | Nizek | Kritičen | Preveri `detect-secrets` baseline, odstrani hardcoded gesla |
| **P0** | Ranljivosti odvisnosti | Nizek | Visok | `pip-audit -r requirements.txt` |
| **P1** | Audit tihih izjem | Srednji | Visok | Audit `database_adapter.py` (15 širokih catch-ev) |
| **P1** | Razširi ruff pravila | Nizek | Srednji | Dodaj `I,UP,B,S` v ruff config |
| **P1** | CORS utrjevanje | Nizek | Srednji | Preveri production CORS_ORIGINS env var |
| **P1** | Dodaj slowapi v requirements | Nizek | Srednji | `pip install slowapi && pip freeze | grep slowapi` |
| **P2** | Dodaj mypy | Srednji | Srednji | Začni samo z `bot/core/` |
| **P2** | Test coverage baseline | Srednji | Visok | `pytest --cov` za izmero trenutnega stanja |
| **P2** | Čiščenje mrtve kode | Nizek | Nizek | `vulture --min-confidence 80` |
| **P2** | Zamenjaj print() z logger | Srednji | Srednji | 21 pojavitev v 4 routerjih |
| **P3** | Strukturirano logiranje | Visok | Srednji | Migriraj na structlog v entry pointih |
| **P3** | Optimizacija indeksov | Srednji | Srednji | `pg_stat_user_tables` poizvedba |
| **P3** | CI pipeline | Srednji | Visok | GitHub Actions workflow |
| **P3** | Dekompozicija god files | Visok | Visok | Načrt za razbitje 3 velikih datotek |

## P0 - Takojšnji popravki (ta teden)

### 1. Odstrani hardcoded gesla iz scriptov
```bash
# Poišči vse:
grep -rn "etlegacy_secure_2025" --include="*.py" .
# Zamenjaj z:
os.getenv("DB_PASSWORD")  # brez fallback!
# Rotiraj geslo - staro je v Git zgodovini
```

### 2. SQL injection pregled
```bash
bandit -r bot/ website/ -t B608  # B608 = SQL injection test
grep -rn 'f"SELECT\|f"INSERT\|f"UPDATE\|f"DELETE' --include="*.py" .
```

### 3. Dependency vulnerability scan
```bash
pip install pip-audit
pip-audit -r requirements.txt
pip-audit -r website/requirements.txt
```

## P1 - Ta mesec

### 4. Razširi ruff pravila
Trenutni config (`pyproject.toml`):
```toml
select = ["E", "F", "W"]
```
Priporočen razširjen config:
```toml
[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "S", "T20", "SIM", "C4"]
ignore = ["E501", "E402", "S101"]
```
- `I` = isort (uvrstitev importov)
- `UP` = pyupgrade (modernizacija Python kode)
- `B` = bugbear (pogoste napake)
- `S` = bandit security pravila
- `T20` = zaznava print() ukazov
- `SIM` = poenostavitve
- `C4` = comprehensions

### 5. Audit tihih izjem
```bash
# Poišči vse bare except:
grep -rn "except:" --include="*.py" bot/ website/
# Poišči except Exception s pass:
grep -rn -A1 "except Exception" --include="*.py" . | grep "pass"
# Bandit check:
bandit -r bot/ website/ -t B110  # B110 = try-except-pass
```
**Strategija po plasteh:**
1. Tier 1 (kritična pot): `database_adapter.py`, parserji, automation
2. Tier 2 (servisi): `bot/services/`
3. Tier 3 (cog handlerji): vsaj `logger.error()` namesto `pass`
4. Tier 4 (orodja/skripte): nižja prioriteta

### 6. Zamenjaj print() z logger
21 pojavitev v produkcijskih routerjih:
- `players_router.py` (8x)
- `sessions_router.py` (3x)
- `records_router.py` (6x)
- `diagnostics_router.py` (2x)

### 7. Dodaj slowapi v requirements.txt
Rate limiting je varnostna funkcija - ne sme tiho degradirati.

### 8. Izvleci deljene konstante
`KILL_MOD_NAMES`, `_strip_et_colors()`, `_weapon_name()` v skupen `website/backend/utils/et_constants.py`

## P2 - Naslednji mesec

### 9. Test coverage baseline
```bash
pytest --cov=bot --cov=website --cov-report=term-missing
```
Prioriteta testiranja:
1. `database_adapter.py`, `community_stats_parser.py`, `round_linker.py`
2. `storytelling_service.py`, `rivalries_service.py`
3. FastAPI router endpointi
4. End-to-end pipeline testi

### 10. Dodaj mypy
```toml
[tool.mypy]
python_version = "3.11"
warn_return_any = true
ignore_missing_imports = true
```
Začni samo z `bot/core/` - postopno širi.

### 11. Dead code cleanup
```bash
pip install vulture
vulture bot/ website/ --min-confidence 80 --sort-by-size
```

## P3 - Dolgoročno

### 12. CI Pipeline (GitHub Actions)
```yaml
name: Code Quality
on: [pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install ruff bandit
      - run: ruff check bot/ website/
      - run: bandit -r bot/ website/ -ll
  security:
    runs-on: ubuntu-latest
    steps:
      - run: pip install pip-audit
      - run: pip-audit -r requirements.txt
```

### 13. Dekompozicija god files
- `ultimate_bot.py` (6,229 vrstic) -> izloči task loops, schema validation, admin notifications
- `proximity_router.py` (5,497 vrstic) -> sub-routerji po domeni
- `records_router.py` (3,163 vrstic) -> ločeni records, awards, weapons, maps

### 14. Razbitje bot↔website sklopitve
Izvleci `database_adapter`, `utils`, `config` v skupen `shared/` paket.

### 15. Strukturirano logiranje
Migriraj na `structlog` s korelacijskimi ID-ji (gaming_session_id, player_guid, round_id).

## Orodja

| Orodje | Namen | Status v projektu |
|--------|-------|-------------------|
| `ruff` | Linting + formatiranje | Nameščen, AMPAK minimalna pravila (E,F,W) |
| `bandit` | Varnostno skeniranje | NI nameščen |
| `mypy` | Type checking | NI nameščen |
| `detect-secrets` | Skeniranje sekretov | Nameščen v pre-commit |
| `pip-audit` | Ranljivosti odvisnosti | NI nameščen |
| `vulture` | Mrtva koda | NI nameščen |
| `pytest-cov` | Pokritost testov | Nameščen, coverage neznan |
| `slowapi` | Rate limiting | Uporabljen ampak NI v requirements.txt |
| `structlog` | Strukturirano logiranje | NI nameščen |

---

# DEL 4: SLOMIX vs INDUSTRIJA - Primerjava

## Kje je Slomix BOLJŠI od povprečja vibe-coded projektov

| Kategorija | Slomix | Tipičen vibe-coded projekt |
|------------|--------|--------------------------|
| Verzijski nadzor | Git z branching policy | Pogosto brez Git |
| .env za sekrete | Da (razen 4 scriptov) | 78% hardcoded |
| Parametrizirane poizvedbe | Da (večinoma) | Pogosto f-string SQL |
| CSRF zaščita | Da (CSRFMiddleware) | 0% po Tenzai študiji |
| Test infrastruktura | 92 test datotek | Pogosto 0 testov |
| Rollback strategija | Git + feature branches | Ni rollback-a |
| Dokumentacija | CLAUDE.md + 20+ doc datotek | Pogosto nič |
| Pre-commit hooks | detect-secrets, ruff | Pogosto nič |
| Rate limiting | Implementirano (rate_limit.py) | Pogosto nič |
| Session secret validacija | Da (startup check) | Pogosto hardcoded |

## Kje je Slomix NA RAVNI INDUSTRIJE (problematično)

| Kategorija | Slomix problem | Industrija problem |
|------------|---------------|-------------------|
| God files | 6,229 vrstic (ultimate_bot.py) | "Spaghetti code" brez strukture |
| Tihe izjeme | 435 širokih catch-ev v bot/ | #1 failure pattern po Columbia DAPLab |
| print() logging | 21x v produkcijskih routerjih | Pogost anti-pattern |
| Duplicirana koda | KILL_MOD_NAMES v 2 datotekah | 8x več duplikacij pri AI kodi |
| Manjkajoči testi za servise | storytelling, rivalries brez testov | Pogosto 0% pokritost |
| Tight coupling | bot/ ↔ website/ dvosmerja | Monoliti brez mej |

## Kje ima Slomix UNIKATNA tveganja

| Tveganje | Opis |
|----------|------|
| Geslo v Git zgodovini | `etlegacy_secure_2025` je permanentno v zgodovini |
| Diagnostics brez auth | 11 endpointov razkriva operativne podatke |
| slowapi tiha degradacija | Rate limiting izpade brez opozorila |
| Memory leak v locks | `_compute_locks` raste neomejeno |

---

# ZAKLJUČEK

## Kaj moramo narediti ZDAJ (P0)
1. Odstraniti hardcoded gesla in rotirati DB geslo
2. Pognati `bandit -t B608` za SQL injection pregled
3. Pognati `pip-audit` za dependency ranljivosti

## Kaj moramo narediti TA MESEC (P1)
4. Razširiti ruff pravila (dodaj S, B, I, UP, T20)
5. Začeti audit tihih izjem (435 catch-ev)
6. Zamenjati print() z logger (21 mest)
7. Dodati slowapi v requirements.txt
8. Izvleči deljene konstante

## Kaj moramo narediti NASLEDNJI MESEC (P2-P3)
9. Vzpostaviti test coverage baseline
10. Dodati mypy type checking
11. Nastaviti CI pipeline
12. Začeti dekompozicijo god files
13. Razbitje bot↔website sklopitve

---

**Viri**: Columbia DAPLab, Veracode, GitGuardian, Tenzai, Wiz, CodeRabbit, Forrester, Kaspersky, Invicti, Databricks, Stack Overflow, LogRocket, Fortune (Cursor CEO), AIM Consulting, Codepanion, 40+ člankov.
