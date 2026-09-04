# HANDOFF — 2026-09-04 (Fable 5.1 → naslednja seja/model)

## Kje smo (verificirano)
- **Stats 2.0 R1–R5 KONČAN** (#897, #898, #899, #902, #903 na mainu): ena
  Sessions stran, session stran s 5 zavihki, basics/awards, razširjena vrstica
  igralca. Dev :8000 rabi restart (ownerjeva poteza); moj uvicorn :8056 teče
  na veji `feat/bot-twins-route-distinctiveness` (koda = main + skripta).
- **Frame-health v6.13** v vseh 6 Lua modulih: mergan (#905), **deployan na
  puran** (dokazano: 6× `FH init … mod=`), dva bot testa izmerjena
  (`scripts/frame_health_report.py`); zbiralnik vsakih 10 min v
  `~/slomix-server-logs/`. Odprt sum: 9 s `self` trackerja ob 0 igralcih
  (2. 9.) — ob ponovitvi ga `FM top=` poimenuje; nevihta praznega strežnika =
  gostitelj (residual).
- **Match moments**: r. 1 `escort_mover` (#908) + r. 5 `types=` filter in
  panel »objective escorts« (#909) mergani.
- **Docs 19/20/21/22** (lokalno v `docs/design/`, NE v repu): per-user pogled,
  match moments, runtime v2 (šele po ultra pregledu), digitalni dvojčki botov.

## V teku (NEZAKLJUČENO) — veja `feat/bot-twins-route-distinctiveness`
- `scripts/backtest_route_distinctiveness.py` + `tests/unit/test_route_distinctiveness.py`
  (9 testov zeleno, 5 mutacij videnih pasti) = doc 22 rezina 1: ali se poti
  igralcev na isti mapi razlikujejo (JS divergenca self-split proti cross,
  druga pot nearest-point, kontrola s premešanimi oznakami, dwell).
- **Korpusni tek še ni dal številk** (ob predaji je tekel v ozadju; izpis v
  scratchpadu seje je začasen). Ponovi:
  `venv/bin/python scripts/backtest_route_distinctiveness.py --json /tmp/route_distinct.json`
  (read-only, ~10+ min; 1-sekundni vzorci). Nato: številke v doc 22 §5/§6 in
  PLAN (proga doc 22, rezina 1), PR, ownerjev merge. Odločitev za ownerja:
  ali gre v rezino 2 (dwell metrika) in 3 (per-bot `.gm` profil).

## Odprte ownerjeve odločitve
- Vrstni red po rezini 1: doc 19 (per-user pogled) ali moments r. 2 (Lua časi
  moverja) ali dvojčki r. 2/3.
- Doc 21 (runtime v2) šele po ultra pregledu nove strani; ultra pregled še ni
  sprožen (rabi pregledni PR z bazo na začetku faze 0).
- BACKLOG: `/detail` brez `response_model`; tank `total_distance` ~0 v
  112/128 rund (meritev premika tanka v Lua); moments brez besednjaka
  »unavailable«.

## Sestrska seja
Dela v ločenem worktreeju `/home/samba/share/slomix-arena` (1v1 arena Lua,
`/api/diagnostics`); merge okna usklajujeva prek sporočil. Moje odgovore na
njena Lua vprašanja (respawn brez vnosa = `g_forcerespawn -1` + gib obeh prek
`et.G_Damage`, hook `et_ClientSpawn` teče PO ščitu, vali naključno zamaknjeni,
attacker 1022 za statistiko) je dobila 4. 9.

## Pravila, ki so se danes potrdila
- Cwd past: `cd website/frontend && git add website/...` pade — vedno iz korena.
- Test stub po podnizu URL-ja: `/detail` je ujel `/kill-impact/details` → ujemaj
  konec poti.
- Sestrska seja v istem drevesu = nevarnost; ločen worktree.
