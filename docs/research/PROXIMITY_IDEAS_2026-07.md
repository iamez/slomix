# Proximity — idejni katalog + formule (2026-07-03)

> **Namen:** proximity je naš "skriti adut" — zajem podatkov je bogat in stabilen, manjka pa
> produkt: kaj in kako prikazati. Ta dokument konsolidira VSE obstoječe vire idej
> (Good Night plan "opportunity atlas", PROXIMITY_GAP_ANALYSIS_2026-06, smart-scoring design,
> map-viz vizija) + svež online research v en **data-ready ocenjen katalog** s formulami v0
> in konkretnim vrstnim redom. Nič tu ni koda — to je meni za odločanje.
>
> **Severnica (iz Good Night plana):** friendship-safe, rank-vs-self, "Discord triggers,
> website explains", en panel naenkrat — ne 12 live plošč.

---

## 1. Kaj pravi profi praksa (validacija smeri)

| Vir | Kaj delajo | Nauk za Slomix |
|---|---|---|
| [Leetify Rating](https://leetify.com/blog/leetify-rating-explained/) | kill vrednost = Δ win-probability (ekonomija, št. živih, prejšnja eliminacija); zero-sum; bell-curve prikaz s 5 pasovi | naš KIS/EIS z (alive_count, reinf timing, health) je ISTA filozofija — kontekstualna vrednost killa. Prikaz: pasovi ("nad svojim običajnim") namesto surove številke |
| [HLTV Rating 3.0](https://www.hltv.org/news/42485/introducing-rating-30) | 6 pod-ratingov (Kills, Damage, Survival, KAST, Multi-kills, Round Swing); **Round Swing je po lansiranju preveč dominiral → rebalans na 60-40** | pri composite formulah (Form "impact", prox_overall) VEDNO backtest uteži — ena komponenta ne sme prevladati. Naš clamp [0.4, 2.5] + renormalizacija je pravi instinkt |
| [Strava segments](https://support.strava.com/hc/en-us/articles/216918167-Strava-Segments) | tisoče LOKALNIH lestvic namesto ene globalne; PR-ji so zasebni; "against yourself" | per-map objective records ("segments") + osebni PB-ji so že naša smer (S4). Proximity rekordi naj bodo per-map/per-zone, ne all-time global |
| [Scope.gg](https://scope.gg/) vs [CS Demo Manager](https://cs-demo-manager.com/) | casual → preprost intuitiven pregled brez preobilja; power-user → desktop z globokimi filtri/heatmapi | **dvo-površinska strategija potrjena**: story-izvlečki za vse (Session Detail/Story), surovi proximity dashboard za power userje. Ne siliti vseh v 81 endpointov |
| OpenSkill ([arxiv 2401.05451](https://arxiv.org/abs/2401.05451)) | Bayesov team rating, asimetrične ekipe, balance flag, hitrejši od TrueSkill | za friendship-safe balancer: ET-Rating + negotovost (σ) + stomp-risk; OpenSkill je referenčna matematika, ne dependency |

---

## 2. Inventar podatkov (osveženo 2026-07-03)

Vse iz PROXIMITY_GAP_ANALYSIS_2026-06 drži; novo od takrat:

| Vir | Stanje 07-03 | Opomba |
|---|---|---|
| `proximity_aim_lock` | **ŽIVO** — 6.913 vrstic prod (6.536 po 06-22), max 51,2 s (clamp fix deluje) | aktiviran 2026-06-22; edini v7 zajem, ki je vklopljen |
| `proximity_shot_fired` | živo dev+prod (116k prod po 06-22) | aim analytics podlaga |
| `proximity_kill_outcome` | 26k+ vrstic, dela | **odklene KROGT/EIS/MER/TDS** |
| `spawn_select`, `skill_snapshot`, `comm_events` | dormant (flagi OFF) | vklop šele, ko ima UI porabnika |
| orphan round_id | shot_fired ~7,7 % dev | sanacija = data-quality postavka |

---

## 3. Katalog idej — data-ready ocena

Legenda: 🟢 podatki + infra obstajajo, samo prikaz/agregat · 🟡 podatki so, rabi novo service/render plast · 🔴 rabi nov zajem ali netrivialno raziskavo · ✋ friendship-safe tveganje (zahteva pozitivno framanje)

### A. Story layer (prioriteta 1 — po planu in po Scope.gg nauku "casual rabi zgodbo")

| # | Ideja | Podatki | Formula/logika v0 | Surface | Ocena |
|---|---|---|---|---|---|
| A1 | **Session moments strip** — 3–5 momentov večera (clutch revive, carrier stop, comeback push) | storytelling_kill_impact, trade_event, carrier_kill, objective_run | obstoječi moment detektorji + Story Worthiness Score iz plana (§Algorithm family 4) s shame-filtrom | Session Detail vrh | 🟢 |
| A2 | **Stopwatch Map Race Story** — ena kartica na map-par: target čas, R2 chase, odločilni wave, ključni pressure igralec | rounds, lua_round_teams, spawn_timing, team_push | plan §"Best near-term unique idea"; stage-split iz construction/vehicle eventov | Session Detail / Tonight po koncu mape | 🟡 |
| A3 | **"Invisible value" povzetek v besedi** — gravity/space/enabler že računamo; nihče jih ne bere kot številke | obstoječi 4 endpointi (živi, polni) | template: "X je nočes vlekel največ pozornosti nase (gravity 82) — ekipa je za njim dihala lažje" | Story stran + digest vrstica | 🟢 |
| A4 | **Duo Trust kartica** — kdo tradea/revivea/crossfirea s kom | lua_trade_kill, revive, crossfire_opportunity | duo_score = shrunk(trade_rate + revive_rate + crossfire_share); shrinkage k=10 skupnih rund (plan §family 7) | Profil + Session Detail | 🟢 |

### B. Map intelligence (prioriteta 2 — "proximity postane vizualen in zapomnljiv")

| # | Ideja | Podatki | Formula/logika v0 | Surface | Ocena |
|---|---|---|---|---|---|
| B1 | **"Where pushes die" overlay** — heatmap kje umrejo neuspešni pushi + carrier smrti | team_push (60k), carrier_kill, combat_position; `map_transforms.json` + worldToCanvas infra OBSTAJA | filter push=failed → death coords → density render (ista pot kot obstoječi death heatmap) | Maps/Proximity map panel | 🟡 |
| B2 | **Chokepoint index** — cone z visoko gostoto smrti + denied time + ponovljenih fightov | combat_position, kill_outcome, spawn_timing | grid-cluster (npr. 256u celice): score = deaths × repeat_factor × denied_ms | isti panel kot B1 | 🟡 |
| B3 | **Objective stage timeline** — "gate faza običajno odloči to mapo" | construction_event (195+), vehicle_progress, objective_run | per-map histogram: pri kateri stopnji se runde končajo | Record Book / Maps | 🟡 |
| B4 | **Personal danger zones** (zasebno!) — "največkrat umreš pri spodnjem tunelu" | combat_position per igralca | igralčeve smrti → top-3 celice; **privat/opt-in** (plan: negative = private) | Profil, zasebni tab | 🟡 ✋ |
| B5 | Named zones — hotspoti dobijo imena skupnosti | clusteri iz B2 | lore feature, kasneje | Maps | 🔴 (odloži) |

### C. Nove formule / metrike (uporabnikova izrecna želja — "formule lahko ustvarimo")

Vse spodnje so bile 2026-03 design-only; **KILL_OUTCOME zdaj dela → odklenjeno**:

| # | Metrika | Formula v0 | Podatki | Ocena |
|---|---|---|---|---|
| C1 | **KROGT** (ET-jeva KAST/KOST) — % rund s Kill/Revive/Objective/Gib/Traded prispevkom | krogt = rounds_with_any(K,R,O,G,T) / rounds_played | pcs + kill_outcome + revive + objective_run + trade_event | 🟢 service-only |
| C2 | **TDS** — Team Denial Score: efektivno odvzet čas nasprotniku / trajanje runde | Σ denied_ms (kill_outcome: dead→respawn, gib→+penalty) / round_ms | kill_outcome + spawn_timing | 🟢 service-only |
| C3 | **EIS** — Elimination Impact Score (kontekstualni kill) | kill × f(spawn_timer_remaining) × g(alive_diff) × h(gib?) — poravnano z Leetify Δwin-prob filozofijo | kill_outcome + spawn_timing + alive_count (Oksii polja ŽE v DB) | 🟢 (KIS že blizu — konsolidiraj, ne podvajaj!) |
| C4 | **MER** — Medic Efficiency: revive utilization + clutch revives | revive_value = spawn_timer_saved_ms; clutch = revive ko alive_diff<0 | proximity_revive + spawn_timing | 🟡 (revive kontekst delen) |
| C5 | **Stagger debt** — koliko ekipa zapravi z razbitimi spawn valovi | Σ (solo-push smrti v tuji wave fazi) → "dolg" v sekundah | spawn_timing + team_cohesion + kill_outcome | 🟡 (plan §Wave Fight Ledger v0) |
| C6 | **Objective Pressure Seconds** — realen pritisk na cilj vs prazno gibanje | sekunde znotraj r radija cilja z živim carrier/engi namenom | team_push, carrier_event, objective coords | 🟡 |
| C7 | **Player DNA** (4 osi) — fingerprint stila: Aggro/Anchor × Solo/Pack × Obj/Frag × Early/Late | percentili iz: avg dist do sovražnika, cohesion share, obj events share, kill-time razporeditev | tracks, cohesion, objective_run, kill čas | 🟡 (samo opisno, brez "boljši/slabši"!) ✋ |
| C8 | **Aim fingerprint v2** — lock-time + time-to-target iz aim_lock (zdaj ŽIVO) | median lock_ms, locks/min, lock→kill konverzija | aim_lock (6.9k in raste) + shot_fired | 🟡 (kartica "stil", NE "aim grade" — plan anti-tryhard) ✋ |

> **Opozorilo (HLTV nauk):** EIS/KIS/impact so sorodne ideje — pred novo formulo konsolidirati
> s KIS v2 in ET Rating "impact" faktorjem, sicer dobimo 3 rahlo različne "kill vrednosti"
> (isti problem kot session scoring divergence). En kanoničen "kill value" service.

### D. Live layer (zadnje — šele ko so derivati zaupanja vredni)

| # | Ideja | Ocena |
|---|---|---|
| D1 | Live Director — en stavek na Tonight ("Team B drži objective room, chase znotraj 30 % comeback okna") | 🟡 čaka C5/C6 zaupanje |
| D2 | Pressure pulse meter | 🔴 odloži |

---

## 4. Predlagani vrstni red (prvi trije rezi)

Po planovi prioritizaciji (story → map → identity → live) in cost/value:

1. **A1 + A3: Session moments + invisible-value stavki** — 🟢 vse obstaja (detektorji, 4 endpointi, Story stran); samo selekcija + copy. Takojšnja vidna vrednost za VSE igralce.
2. **B1: "Where pushes die" map panel** — 🟡 prvi vizualni proximity produkt; podatki (team_push 60k) + render infra (map_transforms, heatmap koda) obstajata; nova je le agregacija failed-push → coords.
3. **C1 + C2: KROGT + TDS service** — 🟢 čisti SQL/service, brez UI tveganja; najprej **backtest** (Phase 0 stil: zadnjih 20–30 sej, ročni pregled), potem šele panel. KROGT je ET-jev KAST — profi standard, razumljiv vsem.

Vzporedno (data-quality, cenovno nizko): orphan round_id sanacija (shot_fired 7,7 %) — dvigne zaupanje vseh zgornjih.

## 5. Backtest pristop (obvezno pred UI — plan Phase 0)

- skripta `scripts/backtest_proximity_metrics.py` (read-only): za zadnjih 20–30 sej izračunaj C1/C2 (+ B1 agregat) → CSV/markdown izpis
- ročni pregled z ownerjem: ali se KROGT/TDS ujemata s spominom ("kdo je bil ta večer koristen")?
- tone check: ali je spodnja polovica igralcev še vedno pozitivno opisljiva? (friendship-safe)
- šele po potrditvi: service + panel (feature flag, default off)

## 6. Kaj NE delati (potrjeni anti-cilji)

- ne "aim grade" / "worst player" / javni negativni okvirji (plan §What not to copy)
- ne 12 live panelov; en stavek naenkrat
- ne nova "kill value" formula brez konsolidacije s KIS/impact
- ne comm_events/fireteam obljube (engine limit, koš D)
- ne React build za nove površine — legacy JS je kanon (route-registry mode=LEGACY)

## Viri

- Interni: `docs/SLOMIX_GOOD_NIGHT_ENGINE_PLAN_2026-06-28.md` (opportunity atlas, algorithm families, prioritizacija), `docs/PROXIMITY_GAP_ANALYSIS_2026-06.md`, `docs/PROXIMITY_SMART_SCORING_DESIGN.md`, memory `smart_scoring_design`, `proximity_map_viz_vision`, `user_vision_invisible_value`
- Zunanji: [Leetify Rating explained](https://leetify.com/blog/leetify-rating-explained/) · [HLTV Rating 3.0](https://www.hltv.org/news/42485/introducing-rating-30) · [Strava Segments](https://support.strava.com/hc/en-us/articles/216918167-Strava-Segments) · [Scope.gg](https://scope.gg/) · [CS Demo Manager](https://cs-demo-manager.com/) · [OpenSkill paper](https://arxiv.org/abs/2401.05451)
