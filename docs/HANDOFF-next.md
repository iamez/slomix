# HANDOFF — Fable → naslednji model (2026-09-02, popoldne)

Pisano ob menjavi CLI + modela. Ta datoteka NADOMEŠČA `docs/HANDOFF-fable.md`
(tisti je posnetek jutranje predaje in je zastarel za ~15 merganih PR-jev).
Vir resnice za načrt je `docs/PLAN.md` (na mainu, svež z #890). Pravila in
pasti nosi lokalni agentov memory (`~/.claude/projects/…/memory/MEMORY.md`, ni v repu; v sejo se naloži samodejno) — ta datoteka je
posnetek POZICIJE.

## 1. Trenutni plan in pozicija

`docs/PLAN.md` na mainu. Kratko: **faza 5 nove SPA ZAKLJUČENA** (inventory
pending 0), **faza 6 ima štiri mergane rezine**: availability r. 1 (#887),
uploads r. 1 (#888), live (#889), greatshot (#890). Endpoint gap = **8
pravih poti** (`tests/data/endpoint_gap.txt`; 74 ob začetku 1. 9.).

Naslednje delo (vrstni red iz PLAN.md):
1. Faza 6 preostanek: availability r. 2 (linked formi:
   settings/subscriptions/link-token/preview/campaigns, betting UI),
   uploads r. 2 (resumable, delete), preostale poti: `/api/bets`,
   `/api/bets/market`, `/api/diagnostics`, `/api/stats/sessions` (zapre se
   šele z upokojitvijo legacy sessions.js — NE briši vrstice),
   `/api/uploads/resumable` (v `endpoint_required_extra.txt` — zahteva
   TOČEN klic).
2. Spider-web follow-upi (za paritetno fazo 6).
3. Faza 7: wrapped, compare, Clips, upokojitev začasne /rounds.
4. Ultra pregled (owner-triggered) → 1–2 tedna teka na dev → pogovor o
   produkciji. Prod ZAMRZNJEN na v1.39.0.

## 2a. Narejeno IN verificirano (zadnji del seje, 2. 9. popoldne)

- **#889 live**: obe review niti POPRAVLJENI (ne zavrnjeni): feed kurzor
  napreduje po pogodbi `seq > since` (kopičenje klientno, kap 200, gap
  nota ob prepisu ringa; sintetični test, ker posneti tihi feed z
  `last_seq 0` kurzorja ne more preizkusiti); štirje zgodovinski hooki
  dobili `refetchInterval` 60 s, ki so ga komentarji obljubljali. MERGAN.
- **#890 greatshot**: `/app/greatshot` + `/app/greatshot/demo/:id`;
  `apiUpload` v tipizirani plasti (FormData, brez ročnega Content-Type,
  `pathParams` kot `apiPost`); fixture iz PRAVEGA analiziranega dema
  (etl_adlernest, 9 highlightov, 0 clip povezav — pripeto, ker render job
  ni tekel). Backend: skenerjev `UnsupportedDemoError` zdaj 400 z
  njegovimi besedami; **zavrnitev ne pusti ničesar** — nov
  `_discard_rejected()` v `save_upload` (vsa 4 zavrnitvena mesta, datoteka
  IN mapa), pripeto z dvema »leaves no trace« testoma, oba videna pasti
  pod mutacijo (cmp dokaz); runtime dokaz in-process (junk → 400, 0
  datotek, 0 map). Polling prestavljen iz renderja v `useEffect`. MERGAN.
- Dokazna veriga pred vsakim pushem: typecheck s svežim openapi.d.ts,
  vitest (569), build:app, živ Playwright na :8056, poln pytest (6152).

## 2b. Narejeno, a neverificirano / delno

- **Watcher v6.12 na puranu**: deployan in dokazan s SIGSTOP, a PRAVA
  meritev = naslednji večer igre (`~/.etlegacy/legacy/proximity/
  frame_health.log`, zbiralnik cron vleče v `~/slomix-server-logs/`).
  Loči populacijo A (naš round-end burst) od B (host). Glej memory
  `lag_investigation_2026-09-01.md`.
- Dev CSRF najdba: dovoljeni origini prihajajo iz `website/.env` (NE
  koren `.env`); lokalno dodani :8056 origini — datoteka je gitignorana,
  spremembe NISO v repu in se ob svežem checkoutu ne obnovijo same.

## 3. Odprte odločitve (ownerjeve)

- Puran 20:00 cron kill (najden med lag preiskavo) — ali ga umakniti.
- `local_et_setup.sh` P1 webhook zadeva (sestrska nit).
- Hosting ticket, če meritev potrdi populacijo B (host hitchi).
- Izrez release vlaka **1.45.0 (#882 odprt)** — kdaj.
- Faza 3 časovnih polj (rekonstrukcija zgodovine) — čaka izrecen preklic
  starejše »no backfill« odločitve; načrt v
  `~/.claude/plans/distributed-inventing-fox.md` (sestrin razdelek).

## 4. Ideje / tehnični dolg (nezapisano drugje)

- `MYTHREADS.json` in `scripts/codex_audit_prompt.md`/`run_codex_audit.sh`/
  `check_env.py`/`live_headless_check.py` ležijo untracked v korenu —
  pospraviti (lokalno ali izbrisati), niso za repo.
- **Čiščenje worktreejev = prva naloga nove seje**: 38 worktreejev,
  večina zastarelih (`/home/samba/share/slomix-*` + scratchpad `wt*`).
  Protokol: za VSAKEGA `git -C <wt> status --short` +
  `git -C <wt> ls-files -o --exclude-standard` PRED odstranitvijo;
  ⛔ `tpp`/`tppbf` (scratchpad) sta SESTRINA (#885/#886) — ne dotikaj.
- Greatshot renders: stran linka clipe, a render jobi ne tečejo nikjer —
  fixture jih nima; ko bodo, posnetek z clip_download ≠ null.
- 44 živih review niti na starih merganih PR-jih (memory
  `mechanism_without_a_consumer_2026-09-01.md`) — triaža po tem, ali se
  je datoteka od merga spremenila.

## 5. Ad hoc spremembe izven plana (ta seja)

- `website/backend/services/greatshot_store.py` — `_discard_rejected()`
  (del #890, opisano zgoraj).
- Moj uvicorn na **:8056** (dev, ročno zagnan, nohup — preživi restart
  CLI; preveri `curl 127.0.0.1:8056/api/status`). Restart tega procesa je
  edina izjema od pravila »restart samo owner«.
- Memory: nov zapis `gh_pr_edit_projectcards_break_2026-09-02.md` —
  `gh pr edit` na tem repu TIHO odpove (projectCards deprecation); telo
  PR prek `gh api … --method PATCH`, po editu vedno preveri z
  `gh pr view --json`.

## 6. Operativno za novo sejo

- **`~/slomix-ops/cycle.sh`** — merge-gate cikel (args: PR št., veja,
  squash naslov, pot do body datoteke). Edino nosilno orodje, rešeno iz
  starega scratchpada.
- Stari scratchpad (berljiv, a sejno-specifičen):
  `/tmp/claude-1000/-home-samba-share-slomix-discord/57cfdfc9-736d-47cc-8337-d4c657569cbe/scratchpad/`
  — `gs/` (greatshot posnetki), `body_gs.md`, logi ciklov.
- Rekonstruirani plani: `~/claude-plan-recovery/` (INDEX.md; lokalno, NE
  v repo).
- Sestrska seja: njeni datoteki-področja so `postgresql_database_manager.py`,
  `stats_import_mixin.py`, `tools/slomix_backfill.py`, `scripts/repair_*`,
  `data_plausibility_audit.py`, `docs/KNOWN_ISSUES.md`, alive_pct del
  `sessions_router.py`; njena PR-ja #885/#886.
- Checklist ob zagonu: (1) `git log origin/main -1` vsebuje #890;
  (2) `curl -s 127.0.0.1:8056/api/status` → 200; (3) mergaj PR te
  datoteke; (4) čiščenje worktreejev po protokolu iz §4.
