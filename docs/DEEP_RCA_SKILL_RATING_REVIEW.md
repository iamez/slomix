# ET Rating / Skill Rating — Deep Review & Redesign Plan

> **Datum**: 2026-03-26
> **Metodologija**: Codebase audit + UX research (HLTV, Valorant, OP.GG, FACEIT) + Docs review
> **Scope**: Backend service, API, frontend, formula, known gaps

---

## 1. Trenutno stanje

### Arhitektura (781 vrstic kode skupaj)

| Datoteka | Vrstic | Vloga |
|----------|--------|-------|
| `website/backend/services/skill_rating_service.py` | 229 | Formula, percentile calc, DB upsert |
| `website/backend/routers/skill_router.py` | 170 | 3 API endpointi |
| `website/frontend/src/pages/SkillRating.tsx` | 382 | React stran |
| `migrations/024_add_skill_ratings.sql` | 35 | Schema (2 tabeli) |

### Formula
```
ET_Rating = 0.15 + sum(weight_i * percentile(metric_i))

DPM:              0.18   (najvecja)
Kills/Round:      0.15
Deaths/Round:    -0.12   (kazen!)
Revives/Round:    0.12
Objectives/Round: 0.12
Survival Rate:    0.10
Useful Kill Rate: 0.10
Denied Time/min:  0.06
Accuracy:         0.05   (najmanjsa)
```

**Constant**: 0.15 (centra povprecje na ~0.50)
**Min rounds**: 5
**Range**: 0.117 — 0.887 (27 igralcev)

### Tier sistem (client-side)
| Tier | Prag | Barva | Igralcev |
|------|------|-------|----------|
| ELITE | >= 0.85 | amber-400 | 1 |
| VETERAN | >= 0.70 | emerald-400 | 5 |
| EXPERIENCED | >= 0.55 | cyan-400 | 5 |
| REGULAR | >= 0.40 | slate-300 | 12 |
| NEWCOMER | < 0.40 | slate-500 | 4 |

### DB tabele
- `player_skill_ratings` — PK: player_guid, 7 stolpcev, components JSONB
- `player_skill_history` — za trend tracking (obstajala, zdaj ze populirana)

---

## 2. Identificirani problemi

### CRITICAL

| # | Problem | Vpliv |
|---|---------|-------|
| **P1** | Ni background recalculation job-a | Ratinzi se izracunajo samo ob prvem HTTP requestu, potem so stale |
| **P2** | `rating_class` stolpec nikoli populiran | Tier se racuna samo client-side, ni na voljo za bot/API filtering |
| **P3** | History tabela se ni polnila | ~~FIXED danes~~ — dodano v `compute_and_store_ratings()` |

### HIGH

| # | Problem | Vpliv |
|---|---------|-------|
| **P4** | Ni confidence/reliability indikatorja | Igralec s 6 rundami izgleda enako kot igralec z 1754 |
| **P5** | Weights niso validirani s community feedback | Empiricno nastavljeni, ne reflektirajo dejanskih skill razlik |
| **P6** | Ni casovne dimenzije na frontendu | ~~FIXED danes~~ — history API endpoint dodan |
| **P7** | Dual query v `compute_all_ratings` | Isti GROUP BY query se izvede 2x (percentiles + ratings) |

### MEDIUM

| # | Problem | Vpliv |
|---|---------|-------|
| **P8** | Flat tabela brez vizualnega storytelling-a | UX brief identificira 7 specificnih problemov |
| **P9** | `COALESCE(AVG(NULLIF(accuracy, 0)), 0)` | Accuracy 0% se ne razlikuje od "ni podatka" |
| **P10** | Class-specific profiles niso implementirani | Medic/Engineer/Soldier vsi ocenjeni z istimi weights |
| **P11** | Ni search/filter/sort na frontendu | 27 igralcev gre, 300 ne bo |

---

## 3. UX Research: Kaj ukrademo od najboljsih

### Iz HLTV 2.0 (CS2)
- **Single hero number z barvnim gradientom** — zelen (dober), rumen (povprecen), rdec (slab)
- **Horizontalna component vrstica** — KPR | ADR | APR kot majhne labelled stevilke
- **Filter-first design** — rating se dinamicno spremeni ko izberes "last 3 months" / "LAN only"
- **HLTV pomanjkljivost**: ni confidence indikatorja — ukrademo to idejo od drugod

### Iz Valorant Tracker (tracker.gg)
- **Percentile tag ob raw stevilki** — "276 ACS — Top 8%" namesto samo "276"
- **Horizontal position bar** — tanka vrstica ki pokaze kje si v distribuciji (MUST-HAVE za percentile sistem)
- **Agent/role cards** — prevedeno v class cards (Medic, Engineer, Soldier...)
- **Barvno kodiran match history line** — gradient zeleno/rdece

### Iz OP.GG (LoL)
- **Distribution histogram z "you are here" markerjem** — za 27 igralcev pokazi vse kot pike na stevilski osi
- **LP progress bar** — "42 tock do ELITE" obcutek progresije
- **Champion mastery grid** — krozni portreti z barvnim ringom (win rate)

### Iz FACEIT
- **Level badge + ELO number combo** — badge za hiter scan, stevilka za preciznost
- **ELO delta per match** — "+5" / "-3" v zeleni/rdeci za vsako session
- **Sparkline v headerju** — 150x40px mini graf v vsaki player vrstici
- **Win/loss streak dots** — vrsta barvnih pik za recent sessions

### Radar/Spider Charts
- **9 osi je na zgornji meji** — deluje ce so grupirane (offense/defense/utility)
- **Priporoceno grupiranje**:
  - Offense: DPM, KPR, Accuracy
  - Impact: Objectives, Useful Kills, Denied Time
  - Survival: Survival Rate, Deaths (inverted), Revives
