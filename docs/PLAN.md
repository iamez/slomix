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

**Zadnja posodobitev:** 2026-09-03 (Fable 5.1, R2 v delu)

Owner (3. 9.): »Sessions« + »Sessions 2.0« → ENA stran; seznam po datumu in
id-ju s thumbnailom; ob kliku najprej jedrnat summary (basics tabela +
tekstovne nagrade v gibhub slogu), podrobnosti za klikanje do power userja.
Dizajn: `docs/design/18_STATS_2_0_SESSIONS.md` (lokalno). Odločitve: vzdevki
nagrad (tabela v backendu) · Smart Stats = zavihek session strani · ACC =
hits/shots lahkih orožij.

| rezina | obseg | stanje |
|---|---|---|
| R1 | en arhiv `/sessions` z levelshoti, `#id`, BOX, mape, »one half missing«; `/sessions2` redirect; podnav brez podvojitve | #897 merged |
| R2 | backend `GET /stats/session/{id}/basics` + `/awards` (response_model, vrata `/detail` + brez botov, KIS null=not covered, pravila agregacije nagrad z vzdevki, korpusni tek `scripts/audit_session_basics.py`) | ta veja |
| R3 | summary plast 1: `DataTable` basics (TP, denied %, DPM, KIS, KIS/min, DMG, DMR, ACC, HS %, GIBS, UK, SK, FSK, REV, REV'D) + awards | — |
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

## Odprte ownerjeve odločitve

- puranov cron `0 20 * * * kill etlded` (vrže igralce sredi igre) — pogojni
  kill ali prestavitev.
- `scripts/local_et_setup.sh` P1: produkcijski webhook v lokalnem strežniku.
- hosting ticket, če watcher potrdi populacijo B (host stall).
