> Research agent report (R2, 2026-06-11) — best-in-class stats UX patterns.
> Input for docs/VISION_2026.md. Sources inline.

# UX & Information-Architecture Patterns from Best-in-Class Sports/Esports Stats Products
## Research report for slomix.fyi (private W:ET community, 10–30 players, 3v3/6v6 stopwatch evenings)

**Method:** 16 web searches + targeted page fetches across Leetify, Mobalytics, op.gg/u.gg, HLTV, Sofascore, Tracker.gg, FACEIT, Strava, Whoop, Spotify Wrapped, NN/g, and dashboard-design literature. Every pattern includes a source URL and a concrete mapping to an existing slomix page.

---

## 0. Cross-cutting principles (the three ideas that explain everything below)

**P0.1 — Shneiderman's mantra: "Overview first, zoom and filter, details on demand."**
The single most consistent IA pattern across every product studied. Dashboards should show summaries first and use drill-downs rather than displaying everything on one screen; the most common details-on-demand implementation is the tooltip. ([UXPin dashboard principles](https://www.uxpin.com/studio/blog/dashboard-design-principles/), [Shneiderman mantra overview](https://jtr13.github.io/cc21/ben-shneidermans-visualization-mantra.html))
→ **slomix mapping (sitewide):** slomix's strength is depth (proximity, journeys, wave-cycle ledgers) but its risk is showing depth *first*. Every page should open with 3–5 headline numbers/verdicts and push current dense panels one click down. This is the framing principle for everything below.

**P0.2 — Frame data as identity, not measurement.**
Spotify Wrapped doesn't say "47,283 minutes," it says "you spent 788 hours finding yourself" — identical data, different framing; it picks *few* highlights and makes them about who you are. ([UX Playbook on Wrapped](https://uxplaybook.org/articles/spotify-wrapped-ux-design-lessons), [data-storytelling analysis](https://medium.com/@sharathckottam9/the-tech-behind-the-feels-why-spotify-wrapped-is-a-masterclass-in-data-storytelling-0337e0aa6481))
→ **slomix mapping:** the smart-stats/story page already has narratives and kill-impact — the missing piece is *identity framing* ("You were the entry fragger tonight", "Your wave-cycle discipline carried Round 2") rather than metric recitation.

**P0.3 — A 10–30-player community is a *social* product, not an analytics product.**
Leetify explicitly positions match reports as helping users "uncover narratives to discuss after the match" and "compare accomplishments with friends" ([leetify.com](https://leetify.com/)). For a private community, the comparison set ("vs. our group's average," "vs. your last 10 sessions") is more meaningful than any absolute number.

---

## 1. Post-match report flow — "what happened + what it means for YOU"

### Pattern 1.1 — Verdict-first rating with bell-curve context (Leetify)
Leetify's hierarchy is: **Overall Rating → bell-curve context (Great/Good/Average/Subpar/Poor) → round breakdown → action-level details.** The headline is a single zero-centered number, immediately contextualized on a distribution so the player knows *is this good?* before seeing *why*. ([Leetify Rating explained](https://leetify.com/blog/leetify-rating-explained/))
→ **Mapping — Session Detail page:** add a per-player "session verdict" strip at the top of session detail: one composite number (you already have kill-impact scores) placed on the *community's* distribution ("top 20% of your last 30 sessions"). Team matrix and per-map tables move below the fold.

### Pattern 1.2 — Three-step drill-down: round timeline → category attribution → consistency vs. your own baseline (Leetify Rating Breakdown)
The Rating Breakdown tab has exactly three sections: (1) **Rating by Round** — bars showing each round's win-probability contribution; (2) **Rating Gained & Lost** — hover a round to see *which category* you were rewarded/punished for, summed into "areas you excel at / areas to work on"; (3) **Consistency** — this game vs. your 60-match average, split by side. ([Rating Breakdown guide](https://leetify.com/blog/rating-breakdown/))
→ **Mapping — Smart-stats/Story page:** restructure the kill-impact display into this exact 3-layer flow: momentum chart (you have it) → click a spike to see which *category* drove it (frags, revives, objective time — from proximity data) → "vs. your average over last 10 sessions, Axis/Allies split." The third layer (self-baseline comparison) is the cheapest to add and the highest value: it answers "was tonight good *for me*?"

### Pattern 1.3 — Performance graded against a relevant cohort, not absolutes (op.gg post-game analysis)
op.gg's post-game screen grades performance across multiple metrics **compared against the average for your champion and rank** — every number arrives pre-contextualized. Its OP Score is computed on a rolling timeline (every 3–5 min) so the *trajectory* of performance is visible, not just the total. ([op.gg match detail docs](https://help.op.gg/hc/en-us/articles/31091817743129-Viewing-detailed-match-data), [OP Score explained](https://help.op.gg/hc/en-us/articles/31088715328665-What-is-OP-Score), [op.gg features guide](https://www.wombocombo.gg/blog/game-analytics/opgg-features-complete-guide))
→ **Mapping — Session Detail / competitive card:** for each stat shown post-session, render the delta vs. (a) the player's own trailing average and (b) the community average for that map/side. A small ▲/▼ + percentile chip next to each number is enough; no new charts needed.

### Pattern 1.4 — Skill scores → one prioritized piece of advice (Mobalytics GPI)
Mobalytics scores 8 skill areas 0–100 via ML, presents them as a radar diagram (icons, click-to-drill), and converts the *weakest* area into specific written advice ("improve your Dueling score from 50 to 70," "focus on farming in the early game") — coaching philosophy: beginners should focus on **one thing**. ([GPI overview](https://mobalytics.gg/gpi/), [how GPI advice is created](https://mobalytics.gg/blog/how-mobalytics-gpi-advice-is-created-and-given-to-you/), [GPI score reading](https://support.mobalytics.gg/hc/en-us/articles/115001840411-What-is-a-GPI-How-do-I-read-my-GPI-score), [Mobalytics 2.0 UX changelog](https://medium.com/mobalytics/changelog-2-0-12-04-2018-b68cf5786b62))
→ **Mapping — Player profile competitive card:** you already compute 9–15 metric percentiles (ET Rating). Add one auto-generated "focus line" under the card: pick the player's lowest percentile dimension and phrase it as a single sentence with a target ("Your trade-kill rate is your weakest area — 34th percentile; getting to 50th would have flipped 2 rounds last session," wired from wave-cycle/crossfire data). One sentence, not a coaching essay.

### Pattern 1.5 — Post-match self-report correlation (Leetify Post-Match Journal)
Leetify prompts yes/no questions after each match ("Did I sleep well?"), then correlates answers with win rate, displaying **confidence intervals rather than definitive claims** that converge as data accumulates. Prompts appear inline in the match report; batch-answering is supported. ([Post-Match Journal](https://leetify.com/blog/post-match-journal/))
→ **Mapping — Availability page / session detail:** low priority but uniquely suited to a small community: a one-tap "how did tonight feel?" (😫/😐/🔥) on session detail, correlated over time with performance. With 2–3 sessions/week the dataset builds fast and gives the story page another narrative input ("You play 0.4 KIS better on Fridays").

---

## 2. Player profile information architecture

### Pattern 2.1 — Identity header: photo + 4–5 headline stats, everything else linked (HLTV)
HLTV's redesigned player profile leads with the player's photo and exactly five numbers (Age, Team, Rating, Maps played, KPR/DPR), then deliberately becomes "less stats oriented and more general" — achievements, trophies, gallery, links out to deep stats pages. Stats live one click away, not on the profile itself. ([HLTV announcement](https://www.hltv.org/news/17402/introducing-new-player-profiles))
→ **Mapping — Player profile:** slomix's profile is currently a long scroll of dense panels (weapons, hit regions, aim rose, combat timing). Adopt the HLTV split: a compact identity header (avatar/Discord badge, ET Rating + tier, K/D, sessions played, signature weapon, current streak) followed by **tabs**: Overview / Combat (weapons + hit regions + aim rose) / Timing / Movement (proximity) / History. The aim rose and hit regions are "details on demand," not headline content.

### Pattern 2.2 — Attributes ("what type of player"), not just stats (HLTV attributes, Sofascore Attribute Overview)
HLTV's newest profile feature is **attributes** — "what type of player the player is rather than showing stats" ([HLTV stats](https://www.hltv.org/stats), [HLTV app listing](https://apps.apple.com/us/app/hltv-org/id1078945675)). Sofascore distinguishes the same way: Attribute Overview "indicates a player's overall potential and strengths," explicitly *different* from stat overviews with concrete numbers. ([Sofascore player performance guide](https://www.sofascore.com/news/football-player-performance-how-to-use-heatmaps-stats-and-attribute-overviews-to-measure-contribution))
→ **Mapping — Player profile + Hall of Fame:** you already researched player archetypes (smart-storytelling architecture). Ship the archetype label *on the profile header* — "Aggressive Entry / Objective Anchor / Lurker" — derived from proximity + timing data, with a small radar. In a 10–30-person community, archetype labels become social currency ("our lurker") far beyond what another table delivers.

### Pattern 2.3 — Per-champion/per-weapon row summaries sorted by volume, with filters (op.gg champions tab)
op.gg lists every champion played this season sorted by games, each row showing games/win rate/KDA/CS — a scannable "what do I actually play" view, with tier/role/mode filters. ([op.gg features guide](https://www.wombocombo.gg/blog/game-analytics/opgg-features-complete-guide))
→ **Mapping — Player profile:** add a "Maps" mini-table to the profile Overview tab: per-map rows (games, win rate, KIS avg, best side), sorted by games played. You have the data; this is the most-asked casual question ("which map am I actually good on?") and currently requires manual session archaeology.

### Pattern 2.4 — Time-range selector as first-class control (op.gg session stats; Whoop trends)
op.gg's overlay shows *current-session* stats explicitly because momentum-now beats lifetime aggregates psychologically ([op.gg features guide](https://www.wombocombo.gg/blog/game-analytics/opgg-features-complete-guide)); Whoop frames every weekly number against the 3-week trailing average ([Whoop WPA](https://www.whoop.com/eu/en/thelocker/new-weekly-performance-assessment/)).
→ **Mapping — Player profile:** add one global scope switcher at the top of the profile: **Last session / Last 10 sessions / This season / All time** — and make *Last 10 sessions* the default, not all-time. All-time aggregates hide form; a community playing 2–3×/week cares about form. (You already have `gaming_session_id` scoping in the backend; this is mostly a frontend control.)

### Pattern 2.5 — Career timeline & trophies (HLTV; Sofascore season list)
HLTV profiles show trophies and seasonal achievements; Sofascore lists per-competition season rows (rating, matches, goals) as a career spine. ([HLTV profiles](https://www.hltv.org/news/17402/introducing-new-player-profiles), [Sofascore player page](https://www.sofascore.com/player/heung-min-son/111505))
→ **Mapping — Player profile History tab + Awards:** render a vertical timeline of the player's ET Rating per month with award icons pinned at the session where they were earned (you already have `player_skill_history` + the awards system). This converts two disconnected pages (profile, awards) into one career narrative.

---

## 3. Live UX — minimum viable "tonight's session live hub"

### Pattern 3.1 — Attack Momentum: one real-time chart that answers "who's winning *right now*" (Sofascore)
Sofascore's signature live element is a single rising/falling pressure graph computed from event stream (shots, dangerous-zone entries, set pieces), valuable precisely because it lets fans follow the match "without needing extensive statistics." ([How Attack Momentum changed sport analysis](https://www.sofascore.com/news/how-sofascores-attack-momentum-changed-sport-analysis))
→ **Mapping — new "Tonight" view (extension of Sessions):** slomix already computes momentum post-hoc on the story page. The MVP live hub is: current map + round, team scores, and a *live-updating* version of the existing momentum chart fed from the Lua webhook events. Don't build a live scoreboard with 20 columns — one chart + score is the Sofascore lesson.

### Pattern 3.2 — Win-probability line as live narrative (ESPN NBA gametracker, inpredictable)
ESPN publishes live win-probability graphs updating "in real time following every play"; the chart itself *is* the story of the game — comebacks read as visible cliffs. ([ESPN analytics/WPA](https://espnanalytics.com/wnba-wpa/), [inpredictable live WP boxes](http://stats.inpredictable.com/nba/wpBox_live.php))
→ **Mapping — Tonight view / session detail:** for stopwatch ET, a simple "hold probability" line per round (derived from your stagger/first-blood/wave-cycle analytics: men alive differential, spawn timing, objective progress) replayed live, then frozen into the session-detail recap. Even a crude heuristic line gives spectators-from-phone something to watch between rounds.

### Pattern 3.3 — Polling conventions: 2–5 s perceived-live frontend, simple transport (industry consensus)
Flashscore refreshes every 2–3 s, Sofascore every 3 s, ESPN 5–8 s; for the backend, SSE is recommended over WebSockets for score feeds (auto-reconnect via `Last-Event-ID`, plain HTTP, no sticky sessions). ([Sportmonks live-score architecture](https://www.sportmonks.com/blogs/how-to-build-a-live-score-app-architecture-for-sub-second-updates/), [Sportmonks livescore best practices](https://www.sportmonks.com/blogs/building-a-real-time-livescore-app-with-a-football-api-best-practices/))
→ **Mapping — Tonight view:** for 10–30 users, plain **5–10 s polling of a tiny JSON endpoint** (score, round clock, momentum array tail) is fully within convention — no WebSocket infrastructure needed. SSE from FastAPI is the upgrade path if round events should push instantly. Key conventional detail: show a "LIVE" pulse dot + last-updated timestamp so users trust the feed.

### Pattern 3.4 — Round-history strip (HLTV live scoreboard)
HLTV/CS live pages show a compact per-round icon strip (who won each round, how) with economy indicators — the at-a-glance match story during play. ([HLTV livescore introduction](https://www.hltv.org/news/18733/introducing-livescore-and-filtering), [HLTV matches](https://www.hltv.org/matches))
→ **Mapping — Tonight view + Session detail:** a horizontal strip of map-chips for tonight: each completed map shows winner color + hold time; the in-progress map pulses. You already built the per-life timeline strip on Player Journey — same visual grammar, session level. This strip then becomes the header of the session-detail page after the night ends (live artifact = recap artifact, zero duplicate work).

---

## 4. Community hub home page — above the fold for a returning member

### Pattern 4.1 — Three-zone front page: now / next / what you missed (HLTV)
HLTV's front page is matches-now + upcoming (with live scores), latest results, news, and rankings in fixed sidebars — a returning visitor's three questions (anything live? what happened? what's next?) answered without scrolling, layout consistent across redesigns. ([HLTV front](https://www.hltv.org/), [HLTV redesign notes](https://www.hltv.org/news/20530/a-new-beginning-for-hltvorg))
→ **Mapping — Home page:** restructure home into exactly three above-the-fold cards: **(1) Next session** — next availability-poll date + who's in (pull from your availability system); **(2) Last session recap** — winner, score, MVP, one-line narrative, link to session detail; **(3) Movers** — top 3 ET-Rating gainers/losers since last session. Leaderboard teaser and everything else below.

### Pattern 4.2 — "Movers" / form deltas as the returning-member hook (op.gg session stats; Whoop trends logic)
The pattern across products: returning users engage with *change*, not state — op.gg surfaces current-session momentum ([op.gg features guide](https://www.wombocombo.gg/blog/game-analytics/opgg-features-complete-guide)); Whoop's weekly assessment compares everything to your trailing average ([Whoop WPA](https://www.whoop.com/eu/en/thelocker/new-weekly-performance-assessment/)).
→ **Mapping — Home page Movers card:** "▲ olympus +14 rating · ▲ superboyy first-ever 2.0 KIS night · ▼ ez 3-session slump." You have `player_skill_history` per session — this is a single query. For a private community this card *is* the morning-after conversation starter in Discord.

### Pattern 4.3 — Hub identity block: rules, format, join state (FACEIT hubs)
FACEIT hub pages lead with identity (banner, name, description, requirements) and one primary action; the dashboard sorts hubs by *most active*. ([FACEIT organizer page setup](https://support.faceit.com/hc/en-us/articles/115000014604-Creating-setting-up-your-organizer-page), [FACEIT hub example](https://www.faceit.com/en/hub/b9346b6a-f464-4034-800e-b2a50d5eace3/Faceit%20Community%20Hub))
→ **Mapping — Home page:** minor but cheap: a small standing block with the community's cadence ("3v3/6v6 stopwatch · Tue/Thu/Sun 21:00 CET") and a single CTA that flips state: "Vote availability" before the poll closes → "Session live — watch" during play → "Read last night's recap" after. One button whose label tracks the community's lifecycle.

### Pattern 4.4 — Grassroots-club guidance: seasonal front-and-center, weekly updates, functionality over flash
Youth/club site best practice converges on: put the *currently relevant* thing front and center (registration pre-season, schedule in-season), keep navigation shallow, update weekly. ([PlayMetrics youth sports best practices](https://home.playmetrics.com/blog/youth-sports-website-best-practices), [Clubforce club website guide](https://clubforce.com/latest-news/the-ultimate-how-to-guide-to-sports-club-websites-in-2023/))
→ **Mapping — Home page:** validates the three-card design above; also argues the home page should be *time-aware* (the Tonight card auto-promotes to the top slot on session evenings).

---

## 5. Mobile reality — morning-after phone check

### Pattern 5.1 — Bottom tab bar, 4 items, always labeled (NN/g, Material/HIG consensus)
Bottom navigation is the recommended primary-nav pattern: thumb-reachable, 3–5 items max (4 is the sweet spot), always with text labels — NN/g found hidden menus decrease task completion/discoverability by ~21%. ([NN/g mobile navigation patterns](https://www.nngroup.com/articles/mobile-navigation-patterns/), [UXPin mobile navigation](https://www.uxpin.com/studio/blog/mobile-navigation-examples/), [DesignStudio mobile nav UX](https://www.designstudiouiux.com/blog/mobile-navigation-ux/))
→ **Mapping — sitewide (vanilla JS shell):** on <768px, render a fixed bottom bar with exactly four labeled tabs: **Home · Last Session · Me (profile) · Boards**. Everything else (proximity, uploads, records, awards) goes behind a fifth "More" item. This is the highest-impact mobile change available — no page rewrites required, just a nav shell.

### Pattern 5.2 — Collapse tables to cards; preserve hierarchy by demoting secondary stats
The standard responsive-table pattern: each row becomes a card (rows→columns), showing the primary column by default with tap-to-expand; the failure mode is flat cards where everything has equal weight — secondary/tertiary stats must be visually de-emphasized. Horizontal scroll with a cut-off-column affordance is the fallback when cross-row comparison matters. ([5 practical responsive-table solutions](https://medium.com/appnroll-publication/5-practical-solutions-to-make-responsive-data-tables-ff031c48b122), [LightIT responsive tables UX](https://lightit.io/blog/responsivetables/), [responsive patterns demo](https://tools.simonwillison.net/mobile-tables))
→ **Mapping — Leaderboards + Session detail team matrix:** leaderboard rows → cards on mobile: rank + name + ONE headline stat large; KDR/accuracy/etc. in a muted second line; tap expands. The team matrix is the exception — it's a comparison grid, so keep it as a horizontally scrollable table with a sticky player-name column and a visible cut-off column edge.

### Pattern 5.3 — Mobile = recap consumption, not analysis (HLTV mobile philosophy)
HLTV's mobile design targets "quick access to matches with livescores, results, and the latest news," with deep stats as secondary exploration. ([HLTV mobile beta](https://www.hltv.org/news/12141/new-mobile-design-now-in-beta), [HLTV redesign](https://www.hltv.org/news/20530/a-new-beginning-for-hltvorg))
→ **Mapping — prioritization rule:** make exactly three flows excellent on mobile and let the rest be "best on desktop": (1) home three-card scan, (2) last-session recap incl. story page, (3) own profile header + focus line. Proximity heatmaps/journeys can legitimately show a "best viewed on desktop" hint — Player Journey canvases shouldn't block the mobile budget.

### Pattern 5.4 — Story-format recap optimized for screenshots (Wrapped, Strava)
Wrapped cards are explicitly designed for screenshot sharing (aspect ratio, typography, contrast chosen for Instagram); Strava's Year in Sport uses a tappable story carousel (Lottie/JSON animations) with a share button on every scene. ([UX Playbook on Wrapped](https://uxplaybook.org/articles/spotify-wrapped-ux-design-lessons), [It's Nice That on Strava × Manual](https://www.itsnicethat.com/articles/manual-strava-year-in-sport-graphic-design-150321), [Strava Year in Sport support](https://support.strava.com/hc/en-us/articles/22067973274509-Your-Year-in-Sport))
→ **Mapping — Session detail / story page:** add one **share-card render**: a 1080×1920-proportioned "session card" (date, map list, score, MVP, one stat, one narrative line) generated to canvas with a "copy image" button. The destination is the community's Discord channel — this closes the loop between the site and where the community actually talks.

---

## 6. Data storytelling — structure of a great auto-generated recap

### Pattern 6.1 — Sports-recap canonical structure (AP/NLG systems)
Automated recap systems encode the sportswriting skeleton: **results-oriented lede (winner + score) → how it was won/lost → key moments in sequence → standout performances → context/implications.** AP runs this for every minor-league baseball game; WSC Sport generates narrated recaps in 1–2 minutes from event data. ([ZenML on WSC Sport LLM commentary](https://www.zenml.io/llmops-database/automated-sports-commentary-generation-using-llms), [AWS sports-narrative NLG](https://aws.amazon.com/blogs/machine-learning/enhance-sports-narratives-with-natural-language-generation-using-amazon-sagemaker/))
→ **Mapping — Story page generator:** make your narrative generator follow this exact five-beat template per session: (1) lede: "Allies took the night 5–3"; (2) mechanism: "won on faster full-holds — average hold 4:12 vs 6:30" (BOX/stopwatch data); (3) moments: top-3 momentum swings from the existing chart, each with timestamp + actor; (4) standouts: MVP + one surprising performer (biggest positive deviation from own baseline, not just top fragger); (5) implication: streaks/records touched ("supy's 3rd straight MVP — one short of the record"). Each beat links to the page that evidences it (session detail, records, profile).

### Pattern 6.2 — Few highlights, identity-framed, sequenced as a story (Spotify Wrapped)
Wrapped's structure: a handful of curated highlights (top artists, minutes, top song) in a fixed narrative sequence, framed as identity, with deliberate scarcity — "clarity beats complexity"; anticipation/annual ritual amplifies it. ([UX Playbook](https://uxplaybook.org/articles/spotify-wrapped-ux-design-lessons), [psychology of Wrapped](https://medium.com/design-bootcamp/why-were-hooked-on-spotify-wrapped-the-perfect-blend-of-ux-and-psychology-b4aa06c9b81f))
→ **Mapping — new "Season Wrapped" (Awards/HOF extension):** quarterly/seasonal per-player wrapped: 6–8 cards max — total rounds, signature map, signature weapon, archetype, best night, nemesis & best-duo teammate (proximity + matchup data), one record held. Tie to your existing season_manager. This is the single feature with the highest community-delight-per-effort given the data already exists.

### Pattern 6.3 — Yearly recap as aggregation of personal bests + social graph (Leetify Recap)
Leetify's annual recap aggregates rank progression, **best-winrate friends**, longest win/loss streaks, and personal-best games. ([Leetify 2024 recap](https://leetify.com/2024), [progress report](https://leetify.com/progress-report))
→ **Mapping — Hall of Fame / Awards:** the "best-winrate teammate" angle is uniquely powerful in a fixed 10–30-player pool: surface duo synergy ("you + olympus: 71% together, 44% apart") in wrapped cards and on the matchup page. You already have team assignment per round; this is a join, not a new pipeline.

### Pattern 6.4 — Trailing-baseline framing for every number (Whoop WPA/MPA)
Whoop's weekly assessment compares each metric to the 3-week average and to the community; its monthly report renders strain/recovery balance as an annotated time series with sustained deviations highlighted in color. Insight = deviation from *your own* baseline, rendered visually. ([Whoop WPA](https://www.whoop.com/eu/en/thelocker/new-weekly-performance-assessment/), [Whoop MPA](https://www.whoop.com/eu/en/thelocker/monthly-performance-assessment/))
→ **Mapping — Story page + profile:** adopt as a *writing rule* for all generated narrative: never state a raw number without its baseline delta ("23 frags — 6 above your usual"). Implement once as a helper (`format_with_baseline(stat, trailing_avg)`) used by every narrative template.

### Pattern 6.5 — Uncertainty-honest insights (Leetify journal confidence intervals)
Leetify displays correlations with confidence intervals "rather than definitive claims," converging as data accumulates. ([Post-Match Journal](https://leetify.com/blog/post-match-journal/))
→ **Mapping — Story page:** for small-sample insights (10–30 players, short sessions), tag generated claims with sample size ("based on 7 sessions") or suppress below a threshold. Protects the story page's credibility — the main currency an auto-narrator has with a community that knows the ground truth firsthand.

---

## 7. Prioritized adoption roadmap for slomix.fyi

| # | Change | Pattern(s) | Page | Effort |
|---|--------|-----------|------|--------|
| 1 | Home → three cards: Next session / Last night recap / Movers | 4.1, 4.2, 4.3 | Home | S |
| 2 | Mobile bottom tab bar (Home · Last Session · Me · Boards) + leaderboard cards | 5.1, 5.2 | sitewide, Leaderboards | S–M |
| 3 | Profile: identity header + tabs + default scope "last 10 sessions" + per-map mini-table | 2.1, 2.3, 2.4 | Player profile | M |
| 4 | Session detail: verdict strip (rating + distribution) on top, baseline deltas on every stat | 1.1, 1.3, 6.4 | Session detail | M |
| 5 | Story generator: five-beat AP template + baseline-delta writing rule + sample-size tags | 6.1, 6.4, 6.5 | Story page | M |
| 6 | One-sentence "focus line" from weakest percentile dimension | 1.4 | Profile competitive card | S |
| 7 | Shareable session card (canvas render → Discord) | 5.4 | Session detail | S–M |
| 8 | "Tonight" live hub: score + map-chip strip + live momentum, 5–10 s polling | 3.1, 3.3, 3.4 | new (Sessions) | M–L |
| 9 | Archetype labels + duo-synergy stats | 2.2, 6.3 | Profile, Matchup | M |
| 10 | Season Wrapped (6–8 cards/player/quarter) | 6.2, 6.3 | Awards/HOF | L |
| 11 | Career timeline (rating sparkline + pinned awards) | 2.5 | Profile History | M |
| 12 | Hold-probability line (live + recap replay) | 3.2 | Tonight, Session detail | L |

**The one-paragraph thesis:** slomix already has deeper data than most commercial products studied; the gap is purely architectural. Best-in-class products all do the same three things slomix doesn't yet: they put a **contextualized verdict before evidence** (Leetify), they default every number to **comparison against your own recent baseline and your community** (op.gg, Whoop), and they convert the same data into a **few identity-framed, shareable story beats** (Wrapped, Strava, AP recaps). For a 10–30-player community, optimize for the morning-after phone check and the Discord conversation — recap-first mobile flows and shareable cards — and let the proximity depth remain the desktop rabbit hole it's good at being.

Sources: [Leetify Rating explained](https://leetify.com/blog/leetify-rating-explained/) · [Leetify Rating Breakdown](https://leetify.com/blog/rating-breakdown/) · [Leetify Post-Match Journal](https://leetify.com/blog/post-match-journal/) · [Leetify 2024 Recap](https://leetify.com/2024) · [Leetify home](https://leetify.com/) · [Mobalytics GPI](https://mobalytics.gg/gpi/) · [Mobalytics GPI advice](https://mobalytics.gg/blog/how-mobalytics-gpi-advice-is-created-and-given-to-you/) · [Mobalytics GPI reading guide](https://support.mobalytics.gg/hc/en-us/articles/115001840411-What-is-a-GPI-How-do-I-read-my-GPI-score) · [Mobalytics 2.0 changelog](https://medium.com/mobalytics/changelog-2-0-12-04-2018-b68cf5786b62) · [op.gg match detail](https://help.op.gg/hc/en-us/articles/31091817743129-Viewing-detailed-match-data) · [OP Score](https://help.op.gg/hc/en-us/articles/31088715328665-What-is-OP-Score) · [op.gg features guide](https://www.wombocombo.gg/blog/game-analytics/opgg-features-complete-guide) · [HLTV new player profiles](https://www.hltv.org/news/17402/introducing-new-player-profiles) · [HLTV livescore](https://www.hltv.org/news/18733/introducing-livescore-and-filtering) · [HLTV redesign](https://www.hltv.org/news/20530/a-new-beginning-for-hltvorg) · [HLTV mobile beta](https://www.hltv.org/news/12141/new-mobile-design-now-in-beta) · [Sofascore Attack Momentum](https://www.sofascore.com/news/how-sofascores-attack-momentum-changed-sport-analysis) · [Sofascore heatmaps & attributes](https://www.sofascore.com/news/football-player-performance-how-to-use-heatmaps-stats-and-attribute-overviews-to-measure-contribution) · [ESPN WPA](https://espnanalytics.com/wnba-wpa/) · [inpredictable live WP](http://stats.inpredictable.com/nba/wpBox_live.php) · [Sportmonks live-score architecture](https://www.sportmonks.com/blogs/how-to-build-a-live-score-app-architecture-for-sub-second-updates/) · [Sportmonks livescore best practices](https://www.sportmonks.com/blogs/building-a-real-time-livescore-app-with-a-football-api-best-practices/) · [FACEIT organizer pages](https://support.faceit.com/hc/en-us/articles/115000014604-Creating-setting-up-your-organizer-page) · [NN/g mobile nav patterns](https://www.nngroup.com/articles/mobile-navigation-patterns/) · [UXPin mobile navigation](https://www.uxpin.com/studio/blog/mobile-navigation-examples/) · [Responsive tables (App'n'roll)](https://medium.com/appnroll-publication/5-practical-solutions-to-make-responsive-data-tables-ff031c48b122) · [LightIT responsive tables](https://lightit.io/blog/responsivetables/) · [UX Playbook on Wrapped](https://uxplaybook.org/articles/spotify-wrapped-ux-design-lessons) · [Wrapped data storytelling](https://medium.com/@sharathckottam9/the-tech-behind-the-feels-why-spotify-wrapped-is-a-masterclass-in-data-storytelling-0337e0aa6481) · [Wrapped psychology](https://medium.com/design-bootcamp/why-were-hooked-on-spotify-wrapped-the-perfect-blend-of-ux-and-psychology-b4aa06c9b81f) · [Strava Year in Sport](https://support.strava.com/hc/en-us/articles/22067973274509-Your-Year-in-Sport) · [Strava × Manual design](https://www.itsnicethat.com/articles/manual-strava-year-in-sport-graphic-design-150321) · [Whoop WPA](https://www.whoop.com/eu/en/thelocker/new-weekly-performance-assessment/) · [Whoop MPA](https://www.whoop.com/eu/en/thelocker/monthly-performance-assessment/) · [WSC Sport LLM recaps](https://www.zenml.io/llmops-database/automated-sports-commentary-generation-using-llms) · [AWS sports NLG](https://aws.amazon.com/blogs/machine-learning/enhance-sports-narratives-with-natural-language-generation-using-amazon-sagemaker/) · [UXPin dashboard principles](https://www.uxpin.com/studio/blog/dashboard-design-principles/) · [Shneiderman mantra](https://jtr13.github.io/cc21/ben-shneidermans-visualization-mantra.html) · [PlayMetrics youth sports sites](https://home.playmetrics.com/blog/youth-sports-website-best-practices) · [Clubforce club website guide](https://clubforce.com/latest-news/the-ultimate-how-to-guide-to-sports-club-websites-in-2023/)
