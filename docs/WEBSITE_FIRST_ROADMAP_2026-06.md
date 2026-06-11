# Website-first roadmap v2 (2026-06-11)

> Izvedbeni načrt za [VISION_2026.md](VISION_2026.md). v2 nadomešča prvotni
> gap-analysis roadmap (isti dan) — zdaj research-informed (R1-R4 reporti v
> docs/research/). Bot ostane pipeline/ops/notifikacije; website postane dom.
> Vsak sprint = en shippable PR set; reuse-first (obstoječi API-ji/tabele).

## Sprint S1 — "JUTRO" (push layer; največ vrednosti/trud)
Cilj: druga engagement seansa na vsak igralni večer.
1. **Jutranji Discord digest** (bot): po koncu seje (session end detection
   obstaja) auto-post: zmagovalec, score po mapah, MVP po KIS, 1 narativ,
   novi PB-ji/rekordi — vsak element deep-link na web. Reuse: storytelling
   narrative/momentum, PB cards (competitive), session detail URL-ji.
2. **Home tri kartice**: naslednja seja (availability API) / včerajšnji
   recap (sessions latest + story) / movers (`player_skill_history` delta).
3. **Baseline-delta helper** (`format_with_baseline`) + uporaba v story
   templateih in session detail ("23 fragov — 6 nad povprečjem").
4. **Verdict strip** na session detail: per-igralec ocena večera na
   distribuciji zadnjih 30 sej (KIS composite obstaja).
Bot diet: `!last_session` dobi deprecation notico z linkom.

## Sprint S2 — "RAČUN" (most do interaktivnega)
1. **My account stran**: Discord OAuth (obstaja) → poveži/odveži GUID,
   aliasi, display ime. Reuse: link cog logika → API endpointi.
2. **Role gating**: `require_admin` dependency (user_permissions tabela
   obstaja) + frontend skritje admin akcij. Predpogoj za S3/S4 write poti.
Bot diet: `!link`/`!myaliases`/`!setname` deprecation notice.

## Sprint S3 — "VEČER" (ritual)
1. **Session lobby**: potrjen/standby/sub nivoji na availability strani +
   "rabimo N-tega" Discord ping (bot API). Sub appearances kot stat.
2. **MVP glasovanje** po seji (1 klik, auth iz S2) + MVP leaderboard +
   "most underrated" (MVP votes vs KIS).
3. **Captain draft UI**: kapetana izbirata iz potrjenih; ET Rating predlaga
   balans (read-only suggestion).
4. **Challenge tedna**: definicija (admin), avto-razglas v digestu.

## Sprint S4 — "TEKMA" (sezone + stave)
1. **Mesečna sezona**: season_manager scope na leaderboardih s soft-reset
   pogledom; all-time ostane na profilih/records.
2. **Sezonski awardi + HoF graviranje**: MVP (vote), Oracle, Iron Man
   (prisotnost), Most Improved, lesena žlica (vote, opt-in).
3. **Parimutuel predikcije v1**: brezvredne točke, pool-split; markets:
   zmagovalec večera, prop-beti iz competitive metrik (first blood, stagger).
   Reuse: predictions tabele/cog kot backend osnova.
4. **Per-map record table** ("segmenti"): najhitrejši hold/doc-run per mapa
   iz round timing podatkov; PB notifikacije v digest.

## Sprint S5 — "IDENTITETA" (profil + mobile)
1. **Profil IA prenova**: identity header (rating, tier, arhetip, streak) +
   zavihki (Overview/Combat/Timing/Movement/History) + privzeti scope
   "zadnjih 10 sej" + per-map mini tabela.
2. **Arhetip label** (storytelling archetypes obstajajo) + **focus line**
   (najšibkejši percentil → en stavek) + **duo synergy** stat.
3. **Mobile bottom nav** (4 zavihki: Home/Last Session/Me/Boards) +
   leaderboard kartice na <768px. Tri mobilne poti odlične, ostalo desktop.
4. **Karierna časovnica**: rating sparkline + pripeti awardi (History tab).

## Sprint S6 — "SPOMIN" (estate)
1. **"Na današnji dan"**: dnevni bot post (rekordi/momenti istega datuma).
2. **Record book**: all-time + head-to-head kariere (rivalries razširitev) +
   prvenstva po sezonah na enem mestu; konsolidacija records/awards/HoF
   (obrezovanje strani, ne dodajanje!).
3. **Slomix Wrapped**: sezonske kartice (canvas share format iz S1.4).
4. **LAN stran**: countdown + foto arhiv po letih.
5. **DB export ritual**: viden "estate" backup (mesečni dump artefakt).

## Sprint S7 — "LIVE" (Tonight hub)
1. **Tonight view**: score, map-chip strip, živ session-team-momentum
   (Lua webhook feed, 5-10 s polling, LIVE pulse + last-updated).
2. Kasneje: hold-probability krivulja (spawn/stagger heuristika), SSE
   upgrade če polling ne zadošča.

## Posebna stava (vzporedno, kadar koli): demo↔stats fuzija
Auto-queue greatshot render za top "momente" seje (KIS spike, PB run) →
klip v jutranjem digestu. Nihče v ET ekosistemu tega nima (R3 bet #1).
Predpogoj: greatshot job API (obstaja) + moment→demo timestamp mapping.

## Pravila izvedbe
- Vsak sprint svoj PR (bundled), full pytest + lint, merge lastnik.
- Nova stran sme nastati samo, če nadomesti/združi obstoječo (anti ghost-town).
- Nič, kar rabi dnevno ročno hranjenje.
- Bot ukazi dobijo deprecation notice šele, ko je web ekvivalent potrjen.
- Anti-cilji iz VISION_2026.md veljajo za vse sprinte.
