# Slomix — celovit pregled zadnjih 20 dni (2026-06-13 → 2026-07-03)

> **Metoda:** git/PR arheologija (#389–#431), branje vseh vizijskih dokumentov, križna verifikacija
> obeh globokih auditov (Wave 1 + Wave 2) proti aktualni kodi, **read-only preverbe dev IN prod**
> (psql, verify_post_deploy, SSH), ciljani online research profi prakse. Vsaka trditev ima dokaz.

---

## TL;DR

**Zadnjih 20 dni je bil najproduktivnejši mesec projekta**: 5 sprintov (S3–S7) + betting +
dva globoka audita s sanacijo + deploy-hardening + go-live 1.20/1.21 + Form feature. Vizija je
**konsistentna in se je poglobila** (VISION_2026 → Good Night Engine). Kritičnih napak nismo
našli; **vse HIGH/MED audit najdbe so potrjeno popravljene v kodi**, produkcija je zdrava
(verify ALL GREEN). Ostaja pa **6 konkretnih odprtih postavk** (spodaj, vse z rešitvami) in
2 dokumentacijski luknji: **165 KB krovna vizija sploh še ni v gitu** in README diff čaka.
Proximity smer je zdaj konkretizirana v `PROXIMITY_IDEAS_2026-07.md` (katalog s formulami).

---

## 1. Kronologija — kaj vse smo naredili

| Sklop | PR-ji | Vsebina |
|---|---|---|
| **S3 VEČER** | #389 | peer-voted MVP, weekly challenge, lobby "need N more", captain draft |
| **S4 TEKMA** | #391 | quarterly seasons, HoF awards, **parimutuel betting**, per-map "segments" rekordi |
| **S5 IDENTITETA** | #395 | profil = kariera: identity strip, archetype, focus line, duo synergy, mobile nav |
| **S6 SPOMIN** | #397 | On This Day, konsolidiran Record Book, Slomix Wrapped |
| **S7 LIVE** | #398, #402 | Tonight hub: logični-team score, pulse, momentum, hold-probability, R2 chase |
| **Varnost/kvaliteta** | #399, #413 | uploads CSRF, CVE bumpi, pip-audit+bandit CI gate |
| **Deep audit** | Wave 1 (06-27, 27 najdb) + Wave 2 (06-29, 31 najdb) | 49+66 agentov, adversarialna verifikacija |
| **Sanacija** | #403, #405, #409 | aim-lock inflacija, bot-polluted awards, prox scope, orphan R2, a11y, timing mixin |
| **Deploy hardening** | #407, #411 | React build ob deployu, atomic swap, SHA cache-bust, retry panel |
| **Betting dozorel** | #406, #414, #419 | roster-bound settle, auto-open, auto-settle, hindsight guard |
| **Go-live** | #412, čeklista 06-30 | backup/verify/backfill skripte; **prod 1.20→1.21 (2026-07-02), verify ALL GREEN** |
| **Form** | #428, #430 | Form stran + **composite Form Index** (rank-vs-self, proximity impact faktor) |
| **Perf/DB** | #417, #421 | micro-perf sweep, bootstrap DDL drift guard |

## 2. Vizija — je konsistentna?

**Da, in se krepi.** Severnica "večer je produkt, website je spomin" (VISION_2026, 06-11) je
ostala nespremenjena skozi vseh 7 sprintov; Good Night Engine plan (06-28, 165 KB) jo je
**poglobil za dejansko publiko** (40+/50+ friend group): friendship-safe, rank-vs-self,
"public = positive", anti-ladder. Form Index (#430) je prva realizacija tega plana (družina 2:
Own-Form) — torej izvedba SLEDI planu, ne obratno. Nobene kontradikcije med dokumenti nismo
našli; edina "drift" točka je README (posodobitev pripravljena, necommitana).

⚠️ **Operativno tveganje:** krovni plan `SLOMIX_GOOD_NIGHT_ENGINE_PLAN_2026-06-28.md` je
untracked — en `rm -rf` od izgube. → commit (glej §6, postavka 0).

## 3. Korektnost — audit status (križno preverjeno v kodi 2026-07-03)

### HIGH/MED — vse popravljeno ✅
| Najdba | Dokaz popravka |
|---|---|
| W1 HIGH aim-lock duration inflacija (Lua flush) | prod: max duration 51,2 s, 0 vrstic >60 s |
| W1 MED narrative baseline kontaminacija | `narrative.py:410` — `before_session_id=before_gsid` |
| W1 MED season awards bot pollution | `season_awards_service.py:22-29` — skupni OMNIBOT/[BOT] predikat |
| W1 MED Tonight double-fullhold | `players_router.py:387-391` — draw, 1 pt vsakemu |
| W1 MED parimutuel settle binding | migracija 011 na prod ✅ (team_a/b_guids stolpca obstajata) |
| W1 MED betting hindsight | `bets_router.py:242-247` cutoff + guard prek session_results |
| W1 bait_score coverage bias | `players_profile_router.py:271-286` — ista proximity populacija |
| W2-01 HIGH `!last_session maps` crash | `session_view_handlers.py:871-901` — `.format()` prisoten |
| W2-06 winner_team invert (sessions.js) | `sessions.js:1469` — komentar + pravilen mapping |
| W2-07 BOX orphan/dup R2 | `box_scoring_service.py:236,254` — eksplicitno obravnavano |
| W2-08 skill rating round_date grain | `skill_rating_service.py:477-483` — gsid mapping |
| Codex prox-scores scope gap | verify_post_deploy: "scope filters results ✅" (prod) |

### Še odprto (LOW razred + operativa) — glej §6 za rešitve
- On-This-Day grupira po datumu, ne gaming_session_id (`on_this_day_service.py:60`)
- MAP_IMAGE_MAP + helperji še vedno ×3 JS datoteke (W2-22/26/27)
- prod: **42 orphan R2 rund še valid** (backfill A5 `--apply` ni bil pognan)
- betting auto-open ne nastavi `closes_at` (cutoff pade na "rezultat obstaja" guard)
- Wave 2 Val B/C/D delno (mixin ✅, a11y del ✅; dedup JS in dual-frontend odločitev odprta)

### Sveže preverbe (dev+prod, 2026-07-03)
- prod = v1.21.0, slomix-bot + slomix-web active; #430 composite Form še NI na prod (čaka release 1.22.0, PR #431 odprt) — **naslednji deploy = 1.22.0**
- verify_post_deploy proti slomix.fyi: **ALL GREEN** (modern assets, Tonight, betting, prox scope)
- aim_lock živ in ČIST na obeh (6.9k vrstic, clamp deluje); shot_fired živ
- betting: prod 0 marketov (deploy 07-02 > zadnja seja 06-30 → auto-open še netestiran v živo; **prvi pravi test = naslednji igralni večer**); dev ima 1 star testni market (06-13, brez session_date) — pospraviti
- testi: 363 form/movers/composite testov passed
- ⚠️ dev backend na :8000 teče **staro kodo** (movers vrača pre-#428 obliko) — restart ob priložnosti (nisem restartal brez vprašanja)

## 4. Primerjava s profi prakso ("kako to delajo profiji")

| Področje | Profi | Mi | Verdikt |
|---|---|---|---|
| Kontekstualna vrednost killa | [Leetify](https://leetify.com/blog/leetify-rating-explained/) Δwin-prob (ekonomija, živi, trade); [HLTV 3.0](https://www.hltv.org/news/42485/introducing-rating-30) Round Swing | KIS v2 (health/alive/reinf multiplierji, soft cap) | ✅ ista filozofija, prilagojena ET |
| Composite rating balans | HLTV je moral Round Swing **rebalansirati** (preveč dominiral) | Form Index: clamp [0.4, 2.5] + renormalizacija uteži | ✅ pravi instinkt; **backtest uteži** ob prvih živih podatkih |
| Prikaz | Leetify bell-curve pasovi, ne surove številke | verdicts/labels ("nad svojim običajnim") | ✅ + naša friendship-safe nadgradnja |
| Osebni napredek | [Strava](https://support.strava.com/hc/en-us/articles/216918167-Strava-Segments): lokalni segmenti, zasebni PR-ji | per-map segments (S4), Form vs lastna baseline | ✅ validirana smer |
| Casual vs power-user | [Scope.gg](https://scope.gg/) preprost / [CSDM](https://cs-demo-manager.com/) globok | story-izvlečki za vse + surovi proximity za power userje | ✅ dvo-površinska strategija potrjena |
| Team balans | [OpenSkill](https://arxiv.org/abs/2401.05451) Bayes + negotovost | planiran friendship-safe balancer (stomp-risk, manual override) | 🟡 še ne zgrajen; matematika plana je skladna |
| Parimutuel integriteta | cutoff PRED dogodkom, hard lock | guard šele ob rezultatu; `closes_at` se ne nastavlja | 🟡 glej §6.4 |

**Kje namerno odstopamo (upravičeno):** brez zero-sum ratinga, brez globalne lestvice kot
homepage — publika je friend group, ne ladder. To je dokumentirana odločitev, ne napaka.

## 5. Proximity — skriti adut (poseben sklop)

Celoten katalog: **`docs/research/PROXIMITY_IDEAS_2026-07.md`**. Bistvo:
- podatki in cevovod so bogati in zdravi (81 endpointov, aim_lock zdaj živ);
  problem je 100 % **produkt/prikaz**, ne zajem
- ideje OBSTAJAJO (Good Night atlas: 14 big bets + prioritizacija) — manjkala je konsolidacija
  in data-ready ocena → zdaj narejena
- **prvi trije rezi:** ① session moments + invisible-value stavki (vse 🟢 obstaja),
  ② "where pushes die" map overlay (podatki+render infra obstajata),
  ③ KROGT + TDS formuli (KILL_OUTCOME dela → odklenjeno; najprej backtest)
- pravilo: pred vsakim UI → Phase 0 backtest + owner tone review

## 6. Odprti problemi → rešitve

**0. Vizija ni v gitu** → docs PR: `SLOMIX_GOOD_NIGHT_ENGINE_PLAN` + README (+ ta dva dokumenta). *(v teku — glej PR)*

**1. Session scoring divergence** (bot 2-4 vs BOX 3-7 za isto sejo; per-map zmagovalci OK)
→ **En kanoničen scoring service**: BOX (`box_scoring_service.py`, Oksii-style, zdaj še orphan-R2 odporen) postane edini vir; bot `!last_session` in web `get_session_score` ga kličeta (shared lib ali interni API). Regression test: vsi trije surface-i == isti seštevek. Owner je potrdil "vsak escape je mapa zase" → map-count tally, brez serijske agregacije. Effort: ~1 PR.

**2. is_bot_round gap** (test runde dobijo is_valid=false ročno; upstream detekcija manjka)
→ Parser ob importu: če >50 % igralcev matcha `OMNIBOT%`/`[BOT]%` → `is_bot_round=true` (+ backfill za zgodovino). Per-query OMNIBOT filtri ostanejo kot defense-in-depth (audit je pokazal, da so edina zanesljiva zaščita). Effort: majhen PR + backfill dry-run.

**3. UTC-vs-CET kontradikcija** (`round_linker.py` "UTC prod" vs `ultimate_bot.py` "both CET")
→ Ena konstanta (npr. `bot/core/time_constants.py: SERVER_TZ`), preveri dejanski TZ obeh strojev (`timedatectl`), popravi napačni komentar, DTZ005 mesta postopoma nanjo. Effort: majhen PR.

**4. Betting `closes_at` ni nastavljen** ob auto-open
→ Odločitev ownerja: (a) živo stavljenje med večerom je FEATURE (bench se vključuje) → potem samo dokumentiraj + obdrži result-guard; ali (b) profi cutoff: auto-open nastavi `closes_at = konec 1. mape` (stave le pred/na začetku večera). Priporočam (b) zaradi Oracle award integritete. Effort: nekaj vrstic v `bets_lifecycle.py`.

**5. Prod: 42 orphan R2 še valid** (A5 backfill ni bil pognan)
→ Owner-gated: `./scripts/db_backup.sh` → `python -m scripts.backfill_orphan_r2` (dry-run pregled) → `--apply` na prod. Enako `backfill_aim_lock_clamp` je po podatkih že čist (0 vrstic >60 s) → verjetno ni potreben, dry-run potrdi.

**6. On-This-Day date-grain** → GROUP BY gaming_session_id; če je na datum več sej, prikaži največjo ali obe ločeno. Effort: trivialen.

**7. JS dedup (W2-22/26/27)** → `website/js/lib/map-assets.js` (MAP_IMAGE_MAP + mapImageFor + formatDuration…), import v sessions/session-detail/sessions2. Effort: majhen PR, nizko tveganje.

**8. Dual-frontend dolg** (~10k LOC nedosegljivega Reacta) → po #407/#411 modern route delujejo; priporočilo: **obdrži 4 modern route** (zdaj build ob deployu), **arhiviraj ~21 nedosegljivih React strani** (git mv v `website/frontend/archive/` ali izbris — git zgodovina ostane). Owner odloči; ne blokira ničesar.

**9. Dev okolje:** star testni market (id=1) pobriši; dev backend restart za novo Form kodo (ob priložnosti).

## 7. Vprašalnik za ownerja (odklene naslednjo fazo)

Iz Good Night plana (§Open questions) + operativa:
1. Jezik copy-ja: slovenščina, angleščina ali mešan Discord sleng?
2. Kako "goofy" so lahko labeli? ("Kava aim", "Late chaos", "Old reliable duo")
3. Focus lines (negativna diagnostika): privat-only, opt-in ali owner-only?
4. Memory engine: dnevno ali samo ob močnem kandidatu? (plan priporoča: samo močan)
5. Katere statistike so off-limits za javno negativno framanje?
6. Team suggestions: upoštevati voice/social preference?
7. Betting cutoff: živo stavljenje med večerom (a) ali cutoff po 1. mapi (b)? (§6.4)
8. Proximity prva rezina: potrjuješ vrstni red ①moments ②where-pushes-die ③KROGT/TDS?

## 8. Priporočen naslednji sprint (predlog)

1. **Housekeeping PR** (ta teden): vizija v git + README + §6.2/3/6/7 mikro-fixi (en bundled PR po feedback_bundle_small_prs)
2. **Scoring poenotenje** (§6.1) — največji trust-win pred novimi featurji
3. **Phase 0 backtest** (Good Night Index + KROGT/TDS nad zadnjimi 20–30 sejami, read-only skripta + owner review) — vrata v Good Night fazo 1 in proximity rezino ③
4. Ob naslednjem igralnem večeru: opazuj **prvi živi auto-open/auto-settle** betting cikel (prod še ni imel priložnosti)

---
*Pripravil: Claude (Fable 5), 2026-07-03. Vse preverbe read-only; brez sprememb runtime kode.*
