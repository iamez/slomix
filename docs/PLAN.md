# PLAN — edini vir resnice za tekoči načrt

> Pravilo: ta datoteka se posodobi ob VSAKEM koraku. Nič se ne »dogovori«
> samo v pogovoru. Bereta jo obe seji (in vsak prihodnji model).
> Podrobne raziskovalne zapiske drži lokalno (docs/REPO_BOUNDARY.md);
> tu je samo načrt in pozicija. Repo je javen — brez skrivnosti.
>
> **Sočasnost (več agentov, plan mode):**
> - Plan-mode datoteke (`~/.claude/plans/*.md`) so ZAČASNE in si jih seje
>   DELIJO po slugih — ista datoteka je bila prepisana 3× v dveh dneh
>   (tri različne seje, trije nepovezani načrti). Nikoli niso vir resnice:
>   trajni izid se ob ExitPlanMode PREPIŠE SEM.
> - Ta datoteka se ureja SAMO prek veje+PR (kot vse) — sočasni prepis se
>   pokaže kot git konflikt, ne kot tiha izguba; vsaka verzija je commit.
> - Vsaka delovna proga ima SVOJ razdelek in ureja samo svojega +
>   skupno glavo; razdelki različnih prog se v gitu zlijejo brez konflikta.
> - Vsak razdelek nosi vrstico »Zadnja posodobitev: datum (kdo)«.

**Zadnja posodobitev:** 2026-09-03 (Fable 5.1, uploads rezina 2)

## Proga: nova stran (Fable)

### Kje smo

Nova SPA (website/frontend/src/app) — faza 5 ZAKLJUČENA, faza 6 v teku.
Prod ZAMRZNJEN na v1.39.0 (ownerjeva odločitev 2026-08-28); dev soaka;
deploy NI naloga.

