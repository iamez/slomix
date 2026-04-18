# Mega Audit v3 — Sprint 6 / D.1 (2026-04-18)

**Cilj:** Razbiti monolitski `storytelling_service.py` (3302 vrstic) na mixin modular paket.
**Branch:** `chore/audit-v3-sprint6-storytelling-split`
**Trajanje:** ~1 h

## Pristop — AST-based mixin split

Uporabljen **AST parse** (`ast` modul) za deterministično razdelitev vseh 42 metod `StorytellingService` v 9 mixin classov po domenih. Glavni class deduje iz vseh mixinov → public API je identičen, 83 storytelling-related testov se ne spreminja.

**Zakaj mixin pattern:**
- Client API nespremenjen: `StorytellingService(db).compute_session_kis(...)` deluje kot prej
- Module-level konstante ostanejo module-level
- Backward-compat: `from website.backend.services.storytelling_service import StorytellingService`
- Ne lomimo 83 testov (facade class MRO pokaže vseh 42 metod)

## Struktura

```
website/backend/services/
├── storytelling_service.py          (14 lines — backward-compat shim)
└── storytelling/
    ├── __init__.py                  (re-export StorytellingService + base.*)
    ├── base.py                      (180 — konstante, helperji, __all__)
    ├── service.py                   (38 — facade class, MRO 9 mixinov)
    ├── kis.py                       (289 — _KisMixin)
    ├── loaders.py                   (112 — _LoadersMixin: 7 × _load_*)
    ├── moments.py                   (889 — _MomentsMixin: detect_moments + 12 × _detect_*)
    ├── archetypes.py                (264 — _ArchetypesMixin)
    ├── synergy.py                   (306 — _SynergyMixin)
    ├── win_contribution.py          (364 — _WinContributionMixin)
    ├── momentum.py                  (221 — _MomentumMixin)
    ├── narrative.py                 (392 — _NarrativeMixin)
    └── advanced_metrics.py          (478 — _AdvancedMetricsMixin)
```

**Pred:** 1 fajl, 3302 vrstic, max=3302.
**Po:** 11 fajlov, max=**889** (moments.py).

## Ruff config

Dodan `per-file-ignore` za F403/F405 v `website/backend/services/storytelling/*` — `from .base import *` z eksplicitnim `__all__` v base.py je runtime-safe, ampak ruff static check ga označi kot negotovo.

## Verifikacija

- `ruff check bot/ website/backend/ shared/` — 0 errors
- `pytest tests/` — **508 passed**, 45 skipped, 0 failed
- Import sanity: StorytellingService MRO 11, 42 public metod
- Backward-compat: vsi obstoječi imports delajo

## Remaining Mega Audit v3

Po tem PR-ju ostane samo **P3e** (ultimate_bot.py decomp):
- 6251 vrstic → <2500 (facade)
- Izvleček ~100 metod v ~12 novih servisov
- Priporočeno razbito v **4 PR-je** (po podfazah) — bot production stability

AST split strategy iz D.1 je direktno re-usable.

---

**Avtor:** Mega Audit v3 Sprint 6 / D.1 (Claude Opus 4.7, 1M context, AST split)
**Datum:** 2026-04-18
