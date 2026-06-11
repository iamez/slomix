> Research agent report (R1, 2026-06-11) — engagement mechanics for small
> competitive communities. Input for docs/VISION_2026.md. Sources inline.

# Engagement Mechanics in Competitive-Gaming Community Platforms — What's Sticky, and What Transfers to a 10-30 Player Private ET:Legacy Community

**Research context:** Private Wolfenstein: ET community, 10-30 actives, organized 3v3/6v6 stopwatch sessions 2-3 evenings/week, one server, Discord, custom deep-stats website (slomix.fyi) becoming the primary interface.

**Headline finding:** The mechanics that transfer best are the ones that lower friction to showing up (signup → autobalance → server, with sub handling), create *temporal rhythm* (seasons/monthly resets layered over lifetime stats), and exploit the fact that everyone knows each other (predictions on your friends, named awards, inside-joke trophies). The mechanics that transfer worst are the ones designed to solve problems you don't have: open matchmaking pools, anti-toxicity rank gating, paid currency economies, and generic badge grids. Research on dead pug platforms shows the "exclusive in-house among friends" model your community already runs is the *survivor* state, not the deficient one — the website's job is to amplify it, not replace it.

---

## 1. PUG / Gather Systems

### 1.1 FACEIT Hubs/Clubs — community-scoped queue with captain picks
**How it works:** Players join a community hub with its own rules and map pool. A match fires when 12 players are queued; all 12 enter a match room; captains (random or designated "priority captain" roles) alternate-pick teams, then ban maps. Hubs have their own leaderboards and can pay out FACEIT Points. ([FACEIT CS2 Hubs support doc](https://support.faceit.com/hc/en-us/articles/9936212211740-CS2-Hubs), [Clubs FAQ](https://support.faceit.com/hc/en-us/articles/16898079292956-Clubs-FAQ))
**What makes it sticky:** the queue itself is visible (seeing 9/12 queued pulls in the last 3), captaincy is a status ritual, and hub-scoped leaderboards make rank locally meaningful.
**Verdict: ADAPT.** You don't need the queue-threshold trigger (sessions are scheduled), but the *visible signup widget* ("7/12 confirmed for tonight, need 5 more") and the captain-pick ritual transfer directly. A "session lobby" page on slomix.fyi showing who's in for tonight, with team-draft done on the site (captains alternate-picking from confirmed players, picks visible live), turns pre-session logistics into an engagement moment instead of Discord noise.

### 1.2 TF2 pickup flow (tf2pickup.eu / ETF2L mixes) — add-up → ready-up → assignment → punish no-shows
**How it works:** Players "add up" on specific classes; when enough are ready, a ready-check fires; teams are assigned; players get 5 minutes to join server + voice; no-show = reported and subbed, mid-match leaving = punishable "ragequit," you may only play the class/team you were assigned. ([tf2pickup.eu rules](https://tf2pickup.eu/rules), [ETF2L pickup community roundup](https://etf2l.org/2022/02/11/popular-places-to-play-competitive-tf2-pickup-mix-games-in-europe/))
**Verdict: ADAPT.** The full flow is overkill, but two pieces matter: (a) **ready-check / confirmed-attendance state** — formalizing "I'm in tonight" makes attendance a commitment device, and your existing availability_poll cog already half-does this; surface it on the website; (b) **class/role add-up** for 3v3 (medic/engi/fdops equivalents in ET terms — who's covert, who carries docs) so drafting accounts for roles, not just skill.

### 1.3 The substitute system — the single most-cited make-or-break feature
**How it works (and fails):** In the teamfortress.tv FACEIT hub discussion, the dominant community demand was a sub system: "a substitute system is a must or this will fail" — one no-show cancels the match and forces a full re-queue; a mid-game leaver creates an unwinnable 5v6. ([teamfortress.tv FACEIT Hub Discussion](https://www.teamfortress.tv/44859/faceit-hub-discussion))
**Verdict: YES.** With 10-30 players, one absence per session is the *norm*, not the exception. A "standby/sub" signup tier (can't commit, but ping me if short) plus a one-click "we need a 6th" Discord ping from the website is probably the highest-leverage attendance mechanic on this whole list. Track "sub appearances" as a stat — answering the call should be visible and honored.

### 1.4 In-house Discord queue bots (InhouseQueue, mrtolkien/inhouse_bot) — TrueSkill autobalance + MVP votes
**How it works:** Discord-native flow: queue buttons per role, ready check, TrueSkill/MMR-balanced teams **or** captain draft by the two highest-rated players, auto voice-channel creation, result reporting, then separate Winner/MVP/MMR leaderboards and a post-match **MVP vote** (most votes = +1 MVP score). MMR decays with inactivity. ([inhousequeue.xyz](https://inhousequeue.xyz/), [In House Queue bot listing](https://discord.bots.gg/bots/1001168331996409856), [mrtolkien/inhouse_bot](https://github.com/mrtolkien/inhouse_bot), [KennethWang discord-inhouse-league](https://github.com/KennethWangDotDev/discord-inhouse-league))
**Verdict: YES (selectively).** You already have a far better skill signal than TrueSkill (your 15-metric ET Rating) — use it for suggested-balanced-teams with a manual override. The **post-match MVP vote** is the gem: it's peer recognition (not algorithm output), takes 10 seconds, gives every player a reason to open the site right after the round, and produces a leaderboard the stats can't fake. The notable interaction: compare MVP votes vs. your computed impact rating — "most underrated player" falls out for free.

### 1.5 Why open pug platforms die — and what that says about you
**Finding:** The recurring TF2 lifecycle: open pug site launches → good players tire of randoms/toxicity → they retreat to **exclusive in-houses where they control the invite list** → the open site hollows out and dies (TF2Center "basically unplayable," PugChamp unmaintained, MixChamp fired matches too eagerly to balance them). Players framed it as restaurants vs. fast food — slower, curated pugs (PugChamp captains) beat instant low-quality ones. ([teamfortress.tv: pugchamp still exists](https://www.teamfortress.tv/59583/pugchamp-still-exists-btw), [Mixchamp died?](https://www.teamfortress.tv/42279/mixchamp-died), [FACEIT Hub Discussion](https://www.teamfortress.tv/44859/faceit-hub-discussion))
**Verdict: N/A (strategic insight).** Your community *is* the end-state that survives. Don't build open-matchmaking features; build tools that make the curated group's ritual smoother. Also note the intrinsic-motivation finding from the same thread: a dedicated medic played support "to get better… with stronger teammates" — improvement-oriented analytics (which slomix already has) are themselves a retention mechanic for the support-role players that team modes depend on.

---

## 2. Ladders, Seasons, Divisions

### 2.1 ESEA PUG seasons — 3-month cycles, placement matches, soft reset, end-of-season badges
**How it works:** PUGs run in 3-month seasons; soft MMR reset + 5 placement matches each season; ranks (A+ … D-) gate queues; inactivity decay; top finishers get permanent profile badges for that season. ([ESEA: A New Season Begins](https://blog.esea.net/rank-seasons/), [How long do ESEA pug seasons last](https://support.esea.net/hc/en-us/articles/360013204693-How-long-do-ESEA-pug-seasons-last-), [ESEA ranking FAQ](https://play.esea.net/index.php?s=support&d=faq&id=257))
**Verdict: ADAPT.** Divisions are meaningless at N=20, but the *cycle* is the point: a reset means a bad month doesn't condemn you to the bottom of the ladder forever, and a new season is a re-entry hook for lapsed players. For your group: **quarterly or monthly "Slomix Seasons"** with a soft-reset seasonal rating alongside the all-time one, and permanent per-season winner badges on player profiles ("Spring '26 Champion").

### 2.2 ETF2L/RGL league seasons — weekly fixture rhythm, map-of-the-week, playoffs, physical/cosmetic medals
**How it works:** ETF2L runs round-robin seasons (8 teams, one match/week, two maps, 3/2/1/0 golden-cap point scheme, top 4 → double-elim playoffs, promotion/relegation). RGL runs 3 seasons/year with cups in between; lower divisions get a **map of the week** schedule; all participants get division-tiered cosmetic medals. ([ETF2L Liquipedia S44 Div2](https://liquipedia.net/teamfortress/ETF2L/Season_44/Division_2), [etf2l.org](https://etf2l.org/), [comp.tf RGL wiki](https://comp.tf/wiki/RGL), [RGL TF2 wiki medals](https://wiki.teamfortress.com/wiki/Tournament_Medal_-_RGL.gg))
**Verdict: ADAPT.** The transferable elements are *rhythm devices*, not structure: (a) **map of the week** — pre-announcing next session's map pool creates anticipation and theory-crafting between sessions; (b) **a finale** — last session of the season is "playoffs night" with the season award ceremony after; (c) **participation medals tiered by season** on profiles — RGL proves people genuinely care about cheap cosmetic markers *when they index a real shared experience*.

### 2.3 Minimum viable season for one friend group
**Synthesis finding:** Game-design literature on leaderboard cadence converges on **layered timescales**: daily/weekly for quick feedback, monthly/seasonal for arc, all-time preserved on profiles — "reset leaderboards monthly or seasonally to keep the race fresh while preserving lifetime stats," because timed resets create login spikes and give lapsed players "an excuse to jump back in." ([Yu-kai Chou leaderboard design guide](https://yukaichou.com/gamification-analysis/leaderboard-design-definitive-guide-octalysis/), [AC&A on leaderboards & retention](https://adriancrook.com/how-leaderboards-impact-player-retention/), [gamedesignskills.com retention strategies](https://gamedesignskills.com/game-design/player-retention/))
**Verdict: YES.** Concretely for slomix: per-session leaderboard (already exists) → **monthly season** with named winner + 2-3 awards → all-time records page. A month at 2-3 sessions/week = 8-12 sessions, enough for a meaningful race but short enough that nobody is mathematically eliminated for long. ESEA-style decay is unnecessary; absence already punishes itself in a monthly window.

---

## 3. Predictions / Pick'em / Fantasy on Your Own Friends

### 3.1 Twitch Channel Points Predictions — parimutuel betting with valueless points
**How it works:** Streamer poses a question with 2-10 outcomes; viewers stake channel points during a 1-30 min window; winners split the losers' pool proportionally. Because points have no monetary value and can't be transferred, it's legally an "interactive feature," not gambling. Twitch frames it as the two pillars of engagement: "interactivity and stakes." ([Twitch blog announcement](https://blog.twitch.tv/en/2020/12/12/channel-points-predictions-let-your-viewers-guess-your-destiny/), [Twitch help](https://help.twitch.tv/s/article/channel-points-predictions?language=en_US), [StreamScheme guide](https://www.streamscheme.com/guide-to-twitch-predictions/))
**Verdict: YES — the best-fit prediction model for you.** Parimutuel (pool-split) beats fixed odds because no one has to set lines for "team Anže vs team Miha." Before each session or each map: "Which team takes this stopwatch?" / "Under or over 6:00 on the first hold?" Stakes in a valueless site currency. Crucially it gives **non-playing members and benched players a reason to watch and care** — the exact population a 30-person community loses first. Open-source precedent exists: [elh/bettor](https://github.com/elh/bettor), a parimutuel Discord bot explicitly inspired by Twitch predictions.

### 3.2 HLTV Pick'em & Fantasy — picks, role bonuses, boosters, small leagues
**How it works:** Pick'em = bracket/advancement picks scored per correct call. Fantasy = $1M-budget 5-man draft within small private leagues (snake draft, each pro ownable by one friend), scoring = rating delta + role-fit bonuses + 17 optional "boosters" (+5 each when their condition hits). ([HLTV: Introducing Fantasy](https://www.hltv.org/news/26309/introducing-fantasy), [hltv.org/fantasy](https://www.hltv.org/fantasy))
**Verdict: ADAPT.** Full fantasy drafting is too heavy for 2-3 nights/week. But two pieces map beautifully onto your data: (a) **prop-bet style "boosters"** — "X gets 5+ first-bloods tonight," "Y survives a full hold," powered by your stopwatch-competitive analytics (first blood, stagger, wave-cycle data already exists on the proximity branch); (b) **role-fit scoring** — predicting *who tops which metric* (most revives, best aim-lock %, most doc-runs) rather than just match winner, which spreads attention across the whole roster instead of just the carry.

### 3.3 Office pick'em pools — social glue, not prizes
**How it works / why people stay:** weekly picks against the office; research-backed observations: pools "build culture, foster friendships, create buzz," prizes don't need to be cash, the week-by-week tension sustains engagement deep into a season, and rules should prevent late joiners from chasing prizes — consistency itself is the product. ([Splash Sports pick'em office pools](https://splashsports.com/blog/pickem-office-pools-game-rules-scoring-and-strategy), [pickz.co office pick'em guide](https://pickz.co/blog/office-pick-em-pools))
**Verdict: YES.** This is the cultural proof that predicting *people you know* is stickier than predicting strangers: the payoff is bragging rights in conversation. A season-long predictor leaderboard ("best oracle of Spring '26") alongside the player leaderboard means even your worst aimer can win *something*, which is a retention lever for the bottom half of the skill curve.

---

## 4. Retention Loops on Stats Sites

### 4.1 Leetify — match report as home page, friend feed, Post-Match Journal, annual recap
**How it works:** Home page centers on *your latest match report* plus recent "accomplishments"; you follow friends and see their rankups/highlights; the Pro **Post-Match Journal** asks custom yes/no questions after each match (slept well? warmed up?) and computes correlations with win rate, with confidence intervals that narrow over time — a self-discovery loop that compels return visits; annual recap aggregates rank progress, **best-winrate teammate**, longest win/loss streaks, personal-best games. ([leetify.com](https://leetify.com/), [Post-Match Journal blog](https://leetify.com/blog/post-match-journal/), [new Home page blog](https://leetify.com/blog/our-new-home-page-a-place-to-celebrate-accomplishments/), [2025 Recap](https://leetify.com/2025))
**Verdict: YES, in pieces.**
- *Match-report-as-landing-page*: **YES** — after a session, slomix.fyi's front page should be tonight's session story (you have storytelling/narrative infra already), not a dashboard.
- *Friend feed*: **NO** — at N=20 everyone is in the same session anyway; the session report *is* the feed.
- *Post-Match Journal*: **ADAPT** — a one-tap post-session pulse ("how was tonight? favorite map?") could drive your map-pool/format decisions and gives players authorship; skip the correlation engine.
- *Best-winrate-teammate stat*: **YES** — "you win 71% with Player X" is irresistible in a community that drafts teams every session and feeds directly into draft-night banter.

### 4.2 Tracker.gg — session reports, weekly improvement reports, daily XP check-in
**How it works:** Real-time post-match breakdowns, **session reports with insights and improvement tips**, weekly improvement reports, last-20-match timelines, auto-clipped highlights; the app adds a daily check-in economy (confirm matches → XP → reward packs). ([tracker.gg](https://tracker.gg/), [TRN mobile app](https://tracker.gg/mobile), [Valorant Tracker](https://tracker.gg/valorant))
**Verdict: ADAPT.** "Session report" (their term for an evening of play) maps 1:1 onto your gaming-session concept — a **next-morning Discord digest linking to the website session page** ("Last night: 7 maps, Player X new PB in damage/min, closest stopwatch 0:04") is the single loop most worth copying: it creates a *second* engagement touch per session, off-peak. The XP-for-checking-in economy is a **NO** — manufactured dailies feel hollow when the group only plays 2-3 nights a week (see §5.3).

### 4.3 Strava — local leaderboards, Local Legends, kudos, group multiplier
**How it works / numbers:** Segment leaderboards only contain people who rode *that* road — local context makes competition feel winnable (a global board demotivates the 99.9%). Two-tier awards split motivations: **KOM** (fastest ever) vs **Local Legend** (most *attempts* in a rolling 90 days — pure frequency, skill-independent). 14B+ kudos given in 2025 (+20% YoY); social context extends streaks ~34%; group activities get 95-121% more kudos than solo ones. ([Trophy.so Strava case study](https://trophy.so/blog/strava-gamification-case-study), [Trophy.so on segmented leaderboards](https://trophy.so/blog/how-strava-uses-segmented-leaderboards-to-drive-engagement), [Strava Local Legends support](https://support.strava.com/hc/en-us/articles/360043099552-Local-Legends), [StriveCloud analysis](https://www.strivecloud.io/blog/app-engagement-strava))
**Verdict: YES — the strongest conceptual match on this list.** Your community is already one big "local segment." Transfers:
- **Per-map records as segments**: fastest doc-run on supply, fastest tank escort, best hold time — each map page gets its own record board (your per-round timing data supports this today).
- **Local Legend-style attendance award**: "most sessions played this quarter" — rewards the people who *show up*, decoupled from skill. For a community whose existential risk is attendance, this is the right thing to celebrate.
- **Kudos**: a lightweight "respect" button on session highlights/PBs. Cheap to build, and Strava's data says peer acknowledgment is the habit loop, not the stats themselves.

### 4.4 Personal bests & streaks — celebrate, but design the off-ramp
**How it works:** Duolingo calls streaks "the single most effective retention lever in the product" (Day-7 retention +14%; 32M DAUs hold 7+ day streaks) — but the critical literature documents *streak anxiety*: the streak becomes the goal, users do the minimum to keep it alive, and a single miss reads as total failure. Duolingo's own fix (streak freezes = forgiveness) *increased* DAU. ([Duolingo blog on streaks](https://blog.duolingo.com/how-streaks-keep-duolingo-learners-committed-to-their-language-goals/), [Deconstructor of Fun streaks teardown](https://duolingo.deconstructoroffun.com/mechanics/streaks), [justanotherpm psychology breakdown](https://www.justanotherpm.com/blog/the-psychology-behind-duolingos-streak-feature))
**Verdict: ADAPT carefully.** Daily streaks are wrong for a 2-3-nights-a-week community (you can't play more than the sessions that exist). Reframe as **in-game streaks** (maps won in a row, sessions with a PB, consecutive sessions attended) measured in *session units*, and make them celebratory-only — never shame a broken streak. PB notifications ("new personal best: 14 kills without dying") are pure upside: variable-ratio, skill-correlated, zero anxiety.

### 4.5 Annual recap / "Wrapped"
**How it works / why it works:** Spotify Wrapped succeeds on quantified self-reflection + **optimal distinctiveness** (your numbers connect you to the group *and* differentiate you) + scarcity (once a year = ritual) + shareability (it showcases the user, not the brand; 500M+ shares in day one, 2025). Leetify's annual recap applies the same model to CS. ([Irrational Labs behavioral analysis](https://irrationallabs.com/blog/spotify-wrapped-behavioral-science/), [Fortune on optimal distinctiveness](https://fortune.com/2025/12/03/why-spotify-wrapped-marketing-genius-individuality-uniqueness-belonging-psychology/), [Leetify 2025 Recap](https://leetify.com/2025))
**Verdict: YES.** A "Slomix Wrapped" — per-player season/year card (signature weapon, nemesis, best teammate, clutch moments, minutes alive) — is cheap given your data depth and lands hardest in a group where everyone will read everyone else's. Run it at season end, not just annually, and design it as an image people drop into Discord.

---

## 5. Badges, Achievements, Quests

### 5.1 What the critics say
**Findings:** "Pointsification" (Deterding) = layering points/badges on activities without redesigning them; badges are its poster child. Meaningless badges "make people feel the system is fake"; gold stars for trivial completion are "insulting to anyone over age seven"; rewards ring hollow when disconnected from real value. The recurring failure mode: streaks/badges *become the point* and displace the actual activity. ([Growth Engineering: Dark Side of Gamification](https://www.growthengineering.co.uk/dark-side-of-gamification/), [Jon Radoff: Gamification, Behaviorism and Bullshit](https://jradoff.medium.com/gamification-behaviorism-and-bullshit-50fe87861239), [Gamification Hub criticisms](https://www.gamificationhub.org/what-are-the-criticisms-of-gamification/), [NerdSip: when streaks become the point](https://nerdsip.com/blog/gamification-gone-wrong-when-streaks-become-the-point))
**Verdict on generic badge grids ("Play 100 rounds!", "Login 5 days!"): NO.** Adults in a 20-person friend group will read auto-generated completion badges as filler, and your community's currency is *reputation among people who watched it happen*, not collection progress.

### 5.2 What works instead: scarce, witnessed, story-bearing awards
**Findings:** RGL's division-tiered medals are valued *because* they index a real season experienced together ([RGL medal wiki](https://wiki.teamfortress.com/wiki/Tournament_Medal_-_RGL.gg)). ESEA's end-of-season placement badges are permanent and scarce ([ESEA rank seasons](https://blog.esea.net/rank-seasons/)). Fantasy-football private leagues — the best natural experiment in keeping ~12 adults engaged for months — run on **perpetual trophies with engraved names ("hall of shame"), last-place punishments, and inside jokes**: punishments exist explicitly "to keep everyone engaged and prevent tanking," and the loser trophy is "a tradition, a running joke, and the best way to keep every manager invested until the final whistle." ([Sleeper: best fantasy punishments](https://sleeper.com/blog/best-fantasy-football-punishments/), [TrophySmack loser trophy guide](https://www.trophysmack.com/blogs/smackzone/fantasy-football-loser-trophies-guide), [FantasyLife punishments](https://www.fantasylife.com/articles/fantasy/fantasy-football-punishments))
**Verdict: YES, with these design rules:**
1. **Scarce & seasonal**: a handful of awards per season (MVP, Best Medic-equivalent, Oracle, Iron Man/attendance, Most Improved), each with one winner, engraved forever on a Hall of Fame page.
2. **Witnessed**: tie awards to moments the group actually saw ("the 0:04 full-hold on Adlernest, May 14") — your event-level data makes machine-detected "moments" badges feasible and *meaningful*, unlike counter badges.
3. **Humor & shame (consensual)**: a rotating wooden-spoon style anti-award voted by the group will do more for session-to-session banter than 50 achievement icons. Fantasy leagues prove the loser trophy is a *retention* device.
4. **Peer-voted beats computed** for the marquee awards (see MVP vote, §1.4) — recognition from friends is the one reward that can't feel hollow.

### 5.3 Quests / missions (FACEIT-style monthly missions, daily check-in XP)
**How it works:** FACEIT monthly missions award FACEIT Points for win counts, with free/premium tiers; ladders (incl. dedicated **win-streak ladders**) pay FP to top finishers. ([FACEIT Missions FAQ](https://support.faceit.com/hc/en-us/articles/10013072193308-Premium-Monthly-Missions), [FACEIT Points](https://support.faceit.com/hc/en-us/articles/10503161344668-FACEIT-Points), [What are Ladders](https://support.faceit.com/hc/en-us/articles/18705813492380-What-are-Ladders))
**Verdict: ADAPT into "weekly challenges," skip the economy.** A points-shop economy needs scale and sinks you don't have. But a single **community challenge of the week** posted before sessions ("this week: most knife kills" / "land a 3-man airstrike") — one per week, themed, with the winner named in the next digest — is a quest mechanic that behaves like an inside joke rather than a grind. If you ever want a currency, make it the prediction-points wallet (§3.1) so the economy has exactly one faucet and one sink.

---

## Priority Matrix for slomix.fyi

| Mechanic | Verdict | Effort | Expected stickiness | Why |
|---|---|---|---|---|
| Next-morning session digest → website (4.2) | YES | Low | High | Second touch per session; bot already has the data |
| Post-session MVP vote (1.4) | YES | Low | High | Peer recognition, 10-sec action, new leaderboard |
| Parimutuel session predictions (3.1) | YES | Medium | High | Engages benched/non-playing members; valueless points |
| Monthly season + soft reset + Hall of Fame (2.1, 2.3) | YES | Medium | High | Rhythm + re-entry hook + permanent honor |
| Session lobby: confirm/standby + captain draft on site (1.1-1.3) | ADAPT | Medium | High | Attacks attendance, the real risk at N=20 |
| Per-map record boards "segments" + PB notifications (4.3, 4.4) | YES | Medium | Medium-high | Local, winnable competition; data exists |
| Attendance "Local Legend" + best-teammate stat (4.3, 4.1) | YES | Low | Medium | Rewards showing up; fuels draft banter |
| Season Wrapped cards, shareable to Discord (4.5) | YES | Medium | Medium (spiky) | Ritual + identity; deep data is your moat |
| Challenge of the week (5.3) | ADAPT | Low | Medium | Quest flavor without grind |
| Voted anti-award / wooden spoon (5.2) | ADAPT | Low | Medium | Fantasy-league-proven banter engine; needs group buy-in |
| Daily streaks, login XP, generic badge grids, points shop | NO | — | Negative | Hollow for adults at this scale; streak anxiety; wrong cadence |
| Open matchmaking, divisions, rank gating, MMR decay | NO | — | — | Solves problems of 10,000-player pools, not 20-friend groups |

**The unifying principle:** every surviving mechanic above converts something your friends *already did together* into something they look at, vote on, predict, or joke about *between* sessions. Mechanics that manufacture activity (dailies, grindy quests, badge collections) fail with adults; mechanics that *memorialize and anticipate shared sessions* (digests, drafts, predictions, season finales, engraved trophies) are the ones with evidence behind them.
