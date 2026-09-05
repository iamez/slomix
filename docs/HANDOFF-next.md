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

## Stanje 5. 9. zvečer (Fable 5.1)
- Doc 22 r. 1 (#913) in r. 2 (#914) MERGANI: razločljivost poti (osebnost =
  časovna utež, identifikacija 81–91 %) in camp-profile (peta plošča vlog,
  hold/still). Podrobnosti v PLAN in spominu `camp_metric_is_episodic`.
- **Moments r. 2 v PR #916** (veja `feat/moments-mover-times`): Lua v6.14
  (`first/last_move_time`, `first/last_escort_time`, sekcija
  `VEHICLE_DESTROYED` iz `et_Damage` veje), parser, migracija 082 (na devu
  aplicirana), detektor `first_escort` → `first_move` → `round_end`.
  Živ dokaz na lokalnem ET 2.85 (:27961) z boti; dve pasti odkriti v živo
  (supply truck se sam odpelje pri 0,6 s; goldrush tank začne pokvarjen →
  fantomski `destroyed_count` v korpusu). Po mergu: **puran deploy = owner**
  (map load, nikoli `lua_restart`; `lua_status` SHA1 = `sha1sum` datoteke).
- Lokalni ET: deploy prek `sudo -n -u et tmux -S …-285.sock run-shell "cp
  /tmp/x.lua …"` (scp pot nima ključa). Strežnik 2.85 po testu UGASNI
  (`local_et.sh -v 2.85.0 stop`), da ne teče čez noč.

## Odprte ownerjeve odločitve
- Po #916: dvojčki r. 3 (per-bot `.gm` profil iz `top_cells`/`hold_pct`,
  prag 25 sej) ali doc 19 (per-user pogled); popravek korpusa
  `destroyed_count` (fantomska +1 na goldrush rundah pred v6.14) — da/ne.
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
