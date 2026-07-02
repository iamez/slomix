# 🎮 Slomix - ET:Legacy Competitive Stats Platform

> **PostgreSQL-powered real-time analytics for competitive ET:Legacy — Discord bot, web dashboard, demo highlight scanner, and game server telemetry**

[![Production Status](https://img.shields.io/badge/status-production-brightgreen)](https://github.com/iamez/slomix)
[![Version](https://img.shields.io/badge/version-1.20.0)](CHANGELOG.md) <!-- x-release-please-version -->
[![PostgreSQL](https://img.shields.io/badge/database-PostgreSQL_17-336791)](https://www.postgresql.org/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/web-FastAPI-009688)](https://fastapi.tiangolo.com/)
[![Data Integrity](https://img.shields.io/badge/data%20integrity-6%20layers-blue)](docs/SAFETY_VALIDATION_SYSTEMS.md)
[![Tests](https://img.shields.io/badge/tests-3246%20passing-success)](tests/)
[![Discord.py](https://img.shields.io/badge/discord.py-2.6.4-5865F2)](https://discordpy.readthedocs.io/)

A **production-grade** Discord bot + web dashboard + demo analysis pipeline with **6-layer data validation**, **real-time Lua telemetry**, **AI match predictions**, and **demo highlight detection** for ET:Legacy game servers.

---

## 🔥 Recent Updates (June 2026)

### **🧭 VISION_2026 — Sprints S1–S4 Shipped (June 2026)** 🆕

**The platform pivoted from "stats viewer" to *the operating system of a 20-year
community* — the website becomes the memory of every game night, the bot becomes
the pipeline. Four research-driven sprints shipped back-to-back.** See the
[Vision & Roadmap](#-vision--roadmap) section below.

- 🌅 **S1 · JUTRO / Morning** (#384) — **Morning Discord digest** posted after every
  session (winner, score by map, MVP, new personal bests, one narrative lede — every
  element a deep-link into the site). **Home pulse cards** (next session / last night /
  movers vs your own form). **Own-form verdict strip** on Session Detail (Leetify-style
  Great/Good/Average/Subpar vs *your* last sessions) + a baseline-delta helper ("23 frags
  — 6 above your average") so no generated number ships without context
- 🪪 **S2 · RAČUN / Account** (#386) — Web **display-name & alias** management, a single
  sanctioned session + role gate (`require_user` / `require_admin` + CSRF) for every write
  endpoint, and a bot-round `is_valid` forward-fix so test/bot rounds never pollute stats
- 🌆 **S3 · VEČER / Evening** (#389) — **Peer-voted MVP** (the community decides, not a
  formula), **weekly challenge**, Planning-Room lobby with confirmed / standby / sub tiers
  + a one-click "need N more" ping, and a **captain draft** that proposes ET-Rating-balanced
  teams with manual override
- 🏟️ **S4 · TEKMA / Competition** (#391) — Quarterly **season** surfacing, **engraved season
  awards** + a Hall-of-Fame "Season Champions" wall (MVP / Iron Man / Most Improved / Oracle),
  **parimutuel session-winner betting** (valueless points, pool-split payout, atomic
  `FOR UPDATE` settlement) that pulls the bench and non-players in, and **per-map
  fastest-objective records** ("segments") + a personal-best digest line

### **🎯 v1.16.0: Full Aim Analytics — v9 True-Aim Shipped (May 19-20)**

**The flagship `mode=aim` lens on the Player Combat Map turns per-shot
origin + view-angles into a rich, research-grounded read of how a player
holds, sweeps, and looks while shooting.**

- 🌹 **5th lens on the Player Combat Map** (#346) — `Kills from`, `Victims die`, `Player dies`, `Presence` joined by **Aim**: origin density + a per-zone **16-bucket yaw rose** + a mean-aim tick per hotspot. Pitch profile (up / level / down), spread metrics, and narrative one-liners surface side-by-side
- 🧮 **Wrap-safe circular statistics** — yaw lives on a circle (±180°), so an arithmetic mean is silently wrong (e.g. 170° and −170° average to 0° but the true mean is ~180°). The new `_circular_yaw_stats` helper does it right: `atan2(mean sin, mean cos)`, mean resultant length `R`, circular std, and a **Rayleigh test** for directional-vs-uniform. Verified live against a real human (1,506 shots) — endpoint matched a manual `psql` cross-check to **0.001°**, while the wrong arithmetic mean would have been off by **38°**
- 📖 **Storytelling, not verdicts** — narrative lines are generated only from real statistics (sample size, dominant compass-sector, ±°  spread, pitch tendency, Rayleigh significance). No fabricated "center" — defensible reads like *"1,506 shots tracked · Most shots aimed SW (28% of fire) · Wide horizontal coverage (±71°) · Level aim (avg +1° pitch)"*
- 🧰 **NEW additive endpoint** `GET /api/proximity/player-aim` — does **not** touch the existing `mode=aim` on the shared `player-heatmap` (3 consumers + ~30 tests stayed green). Dual-stack: legacy JS = production truth, React = parallel
- 🔬 **Research-grounded design** — methodology cross-checked against esports analytics (Leetify, scope.gg), circular-statistics literature, NBA hex-bin shot-chart practice, and spatial-DB downsampling patterns before a line of code was written (`docs/PROXIMITY_AIM_ANALYTICS_PLAN.md`)
- ✅ **Validated on real all-night session** — 30,905 shots from 6 distinct humans across 8 maps; yaw spans `[−180,180]`, pitch `[−71,88]`, **both-zero = 0%** ⇒ `ps.viewangles` binding rock-solid on humans, not just bots

### **🗺️ v1.15.0: Proximity Page Major Redesign + Lua 5.4 Production-Grade (May 14-19)**

**The biggest single proximity push since v6.01: map-first information architecture, every audit finding closed, and two latent Lua-5.4 incompatibilities shipped + caught + fixed under live load.**

- 🗺️ **Map-first information architecture** (#328, #330, #332, #334, #336) — the Player Combat Map is the hero; the page reads top-to-bottom as a single player's story (`HERO Combat Map → Player Story → Map Context → Engagements & Trades → Roles & Classes → Round Replay`). 8 KPIs trimmed to 5, 7 leaderboards consolidated to 3 contextual ones, redundant per-panel "Map name…" inputs replaced by the page-level Scope (#340)
- 🎯 **Per-player heatmap, 4 perspectives** (#328) — `Kills from / Victims die / Player dies / Presence`, every lens scoped to a selected player + map + range. A1 (heatmap blank on calibrated maps) + A2 (no per-player filter) + A6 (256 vs 512 grid drift) closed. Server-side stride downsamples presence (>8 k samples never ship raw)
- 🎯 **Per-player Hit Region Distribution** (#339) — head / arms / body / legs breakdown tied to the same player selector
- 🔓 **Home widget endpoints restored + sanitised** (#338) — `/api/live-status`, `monitoring/status`, `voice-activity/*`, `server-activity/history` accidentally got admin-gated by an earlier security sweep. Restored public, with a strict whitelist sanitiser (no Discord-ID/avatar leak; dropped dead `voice_members` path)
- 🔥 **Webhook `bit`-library crash on Lua 5.4** (#343) — `stats_discord_webhook.lua:1264` used LuaJIT/5.1 `bit.band(bit.lshift(1,4), cs)`. ET:Legacy 2.83.1's Lua 5.4 has **no `bit` library** → every `et_RunFrame` raised `attempt to index a nil value (global 'bit')`, spamming the console for hours. Replaced with native `((1 << 4) & cs) ~= 0` and bumped webhook to v1.7.1
- 🔥 **SHOT_FIRED `outputData` crash on Lua 5.4** (#345) — `proximity_tracker.lua:3157` formatted `round(…, 1)` float origin with `%d`. Lua 5.4 rejects non-integer floats for `%d` ("number has no integer representation"), the throw escaped `outputDataInner`, `trap_FS_CloseWrite` never ran, and **every round's proximity file was left unclosed/corrupt while `shot_fired=true`**. Fix: truncate toward zero in Lua (`math.floor` for ≥0, `math.ceil` for <0 — plain `floor` is off-by-one for negative world coords) then `%d`. Caught by the runbook's *"verify clean end-to-end on a real round"* gate exactly as planned
- 🧰 **Hard-stop deploy discipline** — every SSH write was guarded with backup + anchored sed + a surgical-change proof (`revert(line) == known-good SHA`), so each live change was provably exactly the intended one token

### **⚡ v1.14.x: Deprecation Cleanup, Perf, Audit Sweep (May 10-12)**

- 🧹 **Timezone-aware Datetime Migration** (#214, #216, #222, #230) — Killed every `datetime.utcnow()` and raw `datetime.fromtimestamp()` / `date.today()` in the codebase. Enabled ruff DTZ005 + DTZ007 with explicit `noqa` rationales on the 253 sites that legitimately need naive datetimes (Lua wall-clock, file-mtime, etc.). No more silent UTC/local mixups
- 🔬 **Mega Audit v6** (#210) — Verified-real sweep: 12 actual fixes shipped, 16 false positives ruled out with evidence. Audit methodology refined to demand proof-of-bug, not just code smells
- 📖 **Useless-Defense-Deaths Metric** (#204) — Captures defensive deaths that didn't help the team (panic deaths far from objectives). New endpoint feeds storytelling
- 🩺 **DB Drift Differential Mode** (#201) — `scripts/check_db_drift.py --diff` shows row-level deltas between prod and dev DBs, not just schema delta
- 🔒 **Atomic Stats Insert + Weapon Savepoint** (#199) — `_insert_player_stats` wrapped in a single transaction with a savepoint around weapon stats. Partial-import inconsistencies impossible
- 🛡️ **TOCTOU Closure on player_aliases** (#197) — Closed race window in alias creation; silent excepts in parser now log
- 📝 **Storytelling Math + Narrative Polish** (#205, #208, #228) — Spawn-rush filter, NULL/0 `round_start_unix` filter in enabler/lurker, narrative wordalisation overhaul
- ⚡ **KIS Single-Pass Spawn Aggregation** (#241) — `spawn_mult` + `reinf_mult` merged into one pass over `spawn_timings` (was two passes)
- 🚄 **Records Parallelisation** (#243) — 13 sequential queries on `/api/records` collapsed into `asyncio.gather`. Page-load cut substantially
- 🐛 **Error Handler Exc-Info Fix** (#234) — `exc_info=True` replaced with `exc_info=error` so structured loggers actually capture the exception chain instead of the implicit one

### **🎨 v1.13.x: Session Detail UX Redesign + Canonical GUID Plumbing (May 7-8)**

- 🎯 **Session Detail Faza A** (#186) — Major UX redesign of the Session Detail page on the legacy website. Cleaner header, tighter rows, better R1/R2 split, mobile-friendly
- 🔗 ***_guid_canonical INSERT Fix** (cdb7f51) — Parser helper + KIS now populate `*_guid_canonical` columns on insert (forward-compat), unblocking the broader canonical-ID rollout
- 🚑 **compare_mixin.py Un-ignored** (8f78e19) — File was accidentally in `.gitignore`; stats_cog `!compare` was broken on prod until this landed
- 🧰 **Sync Helper Hardening** (#190, #192, #195) — RCA-driven robustness pass on `scripts/sync_*.sh`: env-loading via `set -a`, base64-encoded SQL over SSH (no quoting hell), and two follow-ups for nits missed in the first ultrareview

### **🎯 v1.12.0: Website Information-Architecture Redesign (May 7)**

**The website got dramatically simpler — fewer pages, clearer hierarchy, less code.**

- 🪶 **Stats Dropdown Minimalised** (#178) — 13 menu items → 6. Things that should be subordinate (records subpages, awards drill-downs) moved out of top-level nav
- 🎨 **Availability Page As #ETL** (#182) — Redesigned to feel like a Discord channel: bigger fonts, bolder colors, clearer "who's coming tonight?" semantics
- ✂️ **About Page Replaces System Overview** (#179) — Old `/#/system-overview` was 7,000 lines of internal architecture. Replaced with a focused `/#/about` page aimed at actual visitors. Net **-7,000 LOC**
- 🐞 **R0 Double-Counting + TIR Formula Fix** (#176) — PCS aggregations were double-counting R0 (warmup) rounds in some leaderboards; TIR formula corrected across the board. Cross-leaderboard numbers now consistent

### **🛡️ v1.11.1: Mass Test Coverage Sweep + Security Hardening (May 6-7)**

**+2,266 unit tests in a single PR (#173) — 5.4× growth — plus two P1 security fixes.**

- 🧪 **Test Coverage 593 → 2,859** — Mandelbrot-style audit sweep added focused tests across 50+ modules: notifier helpers, telegram/signal connectors, scheduler quiet-hours, achievement ledger, BoundedLockDict, file_tracker dedup, replay_service primitives, prox_scoring percentile math, session-matrix aggregation, monitoring allowlist, stopwatch scoring, and dozens more. Every test docstring documents the regression it catches
- 🔒 **Symlink TOCTOU Fix** — `upload_store.resolve_download_path` post-resolve `is_symlink()` check never fired (resolve() follows symlinks). Now walks candidate parents BEFORE resolve(), bounded at storage root so symlinked-mount deploys still work
- 🩹 **JSON Null Roster Normalisation** — `TeamManager._decode_json_array` returned `None` for stored JSON `null` (legacy/malformed rows), then crashed `len(...)` downstream. Now normalises null and non-list shapes to `[]`
- 🐛 **Observed Tripwires Pinned** — `_format_delta_seconds(None)` AttributeError, `_is_reminder_due(None)` AttributeError — both now have explicit tests so a fix is a deliberate change, not silent

### **🧬 v1.11.0: Round Canonical ID + Correlation Saga (May 6)**

**Content-addressed round identity + 6-phase rollout to eliminate orphan correlations.**

- 🆔 **Round Canonical ID** — `sha256(round_start_unix:map_name:round_number)[:16]` as a stable cross-source identifier (Phases 1-4: schema → dual-write → UNIQUE constraint → primary lookup). Idempotent ingest, zero collision risk in our scale window
- ⏱️ **Saga Timeout for Stale Pending Correlations** (Phase 6) — Long-pending pending rows time out gracefully instead of blocking later imports
- 🧹 **Periodic Correlation Sweep** (Phase D + E) — Cleanup tool + scheduled sweep finally closes the orphan-row regression. Cleanup script now preserves multi-match days (best-of-3 style) instead of nuking them
- 🔬 **Strategy 3 Cross-Pollination Fix** — Back-to-back same-map matches no longer mix kill data into the wrong round (600s proximity window + canonical merge)
- 🩹 **Re-linker Repairs Mismatched round_id** — Catches and corrects existing wrong assignments instead of just adding new links
- 🔧 **Storytelling Completeness Diag** — `/diagnostics/storytelling-completeness` endpoint with corrected `rounds_correlated` counter
- 🎨 **Stats Dropdown Reorder + Smart Stats Verification UI** — Verification panel for KIS audit transparency

### **♻️ v1.10.x: Lua Retry Buffer + Quick-Leaders Cleanup (April 25 → May 4)**

- 💾 **Lua v1.7.0 Persistent Retry Buffer** (#152) — Game-server Lua now disk-buffers webhook payloads when Discord rejects them, replays on reconnect. No more lost round notifications during transient network glitches
- 🧽 **Quick-Leaders Dead Code Removal** (#154) — Eliminated stale `session_date` fallback queries that masked actual data integrity issues

### **🚀 v1.9.0: The Big Rollup — Proximity v6.01, Oksii Adoption, KIS v3 (April 25)**

**The largest single release: proximity overhaul, Oksii Lua adoption, scoring v3, and complete website redesign.**

- 🎯 **Proximity v6.01 Objective Intelligence** (#53) — Carrier kills, returns, construction events, vehicle progress with full backend + frontend coverage
- 🩹 **Oksii Lua Adoption** — `killer_health`, `alive_count`, reinf timing flow into KIS v2 multipliers + BOX scoring service
- 🧠 **KIS v3 — Graduated Reinforcement** (#121) — UTRO-inspired 7-tier reinf multiplier (0.70-1.40) replaces binary bonus
- ⚔️ **Player Rivalries** — H2H stats, nemesis/prey/rival classification at `/#/rivalries`
- 🏆 **Win Contribution (PWC/WIS/WAA)** — 5-component formula, dynamic weight redistribution, MVP detection
- 🔮 **Match Predictions** (Phase 1-7) — 4-factor algorithm with auto voice-channel detection
- 🎬 **Greatshot Demo Pipeline** — Upload → UDT scan → highlight detect → cut → render
- 🛠️ **Round Correlation System** — `match_id` canonicalisation + linkage diagnostics
- 📊 **Diagnostics: DB Pool Capacity** (#149) — Live pool utilisation metrics
- 🔥 **Combat Heatmap Overlay** (#145) — Map-image-based grid overlay for kill/death hotzones
- 🧱 **God File Decomposition** — `proximity_router.py` 5,515 → 14 sub-routers; `records_router.py` 3,172 → 10 sub-routers

### **📜 Earlier milestones (Mar–Apr 2026)** — condensed

<details><summary>Click to expand the spring 2026 release history</summary>

- **v1.6.0 — Fairness Overhaul + Story Expansion** (Apr 20-21, PR #76/#78/#121) — Bayesian MVP shrinkage (no more 1-round wonders), WIS v2 harmonic confidence, PWC zero-team-kill fix, BOX score panel, KIS v3 graduated reinforcement, 2× faster storytelling (`asyncio.gather`, 360→36 queries)
- **v1.5.x — Runtime Bug Sweep + Performance RCA** (Apr 19-20, 14 PRs) — Round-linker race + midnight crossover fix, serialized correlations (migration 040), schema drift → zero, hot-path indexes (autocomplete 50ms → <1ms)
- **v1.5.0 — Security + Session Detail 2.0** (Apr 17, PR #79/#80) — `require_admin_user` gate on diagnostics, centralized `strip_et_colors`, Player × Map matrix with stopwatch side-swap + substitution handling
- **Mandelbrot RCA v2.0 + Oksii Adoption** (Mar 29-30) — Oksii Lua v6.01 (`killer_health`, `alive_count`, reinf timing) → KIS v2, BOX scoring, god-file decomposition (`proximity_router.py` 5515 → 14 sub-routers), ruff 2257 → 0
- **v1.5.0 — Round Replay Timeline, Momentum Chart & Codacy Zero** (Mar 28, 53 commits) — Dual-pane replay (`/#/replay`, 420+ events/round, 200ms positions), 30s-window momentum chart, auto session narrative, 11 moment detectors, **58 Codacy issues → 0** (22 XSS, 7 SQLi, zero suppressions)
- **v1.4.0 — Rivalries, Win Contribution & Smart Stats Phase 2** (Mar 27) — H2H rivalries + nemesis/prey/rival, PWC/WIS/WAA win contribution, 9 player archetypes, 35-weapon mapping
- **v1.3.0 — Smart Storytelling, Proximity Pipeline & Deep RCA** (Mar 26-27) — Kill Impact Score (7 multipliers), 5 moment detectors, Team Synergy (5-axis), STATS_READY pipeline redesign
- **v1.1.0 — Stats Accuracy Audit, React 19 & Proximity v5** (Mar 2026) — Full accuracy audit, R0 double-counting fix, React 19 + TypeScript 5.9, ET Rating system

</details>

**[📖 Full Changelog](CHANGELOG.md)**

---

## ✨ What Makes This Special

- 🎬 **Round Replay Timeline** — Dual-pane viewer: event feed + 2D map canvas + scrubber, 420+ events per round, player positions at 200ms precision
- 🧠 **Smart Storytelling** — Kill Impact Score (10+ multipliers), 11 moment detectors, 9 player archetypes, auto-generated session narratives
- ⚖️ **Bayesian MVP + WIS v2** — Fairness-first scoring with shrinkage prior and harmonic confidence weighting; late-joiners don't steal MVP
- 🎯 **Proximity Teamplay Analytics** — Lua v6.10 telemetry: engagements, crossfire, cohesion, trade kills, spawn timing, objective intelligence
- ⚔️ **Player Rivalries** — H2H stats, nemesis/prey classification, per-map drill-down, rivalry leaderboard
- 📈 **ET Rating System** — 9-metric percentile skill rating with per-session drill-down and confidence indicator
- 🔮 **AI Match Predictions** — 4-factor algorithm (H2H, form, map performance, substitutions) with auto voice-channel detection
- 🎬 **Demo Highlight Scanner** — Upload demos, detect multi-kills/sprees, cut clips, ready-to-render highlights
- 🔒 **6-Layer Data Integrity** — Transaction safety, ACID guarantees, per-insert verification, schema drift zero
- 🌅 **Morning Digest & Own-Form Verdicts** — Post-session Discord recap (winner, MVP, new PBs, narrative) + Leetify-style "rate your night vs your own form" verdicts (VISION_2026 S1)
- 🏟️ **Seasons, Awards & Parimutuel Betting** — Quarterly seasons, engraved Hall-of-Fame champions (peer-voted MVP, Iron Man, Oracle), and valueless-points session betting that pulls in the bench (VISION_2026 S4)
- 🤖 **Full Automation** — SSH monitoring, auto-download, auto-import, auto-post (60s cycle) + real-time Lua webhook (~3s latency)

**[📊 Data Pipeline](docs/DATA_PIPELINE.md)** | **[🔒 Safety & Validation](docs/SAFETY_VALIDATION_SYSTEMS.md)** | **[🧭 Vision & Roadmap](#-vision--roadmap)** | **[📖 Changelog](CHANGELOG.md)**

---

## 🧭 Vision & Roadmap

> **North Star: _the evening is the product; the website is its memory._**

Slomix isn't a stats viewer — it's the **operating system of a 20-year community**.
It prepares the next game night, follows it live, tells it back as a story the next
morning, and keeps it forever. **Discord stays the river** (conversation, triggers);
**the website becomes the library** (memory, identity, depth) — and every page is one
deep-link away from Discord. Full write-up: **[docs/VISION_2026.md](docs/VISION_2026.md)**.

### Five Pillars

| Pillar | What it means |
|--------|---------------|
| 🌅 **Morning** | Push the memory — a digest after every session, verdicts vs *your own* form, baseline-anchored numbers |
| 🌆 **Evening** | Ritual & live — session lobby (confirmed/standby/sub), captain draft, a single live momentum view, weekly challenge |
| 🪪 **Identity** | A career, not a table — profile with archetype, one "focus" line, duo synergy, account linking |
| 🏟️ **Competition** | Seasons & valueless betting — engraved season awards, parimutuel pools — **not a global K/D ladder** |
| 🗄️ **Memory** | Be the community's "estate" — "On this day", record book, Slomix Wrapped, LAN archive, 20 years of history |

### Shipped ✅ (June 2026)

- **S1 · Morning** — morning digest, home pulse cards, own-form verdicts, baseline helper
- **S2 · Account** — display names & aliases, unified session + role gating
- **S3 · Evening** — peer-voted MVP, weekly challenge, lobby tiers + "need N more", captain ET-Rating draft
- **S4 · Competition** — quarterly seasons, engraved HoF awards, parimutuel betting, per-map fastest-objective records

### What's coming 🔜

- **S5 · Identity** — career profile IA: identity header + archetype, a single "focus" line ("trade-kill rate 34th percentile — 50th flips 2 rounds"), duo synergy ("with SuperBoyy you win 71%, without 44%"), career timeline
- **S6 · Memory** — "On this day" push, all-time record book, **Slomix Wrapped** (6-8 season cards per player), LAN/meetup page, historical imports (SupaStats 2024)
- **S7 · Live** — Tonight hub: live score + map strip + a single momentum graph (5-10s polling), later a hold-probability curve from spawn/stagger data
- 🎯 **Signature bet — demo↔stats fusion:** no one in the ET ecosystem has ever linked a kill line to a rendered demo clip. We have the Greatshot pipeline *and* the moment detectors — auto-queue a clip from a session's best moments straight into the morning digest

### Anti-goals (what we deliberately **don't** build)

No global all-time K/D ladder up front · no web chat (the river stays in Discord) ·
no growth/SEO machinery · no daily streaks, login-XP, or generic badge grids · nothing
that needs daily manual feeding. Every new page replaces or merges an old one — for a
20-player community, *pruning* matters as much as adding.

---

## 📈 Production Numbers

| Metric | Value |
|--------|-------|
| **Kills Tracked** | 197,618 |
| **Headshot Kills** | 41,994 |
| **Damage Dealt** | 38.5 million |
| **Revives Given** | 19,447 |
| **Rounds Parsed** | 2,541 |
| **Unique Players** | 59 |
| **Stats Per Player Per Round** | 57 fields |
| **Discord Commands** | 100+ across 20 cogs |
| **Database Tables** | 101 (managed via committed SQL migrations) |
| **Test Coverage** | 3,246 tests, CI green |
| **Data Span** | Jan 2025 — Jun 2026 (18 months) |

---

## 🔮 Ecosystem

```text
┌─────────────────────────────────────────────────────────────────┐
│                       SLOMIX ECOSYSTEM                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │  DISCORD    │  │   WEB       │  │  GREATSHOT  │            │
│  │  BOT        │  │   DASHBOARD │  │  SCANNER    │            │
│  │  (Python)   │  │  (FastAPI)  │  │  (UDT+Py)   │            │
│  │  ✅ PROD    │  │  ✅ PROD    │  │  🔶 NEW     │            │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘            │
│         │                │                │                    │
│  ┌──────┴──────┐         │         ┌──────┴──────┐            │
│  │ LUA WEBHOOK │         │         │  PROXIMITY  │            │
│  │ (Real-time) │         │         │  TRACKER    │            │
│  │  ✅ PROD    │         │         │  ✅ PROD    │            │
│  └──────┬──────┘         │         └──────┬──────┘            │
│         │                │                │                    │
│         └────────────────┼────────────────┘                    │
│                          │                                     │
│                  ┌───────▼───────┐                             │
│                  │  PostgreSQL   │                             │
│                  │  101 Tables   │                             │
│                  └───────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
```

| Project | Status | Description |
|---------|--------|-------------|
| **Discord Bot** (this repo) | ✅ Production | 100+ commands, 20 cogs, full automation, AI predictions |
| **Website** (`/website/`) | ✅ Production | FastAPI + React 19/TypeScript SPA: profiles, sessions, leaderboards, proximity, greatshot |
| **Lua Webhook** (`vps_scripts/`) | ✅ Production | Real-time round notifications, surrender timing fix, team capture |
| **Greatshot** (`/greatshot/`) | ✅ Production | Demo upload, highlight detection, clip extraction, render pipeline |
| **Proximity** (`/proximity/`) | ✅ Production | Lua v6.10+ teamplay analytics — engagement, cohesion, crossfire, trade kills, objective intelligence, Oksii-adopted fields (killer_health, alive_count, reinf timing) |

---

## 🏗️ System Architecture

### **Data Pipeline Overview**

```text
┌─────────────────────────────────────────────────────────────────┐
│                    ET:Legacy Game Server (VPS)                   │
│  Stats files (.txt)  |  Lua telemetry  |  Demo files (.dm_84)  │
└──────┬───────────────┼─────────────────┼────────────────────────┘
       │               │                 │
       │ SSH/SFTP      │ Discord         │ Web Upload
       │ (60s poll)    │ Webhook (~3s)   │
       ▼               ▼                 ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Layer 1-2:   │ │ Lua Webhook  │ │ Greatshot    │
│ Download &   │ │ Processing   │ │ Scanner      │
│ Dedup Check  │ │ (timing,     │ │ (UDT_json    │
│              │ │  teams,      │ │  → highlights │
│              │ │  pauses)     │ │  → clips)    │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │               │                 │
       ▼               ▼                 ▼
┌──────────────────────────────────────────────────┐
│  Layer 3-4: Parser Validation & Differential     │
│  ✓ R2 differential  ✓ Cross-field checks         │
│  ✓ Time-gap matching  ✓ 7-check pre-insert       │
└──────────────────────┬───────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│  Layer 5-6: PostgreSQL (ACID) + Constraints      │
│  ✓ Transaction safety  ✓ FK/NOT NULL/UNIQUE      │
│  101 tables  |  57 columns per player per round   │
└──────────────────────┬───────────────────────────┘
                       │
              ┌────────┼────────┐
              ▼        ▼        ▼
         Discord    Website   Background
          Bot       Dashboard  Workers
        (100+ cmds)(FastAPI)  (Analysis,
                              Render)
```

**Processing Speed:** ~3 seconds per file (download → parse → validate → insert → Discord post)

---

## 🔒 Data Integrity & Safety Systems

### **6 Layers of Protection**

| Layer | Component | What It Protects | Blocking? |
|-------|-----------|------------------|-----------|
| **1** | File Transfer | Download corruption, empty files | ✅ Yes |
| **2** | Duplicate Prevention | Re-processing, bot restarts | ✅ Yes |
| **3** | Parser Validation | Invalid types, impossible stats, R2 differential | ✅ Yes |
| **4** | 7-Check Validation | Aggregate mismatches, data loss | ⚠️ No (warns) |
| **5** | Per-Insert Verification | Silent corruption, type conversion | ✅ Yes |
| **6** | PostgreSQL Constraints | NOT NULL, negative values, orphans | ✅ Yes |

**Result:** Every data point verified at **multiple checkpoints** before commit.

**Security:** Zero `innerHTML` in new code — all dynamic content uses DOM API (`createElement` + `textContent`). 58 Codacy issues resolved with zero suppressions.

**[📖 Full Documentation: SAFETY_VALIDATION_SYSTEMS.md](docs/SAFETY_VALIDATION_SYSTEMS.md)**

### **Round 2 Differential Calculation**

ET:Legacy Round 2 stats files show **cumulative totals** (R1 + R2), not per-round performance. The parser automatically:

1. ✅ Detects Round 2 files by filename
2. ✅ Searches for matching Round 1 file (same map, <60min gap)
3. ✅ Rejects old Round 1 files (different session)
4. ✅ Calculates differential: `R2_actual = R2_cumulative - R1`

```text
Round 1 (21:31): Player vid = 20 kills
Round 2 (23:41): Stats file = 42 kills (cumulative)
         ❌ REJECTED: 21:31 Round 1 (135.9 min gap - different session)
         ✅ MATCHED: 23:41 Round 1 (5.8 min gap - same session)
         Result: vid Round 2 stats = 22 kills (42 - 20)
```

**[📖 Full Documentation: ROUND_2_PIPELINE_EXPLAINED.txt](docs/ROUND_2_PIPELINE_EXPLAINED.txt)**

### **Stopwatch Scoring**

ET:Legacy stopwatch maps have two rounds where teams swap attack/defense. Slomix:

- ✅ Tracks persistent teams across side-swaps using `session_teams`
- ✅ Scores by **map wins** (faster attack time wins), not individual rounds
- ✅ Handles fullholds, double fullholds (1-1 tie), and surrenders
- ✅ Grows teams dynamically as players join (3v3 → 4v4 → 6v6)

---

## 🌟 Features

### **🎬 Greatshot — Demo Highlight Scanner**

Upload ET:Legacy `.dm_84` demo files through the website. The system will:

1. 📤 **Upload** — Secure upload with extension/MIME/header validation, SHA256 hash
2. 🔍 **Parse** — [UberDemoTools](https://github.com/mightycow/uberdemotools) extracts kills, chats, team changes into unified event timeline
3. 🎯 **Detect** — Multi-kill chains, killing sprees, quick headshot sequences, aim moments
4. ✂️ **Cut** — Extract highlight clips from the demo at exact timestamps
5. 🎥 **Render** — Queue video renders (pipeline ready, configurable backend)

**All results stored in PostgreSQL** — analysis JSON, highlight metadata, clip paths, render status. Full API for listing, detail views, and downloads.

**Based on [greatshot-web](https://github.com/mittermichal/greatshot-web) by Kimi (mittermichal).** We adapted his scanner/highlight/cutter/renderer architecture, integrated it with our auth system and PostgreSQL schema, and built UDT from source with [ET:Legacy protocol 84 support](https://github.com/mightycow/uberdemotools/pull/2).

---

### **🎯 Proximity Analytics — Teamplay Intelligence**

Real-time Lua telemetry (v6.10) tracks every player position, engagement, and objective interaction on the game server. The data flows through a dedicated parser into 30+ database tables, powering deep teamplay analytics:

- 📍 **Combat Engagements** — Every 1v1/NvN encounter with distance, duration, and outcome
- 🔥 **Crossfire Detection** — LOS-verified crossfire angles with execution tracking
- 👥 **Team Cohesion** — Periodic team shape snapshots (centroid, dispersion, buddy pairs)
- ⚡ **Team Pushes** — Coordinated movement detection with objective orientation
- 💀 **Trade Kills** — Server-side trade kill detection with reaction timing
- ⏱️ **Spawn Timing** — Per-kill spawn wave efficiency scoring
- 🎯 **Kill Outcomes** — Gib/revive/tap-out tracking with Kill Permanence Rate (KPR)
- 🗺️ **Combat Heatmaps** — Grid-binned kill/death hotzones with map overlay
- 🦴 **Hit Regions** — HEAD/ARMS/BODY/LEGS hit distribution per weapon
- 🏗️ **Objective Intelligence** — Carrier tracking, construction events, vehicle progress

**Pipeline:** STATS_READY webhook triggers proximity import → re-linker task fixes orphaned data → 2min fallback polling. Eliminates 60% of historical linkage failures.

**Website:** Full React dashboard with scope filtering (session/map/round), 7 leaderboard categories, metric tooltips, and GUID→name resolution.

---

### **📈 ET Rating — Skill Rating System**

A 9-metric percentile-based skill rating formula that captures the full picture of competitive ET:Legacy performance:

- 🏅 **Percentile Formula** — Combines KD, DPM, accuracy, headshot%, revives, objectives, alive%, efficiency, damage per round
- 📊 **Per-Session Drill-Down** — See how your rating changes across gaming sessions and maps
- 🎯 **Confidence Indicator** — Low/Medium/High based on rounds played
- 🏆 **Server-Side Tiers** — Bronze through Diamond rankings with auto-refresh when stale
- 📈 **History Tracking** — Trend charts showing rating progression over time
- 👥 **50 Players Rated** — Live leaderboard at `/api/skill/leaderboard`

---

### **🎬 Round Replay Timeline**

Relive every round with a full event replay viewer:

- 🎥 **Dual-Pane Viewer** (`/#/replay`) — Event feed on the left, 2D map canvas on the right, synchronized scrubber bar
- 📍 **Player Positions** — Sourced from `player_track.path` JSONB at 200ms precision — see exactly where every player was at every moment
- ⚡ **420+ Events Per Round** — Kills, deaths, revives, objectives, team actions rendered on an interactive timeline
- 🗺️ **2D Map Canvas** — ET:Legacy map overlay with real-time player position dots and event markers
- 🔌 **3 API Endpoints** — Round event feed, player track positions, round metadata

---

### **🧠 Smart Storytelling Stats**

Transform raw numbers into compelling competitive narratives:

- 💥 **Kill Impact Score (KIS)** — Contextual kill scoring with 10+ multipliers: carrier kills (3-5x), push quality, crossfire (1.5x), spawn timing (1-2x), outcome weight (gib/revive), class bonus, distance factor, low-health clutch, graduated reinforcement timing (0.70-1.40x)
- 🎭 **9 Player Archetypes** — Server-side classification using DPM + denied_time + headshot% + KD + trades + revives: Pressure Engine, Medic Anchor, Silent Assassin, Objective Demon, Trade Specialist, Support Fortress, Flanker, All-Rounder, Wildcard
- ⚡ **11 Match Moment Detectors** — Team wipe, multikill, kill streak, carrier chain, focus survival, push success, trade chain, objective secured, objective denied, objective run, multi-revive — each with per-kill breakdown (weapon names, timestamps, duration)
- 📈 **Momentum Chart** — 30-second window momentum scoring with 0.85 decay factor, Canvas 2D dual-line chart (Axis vs Allies), per-round tab navigation
- 📝 **Session Narrative** — Auto-generated paragraph summarizing MVP, player archetype, defining moment, and team synergy comparison
- 🤝 **Team Synergy Score** — 5-axis per-faction comparison: crossfire rate, trade coverage, cohesion quality, push success, medic bonds
- 🔫 **35-Weapon Name Mapping** — Full ET:Legacy weapon name lookup across all moment and archetype displays
- 🎬 **Legacy Story Page** — Cinematic hero, player story cards, moment timeline, KIS breakdown bars, synergy panel at `/#/story`
- 🗄️ **Backend** — `storytelling_kill_impact` DB table, 4 API endpoints, full data access pipeline

---

### **⚔️ Player Rivalries**

Deep head-to-head competitive intelligence between any two players:

- 📊 **H2H Stats** — Kills, deaths, KD ratio, accuracy, DPM head-to-head for any player pair
- 🏷️ **Nemesis / Prey / Rival Classification** — Automatically determined from win rate and encounter count
- 🔫 **Weapon Breakdown** — Which weapons each player uses most in this specific matchup
- 🗺️ **Per-Map H2H Drill-Down** — See how the rivalry plays out map by map
- 🏆 **Rivalry Leaderboard** — Top rivalry pairs ranked by total encounters
- 🌐 **Dedicated Page** — Full rivalry dashboard at `/#/rivalries`

---

### **🏆 Win Contribution (PWC / WIS / WAA)**

Quantify exactly how much each player contributed to a round win:

- 📐 **Per-Round Win Contribution (PWC)** — 5-component formula: kills, damage dealt, objectives secured, revives given, survival time
- ⚖️ **Dynamic Weight Redistribution** — When a round has zero objectives, objective weight redistributes automatically to kills and damage
- 📈 **Win Impact Score (WIS)** — avg(PWC in won rounds) − avg(PWC in lost rounds): who actually moves the needle
- 🥇 **MVP Detection** — Highest WIS player flagged as MVP per session
- 📊 **Stacked Bar Visualization** — Per-component breakdown bars for every player in every round

---

### **🔮 AI Match Predictions**

- 🤖 **Automatic Detection** — Detects when players split into team voice channels (3v3, 4v4, 5v5, 6v6)
- 🧠 **4-Factor Algorithm** — H2H (40%), Recent Form (25%), Map Performance (20%), Substitutions (15%)
- 🎯 **Confidence Scoring** — High/Medium/Low based on historical data quality
- 📊 **Real-Time Probability** — Live win probability with sigmoid scaling

**Commands:** `!predictions`, `!prediction_stats`, `!my_predictions`, `!prediction_trends`, `!prediction_leaderboard`, `!map_predictions`

---

### **📊 Player Analytics**

- 📊 **53+ Statistics Tracked** — K/D, DPM, accuracy, efficiency, headshots, damage, playtime
- 🎯 **Smart Player Lookup** — `!stats vid` or `!stats @discord_user`
- 🔗 **Interactive Linking** — React with emojis to link Discord account to game stats
- 📈 **Deep Dives** — `!consistency`, `!map_stats`, `!playstyle`, `!fatigue`
- ⚔️ **Matchup Analytics** — `!matchup A vs B`, `!duo_perf`, `!nemesis`
- 🏆 **Achievement System** — Dynamic badges for medics, engineers, sharpshooters, rambo, objective specialists
- 🎨 **Custom Display Names** — Linked players can set personalized names

### **🏆 Leaderboard System**

- 🥇 **11 Categories** — K/D, DPM, accuracy, headshots, efficiency, revives, and more
- 📈 **Dynamic Rankings** — Real-time updates as games are played
- 🎮 **Minimum Thresholds** — Prevents stat padding (min 10 rounds, 300 damage, etc.)

### **⚡ Real-Time Lua Webhook**

- 🔔 **Instant Notifications** — ~3s after round end (vs 60s SSH polling)
- 🏳️ **Surrender Timing Fix** — Stats files show wrong duration on surrender; Lua captures actual played time
- 👥 **Team Composition** — Axis/Allies player lists at round end
- ⏸️ **Pause Tracking** — Pause events with timestamps, warmup duration
- 🔄 **Cross-Reference** — Both data sources stored separately for validation

### **🤖 Full Automation**

- 🎙️ **Voice Detection** — Monitors gaming voice channels (6+ users = auto-start)
- 🔄 **SSH Monitoring** — Checks VPS every 60 seconds for new files
- 📥 **Auto-Download** — SFTP transfer with integrity verification
- 🤖 **Auto-Import** — Parse → Validate → Database (6-layer safety)
- 📢 **Auto-Post** — Round summaries posted to Discord automatically
- 🏁 **Session Summaries** — Auto-posted when players leave voice
- 💤 **Voice-Conditional** — Only checks SSH when players are in voice channels

---

## 🚀 Quick Start

### **One-Command Dev Stack (Recommended)**

```bash
git clone https://github.com/iamez/slomix.git
cd slomix
make dev
```

This starts:
- PostgreSQL (`localhost:5432`)
- Redis cache (`localhost:6379`)
- FastAPI backend (`localhost:8001` — container's `:8000` published to host `:8001`)
- Website (`http://localhost:7000` — default per `WEBSITE_PUBLIC_PORT` in `docker-compose.yml`)

Optional observability stack:

```bash
docker compose --profile observability up --build
```

This also starts Prometheus (`http://localhost:9090`) and Grafana (`http://localhost:3000`).

### **Prerequisites**

- Python 3.11+
- PostgreSQL 12+
- Docker + Docker Compose (for `make dev` workflow)
- Discord Bot Token
- (Optional) SSH access to ET:Legacy game server

### **Installation**

```bash
# Clone & install
git clone https://github.com/iamez/slomix.git
cd slomix
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Configure
cp .env.example .env
nano .env  # Set DISCORD_BOT_TOKEN, DB credentials, SSH settings

# Setup database (100+ tables)
python postgresql_database_manager.py  # Option 1: Create fresh

# Run
python -m bot.ultimate_bot
```

**Automated installer:** `sudo ./install.sh --full --auto` (PostgreSQL + systemd + bot)

**Website:** `cd website && uvicorn backend.main:app --host 0.0.0.0 --port 8000`

### **Configuration**

```env
# Required — the bot reads POSTGRES_* names only (see .env.example)
DISCORD_BOT_TOKEN=...
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=etlegacy
POSTGRES_USER=etlegacy_user
POSTGRES_PASSWORD=...

# Automation (optional but recommended)
SSH_ENABLED=true
SSH_HOST=your.server.com
SSH_PORT=22
SSH_USER=et
SSH_KEY_PATH=~/.ssh/etlegacy_bot

# Voice monitoring
AUTOMATION_ENABLED=true
GAMING_VOICE_CHANNELS=channel_id_1,channel_id_2

# Website
SESSION_SECRET=<python -c 'import secrets; print(secrets.token_urlsafe(32))'>

# Greatshot (optional)
GREATSHOT_UDT_JSON_BIN=/path/to/UDT_json
GREATSHOT_UDT_CUTTER_BIN=/path/to/UDT_cutter
GREATSHOT_STORAGE_ROOT=data/greatshot
```

See `.env.example` for all options.

---

## 📋 Commands

### **🎯 Player Stats**
`!stats <player>` · `!stats @user` · `!compare <p1> <p2>` · `!consistency` · `!map_stats` · `!playstyle` · `!fatigue` · `!find_player`

### **🏆 Leaderboards**
`!leaderboard <category>` (aliases `!lb`, `!top`) — dpm, kd, accuracy, efficiency, revives + more

### **📊 Sessions & Scoring**
`!last_session` · `!last_session graphs` · `!session` · `!rounds` · `!session_score` · `!awards` · `!season_info`

### **⚔️ Matchups & Predictions** (rivalries live on the web at `/#/rivalries`)
`!matchup A vs B` · `!duo_perf p1 p2` · `!nemesis` · `!head_to_head` · `!team_record` · `!predictions` · `!prediction_stats` · `!prediction_trends` · `!prediction_leaderboard` · `!map_predictions`

### **🔗 Account Management**
`!link` · `!unlink` · `!setname` · `!myaliases` · `!achievements` · `!badges`

### **🎮 Server Control**
`!server_status` · `!rcon <cmd>` · `!list_players` · `!list_maps` · `!map_change <name>` · `!server_start` · `!server_stop`

### **🔧 Admin**
`!sync_all` · `!sync_historical` · `!sync_today` · `!assign_teams` · `!correlation_status` · `!backup_db` · `!health` · `!start_monitoring`

**[📖 Full Command Reference: docs/COMMANDS.md](docs/COMMANDS.md)**

---

## 📁 Project Structure

```text
slomix/
├── 📊 bot/                          # Discord bot
│   ├── ultimate_bot.py              # Entry point + SSH monitor loop
│   ├── community_stats_parser.py    # Stats parser with R2 differential
│   ├── endstats_parser.py           # EndStats awards parser
│   ├── cogs/                        # 20 command modules
│   │   ├── last_session_cog.py      # Session stats & summaries
│   │   ├── leaderboard_cog.py       # Rankings
│   │   ├── analytics_cog.py         # Player analytics
│   │   ├── matchup_cog.py           # Matchup analytics
│   │   ├── predictions_cog.py       # AI predictions
│   │   ├── admin_predictions_cog.py # Prediction admin
│   │   ├── server_control.py        # RCON, status, map management
│   │   └── ... (13 more cogs)
│   ├── core/                        # Team detection, achievements, cache
│   └── services/                    # Analytics, scoring, predictions, graphs
│
├── 🎬 greatshot/                    # Demo analysis pipeline (NEW)
│   ├── scanner/                     # UDT parser adapter + demo sniffing
│   ├── highlights/                  # Multi-kill, spree, headshot detectors
│   ├── cutter/                      # UDT_cutter wrapper for clip extraction
│   ├── renderer/                    # Video render interface
│   ├── contracts/                   # Shared types, profiles, game mappings
│   └── worker/                      # Background job runner
│
├── 🌐 website/                      # Web dashboard
│   ├── backend/                     # FastAPI routers, services, greatshot workers
│   │   ├── routers/                 # api, auth, predictions, greatshot, proximity
│   │   └── services/                # greatshot_store, greatshot_jobs
│   ├── frontend/                    # React 19 + TypeScript 5.9 + Vite 7
│   │   ├── src/pages/               # 25 route pages (Sessions, Proximity, Maps, etc.)
│   │   └── src/components/          # Shared components (GlassCard, DataTable, etc.)
│   ├── static/modern/               # Built JS/CSS chunks (from npm run build)
│   ├── js/                          # Legacy JS fallback modules
│   └── index.html                   # Main SPA entry point
│
├── 🎯 proximity/                    # Teamplay analytics engine (v6.10)
│   ├── lua/                         # Game server Lua mod (positions, objectives, hit regions)
│   ├── parser/                      # Engagement + objective data parser
│   └── schema/                      # Database schema (30+ tables)
│
├── 🔧 bin/                          # Compiled binaries (UDT_json, UDT_cutter)
├── 📜 vps_scripts/                  # Game server Lua scripts
├── 📚 docs/                         # Documentation (150+ files)
├── 🧪 tests/                        # Test suite
├── postgresql_database_manager.py   # ALL database operations (one tool to rule them all)
└── install.sh                       # Automated VPS installer
```

**Key Files:**

| File | Purpose |
|------|---------|
| `bot/ultimate_bot.py` | Main entry point, SSH monitor, 20 cog loader |
| `bot/community_stats_parser.py` | R1/R2 differential parser (53+ fields) |
| `postgresql_database_manager.py` | All DB operations: create, import, rebuild, validate |
| `bot/core/database_adapter.py` | Async PostgreSQL adapter with connection pooling |
| `bot/services/prediction_engine.py` | AI match prediction engine (4-factor algorithm) |
| `website/backend/main.py` | FastAPI app with auth, routers, greatshot job workers |
| `greatshot/scanner/api.py` | Demo analysis entry point (UDT → events → highlights) |
| `vps_scripts/stats_discord_webhook.lua` | Game server Lua script (v1.7.1) |

---

## 🗄️ Database Schema

### **PostgreSQL — 101 Tables**

```sql
-- Core Stats (7)
rounds                          -- Round metadata, gaming_session_id, match_id
player_comprehensive_stats      -- 57 columns per player per round
weapon_comprehensive_stats      -- Per-weapon breakdown
processed_files                 -- File tracking with SHA256 hash
player_links                    -- Discord ↔ game account links
player_aliases                  -- Name change tracking
session_teams                   -- Persistent team assignments

-- Lua Webhook (2)
lua_round_teams                 -- Real-time data from game server Lua
lua_spawn_stats                 -- Per-player spawn/death timing

-- Round Detail (4)
round_awards                    -- EndStats awards (7 categories)
round_vs_stats                  -- Player VS player kill/death records
round_correlations              -- R1+R2 data completeness tracking (23 cols)
processed_endstats_files        -- EndStats file tracking

-- Competitive Analytics (3)
match_predictions               -- AI predictions (35 columns, 6 indexes)
session_results                 -- Session outcomes with team compositions
map_performance                 -- Player per-map rolling averages

-- Greatshot (4)
greatshot_demos                 -- Uploaded demo files with status tracking
greatshot_analysis              -- Parsed analysis (metadata, stats, events)
greatshot_highlights            -- Detected highlights with scores
greatshot_renders               -- Video render jobs and output paths

-- Proximity (12+)
combat_engagement               -- Combat encounter tracking
crossfire_pairs                 -- Crossfire detection
proximity_spawn_timing          -- Spawn wave timing analysis
proximity_team_cohesion         -- Team cohesion timeline
proximity_crossfire_opportunity -- Crossfire setups
proximity_team_push             -- Coordinated pushes
proximity_lua_trade_kill        -- Trade kill detection
player_teamplay_stats           -- Teamplay metrics
player_track                    -- Movement data + heatmaps

-- Website & Infrastructure (20+)
server_status_history, voice_members, availability_*, uploads_*
```

**Gaming Session ID:** Automatically calculated — 60-minute gap between rounds = new session.

---

## 🛠️ Development

### **Database Operations**

```bash
python postgresql_database_manager.py
# 1 - Create fresh database (100+ tables + indexes + seed data)
# 2 - Import all files from local_stats/
# 3 - Rebuild from scratch (wipes game data + re-imports)
# 4 - Fix specific date range
# 5 - Validate database (7-check validation)
# 6 - Quick test (10 files)
```

⚠️ **IMPORTANT:** Never create new import/database scripts. This is the **ONLY** tool for database operations.

### **Running Tests**

```bash
# Parser test
python bot/community_stats_parser.py local_stats/sample-round-1.txt

# Database validation
python postgresql_database_manager.py  # Option 5

# Greatshot tests
pytest tests/test_greatshot_highlights.py
pytest tests/test_greatshot_scanner_golden.py

# Discord bot health
!ping    # Latency
!health  # System health check
```

---

## 📚 Documentation Index

### **Getting Started**
- [docs/DEPLOYMENT_CHECKLIST.md](docs/DEPLOYMENT_CHECKLIST.md) — Deployment guide
- [docs/FRESH_INSTALL_GUIDE.md](docs/FRESH_INSTALL_GUIDE.md) — Fresh installation

### **Architecture & Data**
- [docs/DATA_PIPELINE.md](docs/DATA_PIPELINE.md) — Complete data pipeline
- [docs/SAFETY_VALIDATION_SYSTEMS.md](docs/SAFETY_VALIDATION_SYSTEMS.md) — 6-layer validation
- [docs/ROUND_2_PIPELINE_EXPLAINED.txt](docs/ROUND_2_PIPELINE_EXPLAINED.txt) — Differential calculation
- [docs/reference/TIMING_DATA_SOURCES.md](docs/reference/TIMING_DATA_SOURCES.md) — Stats file vs Lua timing

### **Reference**
- [docs/COMMANDS.md](docs/COMMANDS.md) — All 100+ bot commands
- [CHANGELOG.md](CHANGELOG.md) — Version history (canonical)
- [docs/CLAUDE.md](docs/CLAUDE.md) — Full technical reference

---

## 🙏 Acknowledgments

**Built With:**

- [discord.py](https://github.com/Rapptz/discord.py) — Discord API wrapper
- [asyncpg](https://github.com/MagicStack/asyncpg) — PostgreSQL async driver
- [FastAPI](https://fastapi.tiangolo.com/) — Web framework
- [PostgreSQL](https://www.postgresql.org/) — Production database
- [UberDemoTools](https://github.com/mightycow/uberdemotools) — Demo parser

**Special Thanks:**

- **[x0rnn (c0rn)](https://github.com/x0rnn)** — for `gamestats.lua` and the endstats system that generates the stats files this entire platform is built on
- **[Kimi (mittermichal)](https://github.com/mittermichal/greatshot-web)** — for developing Greatshot, the demo analysis tool whose architecture we studied, adapted, and integrated into our system. The highlight detection, event normalization, and pipeline design are his work. We built the bridge; he built the engine.
- **[ryzyk-krzysiek](https://github.com/mightycow/uberdemotools/pull/2)** — for adding ET:Legacy protocol 84/284 support to UberDemoTools
- **[mightycow](https://github.com/mightycow/uberdemotools)** — for UberDemoTools itself
- **[ET:Legacy](https://www.etlegacy.com/)** team — for keeping the game alive after 22 years

---

## 📞 Contact

**Project Maintainer:** [@iamez](https://github.com/iamez)
**Repository:** [github.com/iamez/slomix](https://github.com/iamez/slomix)

---

<div align="center">

**⭐ Star this repo if it helped you!**

Built with ❤️ for the ET:Legacy community

</div>
