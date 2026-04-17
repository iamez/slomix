# Oksii Adoption — Odločitve po researchu
**Datum**: 2026-03-29 | **Na podlagi**: 5-ekipni research + uporabnikove odločitve

---

## Sprejete odločitve

### 1. Reinforcement formula
**Odločitev**: Hibrid — uporabi obstoječo `calculateSpawnTimingScore()` za oba teama (killer + victim). Shrani surove `killer_reinf` in `victim_reinf` sekunde za obe strani.
**Razlog**: Obstoječa funkcija pravilno upošteva reinf_offset. Potrebujemo podatke za OBA teama.

### 2. Tier 2 (stance, turtle)
**Odločitev**: Implementiraj z performance testom (config.debug timerji).
**Razlog**: Uporabnik želi podatke, ampak moramo meriti vpliv 6+ API klicev.

### 3. OUTNUMBERED_THRESHOLD
**Odločitev**: Dinamičen — `max(1, team_size // 3)`
**Razlog**: Prilagodi za 3v3 (threshold=1) in 6v6 (threshold=2) avtomatsko.

### 4. KIS reinf_mult inflacija
**Odločitev**: Relativni threshold — `victim_reinf > (spawn_interval * 0.75)`
**Razlog**: Dinamično za vsak match, ~25% killov dobi bonus namesto 50%.

### 5. BOX scoring
**Odločitev**: Ločen PR od Lua/KIS sprememb.
**Razlog**: BOX je Python-only, lažje testirati in rollbackati.

### 6. et_Revive
**Odločitev**: Najprej testiraj `pers.lastrevive_client` na serverju.
**Razlog**: Če deluje, et_Revive callback ni potreben.

### 7. Redundantni features
**Odločitev**: Nadgradi obstoječa (spawn_distance, entity scanning).
**Razlog**: Ne dupliciraj, ampak izboljšaj z Oksii insights.

### 8. KIS total_impact cap
**Odločitev**: Soft cap z linear compression nad 5.0
```python
def cap_impact(raw: float) -> float:
    if raw <= 5.0:
        return raw
    return 5.0 + (raw - 5.0) * 0.25
```
**Range**: 1.0 - ~8.5. Ohrani vrstni red, prepreči dominacijo enega killa.
**Razlog**: Multiplicative stacking z 10 multiplierji daje absurdne vrednosti (19x). Soft cap pri 5.0 z 25% kompresijo nad tem ohranja razlikovanje ampak prepreči outlierje.

---

## Popravljen scope za implementacijo

### PR 1: Lua + Parser + KIS (Tier 1 + nadgradnje)
- [x] 1.1 killer_health (FIX: index 18, ne 17!)
- [x] 1.2 alive_count (FIX: index 19/20)
- [x] 1.3 reinforcement timing (FIX: reuse calculateSpawnTimingScore, oba teama)
- [x] 1.4 spawn_distance → NADGRADI obstoječ post_spawn_distance
- [x] 2.1 Extended stance (z performance testom)
- [x] 2.2 Turtle detection (reuse obstoječe stamina)
- [x] 2.3 Entity scanning → NADGRADI obstoječ scanObjectiveEntities
- [x] 3.1 et_Revive → NAJPREJ test pers.lastrevive_client
- [x] 3.2 Spawn weapon (trivialno)
- [x] KIS: health_mult, alive_mult (dinamičen threshold), reinf_mult (relativni)
- [x] KIS: soft cap total_impact
- [x] DB migracija 033
- [x] Dataclass posodobitve
- [x] _table_has_column checki

### PR 2: BOX Scoring (ločen)
- [ ] box_scoring_service.py
- [ ] session_round_scores tabela (brez FK na gaming_sessions!)
- [ ] API endpoint
- [ ] Frontend per-map breakdown
- [ ] Team imena namesto Allies/Axis

---

## Kritični popravki plana pred implementacijo

1. CSV COMBAT_POSITIONS indeksi: 18/19/20 (ne 17/18/19)
2. Migracija: 033 (ne 032)
3. Reinf formula: reuse calculateSpawnTimingScore() z reinf_offset
4. Stance: pm_flags + ločen eFlags read (ne zamenjava)
5. _score_kill() (ne compute_kill_impact())
6. Dodaj _load_combat_positions() method za KIS
7. Razširi _load_spawn_timings() query
8. Posodobi INSERT batch (23 → 28+ parametrov)
9. Bot restart med parser in Lua deploy
10. Lua backup pred deployem