| stanje | vrednost |
|---|---|
| izdana verzija (dev) | v1.44.0 (2026-09-02); vlak 1.45.0 = #882 |
| endpoint gap (H1) | **4** na tej veji (5 na mainu po #894; uploads r. 2 zapre `/api/uploads/resumable`) |
| proximity inventory pending | **0** (#884) |
| zgrajene strani faze 5 | proximity (6 rezin + 8 outcome instrumentov), player profil, team comparison, replay, spider-web SW-1 |
| zgrajene strani faze 6 | availability r. 1 (#887), uploads r. 1 (#888), live (#889, kurzor feeda popravljen po reviewu), greatshot (#890) |
| availability r. 2 (ta veja) | linked formi (settings, kanali prek link-tokena, DELETE), promotions (status+jobs, preview z recipients, schedule), betting (bazen, multiplikator, stava, denarnica; BREZ admin kontrol — owner 2. 9.); fixturi povezane stopnje prek dev sentinela (`scripts/e2e_sentinel_rows.py`) + harness posnetkov |
| uploads r. 2 (ta veja) | upload form (single-shot ≤ 50 MiB z XHR napredkom + cancel; resumable init/PATCH/finalize z 409 resync, HEAD resync, stall guard, abort), delete na detailu (dvostopenjsko); fixturi iz ŽIVEGA kroga s sentinelom (init→PATCH→finalize→detail→DELETE) |
| delovna površina | 2. 9.: 41→4 worktreejev, 400→43 lokalnih vej, #891 mergan; protokol v memory `worktree_cleanup_protocol_2026-09-02.md` |

## Naslednji koraki (vrstni red)

1. **Faza 6 — preostanek**: `/api/diagnostics`; availability rezina 3 = admin market kontrole
   (`/api/bets/market`, settle) — ownerjeva odločitev, kdaj; `/api/bets` in
   `/api/stats/sessions` se zapreta šele z upokojitvijo legacy js.
3. **Spider-web follow-upi** (3D kamera, belief regions, label placement;
   W6) — premaknjeno ZA paritetno fazo 6: polish ne prehiteva paritete
   (razlog zapisan 2. 9.).
4. **Faza 7**: wrapped, compare, Clips, upokojitev začasne /rounds.
5. **Ultra pregled** (owner-triggered) → 1–2 tedna teka na dev → pogovor o
   produkciji.

| ratchet | stanje |
|---|---|
| endpoint gap | 4 na tej veji (5 na mainu; 74 ob začetku 1. 9.) |
| proximity inventory pending | **0** (#884) |

## Proga: Stats 2.0 — ena stran »Stats / Sessions« (Fable 5.1)

**Zadnja posodobitev:** 2026-09-03 (Fable 5.1, R3 v delu)

Owner (3. 9.): »Sessions« + »Sessions 2.0« → ENA stran; seznam po datumu in
id-ju s thumbnailom; ob kliku najprej jedrnat summary (basics tabela +
tekstovne nagrade v gibhub slogu), podrobnosti za klikanje do power userja.
Dizajn: `docs/design/18_STATS_2_0_SESSIONS.md` (lokalno). Odločitve: vzdevki
nagrad (tabela v backendu) · Smart Stats = zavihek session strani · ACC =
hits/shots lahkih orožij.

| rezina | obseg | stanje |
|---|---|---|
| R1 | en arhiv `/sessions` z levelshoti, `#id`, BOX, mape, »one half missing«; `/sessions2` redirect; podnav brez podvojitve | #897 merged |
| R2 | backend `GET /stats/session/{id}/basics` + `/awards` (response_model, vrata `/detail` + brez botov, KIS null=not covered, pravila agregacije nagrad z vzdevki, korpusni tek `scripts/audit_session_basics.py`) | PR #898 |
| R3 | summary: glava z BigScore + trak map z levelshoti + figure; `DataTable` (nov, doc 11) z 16 stolpci in tooltipi; nagrade v stavkih; night score + MVP; ostalih 5 panelov za »more ▸«; Playwright thin = seja 80 | ta veja |
| R4 | zavihki Players 22 · Rounds (retire `/rounds`) · Teamplay · Story (retire `/story`) | — |
| R5 | power user: vrstica igralca ▾, KIS details, povezave | — |

Odprto (owner): FSK prag, potrditev vzdevkov, Charts zavihek.

## Proga: lag na puranu + Lua optimizacija (sestrska seja)

**Zadnja posodobitev:** 2026-09-02 (Fable — predaja koordinacije)

Watcher v6.12 ŽIV na puranu (deployan + dokazan 2. 9.). Naslednji večer
igre = meritev (`~/.etlegacy/legacy/proximity/frame_health.log`; zbiralnik
vleče na sambo). Delitev populacij (sestrska seja): A = round-end burst
(naš), B = med pavzo — ⚠️ »ne more biti naša« pokriva SAMO tracker
(levelTime med pavzo zamrzne); webhookov io.popen sweep teče po os.time()
tudi med pavzo in NI izključen. Razsodi meritev prek `self`. Optimizacija bursta: batch write,
šele PO enem večeru self meritev. Sestrska seja koordinira optimizacijo Lua.

## Proga: časovna polja (Opus 5)

**Zadnja posodobitev:** 2026-09-02 zvečer (Opus 5 — agregatni razred varovala)

Dva ločena hrošča v istem deploy oknu (~20. 3. 2026) sta pustila bazo v
stanju, kjer sta obdobji **nezdružljivi**: staro ima engine alive%, a ~2×
napihnjen mrtvi čas (Lua je limbo čas prištevala znova ob vsakem 5-sekundnem
tiku); novo ima pravilen mrtvi čas, a `time_played_percent` je bil od
2026-04 ničla, ker ga aktivna uvozna pot ni pisala. Ker sta komplementarni,
se da vsako obdobje popraviti iz signala drugega.

| faza | kaj | stanje |
|---|---|---|
| 1 | uvozna pot piše `time_played_percent` + parnostno varovalo piscev | **#885**, zelen, čaka ownerjev merge |
| 2 | backfill `time_played_percent` iz surovih datotek | **#886**, zelen; **IZVEDEN** 2. 9. (8.800 → 13.466 vrstic, +4.666; kontrola proti surovim datotekam 22/22) |
| 3 | rekonstrukcija zgodovinskega `time_dead_minutes` iz engine alive% | ⛔ ownerjeva odločitev; velja SAMO za R1 (R2 gre prek kumulativne TAB[8]); prekliče zapis »owner decision — no backfill« v `docs/KNOWN_ISSUES.md` |
| 4a | per-row varovala v plausibility auditu (4 nova pravila) | **#892**, zelen, čaka merge |
| 4b | agregatni razred (»porazdelitev se je premaknila«) | **ta veja**, 7 trend pravil |
| 5 | zastareli zapisi, ki so to skrivali | **#893**, zelen, čaka merge |

⭐ **Ključna meritev (odklepa fazo 3):** po backfillu `alive_pct_drift` prvič
po 5 mesecih spet deluje — 290 parov, engine 79,3 proti izračunanemu 79,3,
povprečna |razlika| **0,15 o. t.**, le 2 para (0,7 %) nad 2 o. t. To potrjuje
oboje: ALIVE% se premakne zanemarljivo IN formula za staro obdobje drži.

⚠️ **Backfill je treba ponoviti** po mergu #885 IN restartu bota — do takrat
vsak nov uvoz spet piše ničle. Skripta piše samo čez ničle, zato je
ponovitev varna in idempotentna.

⭐⭐ **Razrešeno 3. 9.: »tretja raven« je R2, ne igra.** Ločeno po rundah je
**R1 raven skozi vso predpopravkovo obdobje** (delež mrtvega časa 0,44–0,50),
R2 pa teče pri ~0,22 do 2025-04 in od 2025-05 skoči na R1 raven. Torej
`time_dead_minutes` na R2 vrstici pomeni **eno stvar pred majem 2025 in
drugo po njem** — isti vzorec kot popravek 2026-04, eno rundo globlje.

⭐⭐ **Faza 3 je s tem odločljiva, in odgovor je ločen po rundah:**

| era | runda | n | razred B (baza < 0,9 × rekon) | mediana faktorja |
|---|---|---|---|---|
| zgodnje 2025 | **R1** | 2.708 | **0,15 %** | 2,238 |
| pozno (2025-05..2026-03) | **R1** | 1.724 | **1,28 %** | 2,195 |
| zgodnje 2025 | R2 | 2.596 | **37,1 %** | 1,031 |
| pozno | R2 | 1.693 | 10,0 % | 1,992 |

**R1 = en sam čist mehanizem čez vso ero**, R2 ne. Trije neodvisni razsodniki
(3. 9., razširjeni vzorci):

| razsodnik | pokritost | rekon / razsodnik | baza / razsodnik |
|---|---|---|---|
| izmerjeni dead po popravku (n=4.447, prej 344) | 2026-04→ | R1 **1,0000**, R2 0,9993 | — |
| `round_awards` (endstats.lua, n=126) | 2026-01..03 | R1 **1,0020**, R2 1,0053 | 1,96 / 1,74 |
| `player_track` (proximity, n=888) | 2026-02-11→ | R1 0,9166, R2 0,9335 (metoda vrzeli podceni ~8 %) | 1,94 / 2,00 |

⚠️ **Zunanja razsodnika pokrivata SAMO 2026-01..03** (~2.200 vrstic od 8.700).
Za 2025-01..04 (5.304 vrstic) ni neodvisnega vira — tam stoji rekonstrukcija
na mehanizmu (branje stare Lue) + na tem, da je R1 faktor identičen v obeh
erah (2,238 proti 2,195).

⭐ Kje bi prepis **poslabšal**: proti `player_track` je rekonstrukcija bližja
na **80,7 %** vrstic, baza na 19,3 %; mediana napake pade z **1,125 min na
0,289 min**. Razčlenjeno: pri parih, kjer se kandidata skoraj ne razlikujeta
(≤0,5 min, n=118), je izid vseeno; pri napihnjenih (n=727) rekonstrukcija
zmaga v 83,2 %, pri hudih (n=41) v 97,6 %.

⭐ **Nova najdba 2. 9.:** `revives_given` je 0 na vseh 5.538 vrsticah pred
2025-12 — vsaka vseskozna revive lestvica se tiho začne decembra 2025.

## Odprte ownerjeve odločitve

- puranov cron `0 20 * * * kill etlded` (vrže igralce sredi igre) — pogojni
  kill ali prestavitev.
- `scripts/local_et_setup.sh` P1: produkcijski webhook v lokalnem strežniku.
- hosting ticket, če watcher potrdi populacijo B (host stall).
