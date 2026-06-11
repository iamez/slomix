> Research agent report (R3, 2026-06-11) — ET/ET:Legacy ecosystem 2025-26 + positioning map.
> Input for docs/VISION_2026.md. Sources inline.

# ET / ET:Legacy Ecosystem Research Report — June 2026
**Research question:** What does the ET/ET:Legacy ecosystem look like in 2025–26, what do its players miss, and where can a community stats platform (slomix.fyi) be unique?

---

## 1. Active ecosystem 2025–26

### 1.1 ET:Legacy project — alive and shipping
- **2.83.2** released Jan 19, 2025 ("Mom it's working!!!", bug-fix patch); **2.84.0 "Clear the Mines!"** released **May 20, 2026** — weapon zoom, HUD editor, Android overhaul, XPSave expansion, and notably **demo UI refinements (draggable timeline scrubbing, better playback controls)**.
  - https://www.etlegacy.com/blog/et-legacy-2832-mom-its-working
  - https://www.etlegacy.com/blog/et-legacy-284-clear-the-mines
  - *So we should:* treat ET:Legacy as a stable, maintained base — and watch its improving demo playback as a free client-side companion to greatshot.
- **Roadmap**: GitHub milestone "2.8X" due **Aug 1, 2026** (75% complete); long-running renderer2 (OpenGL 3.3+) and Android milestones; 387 issues parked in "Future". No published feature roadmap beyond that.
  - https://github.com/etlegacy/etlegacy/milestones
  - *So we should:* not expect engine-side analytics features; anything deep (positions, aim telemetry) will keep coming from server Lua — exactly slomix's lane.

### 1.2 Player base — small, consistent, evening-pulsed
- Splatterladder still tracks **472 servers** and claims **~2,000 players active at any time of day**; pub life concentrates on Team Muppet, Fearless Assassins, Hirntot (20-year-old community, prime time ~17:30–20:30 CEST).
  - https://et.splatterladder.eu/?mod=serverlist , https://hirntot.org/ , https://steamcommunity.com/app/1873030/discussions/0/5595176692475060989/
  - *So we should:* design for the "evening pulse" pattern — session-centric views (which slomix already has) match how this game is actually played far better than lifetime ladders.

### 1.3 Competitive scene — niche but real, gather-centric
- **ET: Legacy Competitive Discord: ~1,387 members** — the de-facto hub of the comp scene.
  - https://discord.com/invite/ME5fSqNMMr
