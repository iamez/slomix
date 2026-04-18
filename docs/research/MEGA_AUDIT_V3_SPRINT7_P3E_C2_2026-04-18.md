# Mega Audit v3 — Sprint 7 / P3e C.2 (2026-04-18)

**Cilj:** Prvi od 4 podsprintov razbitja `bot/ultimate_bot.py` (6251 vrstic) — ekstrakcija endstats pipeline.
**Branch:** `chore/audit-v3-sprint7-p3e-endstats`
**PR:** #90
**Trajanje:** ~30 min

## Pristop — AST split → mixin inheritance

Uporabljen isti AST-based pristop kot v Sprint 6 (storytelling), a s ključno razliko: **Discord.py `commands.Bot` subclass** zahteva, da je `commands.Bot` zadnji razred v MRO. Mixin gre pred `commands.Bot`:

```python
class UltimateETLegacyBot(_EndstatsPipelineMixin, commands.Bot):
    ...
```

MRO rezultat:
```
UltimateETLegacyBot → _EndstatsPipelineMixin → Bot → BotBase → GroupMixin → Generic → Client → object
```

**Zakaj mixin, ne service DI?**
- `self.db`, `self.config`, `self.processed_files`, `self.track_error` vse živijo na bot instance
- 50+ klicnih mest v cogs/testih → service DI bi pomenil massive call-site refactor
- Mixin pattern: 0 sprememb na klicnih mestih, testi nespremenjeni
- Če kasneje service DI → mixin je intermediate stepping stone

## Metode ekstrahtirane (22)

**STATS_READY pipeline** (2):
- `_fetch_latest_stats_file` — download z game serverja po STATS_READY webhooku
- `_trigger_proximity_scan_after_stats` — trigger proximity import po stats persist

**Quality + filename helpers** (10):
- `_log_endstats_transition`
- `_summarize_endstats_quality`
- `_parse_endstats_filename_timestamp`
- `_are_endstats_from_same_match`
- `_select_richest_endstats`
- `_is_endstats_quality_better`
- `_is_endstats_round_unique_violation`
- `_mark_endstats_filename_handled`
- `_get_round_endstats_quality`
- `_hhmmss_to_seconds`

**Round resolution** (3):
- `_resolve_endstats_round_id`
- `_is_endstats_round_already_processed`
- `_is_endstats_round_ready`

**Retry scheduler** (4):
- `_get_endstats_retry_delay`
- `_clear_endstats_retry_state`
- `_schedule_endstats_retry`
- `_retry_webhook_endstats_link`

**File processing** (3):
- `_store_endstats_and_publish`
- `_process_endstats_file`
- `_process_webhook_triggered_endstats`

## Metrike

| | Pred | Po | Δ |
|---|---|---|---|
| `bot/ultimate_bot.py` | 6251 | 4762 | **-1489 (-23.8%)** |
| `bot/services/endstats_pipeline_mixin.py` | — | 1521 | **+1521 (new)** |
| Tests | 508 pass | 508 pass | ✅ |
| Ruff | 0 errors | 0 errors | ✅ |

## Verifikacija

- `python3 -m py_compile` na oba fajla → OK
- Import: `from bot.ultimate_bot import UltimateETLegacyBot` → OK
- MRO: `_EndstatsPipelineMixin` precedes `Bot` → OK
- `hasattr` check za 5 kritičnih metod → vse dostopne
- `pytest tests/ -q` → 508 passed, 45 skipped
- `ruff check bot/services/endstats_pipeline_mixin.py bot/ultimate_bot.py` → clean

## Gotchas

**1. Ruff auto-fix odstranil `time`, `timedelta`, `round_contract` importe** — v template-u so bili vključeni "just in case", a dejansko jih ekstrahirane metode ne uporabljajo. Ruff počisti to takoj.

**2. Manjkal `discord` import** — metode uporabljajo `except discord.DiscordException:` za Discord API reaction errors. Dodan ročno (ne avto-fix ker ni imported drugje v mixinu).

**3. Manjkala `re` in `os` importa** — `_validate_stats_filename` uporablja regex, `_fetch_latest_stats_file` uporablja `os.path.join` za local paths. Dodana ročno.

## Naslednji koraki

**Sprint 7 / C.3** — webhook handler + lua round storage (~840 vrstic):
- `_WebhookHandlerMixin` (8 metod): webhook mode, filename validation, dispatch
- `_LuaRoundStorageMixin` (6 metod): lua webhook data persistence

Skripta že pripravljena v `/tmp/split_webhook_lua.py`.

**Preostanek:**
- C.3: webhook_handler_mixin + lua_round_storage_mixin (~840 vrstic)
- C.4: stats_import_mixin + monitoring_tasks (~1400 vrstic)
- C.5: cleanup + preostale metode (~500 vrstic)

**Ciljna metrika po P3e:** `ultimate_bot.py` < 2500 vrstic (facade + init + on_* handlerji + main).

---

**Avtor:** Mega Audit v3 Sprint 7 / P3e C.2 (Claude Opus 4.7, 1M context, AST split)
**Datum:** 2026-04-18