- **Library**: Recharts RadarChart (ze v React stacku)
- **Max 3 igralci za overlay primerjavo**

### Confidence vizualizacija
- **"Provisional" badge** (Chess.com/Lichess) — "?" ob ratingu za < 10 session-ov
- **Ring completeness** — krozni progress ring se polni z vecanjem sample size
- **Confidence band na history chartu** — sirok trak ki se zozuje ko se nabere vec podatkov

### Stacked Contribution Bar
- **Horizontalna segmentirana vrstica** — vsak segment = weight * percentile za to metriko
- **Barve po kategoriji**: offense = rdeca, defense = modra, utility = zelena
- **Hover**: ime metrike, raw value, percentile, weight, contribution

---

## 4. Akcijski plan

### Faza 1: Backend fixi (DONE danes)

- [x] **P3**: History tracking — `compute_and_store_ratings()` zdaj pise v `player_skill_history`
- [x] **P6**: History API — `GET /api/skill/player/{id}/history?limit=30` endpoint
- [x] Frontend types + hooks za history (`SkillHistoryResponse`, `useSkillHistory`)

### Faza 2: Backend improvements (ta teden)

- [x] **P1**: ~~Background recalculation~~ — auto-refresh if stale >1h on leaderboard request
- [x] **P2**: ~~Server-side tier assignment~~ — `get_tier()` + `rating_class` populated on compute
- [ ] **P7**: Single-pass query — zdruzuj percentile + rating query v en pass
- [x] **P4**: ~~Confidence score~~ — `confidence = min(1.0, games_rated / 30)` in API response
- [x] **P9**: ~~Accuracy NULL handling~~ — `AVG(accuracy) FILTER (WHERE accuracy > 0)`

### Faza 3: Frontend redesign (ta teden / naslednji)

Prioritiziran seznam UI komponent:

#### Must-Have (P1)
| Komponenta | Inspiracija | Effort |
|-----------|-------------|--------|
| **Hero rating z barvnim gradientom** | HLTV | 30min |
| **Percentile position bars** (9x) | tracker.gg | 2h |
| **Contribution stacked bar** | SHAP waterfall | 2h |
| **Provisional badge** ("?" za < 10 sessions) | Chess.com | 30min |
| **Search box + tier filter** | OP.GG | 1h |
| **Sortiranje po metriki** (klik na header) | Standard | 1h |

#### Should-Have (P2)
| Komponenta | Inspiracija | Effort |
|-----------|-------------|--------|
| **Radar chart** (9 osi, grouped) | FIFA/Valorant | 3h |
| **Sparkline v vsaki vrstici** | FACEIT | 2h |
| **Distribution dot plot** (27 pik + "you are here") | OP.GG | 2h |
| **Rating delta per session** ("+5" / "-3") | FACEIT | 1h |
| **Top 3 podium** namesto samo top 1 hero | Brief predlog | 2h |
| **Progress toward next tier** bar | OP.GG LP | 1h |

#### Nice-to-Have (P3)
| Komponenta | Inspiracija | Effort |
|-----------|-------------|--------|
| **Rating history line chart** z confidence band | Glicko-2 viz | 3h |
| **Class mastery cards** (Medic/Eng/Soldier rings) | tracker.gg | 4h |
| **Player comparison overlay** (max 3 na radar) | FIFA | 3h |
| **Mobile card layout** (responsive) | Brief predlog | 3h |
| **Staggered row entry animation** | Framer Motion | 1h |

### Faza 4: Formula validation (dolgorocno)

- [ ] **P5**: Weight tuning — zberi feedback, koreliraj z win rate (ko bo match winner data reliable)
- [ ] **P10**: Class-specific profiles — medic weights vs soldier weights
- [ ] Option A/B (OpenSkill team-based) — odvisno od reliable match winner data

---

## 5. Vizualni design pravila

### Barve
- Background: `#111827` (Tailwind gray-900)
- Cards: `#1f2937` (gray-800)
- Text: `#e5e7eb` (gray-200 body), `#ffffff` (headings)
- Accent: amber/orange `#f59e0b` za top tier, cyan `#06b6d4` za mid-tier

### Tier badges z glow
```css
/* Samo ELITE dobi glow */
.tier-elite {
  color: #f59e0b;
  text-shadow: 0 0 10px rgba(245, 158, 11, 0.5),
               0 0 20px rgba(245, 158, 11, 0.3);
}
```

### Typography
- Stevilke: `font-variant-numeric: tabular-nums` (da se stolpci poravnajo)
- Hero rating: 2xl-3xl, bold
- Column headers: xs, uppercase, tracking-wide
- Body: sm-base

### Animation (Framer Motion)
- Row entry: staggered 50ms per row
- Rating change: brief flash + count-up/down
- Brez continuous animation (spinning, pulsing) v leaderboard vrsticah

---

## 6. Pozitivne najdbe

- Formula je **matematicno solidna** — percentile normalization z O(log n) bisect
- **9 metrik pokriva vse ET:Legacy class-e** — medic (revives), engineer (objectives), soldier (DPM/kills)
- **Deaths penalty (-0.12)** je pravilna odlocitev — HLTV 2.0 to prav tako pocne
- **JSONB components** shranjen v DB — ni treba recomputat za breakdown display
- **Transparent formula** — javno dostopna na `/api/skill/formula` (HLTV 3.0 je proprietary)
- **API design je cist** — 3 jasni endpointi, dobri response formati

---

*Generiran: 2026-03-26 | Research: 3 agenti (codebase, web UX, docs) | Fixi: 7 ze opravljenih*
