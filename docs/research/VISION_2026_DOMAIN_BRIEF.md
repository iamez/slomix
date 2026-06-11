# Domain distill brief — vhod v VISION_2026 sintezo (2026-06-11)

Strnjeno "kar že vemo" iz lokalnega korpusa; viri so lokalni dokumenti. Stage D
plana `docs/vision-2026`.

## 1. Lastnikova filozofija (memory: user_vision_invisible_value)
- **Surove statistike kaznujejo team play.** Medic, ki oživlja; igralec, ki drži
  spawn; lurker, ki veže dva nasprotnika in umre — vsi izgledajo "slabi" na
  scoreboardu, a so pogosto razlog za zmago.
- **Opisuj, ne sodi**: narativ ("wiseBoy 15s sam za linijami, pritegnil 2,
  umrl pri objectivu — 8s kasneje vid vzel objective") + številke zraven.
  "Stories WITH numbers", ne stories namesto številk.
- Nova izjava (2026-06-11): **website postane primarni interface**, bot ostane
  pipeline/import/monitoring/notifikacije. Roadmap v docs/WEBSITE_FIRST_ROADMAP
  je lastnik označil kot premajhen — hoče research-driven vizijo.

## 2. Kje smo tehnično unikatni (ANALYTICS_BENCHMARK_2026-06, PROXIMITY_*)
- Per-igralec pozicije @200ms za vsako rundo; spawn-wave clocki (offseti
  CS_REINFSEEDS) numerično izpeljani in validirani; spawn-denial/stagger,
  wave-cycle fight ledger, first-blood konverzija, man-advantage, clutch 1vN,
  KIS (kill impact), gravity/space/enabler/lurker, aim telemetrija (yaw/pitch
  circular stats), player journey vizualizacija, session team momentum.
- Benchmark zaključek: spawn-denial/gravity smo PRED industrijo; manjkali so
  fight segmentation (zdaj shipped), percentile-cohort UX, WP modeli (odprto).
- Lua v7 zaloga (dormant, validirana 2026-06-11): AIM_LOCK (crosshair-on-enemy),
  SPAWN_SELECT, SKILL_SNAPSHOT, COMM_EVENTS; backlog: lean, ammo/reload smrti,
  velocity/trickjump, medic/ammo paki, command-map pingi.

## 3. Konkurenčni teren (ET_STATS_COMPETITIVE_AUDIT_2026-03-04, OKSII_VS_SLOMIX)
- **Stiba (etlstats.stiba.lol)**: močan match/session detail (chat timeline,
  match awards), šibek player-identity sloj. Astro+Solid, javno.
- **Hirntot (stats.hirntot.org)**: močan lifetime player profil, alias history,
  global leaderboardi, per-server scope; šibkejši match detail.
- **Oksii**: najbogatejše surovo zajemanje (killer_health, stance...), brez
  analitične/web plasti — mi smo njegove ideje že adoptirali (v6.01+).
- **Nihče nima**: community plasti (gather/avail/predictions), narativov,
  live pogleda, "kariera + spomin" kombinacije. Slomix edini pokriva oboje
  (match detail + player identity) — odprta niša je tretja os: SKUPNOST.

## 4. Skupnostni kontekst
- 10-30 aktivnih, prijatelji 20 let, povprečno 30-40 let, službe/družine;
  igralni večeri 2-3×/teden, en strežnik, slovenska scena z mednarodnimi gosti.
- Že obstaja: availability poll (web+discord+telegram link), uploads (configi,
  klipi), greatshot (demo render pipeline), achievements (bot), predictions
  (bot), skill rating (web), rivalries (web).
- Crossfire.nu nostalgija: lastnik hrani backup arhiv (crossfirebu.rar) —
  "dom scene" koncept mu je blizu (news+forumi+tekme+identiteta na enem mestu).

## 5. Trde omejitve za vizijo
- Produkcija = legacy JS (React mirror NI deliverable).
- En sam VPS + en game server; brez ambicij po multi-tenant javni platformi
  (zaenkrat) — vizija je NAŠA skupnost, ne SaaS.
- Bot ohrani: voice detection, SSH monitor, Lua webhook, Discord notifikacije,
  ops ukaze. Web prevzame: poizvedbe, identiteto, interakcijo.
- Vse novo mora biti mapljivo na obstoječe tabele/API-je ali Lua v7 zalogo.