- **Legacy Continues 2025 LAN**, Łódź, Poland, May 16–18, 2025 — **~20 teams across 6v6 and 3v3 brackets** (exile, v56, #chess-et, AoW, Momentum Gaming; players like niSmo, Rayzed, Graecos). A real LAN in 2025 for a 2003 game.
  - https://www.gamestv.org/forum/4-enemy-territory/931-legacy-continues-2025-team-lineups/
- **Gathers are the unit of play**: daily 3v3/6v6 gathers via Kimi's **Gathermaster** bot (formalized on the official ET:Legacy blog as far back as 2021, still the model today); Oksii's Docker server images bake gather automation into the server itself (`STATS_AUTO_SORT` team assignment on connect, auto-ready when rosters full, BO3 score tracking, auto map rotation).
  - https://www.etlegacy.com/blog/et-legacy-scrims , https://github.com/Oksii/etlegacy
  - *So we should:* recognize slomix's 10–30 player stopwatch community is structurally identical to the wider scene's gather culture — features that close the loop **gather → match → stats → next gather** generalize beyond our community.
- GamesTV forum activity is sparse but the spring 2025 LAN drove broadcasts and betting on the platform; **no 2026 threads** on the ET forum as of this research — the scene's pulse is in Discords, not forums.
  - https://www.gamestv.org/forum/4-enemy-territory/

---

## 2. Stats platforms landscape

| Platform | Niche | State (June 2026) |
|---|---|---|
| **Splatterladder** (et.splatterladder.eu) | Pub server tracker, global XP toplist, serverlist | Alive, revived on .eu domain ("Enemy Territory Stuff is Back"); lifetime XP aggregates only |
| **Trackbase** (et.trackbase.net) | Pub tracker + **TSP skill rating** (kills, hits, HS, revives, engineering, battle sense); official ET:Legacy integration (`sv_advert 3`, whitelist) | Alive; rating is lifetime/pub-oriented, no per-round or positional data |
| **stats.hirntot.org** | One community's pub leaderboards: K/D, playtime, games, two server modes | Alive; lifetime aggregates, paginated leaderboard, no match-level depth |
| **etlstats.stiba.lol** | Comp/gather match stats (audited Mar 2026) | **Returned HTTP 503 on three fetch attempts during this research** — intermittently down |
| **Oksii's stack** | Server-side Lua stats → JSON submit → match-id API → Discord reports | Very active, see below |
| **greatshot (mittermichal)** | Demo cutting/rendering/JSON analysis | Active, see §5 |

Sources: https://et.splatterladder.eu/ , https://et.trackbase.net/ , https://forum.trackbase.net/threads/1094-Trackbase-introduces-new-rating-method/page3 , https://github.com/etlegacy/etlegacy/wiki/Trackbase , https://stats.hirntot.org/ , https://etlstats.stiba.lol/

### New since March 2026 — Oksii is moving fast
His GitHub shows three **new, actively-updated** repos:
- **etl-match-reports** (updated **Jun 8, 2026**) — auto-generated **kill-matrix reports** (markdown + JPEG per map/round) delivered through a Discord bot ("pudibot", `!km <match_id>`).
- **etl-player-chemistry** (updated **Jun 1, 2026**, 115 commits) — pairwise player synergy analysis (undocumented but the name and per-match data folders are clear).
- **etl-statsmig** (Go, May 25, 2026) — stats migration tooling.
  - https://github.com/Oksii?tab=repositories , https://github.com/Oksii/etl-match-reports
  - *So we should:* note that Oksii is converging on slomix territory (match reports, synergy/chemistry) but **Discord-image-first, not web-platform-first**. Slomix's moat is the interactive web layer + positional/aim telemetry he doesn't capture. Also worth a collab ping: his kill-matrix-in-Discord delivery is a cheap UX pattern slomix could adopt for its own data.

### What NOBODY does (the open space)
- **Career identity across servers/communities** — GUID-canonical career pages with name history (trackers do lifetime XP per server; nobody does "this is *you*, across formats and years").
- **Demo/VOD-linked stats** — no platform links a kill row to the demo timestamp or a rendered clip.
- **Positional/spatial analytics** — nobody else has 200ms position data; heatmaps/spawn-route/crossfire analysis is slomix-only.
- **Storytelling** — every peer shows tables; none generates narratives, moments, or "why we lost" analysis.
- **Live match viewing** — ETTV/gamestv exists for broadcasts but no platform does a live stats ticker for gathers.

---

## 3. History lessons: crossfire.nu and GamesTV

### crossfire.nu — what made it THE home
- Registered June 2006; combined **news + opinion columns + forums/journals + server listings + clan recruitment + event coverage** in one place — the social OS of the ET scene through ~2012. The domain still resolves (Google indexes old threads, user profiles, journals) but the fetcher got connection-refused and search snapshots show no fresh editorial content; the social residue lives in a **Facebook group** ("…MAKE ET GREAT AGAIN! (:") and Discords. The 2019 Splash Damage thread "Wolfenstein Enemy Territory THE END?" lists Crossfire among communities "struggling to maintain activity" and pins the scene's decline on lost editorial energy, fewer events, no Steam-era distribution.
  - https://www.crossfire.nu/ , https://website.informer.com/crossfire.nu , https://www.facebook.com/groups/2302260768/ , https://forums.splashdamage.com/t/wolfenstein-enemy-territory-the-end/233669
- The lesson from its life (not just its death): the stats were never the point — **identity and drama were** (journals, columns, rivalries, recruitment posts). Pure infrastructure sites (trackers) survived; the *social* layer died and nothing replaced it except fragmented Discords.
- **GamesTV.org — still alive.** ETTV broadcasts + betting ran for Legacy Continues 2025; its forum hosts the scene's demo-sharing threads; its match archive is the closest thing to a historical record of competitive ET.
  - https://www.gamestv.org/ , https://www.gamestv.org/forum/4-enemy-territory/
- **A modern micro-crossfire for ONE community** = match reports as *news posts*, player profiles as *identity pages*, rivalry/head-to-head pages as *drama*, session recaps as *columns*, plus an awards/records culture. Slomix already has the data layer for all of this; what crossfire teaches is to render it **editorially**, not just tabularly.
  - *So we should:* lean into the storytelling/narrative direction (already the user's stated philosophy) — auto-generated "match report" posts with a comments-in-Discord loop is the highest-leverage missing piece.

---

## 4. What ET players actually want (2024–26 signals)

1. **Demo playback friction** — a May 19, 2025 gamestv thread asking how to watch ETPro demos with an ET:Legacy client on Linux went **unanswered**; a separate thread exists on "replaying ettv demos locally on windows". Demos remain the #1 papercut.
   - https://www.gamestv.org/forum/4-enemy-territory/932-replaying-ettv-demos-locally-on-windows/page-1/
   - *So we should:* make greatshot's web-rendered output the answer — "don't fight clients, watch it in the browser."
2. **Gameplay analysis demand** — Kimi shared converted per-player dm_84 demos from spring 2025 explicitly "to analyze anyone's gameplay" via Legacy mod freecam.
   - https://www.gamestv.org/forum/4-enemy-territory/930-sharing-dm-84-export-from-ettv-demos-from-spring-2/page-1/
   - *So we should:* pair slomix's aim/positional telemetry with demo timestamps — analysis is something the scene's most active contributors already do by hand.
3. **Finding games** — perennial "is this game still alive?" Steam threads; the answer is always "join this Discord / this server at these hours." Discovery is tribal knowledge.
   - https://steamcommunity.com/app/1873030/discussions/0/5595176692475060989/
   - *So we should:* surface "when does our community actually play" (activity calendar already exists — promote it as the answer to "when can I get a game?").
4. **Revival/nostalgia energy** — Feb 2025 Splash Damage forum post founding a new community to "push ET into the 21st century"; the 2019 "THE END?" thread begging for Steam distribution; fan portals like enemyterritory.net (claims "hundreds of active players in 2026") still being built.
   - https://forums.splashdamage.com/t/enemy-territory-elite-community-and-clan/234953 , https://www.enemyterritory.net/en/
   - *So we should:* nostalgia is a feature — career timelines, "on this day" records, and era-spanning player pages monetize emotional attachment that pure K/D tables don't.

---

## 5. Demo/replay ecosystem (greatshot feeders)

- **dm_84 / tv_84** are the ET demo formats; the canonical modern toolchain is a **fork of uberdemotools (UDT_converter)** that converts **ETTV recordings into per-player POV demos with full entity data** — this is what produced the spring 2025 demo dump.
  - https://github.com/mightycow/uberdemotools , https://www.gamestv.org/forum/4-enemy-territory/930-sharing-dm-84-export-from-ettv-demos-from-spring-2/page-1/
- **greatshot-web (mittermichal)** — the upstream of slomix's pipeline: Python/Flask, 346 commits, cuts dm_84/tv_84, exports JSON (hit regions, consecutive kills/HS, revives), renders video with name/flag overlays, downloads ETTV demos from gamestv.org. Its own stated future ideas: **"database of players with statistics," timeline visualization, damage stats** — i.e., it wants to grow toward what slomix already is.
  - https://github.com/mittermichal/greatshot-web , https://github.com/mittermichal/greatshot-render-worker
- **tvdemos.greatshot.xyz** hosts an index of converted spring-2025 competitive demos + asset mirror (et.greatshot.xyz/et/).
- ET:Legacy 2.84's demo UI scrubbing improvements lower the barrier for in-client review.
  - *So we should:* (a) ingest the UDT-converted ETTV archive as a greatshot feed — competitive reference footage of top players to benchmark our aim telemetry against; (b) auto-queue greatshot renders from slomix "moments" (kill-impact spikes, PB runs) — the cross-link demo↔stats is the thing literally nobody in the ecosystem has shipped.

---

## 6. Positioning map

**Axes:** analytics depth (lifetime aggregates → per-round/per-life/positional) × community features (none → full social/editorial layer)

```
community/social
features
  ▲
  │  crossfire.nu (dormant: all social, no stats)
  │      ●
  │
  │  GamesTV.org              ┌────────────────────────────┐
  │   ● (broadcasts,          │   OPEN SPACE:              │
  │      betting, demos)      │   "micro-crossfire +       │
  │                           │    deep analytics"         │
  │  Hirntot ●                │    = slomix's target       │
  │  (community + basic       │  ★ slomix.fyi (today:      │
  │   pub leaderboards)       │    deepest analytics,      │
  │                           │    thin social layer)      │
  │  Splatterladder ●         └────────────────────────────┘
  │  Trackbase ● (TSP rating)
  │              stiba etlstats ●   ● Oksii (match reports,
  │              (match stats,        chemistry — Discord-
  │               fragile uptime)     delivered, no web depth)
  │                                      ● greatshot-web
  │                                        (demo analysis/render,
  │                                         no player identity)
  └──────────────────────────────────────────────────────► analytics depth
```

**Reading:** every peer sits in one corner. Trackers have reach but shallow lifetime stats; Oksii/stiba have match-level comp stats but no web identity layer and fragile/Discord-only delivery; greatshot has demos but no players; crossfire had community but is gone; GamesTV has spectacle but no analytics. **Slomix is alone on the right edge of analytics depth (positional @200ms, spawn-wave, kill-impact, aim telemetry — nobody else captures this) and its open space is straight up the vertical axis:** career identity, narrative match reports, demo↔stat cross-linking, and the records/rivalry culture that made crossfire.nu the scene's home — scoped to one community first, with the gather-centric wider scene as a natural second audience.

**Top 3 unique bets, ranked:**
1. **Demo↔stats fusion** — link kill-impact moments to greatshot-rendered clips (no one has ever shipped this in ET).
2. **Editorial auto-reports** — crossfire-style match "news" generated from data, delivered web + Discord (Oksii validates demand with kill matrices; we have 10x his data).
3. **Career identity** — GUID-canonical, era-spanning player pages with records/"on this day" nostalgia hooks.
