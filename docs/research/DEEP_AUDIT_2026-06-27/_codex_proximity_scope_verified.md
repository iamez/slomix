# Zunanji input (Codex) — preverjena proximity scope najdba

Vir: `docs/SLOMIX_GOOD_NIGHT_ENGINE_PLAN_2026-06-28.md` (Codex, 2026-06-28, untracked).
Status: **PREVERJENO proti živi kodi** med Wave 2 — vključi v Wave 2 poročilo (proximity/correctness).

## Najdba: `/proximity/prox-scores` tiho ignorira scope → fabricated "scoped" prox_overall

- Backend `get_prox_scores` (`website/backend/routers/proximity_scoring.py:549`) sprejme **samo**
  `range_days`, `player_guid`, `limit`. Ne sprejme `session_date`, `map_name`, `round_number`,
  `round_start_unix`. `compute_prox_scores(db, range_days, player_guid)` (`services/prox_scoring.py`)
  prav tako ne filtrira po seji/mapi/rundi.
- Frontend `proximity.js:1668` kliče `scopedUrl('/proximity/prox-scores', { extra: { min_engagements: 30 } })`
  — `scopedUrl` doda scope parametre, ko je izbran datum/mapa/round. Backend jih spusti na tla.
- **Posledica:** ko uporabnik na Proximity strani izbere konkretno sejo/mapo, prox_combat/prox_team/
  prox_gamesense/**prox_overall** kljub temu kažejo 30-dnevni/globalni percentilni score, predstavljen
  kot da je scoped. Krši "no fabricated numbers". Severity: **MEDIUM** (correctness).

## Predlog popravka
Razširi `compute_prox_scores()` + endpoint signaturo, da sprejmeta full scope (uporabi obstoječi
`_build_proximity_where_clause` vzorec iz `proximity_helpers.py`, kot ostali proximity endpointi), ALI
endpoint eksplicitno označi kot namerno globalen + scope badge "all-time/30d" na panelu, da ni dvoumno.
Codexov dokument predlaga enoten `ProximityScope` kontrakt (frontend/API/backend) + scope badge na vsakem
panelu + acceptance teste (izbran datum/mapa/round MORA vplivati na vsak panel). Razumno; uskladi z
anti-bloat (ne nova stran, le doslednost obstoječih panelov).

## Širši Codex doc
`SLOMIX_GOOD_NIGHT_ENGINE_PLAN_2026-06-28.md` (4837 vrstic) je večinoma produktni "Good Night Engine"
plan; akcijsko-preverjen del je zgornja proximity scope vrzel + seznam verjetno scope-nedoslednih React
proximity panelov (potrebno ločeno preveriti, React je sekundaren). Ostalo so predlogi, ne najdbe.
