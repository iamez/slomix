# HANDOFF — Fable → naslednji model (2026-09-02)

Pisano ob koncu Fable seje (1.–2. 9. 2026). Vir resnice za načrt je od
zdaj `docs/PLAN.md`; ta datoteka je posnetek predaje.

## 1. Trenutni plan in pozicija

Glej `docs/PLAN.md`. Kratko: faza 5 nove SPA skoraj zaključena — po #881
ostaneta rezini »player dodatki« (4 poti, oblike že vzorčene) in »map
overlayi« (7 poti; `player-aim` zahteva `map_name`, sicer 400). Nato
spider-web follow-upi, faza 6, faza 7, ultra pregled. Prod zamrznjen na
v1.39.0. Vzporedno: preiskava laga na puranu — watcher v6.12 živ, naslednji
večer igre je meritev; Lua optimizacijo koordinira sestrska seja.

## 2a. Narejeno IN verificirano (ta seja)

- **PR #873** rezina 6 proximity strani (events/drill-down/dispersion) —
  živ Playwright prelet, 2 posneti obliki drill-downa.
- **PR #874 + #876** tracker v6.12 frame-health watcher — deployan na
  puran, dokazan z induciranim SIGSTOP stallom (`gap=524 self=0`), INIT
  vrstica ob vsakem map loadu, harness v CI (lua5.4 job), mutacije viđene
  pasti. Zbiralnik etconsole loga na sambi (cron */10, stabilna pot IZVEN
  repo checkouta — cron nikoli na pot znotraj checkouta!).
- **PR #877** player profil + migracija 080 (GIN jsonb_path_ops):
  hrbtenica 3,5 s toplo → 9 ms; ekvivalenca predikatov dokazana na živih
  podatkih PRED prepisom (2046=2046, 3429=3429).
- **PR #878** team comparison; **#879** replay (unija 4 tipov dogodkov,
  404=odsotnost); **#880** spider-web SW-1 (POV strežniško + assertano na
  žici; ura = unija TREH oblik — `own_hud` ujel posneti fixture; withheld
  allowlist key-exact).
- **v1.44.0 izrezana** (#875; REL-01 config z 080 in ownership opombo).
- Ratcheti: endpoint gap 74→57, inventory pending 33→11, vse spremembe
  z imenovano razliko v testih.

## 2b. Narejeno, a NEVERIFICIRANO (čaka dokaz)

- **PR #881** (outcome instrumenti, 8 panelov) — v merge ciklu; popravek
  enot (18 % ≠ 1.800 %) potisnjen, čaka zelena vrata.
- **Watcher meritev**: instrument živ in dokazan, a PRVI PRAVI VEČER IGRE
  še ni bil izmerjen — `frame_health.log` po naslednji seji je tisti dokaz,
  ki loči hipotezi (velik self = naša Lua; velik gap + majhen self = host).
- Zbiralnik `frame_health` na sambo: cron vpisan, en uspešen prenos; še
  brez večdnevnega teka.

## 3. Odprte odločitve / vprašanja (ownerjeve)

- puranov cron `0 20 * * * kill $(pidof etlded)` — vrže igralce sredi
  igre; pogojni kill ali prestavitev na jutro.
- `scripts/local_et_setup.sh` P1 — lokalni testni strežnik podeduje
  produkcijski webhook (pošilja v pravi Discord kanal).
- hosting ticket za LXC contention, ČE watcher potrdi populacijo B.
- deploy nove strani na produkcijo: šele po ultra pregledu + 1–2 tedna
  teka na dev (ownerjeva beseda 2026-08-28).

## 4. Ideje in tehnični dolg iz te seje, ki NISO bili nikjer zapisani

Preneseno v `docs/BACKLOG.md` (batch write bursta; cache sv_maxclients;
združitev cohesion zank; webhook io.popen gate; replay playback canvas;
kill-outcomes events seznam; spider-web beliefs + manjkajoči mesh za
etl_supply; weapon_breakdown pod player filtrom; past zastarelega
generiranega openapi.d.ts). Dodatno, vredno vedeti:

- ⛔ Razredi napak, ki so se ta teden ponavljali in jih testi zdaj lovijo:
  (a) enota vrednosti je del oblike (odstotek proti frakciji — 2×);
  (b) JSON import ne more držati diskriminirane unije compile-time →
  runtime preverba, ki lahko pade; (c) fixture ne more pasti na vrednosti,
  ki je ne vsebuje → izberi posnetek, ki vejo NOSI (runda 11344 = vsi 4
  tipi; event 306062 = attackers niz z vsebino).
- Meritve pred risanjem: profile 26 s hladno je bila najdba, ne dana
  stvar; EXPLAIN ANALYZE pred vsakim »počasen endpoint«.

## 5. Ad hoc spremembe izven plana (v tej seji)

- **Migracija 080** + containment prepis `kill_query` (meritev jo je
  zahtevala; REL-01 jo je nato formaliziral v v1.44.0 config).
- **Cron na sambi**: zbiralnik etconsole + frame_health (ni bilo v planu;
  nastalo iz izgube loga ob 20:00 killu). Skripta:
  `scripts/pull_puran_console_log.sh`, kopija teče iz
  `~/slomix-server-logs/bin/`.
- **Restart mojega dev uvicorna :8056** (večkrat, za sveže gradnje) in
  `npm run build:app` disciplina (⛔ `npm run build` gradi legacy
  route-host, NE SPA).
- **SIGSTOP/CONT na etlded** (prazen strežnik, 0,4–0,5 s) kot kontrolirani
  stall za validacijo watcherja.
- **Close+reopen #875** za sprožitev checkov na release veji (release PR
  jih sam ne požene).
- Vpis treh procesnih pravil (PLAN/BACKLOG/commit-po-koraku) v CLAUDE.md
  — ta PR.
