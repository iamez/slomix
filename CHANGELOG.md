# Changelog

All notable changes to Slomix are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.26.0](https://github.com/iamez/slomix/compare/v1.25.0...v1.26.0) (2026-07-14)


### Features

* **proximity:** data trust quality endpoint ([#494](https://github.com/iamez/slomix/issues/494)) ([b29977c](https://github.com/iamez/slomix/commit/b29977c0652f28aa16ca9a3a47005e4335ba2392))
* **website:** betting cutoff — auto-open sets closes_at (§6.4b) ([#496](https://github.com/iamez/slomix/issues/496)) ([32c9802](https://github.com/iamez/slomix/commit/32c98028346c50fc0f6d1d67dbb6653e24489bd9))


### Bug Fixes

* **website:** smart-stats map count = maps played, not distinct names ([#497](https://github.com/iamez/slomix/issues/497)) ([18a3f32](https://github.com/iamez/slomix/commit/18a3f32c11727b61dc205f9a0772ca04bbb38d42))

## [1.25.0](https://github.com/iamez/slomix/compare/v1.24.0...v1.25.0) (2026-07-09)


### Features

* **website:** internal API secret for bot→website write-through GETs ([d98b8a9](https://github.com/iamez/slomix/commit/d98b8a9e47a151dbee1cf179ecbc8cfff024df41))
* **website:** internal API secret for bot→website write-through GETs ([8f5c53b](https://github.com/iamez/slomix/commit/8f5c53b5db38b45f1675b8665409015c3d4c27b5))


### Bug Fixes

* **bot:** address 3 codex review findings on KIS cache invalidation ([cd5efd4](https://github.com/iamez/slomix/commit/cd5efd4312f3da31dbbfdd1654b1596810896aa6))
* **bot:** invalidate KIS cache at session end (Smart Stats/Story kill-count freeze) ([0daaf63](https://github.com/iamez/slomix/commit/0daaf63a9848d99d124aac3648c1b14e48cd4d02))
* **bot:** invalidate KIS cache at session end so Story/Smart Stats never freeze mid-session ([83802b3](https://github.com/iamez/slomix/commit/83802b3de4853a76ddde32962f1c248b2957f0e8))
* **bot:** revert delayed second KIS delete — it wiped fresh digest recomputes ([a6ce10b](https://github.com/iamez/slomix/commit/a6ce10b647393513d6b6615279d04a7603d6d3d8))
* **bot:** warm KIS cache after invalidation + correct false self-healing claim ([5bdfca5](https://github.com/iamez/slomix/commit/5bdfca5a6d0ea88ee69f4f8e1c1a28d91675e6c8))
* **proximity,bot:** canonical round-key bundle + KIS formula_version ([b2f0180](https://github.com/iamez/slomix/commit/b2f01803f758d34292fbdc97f430264ed7a4e78c))
* **proximity,bot:** canonical round-key bundle + KIS formula_version + misc audit findings ([e19a651](https://github.com/iamez/slomix/commit/e19a651b6f7ab388e3d4fb5ab6855c0707e8636a))
* **website:** canonical map_name in KIS context keys (audit [#10](https://github.com/iamez/slomix/issues/10)/[#11](https://github.com/iamez/slomix/issues/11)) ([59c2e99](https://github.com/iamez/slomix/commit/59c2e996c93c0a306c1078d23af4dc4540e1a8ec))
* **website:** canonical map_name in KIS context keys (audit [#10](https://github.com/iamez/slomix/issues/10)/[#11](https://github.com/iamez/slomix/issues/11)) ([6be3314](https://github.com/iamez/slomix/commit/6be33140d2e49cbb8cad7b76a1786521fd1b6517))
* **website:** freshness-aware KIS cache-check (staleness cannot recur) ([#489](https://github.com/iamez/slomix/issues/489)) ([3f754f3](https://github.com/iamez/slomix/commit/3f754f35413dd9f3cfb4f8095293a6ce3a9ba0ee))
* **website:** harden internal-secret edge cases (Copilot PR [#487](https://github.com/iamez/slomix/issues/487) review) ([5b21607](https://github.com/iamez/slomix/commit/5b216075a8758d258021de97d96185aeb71c8d3a))

## [1.24.0](https://github.com/iamez/slomix/compare/v1.23.0...v1.24.0) (2026-07-08)


### Features

* **bot:** ROUND_STATS_AUTOPOST_ENABLED toggle for production posting ([#478](https://github.com/iamez/slomix/issues/478)) ([3995433](https://github.com/iamez/slomix/commit/3995433edfb0d4acb449d9a48db5ca594bc38c84))
* **proximity:** clutch-v1 backtest — difficulty multiplier + own-goal data-gap finding (A1) ([#473](https://github.com/iamez/slomix/issues/473)) ([b24cd98](https://github.com/iamez/slomix/commit/b24cd986a8e0690d984957065984982ce47fd02b))


### Bug Fixes

* 4 confirmed findings from codex follow-up audit (pool leaks, UI, path leak) ([#476](https://github.com/iamez/slomix/issues/476)) ([9c9198b](https://github.com/iamez/slomix/commit/9c9198b029c57fc986765270010ed2a9266e5a36))
* **bot:** decouple proximity scan trigger from Discord publish outcome ([#480](https://github.com/iamez/slomix/issues/480)) ([d742970](https://github.com/iamez/slomix/commit/d742970f076f02d62946b78e868c4850509f432d))
* **bot:** session start-date lookup filtered wrong column (missed in [#470](https://github.com/iamez/slomix/issues/470) merge) ([#471](https://github.com/iamez/slomix/issues/471)) ([fb023ce](https://github.com/iamez/slomix/commit/fb023ce0c211c5254d86c9edf0d8e181132e8c71))
* **proximity:** clutch-v1 late-review follow-up — canonical key, victim match, side-switch, spawn cap ([#474](https://github.com/iamez/slomix/issues/474)) ([ab20cf9](https://github.com/iamez/slomix/commit/ab20cf9c5c5fc909b294fbb6e1c579f65ef91711))

## [1.23.0](https://github.com/iamez/slomix/compare/v1.22.0...v1.23.0) (2026-07-08)


### Features

* All-Seeing Eye paket — OIS + SSR + Comp Skill/profil/Adj surfacing + Match Lean + help-harm probe (A1-A5, B4) ([#465](https://github.com/iamez/slomix/issues/465)) ([0de041a](https://github.com/iamez/slomix/commit/0de041af99ad29873297dae659f5f5902f91ecd4))
* **bot,website:** adopt BOX point scale everywhere — 2 points per map, draws 1-1 ([#447](https://github.com/iamez/slomix/issues/447)) ([e255eab](https://github.com/iamez/slomix/commit/e255eab9ae1a6edcba73a60b038789ee39fc0d0d))
* **bot:** auto-persist s.effort at session end ([#470](https://github.com/iamez/slomix/issues/470)) ([fb5056c](https://github.com/iamez/slomix/commit/fb5056c0653a79ece41d9d6b490c6398bc17453e))
* **proximity:** 'Where pushes die' map overlay (slice 2) ([#437](https://github.com/iamez/slomix/issues/437)) ([23f1849](https://github.com/iamez/slomix/commit/23f1849697564ec51f15f3212a36369283760738))
* **proximity:** K-E backtest — target acquisition, reaction under fire, spawn readiness ([#458](https://github.com/iamez/slomix/issues/458)) ([521ba14](https://github.com/iamez/slomix/commit/521ba1499b58fa20afa65a2c4cb3e35e7892c2e6))
* **proximity:** KROGT per-life leaderboard category (slice 3 productization) ([#442](https://github.com/iamez/slomix/issues/442)) ([5c283a9](https://github.com/iamez/slomix/commit/5c283a9f3797c0bc693ebe5ba88bcee8e9d9acef))
* **proximity:** per-life KROGT backtest (slice 3, Phase-0) + catalog status refresh ([#441](https://github.com/iamez/slomix/issues/441)) ([83de6be](https://github.com/iamez/slomix/commit/83de6beaa59aa2b0587b26dc217b74bff43a4ca5))
* **scripts:** Good Night Index v0 Phase-0 backtest ([#449](https://github.com/iamez/slomix/issues/449)) ([7ede8e8](https://github.com/iamez/slomix/commit/7ede8e8571826ec3545894c493e0450ac30dd81d))
* **website:** formula registry + /api/formulas (B6) + rescue K-B backtest scripts ([#463](https://github.com/iamez/slomix/issues/463)) ([182a449](https://github.com/iamez/slomix/commit/182a44927b4ba4a4f8ee92266f0f142639954c15))
* **website:** Good Night Index card on Session Detail (Phase 1) ([#451](https://github.com/iamez/slomix/issues/451)) ([a3c8484](https://github.com/iamez/slomix/commit/a3c848489c4d27767bb020c1bc19288adfa131fe))
* **website:** opening duels + trade discipline (B6) + registry live statuses + flag docs ([#467](https://github.com/iamez/slomix/issues/467)) ([786a3f6](https://github.com/iamez/slomix/commit/786a3f6e2dede1d7f458b4974c5b6a409da7665c))
* **website:** s.effort + adjusted lifetime (K-D) ([#455](https://github.com/iamez/slomix/issues/455)) ([8d3096e](https://github.com/iamez/slomix/commit/8d3096e5f30f2bf4f22b42389a7e2b47d524f3a5))
* **website:** SSR v0.2 — opening net + trade discipline components ([#469](https://github.com/iamez/slomix/issues/469)) ([427deaa](https://github.com/iamez/slomix/commit/427deaa49e5fb9ee115da3157c5e7b80025d718e))


### Bug Fixes

* **bot,website:** address PR [#443](https://github.com/iamez/slomix/issues/443) post-merge review (Copilot x3) ([#445](https://github.com/iamez/slomix/issues/445)) ([bd1d36f](https://github.com/iamez/slomix/commit/bd1d36f6a375ab619dceae651221ce60cd9135fc))
* **bot,website:** unify session scoring — match_id pairing + BOX validity gate ([#443](https://github.com/iamez/slomix/issues/443)) ([b2d54aa](https://github.com/iamez/slomix/commit/b2d54aafc301dc99adcd8271018c2264e702124d))
* **bot:** admin_predictions DB-tier gate + cached !maps + moderator policy doc (B1-B3) ([#460](https://github.com/iamez/slomix/issues/460)) ([d888f49](https://github.com/iamez/slomix/commit/d888f4994331bc1fbf4efe2af888942c9858c942))
* Codex read-only audit remediation — confirmed P1/P2 findings (report.md) ([#457](https://github.com/iamez/slomix/issues/457)) ([17dad82](https://github.com/iamez/slomix/commit/17dad82b0c37d67ef4d8cbd09e734b3965857c9d))
* **proximity:** de-duplicate carrier deaths inside push windows (codex P2, PR [#437](https://github.com/iamez/slomix/issues/437)) ([#439](https://github.com/iamez/slomix/issues/439)) ([04f3ca2](https://github.com/iamez/slomix/commit/04f3ca200ddc009a95712a47debe533f8c3eec98))

## [1.22.0](https://github.com/iamez/slomix/compare/v1.21.0...v1.22.0) (2026-07-04)


### Features

* **website:** composite Form Index — one trackable form number per player ([#430](https://github.com/iamez/slomix/issues/430)) ([41cf5e0](https://github.com/iamez/slomix/commit/41cf5e04b03c8a28301452a163b208c9da025d69))
* **website:** Session Detail 'Moments of the night' strip (proximity slice 1) ([#435](https://github.com/iamez/slomix/issues/435)) ([becd301](https://github.com/iamez/slomix/commit/becd30141867746f7844fa3a63495b0f0253dc91))


### Bug Fixes

* **bot:** housekeeping — bot-round majority rule, On-This-Day session grain, TZ note, Phase-0 backtest ([#434](https://github.com/iamez/slomix/issues/434)) ([d428c6b](https://github.com/iamez/slomix/commit/d428c6b68de3817d19e32a7a9acc141a4539f109))

## [1.21.0](https://github.com/iamez/slomix/compare/v1.20.0...v1.21.0) (2026-07-02)


### Features

* **website:** expand "Movers · vs own form" into a full Form feature ([#428](https://github.com/iamez/slomix/issues/428)) ([839ac28](https://github.com/iamez/slomix/commit/839ac28c0fdca507a4defec7f252e52438d48b2c))

## [1.20.0](https://github.com/iamez/slomix/compare/v1.19.0...v1.20.0) (2026-07-02)


### Features

* **website:** auto-settle betting markets (Faza B2b) ([#419](https://github.com/iamez/slomix/issues/419)) ([b24957f](https://github.com/iamez/slomix/commit/b24957fe89a362b57607476ee0d5eefc307cd029))


### Bug Fixes

* **docs:** restore CLAUDE.md as a symlink to docs/CLAUDE.md ([#424](https://github.com/iamez/slomix/issues/424)) ([1026226](https://github.com/iamez/slomix/commit/10262268db1c36e7cb2fa3f13449dd1666a7ecc5))


### Performance Improvements

* **website:** micro-perf sweep — single kill-outcome scan + batch campaign prefs ([#417](https://github.com/iamez/slomix/issues/417)) ([f2c9b64](https://github.com/iamez/slomix/commit/f2c9b64bc0a5948084227036e37f157cf2a303f2))

## [1.19.0](https://github.com/iamez/slomix/compare/v1.18.0...v1.19.0) (2026-07-01)


### Features

* **proximity:** competitive wave 2 — man-advantage, clutch 1vN, side splits, player passport + killer_reinf backfill ([#378](https://github.com/iamez/slomix/issues/378)) ([e678de1](https://github.com/iamez/slomix/commit/e678de16f18642d6e9b7ccbe67ed89b17c26569e))
* **proximity:** vision sweep — E2E audit, Invisible Value panel, Player Journey + fixes ([#376](https://github.com/iamez/slomix/issues/376)) ([d2558a8](https://github.com/iamez/slomix/commit/d2558a8eef45a17d593f07c02a7e3d7973963ca7))
* Sprint S1 'JUTRO' — morning digest, home pulse cards, own-form verdicts & baselines ([#384](https://github.com/iamez/slomix/issues/384)) ([18ddf1c](https://github.com/iamez/slomix/commit/18ddf1c3efa50ff17e1729b758fd1fde33aba76f))
* Sprint S2 'RAČUN' — web display-name & aliases + role-gating foundation ([#386](https://github.com/iamez/slomix/issues/386)) ([edd3f0f](https://github.com/iamez/slomix/commit/edd3f0f7f867cbc810d8c2c94d1fb983ae2fa18b))
* Sprint S3 'VEČER' — MVP vote, weekly challenge, lobby & captain-draft polish ([#389](https://github.com/iamez/slomix/issues/389)) ([128bb6a](https://github.com/iamez/slomix/commit/128bb6a0cdf782e94b78279a8ebda2a5543c6e18))
* Sprint S4 'TEKMA' — seasons, season awards+HoF, parimutuel betting, per-map records ([#391](https://github.com/iamez/slomix/issues/391)) ([e0b0a4e](https://github.com/iamez/slomix/commit/e0b0a4ea68150a14eeaa0fff62e2a85d5002328b))
* Sprint S5 'IDENTITETA' — profile IA, archetype/focus/duo, career timeline, mobile ([#395](https://github.com/iamez/slomix/issues/395)) ([9f73cee](https://github.com/iamez/slomix/commit/9f73ceefebcd91828e47ded724323dee7e89a03e))
* Sprint S6 'SPOMIN' — On This Day, Record Book, Slomix Wrapped ([#397](https://github.com/iamez/slomix/issues/397)) ([8d58df2](https://github.com/iamez/slomix/commit/8d58df226a0678da4a63242737daf7c4efb89f62))
* Sprint S7 'LIVE' — Tonight hub (live score, momentum, hold-probability) ([#398](https://github.com/iamez/slomix/issues/398)) ([c3f1b8d](https://github.com/iamez/slomix/commit/c3f1b8d81aa21b6bb4da38ea77b6b8e38ee62023))
* **website:** auto-open betting markets (Faza B2) ([#414](https://github.com/iamez/slomix/issues/414)) ([bbc81bf](https://github.com/iamez/slomix/commit/bbc81bf2eba842a480fde7461c6d0955347acf0a))
* **website:** session team momentum + Uploads & Hall of Fame QoL ([#380](https://github.com/iamez/slomix/issues/380)) ([2a228b5](https://github.com/iamez/slomix/commit/2a228b5238d8475c96dc7c9675bb9accdeb4b845))
* **website:** Tonight live hub — logical-team score (fix Axis/Allies) + richer live view ([#402](https://github.com/iamez/slomix/issues/402)) ([991064b](https://github.com/iamez/slomix/commit/991064b54efe6ee315f6fb7bf0fb4a247e2615ee))


### Bug Fixes

* **bot:** silence postgres advisory-lock warning + webhook soft-fail log level ([#400](https://github.com/iamez/slomix/issues/400)) ([a928dab](https://github.com/iamez/slomix/commit/a928dabdd4627a805838c2a991ad8aead7adc74c))
* **security:** audit remediation — uploads CSRF + dependency CVE bumps + audit report ([#399](https://github.com/iamez/slomix/issues/399)) ([09d4e91](https://github.com/iamez/slomix/commit/09d4e9192d3414e873f807892f6dfd0fd285370c))
* **website:** Wave 2 Val D — Sessions a11y + sargable date filter ([#405](https://github.com/iamez/slomix/issues/405)) ([b97ae0a](https://github.com/iamez/slomix/commit/b97ae0a7402f7ec57a17180f5ac197dc08edd2e9))

## [1.18.0](https://github.com/iamez/slomix/compare/v1.17.0...v1.18.0) (2026-06-10)


### Features

* **bot:** deterministic stopwatch round pairing + legacy match_id backfill ([#370](https://github.com/iamez/slomix/issues/370)) ([ec3a95d](https://github.com/iamez/slomix/commit/ec3a95dc1b1ca6c329883d8a7ac1919756267d46))
* **stats:** exclude filler maps (mp_sillyctf) + harden roster-change scoring ([#372](https://github.com/iamez/slomix/issues/372)) ([ee632f9](https://github.com/iamez/slomix/commit/ee632f94af6716e23c9b4882763a552d96656143))
* **website:** aim body hitmap + spread/burst metrics; fix profile JS caching ([#364](https://github.com/iamez/slomix/issues/364)) ([2ac5126](https://github.com/iamez/slomix/commit/2ac512659834eefd46cc7f228716ccba745ec9d2))
* **website:** gibhub.gg-parity player profile + true-aim analytics ([#362](https://github.com/iamez/slomix/issues/362)) ([ef59023](https://github.com/iamez/slomix/commit/ef59023ccdfab89c93065e664ebd2282f0a2d73c))
* **website:** profile completeness + Aim v2 (Leetify-aligned) + lurker perf + identity enrichment ([#366](https://github.com/iamez/slomix/issues/366)) ([85ba0b2](https://github.com/iamez/slomix/commit/85ba0b2ad4b19dbbecfe9550957be0fd331e8abc))


### Bug Fixes

* **bot:** stop round-linker orphan log spam (quiet relinker + 6h abandon) ([#369](https://github.com/iamez/slomix/issues/369)) ([d69c937](https://github.com/iamez/slomix/commit/d69c9376f734c552e5498323caa6a1f0c68dddd1))
* **scripts:** two-phase match_id backfill to avoid unique-constraint violation ([#374](https://github.com/iamez/slomix/issues/374)) ([cbd10fc](https://github.com/iamez/slomix/commit/cbd10fc36f2684e623ece524aa891336029ddace))

## [1.17.0](https://github.com/iamez/slomix/compare/v1.16.0...v1.17.0) (2026-06-02)


### Features

* **bot:** idle-server watchdog — reload neutral map when empty (FM1/FM2) ([#354](https://github.com/iamez/slomix/issues/354)) ([cb5bdcf](https://github.com/iamez/slomix/commit/cb5bdcf6d564fe6c25b29098795576fbe64594ea))


### Bug Fixes

* **audit:** guard crossref 0/0 + correct prediction weight docstring ([#360](https://github.com/iamez/slomix/issues/360)) ([aa38a9a](https://github.com/iamez/slomix/commit/aa38a9a51d7a6eb77b02851e27ab7aa9554565f2))
* **audit:** robustness fixes in matchup/permission/admin cogs + records.js ([#361](https://github.com/iamez/slomix/issues/361)) ([7c8f92a](https://github.com/iamez/slomix/commit/7c8f92a33761abff60c06ed5b51ffedcd67d5206))
* **data-integrity:** exclude orphan R2 from leaderboards + cap time_dead (FM4, RCA-1) ([#350](https://github.com/iamez/slomix/issues/350)) ([22444da](https://github.com/iamez/slomix/commit/22444da6400a183eee31a3be6f8df62806963f2d))
* **lua:** clamp reinf offset to 0-7 in c0rnp0rn8 (FIX-8) ([#356](https://github.com/iamez/slomix/issues/356)) ([13852d1](https://github.com/iamez/slomix/commit/13852d1fa6a242138f6000afb557707bdb66130a))
* **proximity:** re-anchor round time to round-live + coerce weapon to int (RCA-2, M1) ([#352](https://github.com/iamez/slomix/issues/352)) ([3d58f35](https://github.com/iamez/slomix/commit/3d58f3556c92b39239ef4e7f3cbccce1ccb982d0))

## [1.16.0](https://github.com/iamez/slomix/compare/v1.15.0...v1.16.0) (2026-05-19)


### Features

* **proximity:** Full Aim Analytics — Player Combat Map gets a 5th lens (v9 true-aim) ([#346](https://github.com/iamez/slomix/issues/346)) ([fb9fe67](https://github.com/iamez/slomix/commit/fb9fe67ea76e3619b374506fd23ac680d4df5e05))

## [1.15.0](https://github.com/iamez/slomix/compare/v1.14.2...v1.15.0) (2026-05-19)


### Features

* **deploy:** auto-restart services if deploy fails mid-flight ([#263](https://github.com/iamez/slomix/issues/263)) ([afd4429](https://github.com/iamez/slomix/commit/afd4429af24ceb3e2d4e3397405bba3888ee1054))
* **proximity:** page redesign — per-player heatmap, A1/A6 fix, map-first IA ([#328](https://github.com/iamez/slomix/issues/328)) ([b7e8d83](https://github.com/iamez/slomix/commit/b7e8d834f4b8c9445b45deb7487e26f97b35deec))
* **proximity:** Part B owner-visual — map-first reorder + v5.2 fold/dedup + React framing ([#336](https://github.com/iamez/slomix/issues/336)) ([fc2d555](https://github.com/iamez/slomix/commit/fc2d5551ecc56dfb7af3692b4426c8afa589b8c1))
* **proximity:** Part B-2 — A8 fix + 8→5 KPI / 7→3 leaderboards + ④⑤ dividers ([#334](https://github.com/iamez/slomix/issues/334)) ([fdef3d5](https://github.com/iamez/slomix/commit/fdef3d529803916eb0710b9fcd7cb5c542bc6ee0))
* **proximity:** per-player Hit Region Distribution by the Player Combat Map ([#339](https://github.com/iamez/slomix/issues/339)) ([2b691f0](https://github.com/iamez/slomix/commit/2b691f0aad1ace6d840b5a828e8829c22a9e291d))
* **proximity:** Phase 4 Part B — map-first IA recompose (safe subset) ([#330](https://github.com/iamez/slomix/issues/330)) ([a92383d](https://github.com/iamez/slomix/commit/a92383da086de457edb684b7d73d4ae1a715b142))
* **proximity:** Player Combat Map player dropdown + Part B continuation ([#332](https://github.com/iamez/slomix/issues/332)) ([60d936d](https://github.com/iamez/slomix/commit/60d936d8745142edebfd83fd9e439f8a39d77729))


### Bug Fixes

* **deploy:** cache-bust EVERY local JS import, not just 3 entry points ([#261](https://github.com/iamez/slomix/issues/261)) ([f0014be](https://github.com/iamez/slomix/commit/f0014be6ff71ea9239347abf43c6bb65f539c75d))
* **install:** write DISCORD_GUILD_ID (not GUILD_ID) to generated .env ([#306](https://github.com/iamez/slomix/issues/306)) ([a25c414](https://github.com/iamez/slomix/commit/a25c414629be05ee9fe39ecd9ebe7825b2701291))
* **lua:** SHOT_FIRED emit crashed outputData on Lua 5.4; truncate origin to parser contract ([#345](https://github.com/iamez/slomix/issues/345)) ([f53cc42](https://github.com/iamez/slomix/commit/f53cc42798bf877adf9113bdc0c23db0691ba822))
* **lua:** webhook detect_pause crashed every frame on Lua 5.4 — no bit lib ([#343](https://github.com/iamez/slomix/issues/343)) ([ffd9a40](https://github.com/iamez/slomix/commit/ffd9a404dad43be251ee41ec4ead3f7ed956e1d1))
* **proximity:** drop redundant per-panel map boxes — panels follow page Scope ([#340](https://github.com/iamez/slomix/issues/340)) ([9b66a33](https://github.com/iamez/slomix/commit/9b66a33800415fd39ef5080bad97bb253efaaa15))
* **release:** auto-bump pyproject.toml — drifted to 1.0.8 silently ([#267](https://github.com/iamez/slomix/issues/267)) ([889de06](https://github.com/iamez/slomix/commit/889de06b862d393926528ff7b92998a0bac44704))
* **webhook-metadata:** defensive DB gate against stale Lua metadata leak ([#255](https://github.com/iamez/slomix/issues/255)) ([27e3dc9](https://github.com/iamez/slomix/commit/27e3dc9c762adf1172c48c2c89503c3550b590bb))
* **website:** restore public Home live-status widget endpoints + sanitize ([#338](https://github.com/iamez/slomix/issues/338)) ([154ff6f](https://github.com/iamez/slomix/commit/154ff6f3cd4bdfc870c7711cf7af368e35ded8c9))

## [1.14.2](https://github.com/iamez/slomix/compare/v1.14.1...v1.14.2) (2026-05-12)


### Bug Fixes

* **logging:** use exc_info=error instead of exc_info=True in error handlers ([#234](https://github.com/iamez/slomix/issues/234)) ([8e10dbb](https://github.com/iamez/slomix/commit/8e10dbb734cbcb558884619fac87d4dee3a0b465))


### Performance Improvements

* **kis:** merge spawn_mult + reinf_mult into single pass over spawn_timings ([#241](https://github.com/iamez/slomix/issues/241)) ([9683070](https://github.com/iamez/slomix/commit/968307044a44a1faa4d680b67ebbc5ab5d5a2316))
* **records:** parallelize 13 sequential queries via asyncio.gather ([#243](https://github.com/iamez/slomix/issues/243)) ([c347fd4](https://github.com/iamez/slomix/commit/c347fd407b331951bb507e4d7ebd64c03e6450f9))

## [1.14.1](https://github.com/iamez/slomix/compare/v1.14.0...v1.14.1) (2026-05-11)


### Bug Fixes

* **deprecation:** kill datetime.fromtimestamp() + date.today() raw calls ([#216](https://github.com/iamez/slomix/issues/216)) ([345bc6c](https://github.com/iamez/slomix/commit/345bc6c418e96e50586a574773f1f0a8288507b9))
* **deprecation:** replace datetime.utcnow() with timezone-aware UTC ([#214](https://github.com/iamez/slomix/issues/214)) ([72f2d00](https://github.com/iamez/slomix/commit/72f2d001c723ce9fa45eaf2899e041711c2d5dbd))
* **lint:** enable DTZ005 with noqa rationales (204 sites) ([#230](https://github.com/iamez/slomix/issues/230)) ([6241648](https://github.com/iamez/slomix/commit/6241648d74f1bb1bfd7f72e261362b44ac130154))
* **lint:** enable DTZ007 with noqa rationales (49 sites) ([#222](https://github.com/iamez/slomix/issues/222)) ([ff06278](https://github.com/iamez/slomix/commit/ff06278fdf2a55c94330bc7a39e82ed3ee8b742f))
* mega audit v6 — verified-real fixes (12 fixes, 16 false positives ruled out) ([#210](https://github.com/iamez/slomix/issues/210)) ([69f3eb9](https://github.com/iamez/slomix/commit/69f3eb9ba4d10809e7bf31aecc39d58ae263053f))
* **storytelling:** filter NULL/0 round_start_unix in enabler + lurker ([#228](https://github.com/iamez/slomix/issues/228)) ([f61888f](https://github.com/iamez/slomix/commit/f61888fd2bcb4fa6c73a4389175994a0f48e7fe8))

## [1.14.0](https://github.com/iamez/slomix/compare/v1.13.3...v1.14.0) (2026-05-10)


### Features

* **scripts:** add --diff mode to check_db_drift for row-level deltas ([#201](https://github.com/iamez/slomix/issues/201)) ([dc7201f](https://github.com/iamez/slomix/commit/dc7201f44cc7c4ca683a274edfd1d84d44b1d6e6))
* **storytelling:** add useless-defense-deaths metric + endpoint ([#204](https://github.com/iamez/slomix/issues/204)) ([bd42928](https://github.com/iamez/slomix/commit/bd429283e1867e9449a3a943cd894192fb8d2505))


### Bug Fixes

* **bot,proximity:** close TOCTOU on player_aliases + log silent excepts in parser ([#197](https://github.com/iamez/slomix/issues/197)) ([2fdd86d](https://github.com/iamez/slomix/commit/2fdd86d39442fc989f86029f81909940209fad2a))
* **bot:** wrap _insert_player_stats in atomic tx + weapon savepoint ([#199](https://github.com/iamez/slomix/issues/199)) ([ae61048](https://github.com/iamez/slomix/commit/ae61048e2cc0b1f1f7fecbce976ada7719ea3a3c))
* **story:** spawn-rush filter + narrative wordalisation overhaul + audit fixes ([#205](https://github.com/iamez/slomix/issues/205)) ([2951e87](https://github.com/iamez/slomix/commit/2951e87cbaed1a3995e101c8e2bb9e56b5df3976))
* **storytelling,scoring:** math/formula audit fixes (1 real, 2 doc) ([#208](https://github.com/iamez/slomix/issues/208)) ([09d56fe](https://github.com/iamez/slomix/commit/09d56fe8eea9a0c9fd4416b54ed637aa9f018bb4))

## [1.13.3](https://github.com/iamez/slomix/compare/v1.13.2...v1.13.3) (2026-05-08)


### Bug Fixes

* **scripts:** robust env loading + base64-encoded SQL over SSH ([#195](https://github.com/iamez/slomix/issues/195)) ([04b41b3](https://github.com/iamez/slomix/commit/04b41b39a34332c50c4785f5f95b994fa764d6f4))

## [1.13.2](https://github.com/iamez/slomix/compare/v1.13.1...v1.13.2) (2026-05-07)


### Bug Fixes

* **scripts:** two RCA-driven follow-ups missed in initial ultrareview pass ([#192](https://github.com/iamez/slomix/issues/192)) ([9e4b2f8](https://github.com/iamez/slomix/commit/9e4b2f8e1b86a417f48895c39fe132b28481ab09))

## [1.13.1](https://github.com/iamez/slomix/compare/v1.13.0...v1.13.1) (2026-05-07)


### Bug Fixes

* **scripts:** address remaining ultrareview nits on sync helpers ([#190](https://github.com/iamez/slomix/issues/190)) ([ad5321f](https://github.com/iamez/slomix/commit/ad5321f1f34d69911a99f76645f3e67357039810))

## [1.13.0](https://github.com/iamez/slomix/compare/v1.12.0...v1.13.0) (2026-05-07)


### Features

* **website:** Session Detail UX redesign — Faza A ([#186](https://github.com/iamez/slomix/issues/186)) ([ef2427a](https://github.com/iamez/slomix/commit/ef2427ae8af17ad293084ad58733004becf28eef))


### Bug Fixes

* **deploy:** un-ignore compare_mixin.py — stats_cog broken on prod ([8f78e19](https://github.com/iamez/slomix/commit/8f78e19564596a7d0a253fe73286a560d1dc8864))
* **parser,kis:** populate *_guid_canonical on INSERT ([cdb7f51](https://github.com/iamez/slomix/commit/cdb7f5115ccc33f8e4627b4c48128953fe540f98))

## [1.12.0](https://github.com/iamez/slomix/compare/v1.11.1...v1.12.0) (2026-05-07)


### Features

* **website:** minimalize Stats dropdown — 13 items → 6 ([#178](https://github.com/iamez/slomix/issues/178)) ([6c88c59](https://github.com/iamez/slomix/commit/6c88c59243f35d15d681dcb21c4ed268e34f12b9))
* **website:** redesign Availability page as #ETL — bigger, bolder, clearer ([#182](https://github.com/iamez/slomix/issues/182)) ([aa58f24](https://github.com/iamez/slomix/commit/aa58f24ff599a2719f21234738c430f189d61bfc))
* **website:** redesign System Overview as About page (-7000 lines) ([#179](https://github.com/iamez/slomix/issues/179)) ([56b50d0](https://github.com/iamez/slomix/commit/56b50d0408aabbdee799966302a5247d36ea288d))


### Bug Fixes

* **stats:** R0 double-counting + TIR formula bug across PCS aggregations ([#176](https://github.com/iamez/slomix/issues/176)) ([516d9b0](https://github.com/iamez/slomix/commit/516d9b0335051a0f543d64b3a7c11dc1e46330e1))

## [1.11.1](https://github.com/iamez/slomix/compare/v1.11.0...v1.11.1) (2026-05-07)


### Bug Fixes

* **security:** reject symlinks pre-resolve + normalise null roster JSON ([4ca0724](https://github.com/iamez/slomix/commit/4ca072493f10226514005ad94d842461724fc45e))
* **test:** address Codex P2 findings on PR [#173](https://github.com/iamez/slomix/issues/173) ([ce0d098](https://github.com/iamez/slomix/commit/ce0d09810fd792d1495cb233e4b5fce975f26739))
* **upload:** stop symlink walk at storage root boundary ([a91d406](https://github.com/iamez/slomix/commit/a91d4061366ca16d29f0d02525ace3d8ab2ea387))

## [1.11.0](https://github.com/iamez/slomix/compare/v1.10.1...v1.11.0) (2026-05-06)

> **Round Canonical ID + Correlation Saga.** Content-addressed round identity (`sha256(round_start_unix:map_name:round_number)[:16]`) shipped in a 6-phase rollout: schema → dual-write → UNIQUE constraint → primary lookup → saga timeout → periodic sweep. The orphan-row regression that plagued correlation since the proximity pipeline merge is finally closed: cleanup tool now preserves multi-match days (best-of-3 style), the re-linker repairs mismatched `round_id` assignments instead of just adding new ones, and Strategy 3's back-to-back same-map cross-pollination bug (kills mixed into the wrong round) is fixed via a 600s proximity window + canonical merge. New `/diagnostics/storytelling-completeness` endpoint with corrected `rounds_correlated` counter exposes data-quality at a glance, and the Stats dropdown gains a Smart Stats verification UI for KIS audit transparency.

### Features

* **canonical:** Phase 1 — schema + backfill round_canonical_id ([8523952](https://github.com/iamez/slomix/commit/85239529cb5191fdcde30ea3ddcf2d9fb7176f4e))
* **canonical:** Phase 1 — schema + backfill round_canonical_id ([52b7867](https://github.com/iamez/slomix/commit/52b7867c799ce31b234f54262047b4ec7bffd629))
* **canonical:** Phase 2 — dual-write round_canonical_id in ingest paths ([5900d5e](https://github.com/iamez/slomix/commit/5900d5eedbf882db8af66e8edbe32617d66638ff))
* **canonical:** Phase 2 — dual-write round_canonical_id in ingest paths ([3c89d3c](https://github.com/iamez/slomix/commit/3c89d3c049ff35c91ae65d357232868361070f03))
* **canonical:** Phase 3+4 — UNIQUE constraint + canonical_id primary lookup ([cf05fe7](https://github.com/iamez/slomix/commit/cf05fe722a5c3e1c5fb5c3b5f82ab919be3c9019))
* **canonical:** Phase 3+4 — UNIQUE constraint + primary canonical lookup ([bb05994](https://github.com/iamez/slomix/commit/bb05994635c7edbfe52c4b1f638f1e226bf6f9fd))
* **canonical:** Phase 6 — saga timeout for stale pending correlations ([ca7d98c](https://github.com/iamez/slomix/commit/ca7d98c9b5f846259f21124c12523ac9efb19469))
* **canonical:** Phase 6 — saga timeout for stale pending correlations ([ec2fe5a](https://github.com/iamez/slomix/commit/ec2fe5a6ffaf76cc34b61cefe401a1bb47c342af))
* **correlation:** Phase D cleanup + Phase E periodic sweep ([71ebdd3](https://github.com/iamez/slomix/commit/71ebdd3be230d21961e134ca6eabbadf6b27ae0c))
* **correlation:** Phase D cleanup tool + Phase E periodic sweep ([9a69029](https://github.com/iamez/slomix/commit/9a69029cc3421d968dc1d66cebe515efb3d61c3f))
* **diag:** storytelling-completeness endpoint + correct rounds_correlated ([6193c46](https://github.com/iamez/slomix/commit/6193c466836e03bb381d4d6d4349d83293509d5f))
* **tools:** website sanity check — cross-validate API vs SQL ([6fa07c8](https://github.com/iamez/slomix/commit/6fa07c8f4653c51ce3cf30a575bfa7345dea42d3))
* **tools:** website-wide sanity check tool ([0dacbfc](https://github.com/iamez/slomix/commit/0dacbfc9a6495859007c47cc95de27d28fa42da9))
* **website:** Stats dropdown reorder + Smart Stats verification UI ([29ef728](https://github.com/iamez/slomix/commit/29ef7287f891129dfe27243bbb506f573042118b))


### Bug Fixes

* address Copilot + CodeQL review on PR [#169](https://github.com/iamez/slomix/issues/169) ([c9f8991](https://github.com/iamez/slomix/commit/c9f89913a37b272b5f3c34ba0dbef9f17c304910))
* address Copilot review followups from PR [#156](https://github.com/iamez/slomix/issues/156) + [#158](https://github.com/iamez/slomix/issues/158) ([09c7992](https://github.com/iamez/slomix/commit/09c79929a867bfa04fe5039d5d8fbde658375e4a))
* address remaining Copilot review followups (PR [#159](https://github.com/iamez/slomix/issues/159) + [#156](https://github.com/iamez/slomix/issues/156)) ([cd05d67](https://github.com/iamez/slomix/commit/cd05d67be7b05903ec1e9f1e717249a3dadca4ef))
* **canonical:** tighten UniqueViolation detection per Copilot review on PR [#171](https://github.com/iamez/slomix/issues/171) ([be049b1](https://github.com/iamez/slomix/commit/be049b19d56df8f2695d333a6a8178037040e097))
* Copilot review followups — security + correctness sweep across 7 PRs ([a0f0c16](https://github.com/iamez/slomix/commit/a0f0c1664c3292410242ab4f460d43a2f387c024))
* correlation orphan regression remediation (Phase A+B) ([b54dc37](https://github.com/iamez/slomix/commit/b54dc370e4cb10bd97540d6d7110adb02432df14))
* **correlation:** Strategy 3 back-to-back match cross-pollination ([bd22565](https://github.com/iamez/slomix/commit/bd2256502f9ace42bc1157a7cd6b654c4159fb12))
* **correlation:** Strategy 3 round_id merge + 600s proximity window ([9c86dbc](https://github.com/iamez/slomix/commit/9c86dbc80e5384f5eaa8f61df9673e803330402f))
* **diag:** drop unused datetime.date import after auto-compute removal ([90e623a](https://github.com/iamez/slomix/commit/90e623a64331bce05f83219973c898d43f74bf16))
* **proximity:** re-linker detects + repairs mismatched round_id ([ba3c5c4](https://github.com/iamez/slomix/commit/ba3c5c48f8cc2bb8a6471e53013e5fb39059b9ca))
* **proximity:** re-linker detects + repairs mismatched round_id assignments ([9ba7bcf](https://github.com/iamez/slomix/commit/9ba7bcf121793ea5cdd8c96e3bfa464b2a4c63ba))
* Strategy 3 back-to-back match cross-pollination + diag KIS auto-compute ([1e23b34](https://github.com/iamez/slomix/commit/1e23b34c5746872516f2b1d28d21151e43a4794c))
* **tools:** cleanup script preserves multi-match days (best-of-3 stil) ([b6752d9](https://github.com/iamez/slomix/commit/b6752d9ad67e278f5388f36665adbee54983fac7))

## [1.10.1](https://github.com/iamez/slomix/compare/v1.10.0...v1.10.1) (2026-05-04)


### Bug Fixes

* **website:** remove dead session_date fallback queries in quick-leaders ([#154](https://github.com/iamez/slomix/issues/154)) ([ce554e5](https://github.com/iamez/slomix/commit/ce554e57e117ca1ed70e64ad17ce0edbf826eb03))

## [1.10.0](https://github.com/iamez/slomix/compare/v1.9.0...v1.10.0) (2026-04-25)

> **Lua v1.7.0 Persistent Retry Buffer.** The game-server Lua now disk-buffers webhook payloads when Discord rejects them and replays on reconnect. No more lost round notifications during transient network glitches — a long-standing class of "missing R2" reports finally has a fix at the source.

### Features

* **lua:** persistent retry buffer for webhook payloads (v1.7.0) ([#152](https://github.com/iamez/slomix/issues/152)) ([98cb16c](https://github.com/iamez/slomix/commit/98cb16ca2584017e69442d9d273091896400f353))

## [1.9.0](https://github.com/iamez/slomix/compare/v1.8.0...v1.9.0) (2026-04-25)

> **The Big Rollup — Proximity v6.01, Oksii Adoption, KIS v3, AI Predictions, Greatshot pipeline.** This is the largest single release in the project's history, consolidating ~6 weeks of feature work behind release-please's first run. Highlights: **Proximity v6.01 Objective Intelligence** (#53) ships carrier kills, returns, construction events, and vehicle progress with full backend + frontend coverage. **Oksii Lua Adoption** flows `killer_health`, `alive_count`, and reinf timing into KIS v2 multipliers and a new BOX scoring service (Oksii-style stopwatch). **KIS v3** (#121) replaces the binary reinforcement bonus with a UTRO-inspired 7-tier graduated multiplier (0.70-1.40). **Player Rivalries** lands at `/#/rivalries` with H2H stats and nemesis/prey/rival classification. **Win Contribution (PWC/WIS/WAA)** introduces a 5-component fairness formula with dynamic weight redistribution and MVP detection. **Match Predictions** (Phase 1-7) ship a 4-factor algorithm with auto voice-channel detection. **Greatshot Demo Pipeline** completes the upload → UDT scan → highlight detect → cut → render flow. The **Round Correlation System** introduces `match_id` canonicalisation and linkage diagnostics. **God file decomposition** breaks `proximity_router.py` (5,515 → 14 sub-routers) and `records_router.py` (3,172 → 10 sub-routers). DB pool capacity diagnostics (#149) and a map-image combat heatmap overlay (#145) round things out.

### Features

* add cumulative endstats to !last_session + fix race conditions ([2f5fb33](https://github.com/iamez/slomix/commit/2f5fb338634adffe11a795046b689afe5bf42754))
* add proximity tracker prototype ([f44f080](https://github.com/iamez/slomix/commit/f44f0808ff53d4495e7dda0c63078a946217060d))
* add proximity tracker prototype ([85355de](https://github.com/iamez/slomix/commit/85355de181f9f5d853a943b34becd2063dc1000e))
* add website prototype ([#27](https://github.com/iamez/slomix/issues/27)) ([b69d1b3](https://github.com/iamez/slomix/commit/b69d1b38fca5c1c4ebbd322910e3989af8e35301))
* **analytics:** Add player analytics commands (Phase 1) ([cee91a6](https://github.com/iamez/slomix/commit/cee91a6e404ccf9ca2e72194005b0338a3482406))
* **audit:** cleanup sweep — 10 commits covering deferred P5-P8 + F8-F10 + safe_val + orphan drops ([#133](https://github.com/iamez/slomix/issues/133)) ([2b989cc](https://github.com/iamez/slomix/commit/2b989cc7b147b2fa9813ab58abab7a9a55341796))
* **bot,website:** fix R2 lua webhook, add round visualizer, restore planning docs ([16d9412](https://github.com/iamez/slomix/commit/16d9412abfb3d7d022b8674201ddbf484135ee25))
* **bot,website:** WS2+WS3 timing join logging, diagnostics, embed validation ([eff63b9](https://github.com/iamez/slomix/commit/eff63b9fc732b75c3cfffd8bdb664e6ebfdca6fb))
* **bot:** add ADR/KPR/DPR metrics + clean remaining SQLite branches ([ac9369a](https://github.com/iamez/slomix/commit/ac9369a73c7ceea15e05a811dfb17baadca6581b))
* **bot:** add command_error_handler decorator to utils ([463aa59](https://github.com/iamez/slomix/commit/463aa59d56b5cac1551d9fc8cf12bdef25615ff8))
* **bot:** add proximity tracking to round correlation system ([f701ee8](https://github.com/iamez/slomix/commit/f701ee859648a9625b49559305c869abf045be14))
* **bot:** canonicalize match_id in stats import path via round correlation context ([8a9497f](https://github.com/iamez/slomix/commit/8a9497f4efeccd8dfb204a033ca0bcac2d69e694))
* **bot:** enhance correlation service and add linkage diagnostics ([39df70e](https://github.com/iamez/slomix/commit/39df70e3109b8139c377e5779de91f49d51c7a18))
* **bot:** round correlation system + match_id fix + ET:Legacy research ([d47a85c](https://github.com/iamez/slomix/commit/d47a85ccce2e1cd19cb14d33810b4abba2029b48))
* **db:** add SQL migrations 005-013 and website migrations ([48e9361](https://github.com/iamez/slomix/commit/48e9361a35c6b5f153007e6f4dc93d2f2fa68555))
* **db:** migrations 014/015 — proximity round_id columns + backfill ([10b51b8](https://github.com/iamez/slomix/commit/10b51b8b5e9595e050028eed49abec12573984f4))
* Deep RCA audit — 26 fixes, skill rating v1.1, error masking overhaul ([aa5c5ca](https://github.com/iamez/slomix/commit/aa5c5ca61fc760725381b70ca37ffe4530705aac))
* **diagnostics:** expose DB pool capacity + utilisation metrics ([#149](https://github.com/iamez/slomix/issues/149)) ([a1c27c2](https://github.com/iamez/slomix/commit/a1c27c2dba6cd0dcf8bc81d1d854e113a576d443))
* **greatshot:** complete Phase 2-5 + topshots API endpoints ([c3c9797](https://github.com/iamez/slomix/commit/c3c9797b7047370314a8cdfd1e4c6d72a8355809))
* **greatshot:** enhance demo-to-stats cross-reference matching ([f6e7bf1](https://github.com/iamez/slomix/commit/f6e7bf11ad95297ee35311f3fd7a89a9887aff76))
* **greatshot:** enrich highlight metadata and add DB cross-reference ([3e79f9b](https://github.com/iamez/slomix/commit/3e79f9bc968bf0e42ce80632b4fe4e7eac5f39a4))
* **greatshot:** multi-file upload + player stats display ([6814138](https://github.com/iamez/slomix/commit/6814138ab2a58ded5111c9aa0603c1b462591596))
* **kis:** graduated UTRO-inspired reinforcement multiplier ([#121](https://github.com/iamez/slomix/issues/121)) ([48209ce](https://github.com/iamez/slomix/commit/48209cee07d83e1917fec3de63c8b8881b4ecf8b))
* legacy Smart Stats page + round linker fix + endstats guard ([152460d](https://github.com/iamez/slomix/commit/152460d6f553fe11b2530cc77889ee713771dd7d))
* **logging:** add comprehensive logging across bot and website ([fcbb4e5](https://github.com/iamez/slomix/commit/fcbb4e55d08c25aa9cfd93e8f1d9ffc8cf36b903))
* **matchup:** Add matchup analytics system for lineup vs lineup stats ([6a2fca3](https://github.com/iamez/slomix/commit/6a2fca32f761e5da7c5a2285d9e636ce5774b4d5))
* **oksii:** Oksii adoption — KIS v2 multipliers, BOX scoring, Lua deploy ([876555d](https://github.com/iamez/slomix/commit/876555d8a0f6002043c251b1d6203bdf695663a0))
* Player Rivalries + Win Contribution (PWC/WIS/WAA) ([332949f](https://github.com/iamez/slomix/commit/332949fb772078c4ebd4f49e0a0a1a4ac94e2416))
* proximity v5.2 analytics, ET Rating, code quality fixes ([53f5050](https://github.com/iamez/slomix/commit/53f50508580c71ef619da373785d18013252057d))
* **proximity:** add canonical round_id linkage to all proximity tables ([bacbfc1](https://github.com/iamez/slomix/commit/bacbfc1052ed505aab46e6701be63346e58638bf))
* **proximity:** add composite scoring system + complete v5.2 frontend panels ([ebb5f18](https://github.com/iamez/slomix/commit/ebb5f187e9f47663dc2ce5ab451b9eab1535d999))
* **proximity:** add kill outcomes, hit regions, combat heatmaps & movement analytics (v5.2) ([b26b989](https://github.com/iamez/slomix/commit/b26b9896966e3df39bc02df2271e0b210a23dca9))
* **proximity:** add objective coord assets and web map data ([614e533](https://github.com/iamez/slomix/commit/614e53355aed18ee5b049987b120f1bf202462df))
* **proximity:** combat-heatmap panel uses map image overlay ([#145](https://github.com/iamez/slomix/issues/145)) ([227a0f7](https://github.com/iamez/slomix/commit/227a0f7d578006df36e54397aa99b27fcac56117))
* **proximity:** expand Lua tracker, objective coords, and web analytics ([be76076](https://github.com/iamez/slomix/commit/be76076f23d9c861814aa1a91609552f5279973a))
* **proximity:** pipeline fix + full leaderboard scoping + frontend UX overhaul ([d248baa](https://github.com/iamez/slomix/commit/d248baa64b6facedda8bf964b108c53cfdb22e24))
* **proximity:** upgrade gameserver Lua to v5.0 with full teamplay sections ([7cbc3eb](https://github.com/iamez/slomix/commit/7cbc3eb49dc79e352ccc4281fa0d0bc729975ded))
* **proximity:** v6.01 objective intelligence + full frontend coverage + bot GUID fix ([#53](https://github.com/iamez/slomix/issues/53)) ([83bfd1e](https://github.com/iamez/slomix/commit/83bfd1ec1b9a6c3c69f764b6ba3b5bbb962d50c6))
* **proximity:** v6.01 objective intelligence + missing panels + bot GUID fix ([83bfd1e](https://github.com/iamez/slomix/commit/83bfd1ec1b9a6c3c69f764b6ba3b5bbb962d50c6))
* **proximity:** v6.01 objective intelligence + missing panels + bot GUID fix ([73ad6ef](https://github.com/iamez/slomix/commit/73ad6ef0f027b759d5f47b2d08bedeb4593b92c0))
* reconcile local work — sessions redesign, proximity, deploy tooling ([52ba75f](https://github.com/iamez/slomix/commit/52ba75f0c3656fc87bcc3ac1e379e9ea3eae6231))
* **scoring+teams:** Map-based stopwatch scoring + real-time team tracking ([64dc2ab](https://github.com/iamez/slomix/commit/64dc2ab9598798c7df4815a092a7e2207853d2e2))
* **scripts:** add backfill, gate, smoke test, and deployment scripts ([cb0dad6](https://github.com/iamez/slomix/commit/cb0dad6d4b70d02dfb2aa9b3c279a965e49d2ca9))
* **session-embed:** add team detection confidence indicator ([b0cb46d](https://github.com/iamez/slomix/commit/b0cb46de779d2eec322a98464369588e40979403))
* **storytelling:** 4 new objective moment detectors + enhanced kill streaks ([db7f293](https://github.com/iamez/slomix/commit/db7f2938d8762cac8ee84c527bfff127cb241441))
* **storytelling:** add enabler score metric ([c569a9e](https://github.com/iamez/slomix/commit/c569a9e331f9338d3d5deb72f6e424d7c9cfcf25))
* **storytelling:** add gravity and space-created metrics ([2be0deb](https://github.com/iamez/slomix/commit/2be0deb3ca3d0d56c5319104ecf667a600c9ada0))
* **storytelling:** add lurker profile — solo time from player_track paths ([71edee0](https://github.com/iamez/slomix/commit/71edee0b056a9a71bf26dbae1edf04d12c20c193))
* **storytelling:** DPM + denied time + time dead in archetype classification ([6a71907](https://github.com/iamez/slomix/commit/6a71907414dc73853b826ff9e078d2ca8290c0b0))
* **storytelling:** Kill Impact Score — Phase 1 complete ([ed62d9c](https://github.com/iamez/slomix/commit/ed62d9cb399c106f0d8d3199979311134f204bf8))
* **storytelling:** moments timeline + synergy panel + type diversity fix ([ed9032c](https://github.com/iamez/slomix/commit/ed9032c24007db7ebb7d3202f21c487132fb40e0))
* **storytelling:** narrative polish + enabler dedup + frontend panel ([cde42dd](https://github.com/iamez/slomix/commit/cde42dd69717409effe75994cae4d224b5f42ad0))
* **storytelling:** per-player micro-narratives with invisible value metrics ([d8f533e](https://github.com/iamez/slomix/commit/d8f533e116043b79a01293c43d67d4207bf89aef))
* **storytelling:** polish pipeline + hush relinker spam (6 audit findings + 1 infra) ([#128](https://github.com/iamez/slomix/issues/128)) ([b50c41b](https://github.com/iamez/slomix/commit/b50c41b8a773a8f89ff8866fcdaf16e8b6331285))
* **storytelling:** Slomix-stein /#/story page — cinematic Smart Stats UI ([6e2bc35](https://github.com/iamez/slomix/commit/6e2bc354490fb71cb7eddaffa6255738198e266e))
* **storytelling:** Smart Stats Phase 2 — Moments, Archetypes, Synergy ([e34d4e8](https://github.com/iamez/slomix/commit/e34d4e85bc5b6db3fc93ec86b3e86f42d28992ae))
* **storytelling:** team wipe + multikill detectors with rich context ([31d39d1](https://github.com/iamez/slomix/commit/31d39d1f0bfaeb1b2c4286af25f128102ccfbaea))
* **team-detection:** enhance with defender_team validation and confidence scoring ([65c633e](https://github.com/iamez/slomix/commit/65c633e541c14c331ded12fefb6dd950b2ae3e83))
* **timing-comparison:** add timing legend to embed description ([4fa4aa3](https://github.com/iamez/slomix/commit/4fa4aa3aacc50cdd89145ef7d2b49572bda5d2e3))
* **tools:** add pipeline verification script (WS1-007 gate check) ([1b12edb](https://github.com/iamez/slomix/commit/1b12edb41ce9acb945225b3c45f0bb55a35b4398))
* v1.0.6 - analytics, matchup system, website overhaul, proximity tracker ([33a2468](https://github.com/iamez/slomix/commit/33a24683a128fccaf9de5bc005341b2e2e8e616b))
* v1.0.7 - greatshot demo pipeline, DB manager overhaul, README rewrite ([a925cb8](https://github.com/iamez/slomix/commit/a925cb8007a6b22ef5cefba34a6ffd4d9b96499e))
* v1.1.0 — stats accuracy audit, React 19 frontend, proximity v5 ([d5aec31](https://github.com/iamez/slomix/commit/d5aec31e444e26ecd9f9b9b76b840b7080598df6))
* v1.1.0 — stats accuracy audit, React 19 frontend, proximity v5 teamplay ([674cee9](https://github.com/iamez/slomix/commit/674cee9f5c8d2ac5b114711ea8f9f5103372d322))
* v1.4.0 — Replay Timeline, Momentum, Narrative + 2 critical data fixes ([efffc5c](https://github.com/iamez/slomix/commit/efffc5cfac9b0804a30a592114c55d390b7091a4))
* **webhook:** add real-time stats notification via Discord webhook ([4ee9609](https://github.com/iamez/slomix/commit/4ee960953026bd84e5dd7628563662d4893879e1))
* **webhook:** fix Lua gamestate detection + timing comparison service ([622dc65](https://github.com/iamez/slomix/commit/622dc65528257e48edd31c36a4506bda385401a5))
* **web:** prefer exact round_id join with fuzzy fallback in proximity API ([f70253e](https://github.com/iamez/slomix/commit/f70253ec94a211c176f4b618d6b0d6c3f786dc2f))
* **website:** add BOX Score and Invisible Value panels to legacy story page ([#78](https://github.com/iamez/slomix/issues/78)) ([df23d77](https://github.com/iamez/slomix/commit/df23d77aacd7420f253093c3f8f7318cf8c94594))
* **website:** add ET Rating skill system (experimental) ([aa2c514](https://github.com/iamez/slomix/commit/aa2c514c156a94ea935e34e36e7d4e462def4834))
* **website:** add ET Rating to navigation menu ([fe578af](https://github.com/iamez/slomix/commit/fe578af19b117d64c38f26704fc1ea3d48f91640))
* **website:** add Useful Kills, Self Kills, Full Self Kills to session stats ([e9a0cc8](https://github.com/iamez/slomix/commit/e9a0cc82734c6a307a9d444437bd65b595a29c77))
* **website:** admin System Overview redesign + proximity color code fix ([8af0840](https://github.com/iamez/slomix/commit/8af0840111cd4b93bcb75c52e5c1d88fc35564e0))
* **website:** ET Rating v2, nav reorganization, KIS/PWC proximity enrichment ([f63c3bb](https://github.com/iamez/slomix/commit/f63c3bba902bc8acd096db2cd36c0321c773b4c1))
* **website:** React 19 modernization with game assets integration ([2bc069f](https://github.com/iamez/slomix/commit/2bc069f3ed4cc73ec494b76497d0ef03c335c3dd))
* **website:** redesign Admin System Overview page ([96df809](https://github.com/iamez/slomix/commit/96df809a7dc26b2f2bafc82d3328573b68d497cd))
* **website:** replay map visualization with player tracks, kill markers, playback controls ([b9c99d9](https://github.com/iamez/slomix/commit/b9c99d9052659c853275839e7cf84e86361e9405))
* **website:** session detail 2.0 matrix + Mega Audit v3 Sprint 1 ([#79](https://github.com/iamez/slomix/issues/79)) ([7848233](https://github.com/iamez/slomix/commit/7848233429660fb4a058e9e5514afe75a068cca2))
* **website:** sessions redesign, proximity fixes, deploy script updates ([955f52f](https://github.com/iamez/slomix/commit/955f52f157a1e57ebaa4316b642fad9e7f518eb2))
* **website:** show Oksii multiplier badges on story player cards ([b29106e](https://github.com/iamez/slomix/commit/b29106ea3508aa90339e072a70b7d0c6f3b8ad8d))
* **website:** storytelling page improvements — narrative, momentum, KIS fix ([a71b335](https://github.com/iamez/slomix/commit/a71b335ab41f5cbc1e18d0176e167517a5633cd7))
* **website:** wire Smart Stats into legacy navigation ([4b65669](https://github.com/iamez/slomix/commit/4b656697854e85907263ee313c89dbdd23c5859f))


### Bug Fixes

* address all 8 audit findings from Mandelbrot RCA review ([7f54ac4](https://github.com/iamez/slomix/commit/7f54ac4c1fc36d5c068e479809aff4fecd4522d0))
* address codacy findings for availability notifications ([e0b84c5](https://github.com/iamez/slomix/commit/e0b84c5291818153be712e618a275902d6ec53fb))
* address Codex P1/P2 review findings ([1d2f946](https://github.com/iamez/slomix/commit/1d2f946d5fcef8cc77d71a1d3095b7ec92dd8626))
* address PR [#35](https://github.com/iamez/slomix/issues/35) review comments ([04cc599](https://github.com/iamez/slomix/commit/04cc5991e79c48295568e7d23cb487a2a97b60c3))
* address PR31 regressions and weapons/analytics runtime issues ([dd98a17](https://github.com/iamez/slomix/commit/dd98a17e92922de8a8be322ec6c0c6760934b285))
* address remaining Codex findings for legacy JS ([266c05a](https://github.com/iamez/slomix/commit/266c05a96dc9b97bacae849a45236be5c1af42dd))
* **api_helpers:** always strip ET colors from batch_resolve early returns ([#120](https://github.com/iamez/slomix/issues/120) follow-up) ([#126](https://github.com/iamez/slomix/issues/126)) ([f611c94](https://github.com/iamez/slomix/commit/f611c9478c4503c0b3abbee859949303fc641f5f))
* **audit:** address Copilot reviews across PR [#128](https://github.com/iamez/slomix/issues/128) + [#130](https://github.com/iamez/slomix/issues/130) (prod bug + 5 nits) ([#131](https://github.com/iamez/slomix/issues/131)) ([27e5b6d](https://github.com/iamez/slomix/commit/27e5b6d4c8d949adb45b3d5c3c83c19bc2a1610f))
* **bot,docs:** ghost round filter, round linker delay, warning fatigue, SQLite doc cleanup ([bb3cd79](https://github.com/iamez/slomix/commit/bb3cd796721616f5cf748b5e7cf37397f766a97b))
* **bot,lua,web:** multi-phase bugfix sweep from super prompt audit ([64d6f57](https://github.com/iamez/slomix/commit/64d6f5707ba93d36a8d8405e8acc66ef7c1b1774))
* **bot,proximity,greatshot:** execute WS runbook tasks — reconnect, proximity, crossref ([20d84e6](https://github.com/iamez/slomix/commit/20d84e6270852618f14930538b62aa5f1d918468))
* **bot,web:** correct headshot %, denied playtime display, and website formula alignment ([aa116a6](https://github.com/iamez/slomix/commit/aa116a6d1b0ef1e9a4889a61d95c1f8547e2b998))
* **bot,website:** lua round linker fallback + ET color strip in v6 panels ([4e3754f](https://github.com/iamez/slomix/commit/4e3754f17091af549b7982d9951ca77c56bb110c))
* **bot:** add Discord posting error alerting and fix health monitor ([3c840d2](https://github.com/iamez/slomix/commit/3c840d2d5dceffa6863580c000307e9e0e7a2392))
* **bot:** assign random team names when _auto_assign_teams pre-creates "Team A/B" ([27443c8](https://github.com/iamez/slomix/commit/27443c879cd07ac38a2510ae1b9a11e2c92764b2))
* **bot:** bump SSH connect timeout 10s → 20s (Layer 1 audit) ([#115](https://github.com/iamez/slomix/issues/115)) ([a961e13](https://github.com/iamez/slomix/commit/a961e13f77def9d5b8d3fc0e8d64cf9a1326cee5))
* **bot:** correlation merge for Lua/stats match_id mismatch + disable dead cog ([25166fe](https://github.com/iamez/slomix/commit/25166feb956d9f52a12724979ab2c0580c9d8425))
* **bot:** Discord posting error alerting + health monitor fix ([e4771dc](https://github.com/iamez/slomix/commit/e4771dc9f9d6ba52d957830cb93c3d1e76ed3d97))
* **bot:** eliminate round_linker WARN race in STATS_READY webhook ([#140](https://github.com/iamez/slomix/issues/140)) ([e55b5b0](https://github.com/iamez/slomix/commit/e55b5b0e77f0d630c4d850602d92f2ca5552a4e7))
* **bot:** final sprint — session finalization, embed overflow, SQLite guards, matchup SQL ([6d24d2f](https://github.com/iamez/slomix/commit/6d24d2f4cea062567aeed5ea13462d5f0ea9c334))
* **bot:** guard auto team name assignment against repeated attempts ([44c9516](https://github.com/iamez/slomix/commit/44c9516344e8be215b638fc8c0aaebc6a2e069dd))
* **bot:** remove hard dependency on tools.stopwatch_scoring in session cog ([d23f51a](https://github.com/iamez/slomix/commit/d23f51ae76e98aad15118430fd6fb838752e6e26))
* **bot:** remove proximity_revive + proximity_weapon_accuracy from re-linker ([cb588b0](https://github.com/iamez/slomix/commit/cb588b0f43b36fabc1faeba99583b6c8ac66d17a))
* **bot:** resolve Lua round_id linkage race condition ([e216b92](https://github.com/iamez/slomix/commit/e216b92f87b9313477cc925904938c195c588bbf))
* **bot:** round linker timezone mismatch — UTC vs local naive datetime ([52e6521](https://github.com/iamez/slomix/commit/52e652182de3ee2c66996414e802ab7611e7250f))
* **bot:** round_linker — sanity-bound round_start_unix (Layer 2 audit) ([#118](https://github.com/iamez/slomix/issues/118)) ([bebfed5](https://github.com/iamez/slomix/commit/bebfed51d185d609c67b3120d741bec94fa1c3e2))
* **bot:** round_linker race condition + midnight crossover (date_free fallback) ([#109](https://github.com/iamez/slomix/issues/109)) ([e502b0a](https://github.com/iamez/slomix/commit/e502b0a93b64298c66794e445f4af392b92876c4))
* **bot:** serialize round_correlation critical section to prevent race ([#114](https://github.com/iamez/slomix/issues/114)) ([c97ac71](https://github.com/iamez/slomix/commit/c97ac7165923a9b946a1102a2417a4446a9375bb))
* **bot:** SQL param count mismatch and placeholder consistency ([cc94275](https://github.com/iamez/slomix/commit/cc9427511468b63d71e8b834247036c4013ebdbe))
* **bot:** WS0 column cache refresh, restart detection gap guard, sprint closure ([3f42952](https://github.com/iamez/slomix/commit/3f42952872ba370d9394a521d32ff6ceafe01f08))
* Build short→long GUID lookup map, match PCS by first 8 chars. ([0bc636f](https://github.com/iamez/slomix/commit/0bc636fd2472c03f9a824452788fa72bb71f4eb1))
* **ci-security:** unblock test imports and harden retro viz rendering ([2988da8](https://github.com/iamez/slomix/commit/2988da8e69d72d58d09f7e6401153b511a8b2344))
* **ci-tests:** use postgres schema and align db adapter tests ([e3bfdd6](https://github.com/iamez/slomix/commit/e3bfdd6cae82618735832126bf07f074ed69b253))
* **ci:** add all required env vars for Docker Build ([453cf32](https://github.com/iamez/slomix/commit/453cf322a4b33c722a757844a8f57a6edc44fc94))
* **ci:** add schema files and restore adapter/test compatibility ([4f447fa](https://github.com/iamez/slomix/commit/4f447fa7bdbe586df744aec96fcec58a0bb0a8f5))
* **ci:** Docker Build needs .env placeholder + empty except comment ([706c352](https://github.com/iamez/slomix/commit/706c3522d9f6a3c1cb55235868c5dbfd56475f94))
* **ci:** f-string prefix lint + exclude game assets from size check ([e9efcd2](https://github.com/iamez/slomix/commit/e9efcd2dea3692a7c70b83de0e13593648f90df0))
* **ci:** make Codecov non-blocking, exclude build artifacts from Codacy/CodeQL ([f17fd9e](https://github.com/iamez/slomix/commit/f17fd9ed75cf08939ba6d9f65707bdb0f6e5e8a8))
* **ci:** make slowapi optional with no-op stub for CI/test environments ([8114a6d](https://github.com/iamez/slomix/commit/8114a6d2507c96e79c010c073b9e87f133d9433f))
* **ci:** migrate CodeQL action to v4 ([7ab90da](https://github.com/iamez/slomix/commit/7ab90da04e3d2c4496d1d6772a801fbd7996f389))
* **ci:** remove redundant SARIF upload step from CodeQL workflow ([f80e008](https://github.com/iamez/slomix/commit/f80e0083b1515f6d37d11e47276e51c943002ce9))
* **ci:** resolve file-checks and JavaScript lint failures ([3107d7c](https://github.com/iamez/slomix/commit/3107d7cd736031d64cfaac497797a841733f5880))
* **ci:** restore pytest deps and reduce legacy lint noise ([7ad4b74](https://github.com/iamez/slomix/commit/7ad4b74e98185e12e1103870f6e9bd798485738d))
* Codacy object injection — use Map instead of bracket access ([8d3ef81](https://github.com/iamez/slomix/commit/8d3ef81209102cbcd3b7413da52943426a980873))
* **codacy:** resolve static analysis issues blocking PR gate ([ea488a0](https://github.com/iamez/slomix/commit/ea488a0ed5f7787443cdfbedc64a854a037f9b2c))
* **codeql:** address remaining code quality and security alerts ([f34f0b5](https://github.com/iamez/slomix/commit/f34f0b5fee71f9aff030b2657d85c245ed74abeb))
* **codeql:** resolve PR34 security alerts and remaining empty-except ([5aaadb0](https://github.com/iamez/slomix/commit/5aaadb00b9f44506e6204facc6bcda6aef575d29))
* correct 3 critical bugs in unified CLI tools (P1, P2, P3) ([100ffe0](https://github.com/iamez/slomix/commit/100ffe0238a1b1861baeab961f4ef272e0a5eb2d))
* **critical:** production audit fixes - data accuracy, race conditions, performance ([21169df](https://github.com/iamez/slomix/commit/21169dfb6ed9ecb90ac1b215203eca503850696d))
* **db:** commit guid_canonical columns to schema (035 migration) ([#99](https://github.com/iamez/slomix/issues/99)) ([7b145fc](https://github.com/iamez/slomix/commit/7b145fc3c03cbe3baefef91b706547569007bd3a))
* **db:** execute queries on active transaction connection ([bf28d7f](https://github.com/iamez/slomix/commit/bf28d7f9dcbcf68f619637202c765e2574f0628f))
* **db:** guid_canonical migration — permanent fix for proximity-PCS GUID mismatch ([f587ba6](https://github.com/iamez/slomix/commit/f587ba6a53f8e977869b89205d04fc56c5b1f5ac))
* **db:** migration 037 — proximity_reaction_metric + 4 analytics views ([#102](https://github.com/iamez/slomix/issues/102)) ([c04d18e](https://github.com/iamez/slomix/commit/c04d18ead25bf0b2266ee724f7ba47e6f975e244))
* **db:** migration 038 — player_track round-linkage columns + backfill ([#106](https://github.com/iamez/slomix/issues/106)) ([3a28dac](https://github.com/iamez/slomix/commit/3a28dac2f9aa096f5afe2f2935c8f1ea9a3ddac4))
* **db:** migration 039 — consolidate 14 Python-runtime tables into committed migrations ([#112](https://github.com/iamez/slomix/issues/112)) ([ccf05ad](https://github.com/iamez/slomix/commit/ccf05ad116bd6266f10d1d911570d5e83f543592))
* **db:** migration 040 — dedup round_correlations + partial UNIQUE constraint ([#113](https://github.com/iamez/slomix/issues/113)) ([ac43466](https://github.com/iamez/slomix/commit/ac43466b5085e2c8f55830d59a899e1975bd516f))
* **db:** PG 17 ambiguous column in awards leaderboard query ([#107](https://github.com/iamez/slomix/issues/107)) ([cd1f1e1](https://github.com/iamez/slomix/commit/cd1f1e12209f3590233251172ca8bfa35ade6456))
* **db:** schema drift sync — migration 036 (5 fixes + tracker catchup) ([#100](https://github.com/iamez/slomix/issues/100)) ([d473e5b](https://github.com/iamez/slomix/commit/d473e5b5458dd7dcd0bafe1db73d6a93af05f0f5))
* **diagnostics:** restore gaming_sessions query lost in merge ([2abed29](https://github.com/iamez/slomix/commit/2abed296bc111c9c2a9a73c84bbea4196fd0772b))
* **docs:** correct stale 30-minute references to match actual config ([d13e3f5](https://github.com/iamez/slomix/commit/d13e3f58d935e515851bc97e12298d0706c0086d))
* **docs:** untrack investigation/scratch docs added by mistake ([d3bdb8c](https://github.com/iamez/slomix/commit/d3bdb8cc2692ca23a9fc1c8c4cf06afde7821f5e))
* eliminate all innerHTML XSS patterns flagged by Codacy ([f2b0e98](https://github.com/iamez/slomix/commit/f2b0e98643c5862571aac346e920a55795aee36b))
* eliminate ALL SQL string concat + object bracket access for Codacy ([bd1ed13](https://github.com/iamez/slomix/commit/bd1ed137f355502f7970bea79e9d3ff4491ac3ef))
* graph Decimal crash + correlation FK cascade + API rate limiting ([abfb2a8](https://github.com/iamez/slomix/commit/abfb2a810d29f1e5465aacef0b4e928064f7b804))
* **greatshot:** resolve remaining PR31 review regressions ([0d66002](https://github.com/iamez/slomix/commit/0d6600208e5c5aad67fa24bb63b43872553ebb18))
* **greatshot:** scope topshots to authenticated user and fix player_count ([e3af0e3](https://github.com/iamez/slomix/commit/e3af0e347aac54c8070fb0884bf2c4ceebc13da0))
* **greatshot:** serialize clip extraction and rank topshots across all demos ([bade215](https://github.com/iamez/slomix/commit/bade215b832b3cf46fef05bb2de256c05e46c7a1))
* handle None player names in PLAYSTYLE ANALYSIS graphs ([de29ba6](https://github.com/iamez/slomix/commit/de29ba67879ac39337c31eea47e5aba34c4d6be5))
* headshot% = hits/total_hits, revert accuracy to simple avg ([dadf622](https://github.com/iamez/slomix/commit/dadf622d47e95bacc19b48892375a9df79d65ef6))
* implement Copilot review suggestions for proximity prototype ([76b5a39](https://github.com/iamez/slomix/commit/76b5a39ed5c08ac998d2ce109f80fdb8b4d84a5d))
* **linker:** exact round_start_unix match beats closest-timestamp ([#143](https://github.com/iamez/slomix/issues/143)) ([79c8917](https://github.com/iamez/slomix/commit/79c8917efe5eeabae16615f37aa545396ecf3a53))
* **lint:** resolve CI failures — unused vars and imports ([a27b33a](https://github.com/iamez/slomix/commit/a27b33a6009c0b1d6aad2aecdecb611d813c6596))
* **lint:** resolve remaining CI review findings ([52cdad9](https://github.com/iamez/slomix/commit/52cdad9ef4819248c650f9b87e0cd0d652ae8363))
* **lint:** resolve remaining E701/F541/F821 violations ([1af8139](https://github.com/iamez/slomix/commit/1af8139b51bf8aa02939177a63b8ffd41636c74e))
* **lua:** RFC 8259-compliant JSON escape in webhook payload (v1.6.4) ([#125](https://github.com/iamez/slomix/issues/125)) ([e2caef5](https://github.com/iamez/slomix/commit/e2caef5e1affa14cf83db3b33b39999e9a232926))
* Mandelbrot audit — resolve 24 findings (2 CRITICAL, 11 HIGH, 11 MEDIUM) ([c60b9da](https://github.com/iamez/slomix/commit/c60b9da277dacf2d9841738fb760eb9a616e3d74))
* momentum chart infinite resize + CI dependency conflict + review fixes ([9151c6b](https://github.com/iamez/slomix/commit/9151c6b2b9b7796b370f734ef1deadc3833de070))
* MomentumChart non-null assertion → guard check ([6d6e899](https://github.com/iamez/slomix/commit/6d6e8993ac06c6b5e6b8e880c47a6612691894cd))
* **parser+dpm:** expand R2_ONLY_FIELDS and standardize DPM calculation ([88a0551](https://github.com/iamez/slomix/commit/88a05511832573d7217281aa47ea4c78c1e914f1))
* **parser:** correct match summary R2_ONLY_FIELDS and add timing reconciliation ([a26aed2](https://github.com/iamez/slomix/commit/a26aed229eb6c0941334151b485144bcd21f81a9))
* **parser:** correct Round 2 time_dead calculation ([a58331e](https://github.com/iamez/slomix/commit/a58331eee9eb20d2f524c15894ba65797fe676c4))
* **parser:** lower R2-raw fallback threshold 2→1 field (Layer 2 audit) ([#117](https://github.com/iamez/slomix/issues/117)) ([4968da0](https://github.com/iamez/slomix/commit/4968da0a2bd8daa86fba3249d7f260d997b5d60d))
* **proximity:** add type annotations to kill-outcomes endpoint parameters ([0090b24](https://github.com/iamez/slomix/commit/0090b243973112fe2631e236a27d20338e1e9871))
* **proximity:** events empty attacker fields + survival not differentiating ([a2ed263](https://github.com/iamez/slomix/commit/a2ed26331eec165323203ab4ac5eed4ebb941e9c))
* **proximity:** GUID name resolution supports both 32-char and 8-char formats ([b9fdbb8](https://github.com/iamez/slomix/commit/b9fdbb81c0d492632df868c43a96e5ca24f21c6c))
* **proximity:** replace saturated teamplay scoring with 5-metric percentile system ([32f9905](https://github.com/iamez/slomix/commit/32f9905e3c99a4b5712c91018bb4d782831a29b5))
* **proximity:** replace saturated teamplay with percentile scoring ([d3abf28](https://github.com/iamez/slomix/commit/d3abf287bc36c1d3878a7ee7d3cfcb2ece44fd7c))
* **proximity:** revives session_date column + kill-outcomes LIMIT parameterization ([ddae169](https://github.com/iamez/slomix/commit/ddae169b5c901bfeb5c50c5cf35b4578573c3ce8))
* **proximity:** session-scores broken query + full audit report ([be02df8](https://github.com/iamez/slomix/commit/be02df83148c60804b1a19448eac0253f0dd8570))
* **proximity:** upgrade cog from ParserV3 to ParserV4 ([e5d9b13](https://github.com/iamez/slomix/commit/e5d9b13525ce5a6da4a86f82c23646aa8db2d0ed))
* **proximity:** upgrade cog to ParserV4 for v6 section support ([a166a84](https://github.com/iamez/slomix/commit/a166a844be6985df8247a2618ec980676b205f5e))
* R2 correlation semantic merge + GUID prefix matching ([13d44b1](https://github.com/iamez/slomix/commit/13d44b1128990ac2e0fbb5d39b2d45c185d04d4a))
* Relaxed duration matching as first step ([f6e7bf1](https://github.com/iamez/slomix/commit/f6e7bf11ad95297ee35311f3fd7a89a9887aff76))
* remaining Codacy issues — Protocol stubs + health check stack trace ([e44ee2c](https://github.com/iamez/slomix/commit/e44ee2c909403dd28768ae0fcc82750715331a29))
* remove all exception information exposure in proximity_router.py ([684a21b](https://github.com/iamez/slomix/commit/684a21be230197360cc824b6932cce0dba471783))
* remove unnecessary optional chain in Proximity.tsx (last Codacy issue) ([8bf2f6e](https://github.com/iamez/slomix/commit/8bf2f6e0a03df7414dff3654cbf35081a148f70b))
* remove unused date_obj variable in players_router.py ([5d9e1b5](https://github.com/iamez/slomix/commit/5d9e1b5c4b4b44566306a156f87e761dffe4f7fd))
* rename ambiguous variable l → lk (ruff E741) ([ac357a1](https://github.com/iamez/slomix/commit/ac357a11ab519ac46e20ee7bdf3e904e4e10558d))
* replace innerHTML with DOM APIs for kill outcomes + hit regions (XSS) ([533682b](https://github.com/iamez/slomix/commit/533682b9aa72c36345b4a38c204624cf6d3dda3e))
* replace remaining 4 innerHTML blocks with DOM APIs (Codacy XSS) ([bf08322](https://github.com/iamez/slomix/commit/bf083223ea180a2f1a37540924289b669818f620))
* replace removed PUSH_MULTIPLIER import with PUSH_QUALITY_THRESHOLD ([7c6545e](https://github.com/iamez/slomix/commit/7c6545ebcd8444c1a7d7108f4886feb5d6fa6144))
* replace silent except:pass with debug logging in pagination views ([1ec85d3](https://github.com/iamez/slomix/commit/1ec85d3108c0647fc2ffc3fec25b1a96372de745))
* resolve 12 Codacy findings (MD5 security, XSS innerHTML, truthy conditional) ([fd431e1](https://github.com/iamez/slomix/commit/fd431e1878071ed7371f17d414395d53d937e2fa))
* resolve 2 admin command bugs ([6a1b454](https://github.com/iamez/slomix/commit/6a1b4548946b7d39a5ee79c8f3b385db1e955a4f))
* resolve 3 bugs blocking proximity v6 deploy ([4d45384](https://github.com/iamez/slomix/commit/4d45384ecbe5a071901cc4c5dd5514393dff4711))
* resolve 39 Codacy static analysis warnings ([030cbe1](https://github.com/iamez/slomix/commit/030cbe1e1c2b6df0c93c5d9c2ec0257dcc306d2b))
* resolve 5 Codacy issues — void arrow returns + object injection ([8bd889b](https://github.com/iamez/slomix/commit/8bd889b086b05e0588de8fa1022d2b9abb026ef5))
* resolve 6 command bugs from systematic audit ([eab30f0](https://github.com/iamez/slomix/commit/eab30f09703006a2ece4ea94eb55e20a587e1d00))
* resolve all 21 LOW/INFO audit findings ([62cb100](https://github.com/iamez/slomix/commit/62cb10033c7a77392be8980d13a85f9cf24473dd))
* resolve all 58 Codacy issues — XSS, TypeScript, SQL injection ([9086a13](https://github.com/iamez/slomix/commit/9086a134cd6e7b29bb739be83163c8334fbd05cc))
* resolve all CI lint failures (ruff F821, F841, unused imports) ([795a4b1](https://github.com/iamez/slomix/commit/795a4b1fdaa4e4f6f41be2d7cdb5f79904184b44))
* resolve all Codacy/CodeQL code scanning issues (no suppressions) ([ee168b3](https://github.com/iamez/slomix/commit/ee168b3c7e5f72efdb23de33b2188160c48a1be1))
* resolve all remaining Codacy/CodeQL alerts (30 issues, 0 suppressed) ([5790019](https://github.com/iamez/slomix/commit/57900191cca897f29d2d8a578a2cba6c80a01ec5))
* resolve CI lint failures (unused imports + variables) ([bc148ca](https://github.com/iamez/slomix/commit/bc148ca7a88b78c506dfeb788315f3887f4ab1e2))
* resolve Codacy static analysis warnings in PR [#53](https://github.com/iamez/slomix/issues/53) ([f4b1d0a](https://github.com/iamez/slomix/commit/f4b1d0a21e713e98dd8c34f981c63926f104acf7))
* resolve final 17 Codacy issues — SQL concat, object injection, stack trace ([baef473](https://github.com/iamez/slomix/commit/baef473d1f32d1d7512ad4294024713ad41f04cb))
* resolve remaining 10 Codacy issues ([7c5a478](https://github.com/iamez/slomix/commit/7c5a47856b46dc47928558a4324c42049a80b46b))
* resolve ruff lint errors for CI compliance ([cbea046](https://github.com/iamez/slomix/commit/cbea0463f061d20d7fbc2805fbe336b33e0b1856))
* restore StatsCalculator module and apply codebase review fixes ([d0539ed](https://github.com/iamez/slomix/commit/d0539ed0c4e6cd429acb3f3a82d99e9efe69d8b8))
* restore StatsCalculator module and apply codebase review fixes ([aa564f6](https://github.com/iamez/slomix/commit/aa564f62171df6994f8754a1b5452995d1f30dc7))
* rivalries.js double /api/api/ prefix + narrative session_id query ([ff00606](https://github.com/iamez/slomix/commit/ff00606923db24a92eabcacab39480992cda41b6))
* **rivalries:** leaderboard GROUP BY + player threshold + field names ([1ed65b5](https://github.com/iamez/slomix/commit/1ed65b5be9241f334866b1c63f70d13565b9b9ab))
* ruff CI errors — import sort + remove unused fallback_team_dmg ([16c9712](https://github.com/iamez/slomix/commit/16c97127ac00467dbf95bf3e5e542d62240c631f))
* ruff F841 unused var + processed_at updates on file retry ([4f8e244](https://github.com/iamez/slomix/commit/4f8e244c80e5e1b3a223b08dbe272204cefdb77b))
* security audit - 9 critical/high fixes + secrets management system ([d796457](https://github.com/iamez/slomix/commit/d796457b653f33ce5d388ba01e4a03c08313ba04))
* **security:** address CodeQL scanning alerts across codebase ([e96fd61](https://github.com/iamez/slomix/commit/e96fd61a00fa5acfa4181109dd9765e9ccd45dbf))
* **security:** close final CodeQL/Codacy findings ([c4902b4](https://github.com/iamez/slomix/commit/c4902b4c7f749d278de5bf20096c12254d01dffe))
* **security:** stop exposing internal errors in API responses + clean imports ([3d27224](https://github.com/iamez/slomix/commit/3d27224d4b21aa04f843cd7753f7c6a5d75966eb))
* session-scores crash + NULL guid safety + error-swallowing cleanup ([affe541](https://github.com/iamez/slomix/commit/affe5411716ca613ad82b4b97dd73280a9423801))
* storytelling_router broken import + ruff auto-fix tests ([b07de49](https://github.com/iamez/slomix/commit/b07de4940d9ab5d6eeaf1b0afada8a7c9589a31d))
* **storytelling:** _to_date returns string not date object ([35c3f8c](https://github.com/iamez/slomix/commit/35c3f8cc1f353945ae666bfc91b68268aa1a9393))
* **storytelling:** correct date type handling for mixed column types ([e88d54d](https://github.com/iamez/slomix/commit/e88d54d6a7686d95deb0d90ad84da4618aa266b5))
* **storytelling:** correct headshot % formula (hs_hits/total_hits not hs_kills/kills) ([3b9088f](https://github.com/iamez/slomix/commit/3b9088f40a625969090274d05fe81b1d487281e3))
* **storytelling:** enabler O(n²) → windowed scan + review polish ([1f1b04b](https://github.com/iamez/slomix/commit/1f1b04b70ca49f5f65676f4288a09de754990fc6))
* **storytelling:** fully relative archetype thresholds for competitive 3v3 ([4a06983](https://github.com/iamez/slomix/commit/4a069834186df0a1e2eac6251c31f94fe82d597f))
* **storytelling:** GUID length mismatch — PCS 8-char vs proximity 32-char ([0bc636f](https://github.com/iamez/slomix/commit/0bc636fd2472c03f9a824452788fa72bb71f4eb1))
* **storytelling:** loosen archetype thresholds for competitive balance ([5023956](https://github.com/iamez/slomix/commit/5023956b2f2fa0dfedd4222a5a21ada2ab4c6ff7))
* **storytelling:** narrative query gaming_session_id from rounds not PCS ([a3cc92b](https://github.com/iamez/slomix/commit/a3cc92bac5682e31c422e7c2f79cab70434334fe))
* **storytelling:** normalize trait comparison + review fixes ([69d9c45](https://github.com/iamez/slomix/commit/69d9c4597eb52c63806eaf06ff168545540011a1))
* **storytelling:** relative archetype thresholds using session averages ([a91c810](https://github.com/iamez/slomix/commit/a91c810fc29193cc6f46320c0baa278f15a68314))
* **storytelling:** remaining round_date TEXT queries need _to_date_str ([25eb879](https://github.com/iamez/slomix/commit/25eb879aaa743b5290992ce5f5ce852f2bf68f53))
* **storytelling:** restore _PWC_W_* weight constants lost in Sprint 6 split ([#104](https://github.com/iamez/slomix/issues/104)) ([fbc73d0](https://github.com/iamez/slomix/commit/fbc73d0e591562224727b580ad2ebe572d92c323))
* **storytelling:** strip ET colors, fix archetypes, improve moments+synergy ([e81a630](https://github.com/iamez/slomix/commit/e81a6300ee56306384157f66d538224bb0151f93))
* **storytelling:** synergy trade=0 and medic=0 — GUID format mismatch ([68e4817](https://github.com/iamez/slomix/commit/68e4817427b402a59e0b5b8702c01d0829348450))
* **storytelling:** use PCS kills for archetype KD (not KIS kills) ([1e0ce59](https://github.com/iamez/slomix/commit/1e0ce59e09e21d511e0bd3b223b70e51dd4ee554))
* suppress S112 for track path JSON parse skip ([2df0306](https://github.com/iamez/slomix/commit/2df0306be8f50db1e9a3a862c32f849a3ab4d16a))
* **tests:** correct column name file_hash → sha256_hash in db adapter test ([7c8b762](https://github.com/iamez/slomix/commit/7c8b762589cea72c4c2ff91ab1c32dfb9ff2ce28))
* **tests:** create minimal schema in CI test database ([806cdaf](https://github.com/iamez/slomix/commit/806cdafd0ee28c582629345f20a37b09d189e545))
* **tests:** remove stale players/discord_users assertions from diagnostics test ([9a4ef52](https://github.com/iamez/slomix/commit/9a4ef52f3dd6f2ed1431eea222b1c11e8827be6e))
* **tests:** resolve all 53 test failures across 22 files ([aacd8e2](https://github.com/iamez/slomix/commit/aacd8e278359b80102401cf52a87c902f42d27c5))
* **tests:** restore broken test imports after scripts consolidation ([0a1139f](https://github.com/iamez/slomix/commit/0a1139f65dc25f33c264bc8cecf3fef234a92454))
* **tests:** skip tests when dependencies are unavailable ([ad4b747](https://github.com/iamez/slomix/commit/ad4b747d2a4d8da63f891d043d8e81cb92ff5a47))
* **tests:** update mocks for endstats guard + diagnostics table rename ([7424857](https://github.com/iamez/slomix/commit/742485757adc9fa0df8bb17209fecc46d61bdf2e))
* **tools:** RCON packet encoding — use raw bytes for 0xFF prefix ([eb7d29a](https://github.com/iamez/slomix/commit/eb7d29a9c7d34acb429133b385c5f2bd6feb9a87))
* **web,proximity:** dropdown click propagation and midnight session linking ([9d45d3f](https://github.com/iamez/slomix/commit/9d45d3fc54ace0e196261aee232bb13b693f1419))
* **web:** add unsafe-inline to CSP script-src to unblock onclick handlers ([cafeb02](https://github.com/iamez/slomix/commit/cafeb026a8a5927fcf038d3931e09d550ffa3b25))
* **webhook:** consume pending Lua metadata in all file processing paths ([fb472c2](https://github.com/iamez/slomix/commit/fb472c220b4b1eceeebb6d6b09864cb1a26ead3a))
* **web:** sessions nav highlighting and stats dropdown membership ([9d80594](https://github.com/iamez/slomix/commit/9d805940e4ee6d16a52799d6187786e191e20129))
* website import order + re-linker column compatibility ([e971eeb](https://github.com/iamez/slomix/commit/e971eeb69dd77db80cee4edc311778b87a079e30))
* **website,db:** resolve 3 bugs blocking proximity v6 deploy ([f20268d](https://github.com/iamez/slomix/commit/f20268ddaaef104d9efd25bd5980ef1343f0335e))
* **website:** add deaths to session weapon mastery + show death-only weapons ([c17b8a8](https://github.com/iamez/slomix/commit/c17b8a8a98ed8d04685d20f05fbcde3d69335113))
* **website:** add missing session_date param to get_proximity_revives ([b425780](https://github.com/iamez/slomix/commit/b425780f6e2261414fb936a46e94f01dfb4a3f15))
* **website:** add useful_kills + full_selfkills to session detail endpoint ([c7cd672](https://github.com/iamez/slomix/commit/c7cd67256f1fe0a45d7338985f85cbd517fefdb1))
* **website:** add view-skill-rating container to index.html ([8711a57](https://github.com/iamez/slomix/commit/8711a5768b87949083f04c574f18d9dc8f81bb1d))
* **website:** bump BUILD_VERSION to bust browser cache for skill-rating ([a1db7ae](https://github.com/iamez/slomix/commit/a1db7aed3a5a61d0c331fd1a3ac16b964d8811ac))
* **website:** correct table names in diagnostics and records routers ([9325a0f](https://github.com/iamez/slomix/commit/9325a0f1b46d6bdcdc645ce9c3c8164cdf536a6d))
* **website:** correct table names in diagnostics/records routers ([4033833](https://github.com/iamez/slomix/commit/403383348b38b3e262848c6a35b5515126279928))
* **website:** filter 0-kill weapons from weapon mastery table ([c46574a](https://github.com/iamez/slomix/commit/c46574a94203f169eb7f4dc8dd440f912ba97cb6))
* **website:** gaming_sessions is not a table, query rounds instead ([9b43b42](https://github.com/iamez/slomix/commit/9b43b42d9f80c6a6c6631919103adb2bfa837425))
* **website:** gaming_sessions query in diagnostics ([26704b3](https://github.com/iamez/slomix/commit/26704b3015712d8b90c0a74eb9b5aa528fcffcd8))
* **website:** momentum chart axis bias, tab UI, max-w container ([06426c1](https://github.com/iamez/slomix/commit/06426c178383bd9656f6e12c0bd44e18aa27609b))
* **website:** overhaul PWC/WIS/MVP scoring with Bayesian fairness + UX clarity ([#76](https://github.com/iamez/slomix/issues/76)) ([bc13d3c](https://github.com/iamez/slomix/commit/bc13d3ccfda89a071038fcfd59927f3eca4b9a22))
* **website:** proximity page — default scope, leaderboard scoping, HTML render bugs ([e5e86b8](https://github.com/iamez/slomix/commit/e5e86b85fb2598ea3144b1d98e1e900cad6c76bd))
* **website:** React Proximity.tsx — scope filtering for KillOutcomes, HitRegions, HeadshotRates ([886a8bf](https://github.com/iamez/slomix/commit/886a8bf4a4f1481eb7fc815e73e3ce9729042eee))
* **website:** remove dead SQLite fallbacks, fix team_damage + prox_scores ([f2454b9](https://github.com/iamez/slomix/commit/f2454b91dfcb8880ff82c124cccc4dd3f1085400))
* **website:** replace 30 error-swallowing blocks with HTTPException(500) ([e1a5ccb](https://github.com/iamez/slomix/commit/e1a5ccb6208c20e38bf4edb8a44fa93ab28cd052))
* **website:** round_id JOIN, error logging, and Chart.js guards ([7dc8ea2](https://github.com/iamez/slomix/commit/7dc8ea2daa7543fd14b042de4fdb3efd3a406659))
* **website:** session graphs aggregate by player_guid, not player_name ([d37b0c2](https://github.com/iamez/slomix/commit/d37b0c28ba7030f01c0dfef3686df0462408b372))
* **website:** strip ET color codes from proximity names, fix TS errors ([b95d713](https://github.com/iamez/slomix/commit/b95d713bf960a61c580f62cae346cb119d26874b))
* **website:** upload download fix + skill rating single-pass optimization ([2cabaea](https://github.com/iamez/slomix/commit/2cabaea1347ea2948f220b692ed6ed043a28c93b))
* **website:** weapon accuracy uses SUM(hits)/SUM(shots) not AVG(accuracy) ([1b36f7f](https://github.com/iamez/slomix/commit/1b36f7f9bd00d794b484e57ce6c29231fab899e0))
* **website:** weapon mastery session_date filter + dual GUID matching ([4e09a85](https://github.com/iamez/slomix/commit/4e09a85dbdc84632f827c073fe7171b82b5ddf59))


### Performance Improvements

* **bot:** queue + dedup STATS_READY webhooks (scale-out prep) ([#142](https://github.com/iamez/slomix/issues/142)) ([2d9c249](https://github.com/iamez/slomix/commit/2d9c2491e03696f145ea97f80a86e02af37c3473))
* **cache:** enable HTTP cache for /api/storytelling/ endpoints ([#122](https://github.com/iamez/slomix/issues/122)) ([650460a](https://github.com/iamez/slomix/commit/650460a544bd7684db95bb30cd4201e792a4fdfa))
* **db:** add functional + composite indexes for hot query paths ([#041](https://github.com/iamez/slomix/issues/041)) ([#119](https://github.com/iamez/slomix/issues/119)) ([2ad013c](https://github.com/iamez/slomix/commit/2ad013c1f64a0876a46b50e8ed6abe67807b09ad))
* **proximity:** decode jsonb path locally in /tracks endpoint (~30% smaller response) ([#148](https://github.com/iamez/slomix/issues/148)) ([eb89675](https://github.com/iamez/slomix/commit/eb8967550f0756b51200196b7e1f247e2fbdedc6))
* **records:** batch resolve_display_name in hall_of_fame + awards ([#120](https://github.com/iamez/slomix/issues/120)) ([7728038](https://github.com/iamez/slomix/commit/77280386fe7d2cd485891e3a50507bae0ebde449))
* **storytelling:** cache detect_moments by (session_date, limit) ([#138](https://github.com/iamez/slomix/issues/138)) ([4e758c5](https://github.com/iamez/slomix/commit/4e758c5df9c138d820a8e80807ffcff32300cc22))

## [1.8.0](https://github.com/iamez/slomix/compare/v1.7.1...v1.8.0) (2026-04-25)

> **Scale-out prep + observability.** Diagnostics endpoint exposes live DB pool utilisation (#149) so production capacity ceilings stop being a guessing game. Combat heatmap (#145) gains a real map-image overlay instead of a blank grid. The two big stability fixes: round_linker WARN race in the STATS_READY webhook is eliminated (#140), and exact `round_start_unix` matching now beats closest-timestamp matching (#143) — fixing a long-standing source of mis-linkage during back-to-back rounds. Performance: STATS_READY webhooks are queued + deduped (#142) for scale-out, and `/tracks` decodes JSONB locally for a ~30% smaller response (#148).

### Features

* **diagnostics:** expose DB pool capacity + utilisation metrics ([#149](https://github.com/iamez/slomix/issues/149)) ([a1c27c2](https://github.com/iamez/slomix/commit/a1c27c2dba6cd0dcf8bc81d1d854e113a576d443))
* **proximity:** combat-heatmap panel uses map image overlay ([#145](https://github.com/iamez/slomix/issues/145)) ([227a0f7](https://github.com/iamez/slomix/commit/227a0f7d578006df36e54397aa99b27fcac56117))


### Bug Fixes

* **bot:** eliminate round_linker WARN race in STATS_READY webhook ([#140](https://github.com/iamez/slomix/issues/140)) ([e55b5b0](https://github.com/iamez/slomix/commit/e55b5b0e77f0d630c4d850602d92f2ca5552a4e7))
* **linker:** exact round_start_unix match beats closest-timestamp ([#143](https://github.com/iamez/slomix/issues/143)) ([79c8917](https://github.com/iamez/slomix/commit/79c8917efe5eeabae16615f37aa545396ecf3a53))


### Performance Improvements

* **bot:** queue + dedup STATS_READY webhooks (scale-out prep) ([#142](https://github.com/iamez/slomix/issues/142)) ([2d9c249](https://github.com/iamez/slomix/commit/2d9c2491e03696f145ea97f80a86e02af37c3473))
* **proximity:** decode jsonb path locally in /tracks endpoint (~30% smaller response) ([#148](https://github.com/iamez/slomix/issues/148)) ([eb89675](https://github.com/iamez/slomix/commit/eb8967550f0756b51200196b7e1f247e2fbdedc6))

## [1.7.1](https://github.com/iamez/slomix/compare/v1.7.0...v1.7.1) (2026-04-21)


### Performance Improvements

* **storytelling:** cache detect_moments by (session_date, limit) ([#138](https://github.com/iamez/slomix/issues/138)) ([4e758c5](https://github.com/iamez/slomix/commit/4e758c5df9c138d820a8e80807ffcff32300cc22))

## [1.7.0](https://github.com/iamez/slomix/compare/v1.6.0...v1.7.0) (2026-04-21)

> **Cleanup sweep — Mega Audit v3 closeout.** A single PR (#133) bundles 10 commits covering deferred Mega Audit findings P5-P8 and F8-F10, the `safe_val` helper extraction, and orphan-row drops on legacy schemas. Closes the audit cycle that started with v1.5.0 — every flagged finding is now either landed, deferred with a tracking note, or explicitly accepted-as-is.

### Features

* **audit:** cleanup sweep — 10 commits covering deferred P5-P8 + F8-F10 + safe_val + orphan drops ([#133](https://github.com/iamez/slomix/issues/133)) ([2b989cc](https://github.com/iamez/slomix/commit/2b989cc7b147b2fa9813ab58abab7a9a55341796))

## [1.6.0](https://github.com/iamez/slomix/compare/v1.5.5...v1.6.0) (2026-04-21)

> **Fairness Overhaul + Story Expansion.** KIS finally lands a graduated 7-tier reinforcement multiplier (#121) — UTRO-inspired, ties kill weight to actual respawn pressure at time-of-kill instead of a binary bonus. Storytelling pipeline gets a polish pass (#128) that hushes relinker spam and addresses 6 audit findings + 1 infra fix. Robustness: SSH connect timeout bumped 10s → 20s (#115), round_linker sanity-bounds `round_start_unix` to reject pre-2020 timestamps (#118), Lua webhook payloads now use RFC 8259-compliant JSON escapes (v1.6.4, #125), and the parser's R2-raw fallback triggers on 1 dropped field instead of 2 (#117) so single-field network glitches recover cleanly. Performance: HTTP cache enabled on storytelling endpoints (#122), `idx_player_aliases_alias_lower` functional btree drops autocomplete from 50ms → <1ms (#119, migration 041), and `resolve_display_name` is batched across hall-of-fame and awards endpoints (#120).

### Features

* **kis:** graduated UTRO-inspired reinforcement multiplier ([#121](https://github.com/iamez/slomix/issues/121)) ([48209ce](https://github.com/iamez/slomix/commit/48209cee07d83e1917fec3de63c8b8881b4ecf8b))
* **storytelling:** polish pipeline + hush relinker spam (6 audit findings + 1 infra) ([#128](https://github.com/iamez/slomix/issues/128)) ([b50c41b](https://github.com/iamez/slomix/commit/b50c41b8a773a8f89ff8866fcdaf16e8b6331285))


### Bug Fixes

* **api_helpers:** always strip ET colors from batch_resolve early returns ([#120](https://github.com/iamez/slomix/issues/120) follow-up) ([#126](https://github.com/iamez/slomix/issues/126)) ([f611c94](https://github.com/iamez/slomix/commit/f611c9478c4503c0b3abbee859949303fc641f5f))
* **audit:** address Copilot reviews across PR [#128](https://github.com/iamez/slomix/issues/128) + [#130](https://github.com/iamez/slomix/issues/130) (prod bug + 5 nits) ([#131](https://github.com/iamez/slomix/issues/131)) ([27e5b6d](https://github.com/iamez/slomix/commit/27e5b6d4c8d949adb45b3d5c3c83c19bc2a1610f))
* **bot:** bump SSH connect timeout 10s → 20s (Layer 1 audit) ([#115](https://github.com/iamez/slomix/issues/115)) ([a961e13](https://github.com/iamez/slomix/commit/a961e13f77def9d5b8d3fc0e8d64cf9a1326cee5))
* **bot:** round_linker — sanity-bound round_start_unix (Layer 2 audit) ([#118](https://github.com/iamez/slomix/issues/118)) ([bebfed5](https://github.com/iamez/slomix/commit/bebfed51d185d609c67b3120d741bec94fa1c3e2))
* **lua:** RFC 8259-compliant JSON escape in webhook payload (v1.6.4) ([#125](https://github.com/iamez/slomix/issues/125)) ([e2caef5](https://github.com/iamez/slomix/commit/e2caef5e1affa14cf83db3b33b39999e9a232926))
* **parser:** lower R2-raw fallback threshold 2→1 field (Layer 2 audit) ([#117](https://github.com/iamez/slomix/issues/117)) ([4968da0](https://github.com/iamez/slomix/commit/4968da0a2bd8daa86fba3249d7f260d997b5d60d))


### Performance Improvements

* **cache:** enable HTTP cache for /api/storytelling/ endpoints ([#122](https://github.com/iamez/slomix/issues/122)) ([650460a](https://github.com/iamez/slomix/commit/650460a544bd7684db95bb30cd4201e792a4fdfa))
* **db:** add functional + composite indexes for hot query paths ([#041](https://github.com/iamez/slomix/issues/041)) ([#119](https://github.com/iamez/slomix/issues/119)) ([2ad013c](https://github.com/iamez/slomix/commit/2ad013c1f64a0876a46b50e8ed6abe67807b09ad))
* **records:** batch resolve_display_name in hall_of_fame + awards ([#120](https://github.com/iamez/slomix/issues/120)) ([7728038](https://github.com/iamez/slomix/commit/77280386fe7d2cd485891e3a50507bae0ebde449))

## [1.5.5](https://github.com/iamez/slomix/compare/v1.5.4...v1.5.5) (2026-04-20)

> **Round linker hardening + correlation race fix.** Two production-affecting fixes land together: round_linker's race condition + midnight crossover bug is solved by a `round_start_unix BETWEEN` window with date-free fallback (#109), and `asyncio.Lock` serializes the round_correlation critical section (#114) — preventing the race where 4 pipeline events could create duplicate rows. Schema drift closes with migration 039 consolidating 14 Python-runtime tables into committed migrations (#112), and migration 040 dedups existing duplicates plus adds a partial UNIQUE index (#113).

### Bug Fixes

* **bot:** round_linker race condition + midnight crossover (date_free fallback) ([#109](https://github.com/iamez/slomix/issues/109)) ([e502b0a](https://github.com/iamez/slomix/commit/e502b0a93b64298c66794e445f4af392b92876c4))
* **bot:** serialize round_correlation critical section to prevent race ([#114](https://github.com/iamez/slomix/issues/114)) ([c97ac71](https://github.com/iamez/slomix/commit/c97ac7165923a9b946a1102a2417a4446a9375bb))
* **db:** migration 039 — consolidate 14 Python-runtime tables into committed migrations ([#112](https://github.com/iamez/slomix/issues/112)) ([ccf05ad](https://github.com/iamez/slomix/commit/ccf05ad116bd6266f10d1d911570d5e83f543592))
* **db:** migration 040 — dedup round_correlations + partial UNIQUE constraint ([#113](https://github.com/iamez/slomix/issues/113)) ([ac43466](https://github.com/iamez/slomix/commit/ac43466b5085e2c8f55830d59a899e1975bd516f))

## [1.5.4](https://github.com/iamez/slomix/compare/v1.5.3...v1.5.4) (2026-04-20)


### Bug Fixes

* **db:** migration 038 — player_track round-linkage columns + backfill ([#106](https://github.com/iamez/slomix/issues/106)) ([3a28dac](https://github.com/iamez/slomix/commit/3a28dac2f9aa096f5afe2f2935c8f1ea9a3ddac4))
* **db:** PG 17 ambiguous column in awards leaderboard query ([#107](https://github.com/iamez/slomix/issues/107)) ([cd1f1e1](https://github.com/iamez/slomix/commit/cd1f1e12209f3590233251172ca8bfa35ade6456))

## [1.5.3](https://github.com/iamez/slomix/compare/v1.5.2...v1.5.3) (2026-04-19)


### Bug Fixes

* **storytelling:** restore _PWC_W_* weight constants lost in Sprint 6 split ([#104](https://github.com/iamez/slomix/issues/104)) ([fbc73d0](https://github.com/iamez/slomix/commit/fbc73d0e591562224727b580ad2ebe572d92c323))

## [1.5.2](https://github.com/iamez/slomix/compare/v1.5.1...v1.5.2) (2026-04-19)


### Bug Fixes

* **db:** migration 037 — proximity_reaction_metric + 4 analytics views ([#102](https://github.com/iamez/slomix/issues/102)) ([c04d18e](https://github.com/iamez/slomix/commit/c04d18ead25bf0b2266ee724f7ba47e6f975e244))

## [1.5.1](https://github.com/iamez/slomix/compare/v1.5.0...v1.5.1) (2026-04-19)


### Bug Fixes

* **db:** commit guid_canonical columns to schema (035 migration) ([#99](https://github.com/iamez/slomix/issues/99)) ([7b145fc](https://github.com/iamez/slomix/commit/7b145fc3c03cbe3baefef91b706547569007bd3a))
* **db:** schema drift sync — migration 036 (5 fixes + tracker catchup) ([#100](https://github.com/iamez/slomix/issues/100)) ([d473e5b](https://github.com/iamez/slomix/commit/d473e5b5458dd7dcd0bafe1db73d6a93af05f0f5))

## [1.5.0](https://github.com/iamez/slomix/compare/v1.4.2...v1.5.0) (2026-04-17)

> **Security, Performance & Session Detail 2.0.** First post-Mega-Audit-v3 release. **Sprint 2 Security** (#80) introduces the `require_admin_user` FastAPI dependency: 10/11 diagnostics endpoints now require admin session (the 11th stays public as a health check), `strip_et_colors()` is centralized in `api_helpers` (covers 10+ consumer routers), and Discord IDs are masked at INFO log level (`1234****`) with full ID+username moved to DEBUG only. **Session Detail 2.0** (#79) ships a player × map matrix with per-round team assignment that correctly handles stopwatch side swaps (R1 attack = R2 defense — same player in same team cell across maps) AND mid-session substitutions (player on both teams appears in both rosters, stats split by rounds). Backend `build_team_matrix()` uses majority-vote side-to-team mapping; React + legacy JS consumers ship with heatmap, drill-down, and MVP★/sub⚠ badges. **Bayesian MVP/PWC/WIS overhaul** (#76): MVP uses Bayesian shrinkage (C=2 prior) so late-joiners regress toward session average, WIS v2 adopts harmonic confidence dampening (1W/3L halved, all-wins/all-losses → 0), and the `max(team_kills, 1)` PWC fairness fix eliminates 30× score inflation on zero-team-kill edges. **BOX Score Panel** (#78) lands with stopwatch match scoring and 4 parallel Invisible Value fetches (Gravity / Space / Enabler / Lurker) under race-condition guards. Date bounds validation rejects out-of-range queries as DoS mitigation, and the round_correlation_service auto-merges drifted R1/R2 correlations after bot restart.

### Features

* **website:** add BOX Score and Invisible Value panels to legacy story page ([#78](https://github.com/iamez/slomix/issues/78)) ([df23d77](https://github.com/iamez/slomix/commit/df23d77aacd7420f253093c3f8f7318cf8c94594))
* **website:** session detail 2.0 matrix + Mega Audit v3 Sprint 1 ([#79](https://github.com/iamez/slomix/issues/79)) ([7848233](https://github.com/iamez/slomix/commit/7848233429660fb4a058e9e5514afe75a068cca2))


### Bug Fixes

* **website:** overhaul PWC/WIS/MVP scoring with Bayesian fairness + UX clarity ([#76](https://github.com/iamez/slomix/issues/76)) ([bc13d3c](https://github.com/iamez/slomix/commit/bc13d3ccfda89a071038fcfd59927f3eca4b9a22))

## [1.4.2](https://github.com/iamez/slomix/compare/v1.4.1...v1.4.2) (2026-04-06)


### Bug Fixes

* **bot:** assign random team names when _auto_assign_teams pre-creates "Team A/B" ([27443c8](https://github.com/iamez/slomix/commit/27443c879cd07ac38a2510ae1b9a11e2c92764b2))
* **bot:** guard auto team name assignment against repeated attempts ([44c9516](https://github.com/iamez/slomix/commit/44c9516344e8be215b638fc8c0aaebc6a2e069dd))

## [1.4.1](https://github.com/iamez/slomix/compare/v1.4.0...v1.4.1) (2026-04-06)


### Bug Fixes

* **proximity:** replace saturated teamplay scoring with 5-metric percentile system ([32f9905](https://github.com/iamez/slomix/commit/32f9905e3c99a4b5712c91018bb4d782831a29b5))
* **proximity:** replace saturated teamplay with percentile scoring ([d3abf28](https://github.com/iamez/slomix/commit/d3abf287bc36c1d3878a7ee7d3cfcb2ece44fd7c))

## [1.4.0](https://github.com/iamez/slomix/compare/v1.3.0...v1.4.0) (2026-04-03)

> **Storytelling expansion — Invisible Value metrics.** Three new per-round metrics quantify the contributions that don't show up in the K/D column: **Gravity** (how much enemy attention a player draws), **Space-created** (cleared map area enabling teammate plays), and **Enabler score** (kills you set up that teammates finish). Adds a **Lurker profile** computed from `player_track.path` JSONB to surface solo-time players, and per-player **invisible-value micro-narratives** that turn the metrics into prose. Backend perf: enabler score moves from O(n²) to a windowed scan. Bug-fix sweep: 30 error-swallowing blocks across the website replaced with proper `HTTPException(500)`, GUID name resolution now supports both 32-char and 8-char formats, and synergy trade=0/medic=0 (a GUID-format-mismatch silent failure) is fixed. Round correlation system gains proximity tracking integration.

### Features

* **bot:** add proximity tracking to round correlation system ([f701ee8](https://github.com/iamez/slomix/commit/f701ee859648a9625b49559305c869abf045be14))
* **storytelling:** add enabler score metric ([c569a9e](https://github.com/iamez/slomix/commit/c569a9e331f9338d3d5deb72f6e424d7c9cfcf25))
* **storytelling:** add gravity and space-created metrics ([2be0deb](https://github.com/iamez/slomix/commit/2be0deb3ca3d0d56c5319104ecf667a600c9ada0))
* **storytelling:** add lurker profile — solo time from player_track paths ([71edee0](https://github.com/iamez/slomix/commit/71edee0b056a9a71bf26dbae1edf04d12c20c193))
* **storytelling:** narrative polish + enabler dedup + frontend panel ([cde42dd](https://github.com/iamez/slomix/commit/cde42dd69717409effe75994cae4d224b5f42ad0))
* **storytelling:** per-player micro-narratives with invisible value metrics ([d8f533e](https://github.com/iamez/slomix/commit/d8f533e116043b79a01293c43d67d4207bf89aef))


### Bug Fixes

* **proximity:** events empty attacker fields + survival not differentiating ([a2ed263](https://github.com/iamez/slomix/commit/a2ed26331eec165323203ab4ac5eed4ebb941e9c))
* **proximity:** GUID name resolution supports both 32-char and 8-char formats ([b9fdbb8](https://github.com/iamez/slomix/commit/b9fdbb81c0d492632df868c43a96e5ca24f21c6c))
* **proximity:** session-scores broken query + full audit report ([be02df8](https://github.com/iamez/slomix/commit/be02df83148c60804b1a19448eac0253f0dd8570))
* rename ambiguous variable l → lk (ruff E741) ([ac357a1](https://github.com/iamez/slomix/commit/ac357a11ab519ac46e20ee7bdf3e904e4e10558d))
* session-scores crash + NULL guid safety + error-swallowing cleanup ([affe541](https://github.com/iamez/slomix/commit/affe5411716ca613ad82b4b97dd73280a9423801))
* **storytelling:** enabler O(n²) → windowed scan + review polish ([1f1b04b](https://github.com/iamez/slomix/commit/1f1b04b70ca49f5f65676f4288a09de754990fc6))
* **storytelling:** normalize trait comparison + review fixes ([69d9c45](https://github.com/iamez/slomix/commit/69d9c4597eb52c63806eaf06ff168545540011a1))
* **storytelling:** synergy trade=0 and medic=0 — GUID format mismatch ([68e4817](https://github.com/iamez/slomix/commit/68e4817427b402a59e0b5b8702c01d0829348450))
* suppress S112 for track path JSON parse skip ([2df0306](https://github.com/iamez/slomix/commit/2df0306be8f50db1e9a3a862c32f849a3ab4d16a))
* **tools:** RCON packet encoding — use raw bytes for 0xFF prefix ([eb7d29a](https://github.com/iamez/slomix/commit/eb7d29a9c7d34acb429133b385c5f2bd6feb9a87))
* **website:** replace 30 error-swallowing blocks with HTTPException(500) ([e1a5ccb](https://github.com/iamez/slomix/commit/e1a5ccb6208c20e38bf4edb8a44fa93ab28cd052))

## [1.3.0](https://github.com/iamez/slomix/compare/v1.2.0...v1.3.0) (2026-04-01)

> **ET Rating v2 + Replay Map Visualization + GUID canonical fix.** ET Rating expands to a 15-metric formula (9 PCS + 6 proximity) with composite stats endpoint and a legacy JS panel. **Replay map visualization** ships with player tracks, kill markers, and playback controls — turning each round into a navigable 2D timeline. The **`guid_canonical` migration** is the structural fix for the proximity-PCS GUID mismatch that had been quietly cross-polluting analytics: all proximity tables now carry a canonical 8-char column matching player_comprehensive_stats. Session stats gain Useful Kills, Self Kills, and Full Self Kills. Mandelbrot RCA review addresses 8 audit findings; Codacy compliance: 5 issues resolved (void arrow returns + object injection); 30 error-swallowing blocks → `HTTPException(500)`. Smaller wins: weapon mastery filters 0-kill weapons, weapon accuracy uses `SUM(hits)/SUM(shots)` not `AVG(accuracy)`, momentum chart axis bias fixed.

### Features

* **website:** add Useful Kills, Self Kills, Full Self Kills to session stats ([e9a0cc8](https://github.com/iamez/slomix/commit/e9a0cc82734c6a307a9d444437bd65b595a29c77))
* **website:** ET Rating v2, nav reorganization, KIS/PWC proximity enrichment ([f63c3bb](https://github.com/iamez/slomix/commit/f63c3bba902bc8acd096db2cd36c0321c773b4c1))
* **website:** replay map visualization with player tracks, kill markers, playback controls ([b9c99d9](https://github.com/iamez/slomix/commit/b9c99d9052659c853275839e7cf84e86361e9405))


### Bug Fixes

* address all 8 audit findings from Mandelbrot RCA review ([7f54ac4](https://github.com/iamez/slomix/commit/7f54ac4c1fc36d5c068e479809aff4fecd4522d0))
* **bot,website:** lua round linker fallback + ET color strip in v6 panels ([4e3754f](https://github.com/iamez/slomix/commit/4e3754f17091af549b7982d9951ca77c56bb110c))
* **bot:** correlation merge for Lua/stats match_id mismatch + disable dead cog ([25166fe](https://github.com/iamez/slomix/commit/25166feb956d9f52a12724979ab2c0580c9d8425))
* Codacy object injection — use Map instead of bracket access ([8d3ef81](https://github.com/iamez/slomix/commit/8d3ef81209102cbcd3b7413da52943426a980873))
* **db:** guid_canonical migration — permanent fix for proximity-PCS GUID mismatch ([f587ba6](https://github.com/iamez/slomix/commit/f587ba6a53f8e977869b89205d04fc56c5b1f5ac))
* R2 correlation semantic merge + GUID prefix matching ([13d44b1](https://github.com/iamez/slomix/commit/13d44b1128990ac2e0fbb5d39b2d45c185d04d4a))
* resolve 5 Codacy issues — void arrow returns + object injection ([8bd889b](https://github.com/iamez/slomix/commit/8bd889b086b05e0588de8fa1022d2b9abb026ef5))
* ruff CI errors — import sort + remove unused fallback_team_dmg ([16c9712](https://github.com/iamez/slomix/commit/16c97127ac00467dbf95bf3e5e542d62240c631f))
* **website:** add deaths to session weapon mastery + show death-only weapons ([c17b8a8](https://github.com/iamez/slomix/commit/c17b8a8a98ed8d04685d20f05fbcde3d69335113))
* **website:** add useful_kills + full_selfkills to session detail endpoint ([c7cd672](https://github.com/iamez/slomix/commit/c7cd67256f1fe0a45d7338985f85cbd517fefdb1))
* **website:** filter 0-kill weapons from weapon mastery table ([c46574a](https://github.com/iamez/slomix/commit/c46574a94203f169eb7f4dc8dd440f912ba97cb6))
* **website:** momentum chart axis bias, tab UI, max-w container ([06426c1](https://github.com/iamez/slomix/commit/06426c178383bd9656f6e12c0bd44e18aa27609b))
* **website:** remove dead SQLite fallbacks, fix team_damage + prox_scores ([f2454b9](https://github.com/iamez/slomix/commit/f2454b91dfcb8880ff82c124cccc4dd3f1085400))
* **website:** session graphs aggregate by player_guid, not player_name ([d37b0c2](https://github.com/iamez/slomix/commit/d37b0c28ba7030f01c0dfef3686df0462408b372))
* **website:** weapon accuracy uses SUM(hits)/SUM(shots) not AVG(accuracy) ([1b36f7f](https://github.com/iamez/slomix/commit/1b36f7f9bd00d794b484e57ce6c29231fab899e0))
* **website:** weapon mastery session_date filter + dual GUID matching ([4e09a85](https://github.com/iamez/slomix/commit/4e09a85dbdc84632f827c073fe7171b82b5ddf59))

## [1.2.0](https://github.com/iamez/slomix/compare/v1.1.2...v1.2.0) (2026-03-30)

> **Mandelbrot RCA v2.0 + Oksii adoption + the foundation release.** This is the inflection point: the project moves from "feature factory" to "audited platform." A 6-phase Mandelbrot audit drives ruff from 2,257 → 0 errors (8 rule sets enabled), eliminates 23 silent `except: pass` blocks, replaces the unbounded `_compute_locks` dict with a `BoundedLockDict` (max 64, LRU), and centralizes shared constants in `et_constants.py`. Two god files are decomposed: `proximity_router.py` 5,515 → 14 sub-routers, `records_router.py` 3,172 → 10 sub-routers. **Oksii Lua v6.01 adoption** brings `killer_health`, `alive_count`, and reinf timing into KIS v2 (3 new multipliers + soft cap at 5.0) and a new BOX scoring service (`box_scoring_service.py`) for Oksii-style stopwatch map scoring. Storytelling evolves: Gravity, Space-created, Enabler, Lurker, and per-player Invisible Value micro-narratives. Proximity pipeline finally fixes its 60% historical linkage failure rate via STATS_READY webhook + re-linker + 2min polling. AI Match Predictions ship Phases 1-7 with auto voice-channel detection. Player Rivalries (H2H, nemesis/prey/rival classification) and Win Contribution (PWC/WIS/WAA, 5-component formula) land as first-class features. Tests grow from 476 → 540 with 33-round end-to-end bot verification (2,781 positions tracked).

### Features

* add cumulative endstats to !last_session + fix race conditions ([2f5fb33](https://github.com/iamez/slomix/commit/2f5fb338634adffe11a795046b689afe5bf42754))
* add proximity tracker prototype ([f44f080](https://github.com/iamez/slomix/commit/f44f0808ff53d4495e7dda0c63078a946217060d))
* add proximity tracker prototype ([85355de](https://github.com/iamez/slomix/commit/85355de181f9f5d853a943b34becd2063dc1000e))
* add website prototype ([#27](https://github.com/iamez/slomix/issues/27)) ([b69d1b3](https://github.com/iamez/slomix/commit/b69d1b38fca5c1c4ebbd322910e3989af8e35301))
* **analytics:** Add player analytics commands (Phase 1) ([cee91a6](https://github.com/iamez/slomix/commit/cee91a6e404ccf9ca2e72194005b0338a3482406))
* **bot,website:** fix R2 lua webhook, add round visualizer, restore planning docs ([16d9412](https://github.com/iamez/slomix/commit/16d9412abfb3d7d022b8674201ddbf484135ee25))
* **bot,website:** WS2+WS3 timing join logging, diagnostics, embed validation ([eff63b9](https://github.com/iamez/slomix/commit/eff63b9fc732b75c3cfffd8bdb664e6ebfdca6fb))
* **bot:** add ADR/KPR/DPR metrics + clean remaining SQLite branches ([ac9369a](https://github.com/iamez/slomix/commit/ac9369a73c7ceea15e05a811dfb17baadca6581b))
* **bot:** add command_error_handler decorator to utils ([463aa59](https://github.com/iamez/slomix/commit/463aa59d56b5cac1551d9fc8cf12bdef25615ff8))
* **bot:** canonicalize match_id in stats import path via round correlation context ([8a9497f](https://github.com/iamez/slomix/commit/8a9497f4efeccd8dfb204a033ca0bcac2d69e694))
* **bot:** enhance correlation service and add linkage diagnostics ([39df70e](https://github.com/iamez/slomix/commit/39df70e3109b8139c377e5779de91f49d51c7a18))
* **bot:** round correlation system + match_id fix + ET:Legacy research ([d47a85c](https://github.com/iamez/slomix/commit/d47a85ccce2e1cd19cb14d33810b4abba2029b48))
* **db:** add SQL migrations 005-013 and website migrations ([48e9361](https://github.com/iamez/slomix/commit/48e9361a35c6b5f153007e6f4dc93d2f2fa68555))
* **db:** migrations 014/015 — proximity round_id columns + backfill ([10b51b8](https://github.com/iamez/slomix/commit/10b51b8b5e9595e050028eed49abec12573984f4))
* Deep RCA audit — 26 fixes, skill rating v1.1, error masking overhaul ([aa5c5ca](https://github.com/iamez/slomix/commit/aa5c5ca61fc760725381b70ca37ffe4530705aac))
* **greatshot:** complete Phase 2-5 + topshots API endpoints ([c3c9797](https://github.com/iamez/slomix/commit/c3c9797b7047370314a8cdfd1e4c6d72a8355809))
* **greatshot:** enhance demo-to-stats cross-reference matching ([f6e7bf1](https://github.com/iamez/slomix/commit/f6e7bf11ad95297ee35311f3fd7a89a9887aff76))
* **greatshot:** enrich highlight metadata and add DB cross-reference ([3e79f9b](https://github.com/iamez/slomix/commit/3e79f9bc968bf0e42ce80632b4fe4e7eac5f39a4))
* **greatshot:** multi-file upload + player stats display ([6814138](https://github.com/iamez/slomix/commit/6814138ab2a58ded5111c9aa0603c1b462591596))
* legacy Smart Stats page + round linker fix + endstats guard ([152460d](https://github.com/iamez/slomix/commit/152460d6f553fe11b2530cc77889ee713771dd7d))
* **logging:** add comprehensive logging across bot and website ([fcbb4e5](https://github.com/iamez/slomix/commit/fcbb4e55d08c25aa9cfd93e8f1d9ffc8cf36b903))
* **matchup:** Add matchup analytics system for lineup vs lineup stats ([6a2fca3](https://github.com/iamez/slomix/commit/6a2fca32f761e5da7c5a2285d9e636ce5774b4d5))
* **oksii:** Oksii adoption — KIS v2 multipliers, BOX scoring, Lua deploy ([876555d](https://github.com/iamez/slomix/commit/876555d8a0f6002043c251b1d6203bdf695663a0))
* Player Rivalries + Win Contribution (PWC/WIS/WAA) ([332949f](https://github.com/iamez/slomix/commit/332949fb772078c4ebd4f49e0a0a1a4ac94e2416))
* proximity v5.2 analytics, ET Rating, code quality fixes ([53f5050](https://github.com/iamez/slomix/commit/53f50508580c71ef619da373785d18013252057d))
* **proximity:** add canonical round_id linkage to all proximity tables ([bacbfc1](https://github.com/iamez/slomix/commit/bacbfc1052ed505aab46e6701be63346e58638bf))
* **proximity:** add composite scoring system + complete v5.2 frontend panels ([ebb5f18](https://github.com/iamez/slomix/commit/ebb5f187e9f47663dc2ce5ab451b9eab1535d999))
* **proximity:** add kill outcomes, hit regions, combat heatmaps & movement analytics (v5.2) ([b26b989](https://github.com/iamez/slomix/commit/b26b9896966e3df39bc02df2271e0b210a23dca9))
* **proximity:** add objective coord assets and web map data ([614e533](https://github.com/iamez/slomix/commit/614e53355aed18ee5b049987b120f1bf202462df))
* **proximity:** expand Lua tracker, objective coords, and web analytics ([be76076](https://github.com/iamez/slomix/commit/be76076f23d9c861814aa1a91609552f5279973a))
* **proximity:** pipeline fix + full leaderboard scoping + frontend UX overhaul ([d248baa](https://github.com/iamez/slomix/commit/d248baa64b6facedda8bf964b108c53cfdb22e24))
* **proximity:** upgrade gameserver Lua to v5.0 with full teamplay sections ([7cbc3eb](https://github.com/iamez/slomix/commit/7cbc3eb49dc79e352ccc4281fa0d0bc729975ded))
* **proximity:** v6.01 objective intelligence + full frontend coverage + bot GUID fix ([#53](https://github.com/iamez/slomix/issues/53)) ([83bfd1e](https://github.com/iamez/slomix/commit/83bfd1ec1b9a6c3c69f764b6ba3b5bbb962d50c6))
* **proximity:** v6.01 objective intelligence + missing panels + bot GUID fix ([83bfd1e](https://github.com/iamez/slomix/commit/83bfd1ec1b9a6c3c69f764b6ba3b5bbb962d50c6))
* **proximity:** v6.01 objective intelligence + missing panels + bot GUID fix ([73ad6ef](https://github.com/iamez/slomix/commit/73ad6ef0f027b759d5f47b2d08bedeb4593b92c0))
* reconcile local work — sessions redesign, proximity, deploy tooling ([52ba75f](https://github.com/iamez/slomix/commit/52ba75f0c3656fc87bcc3ac1e379e9ea3eae6231))
* **scoring+teams:** Map-based stopwatch scoring + real-time team tracking ([64dc2ab](https://github.com/iamez/slomix/commit/64dc2ab9598798c7df4815a092a7e2207853d2e2))
* **scripts:** add backfill, gate, smoke test, and deployment scripts ([cb0dad6](https://github.com/iamez/slomix/commit/cb0dad6d4b70d02dfb2aa9b3c279a965e49d2ca9))
* **session-embed:** add team detection confidence indicator ([b0cb46d](https://github.com/iamez/slomix/commit/b0cb46de779d2eec322a98464369588e40979403))
* **storytelling:** 4 new objective moment detectors + enhanced kill streaks ([db7f293](https://github.com/iamez/slomix/commit/db7f2938d8762cac8ee84c527bfff127cb241441))
* **storytelling:** DPM + denied time + time dead in archetype classification ([6a71907](https://github.com/iamez/slomix/commit/6a71907414dc73853b826ff9e078d2ca8290c0b0))
* **storytelling:** Kill Impact Score — Phase 1 complete ([ed62d9c](https://github.com/iamez/slomix/commit/ed62d9cb399c106f0d8d3199979311134f204bf8))
* **storytelling:** moments timeline + synergy panel + type diversity fix ([ed9032c](https://github.com/iamez/slomix/commit/ed9032c24007db7ebb7d3202f21c487132fb40e0))
* **storytelling:** Slomix-stein /#/story page — cinematic Smart Stats UI ([6e2bc35](https://github.com/iamez/slomix/commit/6e2bc354490fb71cb7eddaffa6255738198e266e))
* **storytelling:** Smart Stats Phase 2 — Moments, Archetypes, Synergy ([e34d4e8](https://github.com/iamez/slomix/commit/e34d4e85bc5b6db3fc93ec86b3e86f42d28992ae))
* **storytelling:** team wipe + multikill detectors with rich context ([31d39d1](https://github.com/iamez/slomix/commit/31d39d1f0bfaeb1b2c4286af25f128102ccfbaea))
* **team-detection:** enhance with defender_team validation and confidence scoring ([65c633e](https://github.com/iamez/slomix/commit/65c633e541c14c331ded12fefb6dd950b2ae3e83))
* **timing-comparison:** add timing legend to embed description ([4fa4aa3](https://github.com/iamez/slomix/commit/4fa4aa3aacc50cdd89145ef7d2b49572bda5d2e3))
* **tools:** add pipeline verification script (WS1-007 gate check) ([1b12edb](https://github.com/iamez/slomix/commit/1b12edb41ce9acb945225b3c45f0bb55a35b4398))
* v1.0.6 - analytics, matchup system, website overhaul, proximity tracker ([33a2468](https://github.com/iamez/slomix/commit/33a24683a128fccaf9de5bc005341b2e2e8e616b))
* v1.0.7 - greatshot demo pipeline, DB manager overhaul, README rewrite ([a925cb8](https://github.com/iamez/slomix/commit/a925cb8007a6b22ef5cefba34a6ffd4d9b96499e))
* v1.1.0 — stats accuracy audit, React 19 frontend, proximity v5 ([d5aec31](https://github.com/iamez/slomix/commit/d5aec31e444e26ecd9f9b9b76b840b7080598df6))
* v1.1.0 — stats accuracy audit, React 19 frontend, proximity v5 teamplay ([674cee9](https://github.com/iamez/slomix/commit/674cee9f5c8d2ac5b114711ea8f9f5103372d322))
* v1.4.0 — Replay Timeline, Momentum, Narrative + 2 critical data fixes ([efffc5c](https://github.com/iamez/slomix/commit/efffc5cfac9b0804a30a592114c55d390b7091a4))
* **webhook:** add real-time stats notification via Discord webhook ([4ee9609](https://github.com/iamez/slomix/commit/4ee960953026bd84e5dd7628563662d4893879e1))
* **webhook:** fix Lua gamestate detection + timing comparison service ([622dc65](https://github.com/iamez/slomix/commit/622dc65528257e48edd31c36a4506bda385401a5))
* **web:** prefer exact round_id join with fuzzy fallback in proximity API ([f70253e](https://github.com/iamez/slomix/commit/f70253ec94a211c176f4b618d6b0d6c3f786dc2f))
* **website:** add ET Rating skill system (experimental) ([aa2c514](https://github.com/iamez/slomix/commit/aa2c514c156a94ea935e34e36e7d4e462def4834))
* **website:** add ET Rating to navigation menu ([fe578af](https://github.com/iamez/slomix/commit/fe578af19b117d64c38f26704fc1ea3d48f91640))
* **website:** admin System Overview redesign + proximity color code fix ([8af0840](https://github.com/iamez/slomix/commit/8af0840111cd4b93bcb75c52e5c1d88fc35564e0))
* **website:** React 19 modernization with game assets integration ([2bc069f](https://github.com/iamez/slomix/commit/2bc069f3ed4cc73ec494b76497d0ef03c335c3dd))
* **website:** redesign Admin System Overview page ([96df809](https://github.com/iamez/slomix/commit/96df809a7dc26b2f2bafc82d3328573b68d497cd))
* **website:** sessions redesign, proximity fixes, deploy script updates ([955f52f](https://github.com/iamez/slomix/commit/955f52f157a1e57ebaa4316b642fad9e7f518eb2))
* **website:** show Oksii multiplier badges on story player cards ([b29106e](https://github.com/iamez/slomix/commit/b29106ea3508aa90339e072a70b7d0c6f3b8ad8d))
* **website:** storytelling page improvements — narrative, momentum, KIS fix ([a71b335](https://github.com/iamez/slomix/commit/a71b335ab41f5cbc1e18d0176e167517a5633cd7))
* **website:** wire Smart Stats into legacy navigation ([4b65669](https://github.com/iamez/slomix/commit/4b656697854e85907263ee313c89dbdd23c5859f))


### Bug Fixes

* !sync_month error and document SQL query safety ([4a69ac5](https://github.com/iamez/slomix/commit/4a69ac57f9627552b5900d204d751b7def514e61))
* !sync_month error and document SQL query safety ([8dd1229](https://github.com/iamez/slomix/commit/8dd12298d82a2433caf0f6c5322f412d5f7f0336))
* address codacy findings for availability notifications ([e0b84c5](https://github.com/iamez/slomix/commit/e0b84c5291818153be712e618a275902d6ec53fb))
* address Codex P1/P2 review findings ([1d2f946](https://github.com/iamez/slomix/commit/1d2f946d5fcef8cc77d71a1d3095b7ec92dd8626))
* address PR [#35](https://github.com/iamez/slomix/issues/35) review comments ([04cc599](https://github.com/iamez/slomix/commit/04cc5991e79c48295568e7d23cb487a2a97b60c3))
* address PR31 regressions and weapons/analytics runtime issues ([dd98a17](https://github.com/iamez/slomix/commit/dd98a17e92922de8a8be322ec6c0c6760934b285))
* address remaining Codex findings for legacy JS ([266c05a](https://github.com/iamez/slomix/commit/266c05a96dc9b97bacae849a45236be5c1af42dd))
* **bot,docs:** ghost round filter, round linker delay, warning fatigue, SQLite doc cleanup ([bb3cd79](https://github.com/iamez/slomix/commit/bb3cd796721616f5cf748b5e7cf37397f766a97b))
* **bot,lua,web:** multi-phase bugfix sweep from super prompt audit ([64d6f57](https://github.com/iamez/slomix/commit/64d6f5707ba93d36a8d8405e8acc66ef7c1b1774))
* **bot,proximity,greatshot:** execute WS runbook tasks — reconnect, proximity, crossref ([20d84e6](https://github.com/iamez/slomix/commit/20d84e6270852618f14930538b62aa5f1d918468))
* **bot,web:** correct headshot %, denied playtime display, and website formula alignment ([aa116a6](https://github.com/iamez/slomix/commit/aa116a6d1b0ef1e9a4889a61d95c1f8547e2b998))
* **bot:** add Discord posting error alerting and fix health monitor ([3c840d2](https://github.com/iamez/slomix/commit/3c840d2d5dceffa6863580c000307e9e0e7a2392))
* **bot:** Discord posting error alerting + health monitor fix ([e4771dc](https://github.com/iamez/slomix/commit/e4771dc9f9d6ba52d957830cb93c3d1e76ed3d97))
* **bot:** final sprint — session finalization, embed overflow, SQLite guards, matchup SQL ([6d24d2f](https://github.com/iamez/slomix/commit/6d24d2f4cea062567aeed5ea13462d5f0ea9c334))
* **bot:** remove hard dependency on tools.stopwatch_scoring in session cog ([d23f51a](https://github.com/iamez/slomix/commit/d23f51ae76e98aad15118430fd6fb838752e6e26))
* **bot:** remove proximity_revive + proximity_weapon_accuracy from re-linker ([cb588b0](https://github.com/iamez/slomix/commit/cb588b0f43b36fabc1faeba99583b6c8ac66d17a))
* **bot:** resolve Lua round_id linkage race condition ([e216b92](https://github.com/iamez/slomix/commit/e216b92f87b9313477cc925904938c195c588bbf))
* **bot:** round linker timezone mismatch — UTC vs local naive datetime ([52e6521](https://github.com/iamez/slomix/commit/52e652182de3ee2c66996414e802ab7611e7250f))
* **bot:** SQL param count mismatch and placeholder consistency ([cc94275](https://github.com/iamez/slomix/commit/cc9427511468b63d71e8b834247036c4013ebdbe))
* **bot:** WS0 column cache refresh, restart detection gap guard, sprint closure ([3f42952](https://github.com/iamez/slomix/commit/3f42952872ba370d9394a521d32ff6ceafe01f08))
* Build short→long GUID lookup map, match PCS by first 8 chars. ([0bc636f](https://github.com/iamez/slomix/commit/0bc636fd2472c03f9a824452788fa72bb71f4eb1))
* **ci-security:** unblock test imports and harden retro viz rendering ([2988da8](https://github.com/iamez/slomix/commit/2988da8e69d72d58d09f7e6401153b511a8b2344))
* **ci-tests:** use postgres schema and align db adapter tests ([e3bfdd6](https://github.com/iamez/slomix/commit/e3bfdd6cae82618735832126bf07f074ed69b253))
* **ci:** add all required env vars for Docker Build ([453cf32](https://github.com/iamez/slomix/commit/453cf322a4b33c722a757844a8f57a6edc44fc94))
* **ci:** add schema files and restore adapter/test compatibility ([4f447fa](https://github.com/iamez/slomix/commit/4f447fa7bdbe586df744aec96fcec58a0bb0a8f5))
* **ci:** Docker Build needs .env placeholder + empty except comment ([706c352](https://github.com/iamez/slomix/commit/706c3522d9f6a3c1cb55235868c5dbfd56475f94))
* **ci:** f-string prefix lint + exclude game assets from size check ([e9efcd2](https://github.com/iamez/slomix/commit/e9efcd2dea3692a7c70b83de0e13593648f90df0))
* **ci:** make Codecov non-blocking, exclude build artifacts from Codacy/CodeQL ([f17fd9e](https://github.com/iamez/slomix/commit/f17fd9ed75cf08939ba6d9f65707bdb0f6e5e8a8))
* **ci:** make slowapi optional with no-op stub for CI/test environments ([8114a6d](https://github.com/iamez/slomix/commit/8114a6d2507c96e79c010c073b9e87f133d9433f))
* **ci:** migrate CodeQL action to v4 ([7ab90da](https://github.com/iamez/slomix/commit/7ab90da04e3d2c4496d1d6772a801fbd7996f389))
* **ci:** remove redundant SARIF upload step from CodeQL workflow ([f80e008](https://github.com/iamez/slomix/commit/f80e0083b1515f6d37d11e47276e51c943002ce9))
* **ci:** resolve file-checks and JavaScript lint failures ([3107d7c](https://github.com/iamez/slomix/commit/3107d7cd736031d64cfaac497797a841733f5880))
* **ci:** restore pytest deps and reduce legacy lint noise ([7ad4b74](https://github.com/iamez/slomix/commit/7ad4b74e98185e12e1103870f6e9bd798485738d))
* **codacy:** resolve static analysis issues blocking PR gate ([ea488a0](https://github.com/iamez/slomix/commit/ea488a0ed5f7787443cdfbedc64a854a037f9b2c))
* **codeql:** address remaining code quality and security alerts ([f34f0b5](https://github.com/iamez/slomix/commit/f34f0b5fee71f9aff030b2657d85c245ed74abeb))
* **codeql:** resolve PR34 security alerts and remaining empty-except ([5aaadb0](https://github.com/iamez/slomix/commit/5aaadb00b9f44506e6204facc6bcda6aef575d29))
* correct 3 critical bugs in unified CLI tools (P1, P2, P3) ([100ffe0](https://github.com/iamez/slomix/commit/100ffe0238a1b1861baeab961f4ef272e0a5eb2d))
* **critical:** production audit fixes - data accuracy, race conditions, performance ([21169df](https://github.com/iamez/slomix/commit/21169dfb6ed9ecb90ac1b215203eca503850696d))
* **db:** execute queries on active transaction connection ([bf28d7f](https://github.com/iamez/slomix/commit/bf28d7f9dcbcf68f619637202c765e2574f0628f))
* **diagnostics:** restore gaming_sessions query lost in merge ([2abed29](https://github.com/iamez/slomix/commit/2abed296bc111c9c2a9a73c84bbea4196fd0772b))
* **docs:** correct stale 30-minute references to match actual config ([d13e3f5](https://github.com/iamez/slomix/commit/d13e3f58d935e515851bc97e12298d0706c0086d))
* **docs:** untrack investigation/scratch docs added by mistake ([d3bdb8c](https://github.com/iamez/slomix/commit/d3bdb8cc2692ca23a9fc1c8c4cf06afde7821f5e))
* eliminate all innerHTML XSS patterns flagged by Codacy ([f2b0e98](https://github.com/iamez/slomix/commit/f2b0e98643c5862571aac346e920a55795aee36b))
* eliminate ALL SQL string concat + object bracket access for Codacy ([bd1ed13](https://github.com/iamez/slomix/commit/bd1ed137f355502f7970bea79e9d3ff4491ac3ef))
* graph Decimal crash + correlation FK cascade + API rate limiting ([abfb2a8](https://github.com/iamez/slomix/commit/abfb2a810d29f1e5465aacef0b4e928064f7b804))
* **greatshot:** resolve remaining PR31 review regressions ([0d66002](https://github.com/iamez/slomix/commit/0d6600208e5c5aad67fa24bb63b43872553ebb18))
* **greatshot:** scope topshots to authenticated user and fix player_count ([e3af0e3](https://github.com/iamez/slomix/commit/e3af0e347aac54c8070fb0884bf2c4ceebc13da0))
* **greatshot:** serialize clip extraction and rank topshots across all demos ([bade215](https://github.com/iamez/slomix/commit/bade215b832b3cf46fef05bb2de256c05e46c7a1))
* handle None player names in PLAYSTYLE ANALYSIS graphs ([de29ba6](https://github.com/iamez/slomix/commit/de29ba67879ac39337c31eea47e5aba34c4d6be5))
* headshot% = hits/total_hits, revert accuracy to simple avg ([dadf622](https://github.com/iamez/slomix/commit/dadf622d47e95bacc19b48892375a9df79d65ef6))
* implement Copilot review suggestions for proximity prototype ([76b5a39](https://github.com/iamez/slomix/commit/76b5a39ed5c08ac998d2ce109f80fdb8b4d84a5d))
* **lint:** resolve CI failures — unused vars and imports ([a27b33a](https://github.com/iamez/slomix/commit/a27b33a6009c0b1d6aad2aecdecb611d813c6596))
* **lint:** resolve remaining CI review findings ([52cdad9](https://github.com/iamez/slomix/commit/52cdad9ef4819248c650f9b87e0cd0d652ae8363))
* **lint:** resolve remaining E701/F541/F821 violations ([1af8139](https://github.com/iamez/slomix/commit/1af8139b51bf8aa02939177a63b8ffd41636c74e))
* Mandelbrot audit — resolve 24 findings (2 CRITICAL, 11 HIGH, 11 MEDIUM) ([c60b9da](https://github.com/iamez/slomix/commit/c60b9da277dacf2d9841738fb760eb9a616e3d74))
* momentum chart infinite resize + CI dependency conflict + review fixes ([9151c6b](https://github.com/iamez/slomix/commit/9151c6b2b9b7796b370f734ef1deadc3833de070))
* MomentumChart non-null assertion → guard check ([6d6e899](https://github.com/iamez/slomix/commit/6d6e8993ac06c6b5e6b8e880c47a6612691894cd))
* **parser+dpm:** expand R2_ONLY_FIELDS and standardize DPM calculation ([88a0551](https://github.com/iamez/slomix/commit/88a05511832573d7217281aa47ea4c78c1e914f1))
* **parser:** correct match summary R2_ONLY_FIELDS and add timing reconciliation ([a26aed2](https://github.com/iamez/slomix/commit/a26aed229eb6c0941334151b485144bcd21f81a9))
* **parser:** correct Round 2 time_dead calculation ([a58331e](https://github.com/iamez/slomix/commit/a58331eee9eb20d2f524c15894ba65797fe676c4))
* **proximity:** add type annotations to kill-outcomes endpoint parameters ([0090b24](https://github.com/iamez/slomix/commit/0090b243973112fe2631e236a27d20338e1e9871))
* **proximity:** revives session_date column + kill-outcomes LIMIT parameterization ([ddae169](https://github.com/iamez/slomix/commit/ddae169b5c901bfeb5c50c5cf35b4578573c3ce8))
* **proximity:** upgrade cog from ParserV3 to ParserV4 ([e5d9b13](https://github.com/iamez/slomix/commit/e5d9b13525ce5a6da4a86f82c23646aa8db2d0ed))
* **proximity:** upgrade cog to ParserV4 for v6 section support ([a166a84](https://github.com/iamez/slomix/commit/a166a844be6985df8247a2618ec980676b205f5e))
* Relaxed duration matching as first step ([f6e7bf1](https://github.com/iamez/slomix/commit/f6e7bf11ad95297ee35311f3fd7a89a9887aff76))
* remaining Codacy issues — Protocol stubs + health check stack trace ([e44ee2c](https://github.com/iamez/slomix/commit/e44ee2c909403dd28768ae0fcc82750715331a29))
* remove all exception information exposure in proximity_router.py ([684a21b](https://github.com/iamez/slomix/commit/684a21be230197360cc824b6932cce0dba471783))
* remove unnecessary optional chain in Proximity.tsx (last Codacy issue) ([8bf2f6e](https://github.com/iamez/slomix/commit/8bf2f6e0a03df7414dff3654cbf35081a148f70b))
* remove unused date_obj variable in players_router.py ([5d9e1b5](https://github.com/iamez/slomix/commit/5d9e1b5c4b4b44566306a156f87e761dffe4f7fd))
* replace innerHTML with DOM APIs for kill outcomes + hit regions (XSS) ([533682b](https://github.com/iamez/slomix/commit/533682b9aa72c36345b4a38c204624cf6d3dda3e))
* replace remaining 4 innerHTML blocks with DOM APIs (Codacy XSS) ([bf08322](https://github.com/iamez/slomix/commit/bf083223ea180a2f1a37540924289b669818f620))
* replace removed PUSH_MULTIPLIER import with PUSH_QUALITY_THRESHOLD ([7c6545e](https://github.com/iamez/slomix/commit/7c6545ebcd8444c1a7d7108f4886feb5d6fa6144))
* replace silent except:pass with debug logging in pagination views ([1ec85d3](https://github.com/iamez/slomix/commit/1ec85d3108c0647fc2ffc3fec25b1a96372de745))
* resolve 12 Codacy findings (MD5 security, XSS innerHTML, truthy conditional) ([fd431e1](https://github.com/iamez/slomix/commit/fd431e1878071ed7371f17d414395d53d937e2fa))
* resolve 2 admin command bugs ([6a1b454](https://github.com/iamez/slomix/commit/6a1b4548946b7d39a5ee79c8f3b385db1e955a4f))
* resolve 3 bugs blocking proximity v6 deploy ([4d45384](https://github.com/iamez/slomix/commit/4d45384ecbe5a071901cc4c5dd5514393dff4711))
* resolve 39 Codacy static analysis warnings ([030cbe1](https://github.com/iamez/slomix/commit/030cbe1e1c2b6df0c93c5d9c2ec0257dcc306d2b))
* resolve 6 command bugs from systematic audit ([eab30f0](https://github.com/iamez/slomix/commit/eab30f09703006a2ece4ea94eb55e20a587e1d00))
* resolve all 21 LOW/INFO audit findings ([62cb100](https://github.com/iamez/slomix/commit/62cb10033c7a77392be8980d13a85f9cf24473dd))
* resolve all 58 Codacy issues — XSS, TypeScript, SQL injection ([9086a13](https://github.com/iamez/slomix/commit/9086a134cd6e7b29bb739be83163c8334fbd05cc))
* resolve all CI lint failures (ruff F821, F841, unused imports) ([795a4b1](https://github.com/iamez/slomix/commit/795a4b1fdaa4e4f6f41be2d7cdb5f79904184b44))
* resolve all Codacy/CodeQL code scanning issues (no suppressions) ([ee168b3](https://github.com/iamez/slomix/commit/ee168b3c7e5f72efdb23de33b2188160c48a1be1))
* resolve all remaining Codacy/CodeQL alerts (30 issues, 0 suppressed) ([5790019](https://github.com/iamez/slomix/commit/57900191cca897f29d2d8a578a2cba6c80a01ec5))
* resolve CI lint failures (unused imports + variables) ([bc148ca](https://github.com/iamez/slomix/commit/bc148ca7a88b78c506dfeb788315f3887f4ab1e2))
* resolve Codacy static analysis warnings in PR [#53](https://github.com/iamez/slomix/issues/53) ([f4b1d0a](https://github.com/iamez/slomix/commit/f4b1d0a21e713e98dd8c34f981c63926f104acf7))
* resolve final 17 Codacy issues — SQL concat, object injection, stack trace ([baef473](https://github.com/iamez/slomix/commit/baef473d1f32d1d7512ad4294024713ad41f04cb))
* resolve remaining 10 Codacy issues ([7c5a478](https://github.com/iamez/slomix/commit/7c5a47856b46dc47928558a4324c42049a80b46b))
* resolve ruff lint errors for CI compliance ([cbea046](https://github.com/iamez/slomix/commit/cbea0463f061d20d7fbc2805fbe336b33e0b1856))
* restore StatsCalculator module and apply codebase review fixes ([d0539ed](https://github.com/iamez/slomix/commit/d0539ed0c4e6cd429acb3f3a82d99e9efe69d8b8))
* restore StatsCalculator module and apply codebase review fixes ([aa564f6](https://github.com/iamez/slomix/commit/aa564f62171df6994f8754a1b5452995d1f30dc7))
* rivalries.js double /api/api/ prefix + narrative session_id query ([ff00606](https://github.com/iamez/slomix/commit/ff00606923db24a92eabcacab39480992cda41b6))
* **rivalries:** leaderboard GROUP BY + player threshold + field names ([1ed65b5](https://github.com/iamez/slomix/commit/1ed65b5be9241f334866b1c63f70d13565b9b9ab))
* ruff F841 unused var + processed_at updates on file retry ([4f8e244](https://github.com/iamez/slomix/commit/4f8e244c80e5e1b3a223b08dbe272204cefdb77b))
* security audit - 9 critical/high fixes + secrets management system ([d796457](https://github.com/iamez/slomix/commit/d796457b653f33ce5d388ba01e4a03c08313ba04))
* **security:** address CodeQL scanning alerts across codebase ([e96fd61](https://github.com/iamez/slomix/commit/e96fd61a00fa5acfa4181109dd9765e9ccd45dbf))
* **security:** close final CodeQL/Codacy findings ([c4902b4](https://github.com/iamez/slomix/commit/c4902b4c7f749d278de5bf20096c12254d01dffe))
* **security:** stop exposing internal errors in API responses + clean imports ([3d27224](https://github.com/iamez/slomix/commit/3d27224d4b21aa04f843cd7753f7c6a5d75966eb))
* storytelling_router broken import + ruff auto-fix tests ([b07de49](https://github.com/iamez/slomix/commit/b07de4940d9ab5d6eeaf1b0afada8a7c9589a31d))
* **storytelling:** _to_date returns string not date object ([35c3f8c](https://github.com/iamez/slomix/commit/35c3f8cc1f353945ae666bfc91b68268aa1a9393))
* **storytelling:** correct date type handling for mixed column types ([e88d54d](https://github.com/iamez/slomix/commit/e88d54d6a7686d95deb0d90ad84da4618aa266b5))
* **storytelling:** correct headshot % formula (hs_hits/total_hits not hs_kills/kills) ([3b9088f](https://github.com/iamez/slomix/commit/3b9088f40a625969090274d05fe81b1d487281e3))
* **storytelling:** fully relative archetype thresholds for competitive 3v3 ([4a06983](https://github.com/iamez/slomix/commit/4a069834186df0a1e2eac6251c31f94fe82d597f))
* **storytelling:** GUID length mismatch — PCS 8-char vs proximity 32-char ([0bc636f](https://github.com/iamez/slomix/commit/0bc636fd2472c03f9a824452788fa72bb71f4eb1))
* **storytelling:** loosen archetype thresholds for competitive balance ([5023956](https://github.com/iamez/slomix/commit/5023956b2f2fa0dfedd4222a5a21ada2ab4c6ff7))
* **storytelling:** narrative query gaming_session_id from rounds not PCS ([a3cc92b](https://github.com/iamez/slomix/commit/a3cc92bac5682e31c422e7c2f79cab70434334fe))
* **storytelling:** relative archetype thresholds using session averages ([a91c810](https://github.com/iamez/slomix/commit/a91c810fc29193cc6f46320c0baa278f15a68314))
* **storytelling:** remaining round_date TEXT queries need _to_date_str ([25eb879](https://github.com/iamez/slomix/commit/25eb879aaa743b5290992ce5f5ce852f2bf68f53))
* **storytelling:** strip ET colors, fix archetypes, improve moments+synergy ([e81a630](https://github.com/iamez/slomix/commit/e81a6300ee56306384157f66d538224bb0151f93))
* **storytelling:** use PCS kills for archetype KD (not KIS kills) ([1e0ce59](https://github.com/iamez/slomix/commit/1e0ce59e09e21d511e0bd3b223b70e51dd4ee554))
* **tests:** correct column name file_hash → sha256_hash in db adapter test ([7c8b762](https://github.com/iamez/slomix/commit/7c8b762589cea72c4c2ff91ab1c32dfb9ff2ce28))
* **tests:** create minimal schema in CI test database ([806cdaf](https://github.com/iamez/slomix/commit/806cdafd0ee28c582629345f20a37b09d189e545))
* **tests:** remove stale players/discord_users assertions from diagnostics test ([9a4ef52](https://github.com/iamez/slomix/commit/9a4ef52f3dd6f2ed1431eea222b1c11e8827be6e))
* **tests:** resolve all 53 test failures across 22 files ([aacd8e2](https://github.com/iamez/slomix/commit/aacd8e278359b80102401cf52a87c902f42d27c5))
* **tests:** restore broken test imports after scripts consolidation ([0a1139f](https://github.com/iamez/slomix/commit/0a1139f65dc25f33c264bc8cecf3fef234a92454))
* **tests:** skip tests when dependencies are unavailable ([ad4b747](https://github.com/iamez/slomix/commit/ad4b747d2a4d8da63f891d043d8e81cb92ff5a47))
* **tests:** update mocks for endstats guard + diagnostics table rename ([7424857](https://github.com/iamez/slomix/commit/742485757adc9fa0df8bb17209fecc46d61bdf2e))
* **web,proximity:** dropdown click propagation and midnight session linking ([9d45d3f](https://github.com/iamez/slomix/commit/9d45d3fc54ace0e196261aee232bb13b693f1419))
* **web:** add unsafe-inline to CSP script-src to unblock onclick handlers ([cafeb02](https://github.com/iamez/slomix/commit/cafeb026a8a5927fcf038d3931e09d550ffa3b25))
* **webhook:** consume pending Lua metadata in all file processing paths ([fb472c2](https://github.com/iamez/slomix/commit/fb472c220b4b1eceeebb6d6b09864cb1a26ead3a))
* **web:** sessions nav highlighting and stats dropdown membership ([9d80594](https://github.com/iamez/slomix/commit/9d805940e4ee6d16a52799d6187786e191e20129))
* website import order + re-linker column compatibility ([e971eeb](https://github.com/iamez/slomix/commit/e971eeb69dd77db80cee4edc311778b87a079e30))
* **website,db:** resolve 3 bugs blocking proximity v6 deploy ([f20268d](https://github.com/iamez/slomix/commit/f20268ddaaef104d9efd25bd5980ef1343f0335e))
* **website:** add missing session_date param to get_proximity_revives ([b425780](https://github.com/iamez/slomix/commit/b425780f6e2261414fb936a46e94f01dfb4a3f15))
* **website:** add view-skill-rating container to index.html ([8711a57](https://github.com/iamez/slomix/commit/8711a5768b87949083f04c574f18d9dc8f81bb1d))
* **website:** bump BUILD_VERSION to bust browser cache for skill-rating ([a1db7ae](https://github.com/iamez/slomix/commit/a1db7aed3a5a61d0c331fd1a3ac16b964d8811ac))
* **website:** correct table names in diagnostics and records routers ([9325a0f](https://github.com/iamez/slomix/commit/9325a0f1b46d6bdcdc645ce9c3c8164cdf536a6d))
* **website:** correct table names in diagnostics/records routers ([4033833](https://github.com/iamez/slomix/commit/403383348b38b3e262848c6a35b5515126279928))
* **website:** gaming_sessions is not a table, query rounds instead ([9b43b42](https://github.com/iamez/slomix/commit/9b43b42d9f80c6a6c6631919103adb2bfa837425))
* **website:** gaming_sessions query in diagnostics ([26704b3](https://github.com/iamez/slomix/commit/26704b3015712d8b90c0a74eb9b5aa528fcffcd8))
* **website:** proximity page — default scope, leaderboard scoping, HTML render bugs ([e5e86b8](https://github.com/iamez/slomix/commit/e5e86b85fb2598ea3144b1d98e1e900cad6c76bd))
* **website:** React Proximity.tsx — scope filtering for KillOutcomes, HitRegions, HeadshotRates ([886a8bf](https://github.com/iamez/slomix/commit/886a8bf4a4f1481eb7fc815e73e3ce9729042eee))
* **website:** round_id JOIN, error logging, and Chart.js guards ([7dc8ea2](https://github.com/iamez/slomix/commit/7dc8ea2daa7543fd14b042de4fdb3efd3a406659))
* **website:** strip ET color codes from proximity names, fix TS errors ([b95d713](https://github.com/iamez/slomix/commit/b95d713bf960a61c580f62cae346cb119d26874b))
* **website:** upload download fix + skill rating single-pass optimization ([2cabaea](https://github.com/iamez/slomix/commit/2cabaea1347ea2948f220b692ed6ed043a28c93b))

## [1.1.2](https://github.com/iamez/slomix/compare/v1.1.1...v1.1.2) (2026-03-29)


### Bug Fixes

* replace silent except:pass with debug logging in pagination views ([1ec85d3](https://github.com/iamez/slomix/commit/1ec85d3108c0647fc2ffc3fec25b1a96372de745))
* storytelling_router broken import + ruff auto-fix tests ([b07de49](https://github.com/iamez/slomix/commit/b07de4940d9ab5d6eeaf1b0afada8a7c9589a31d))

## [1.1.1](https://github.com/iamez/slomix/compare/v1.1.0...v1.1.1) (2026-03-28)

> **Codacy zero — 58 → 0 issues, no suppressions.** Massive code-quality sweep across XSS (22 CRITICAL: `innerHTML` → DOM API), TypeScript (12 HIGH), SQL injection (7: f-string → whitelists), Protocol stubs, stack-trace exposure, and URL-redirect validation. Zero `# noqa` suppressions added — every finding is fixed at root. CI: 9/9 checks green for the first time. Round Replay Timeline + Momentum Chart + Session Narrative ship alongside (those are the v1.1.0 features that needed the cleanup pass).

### Bug Fixes

* **ci:** make slowapi optional with no-op stub for CI/test environments ([8114a6d](https://github.com/iamez/slomix/commit/8114a6d2507c96e79c010c073b9e87f133d9433f))
* **diagnostics:** restore gaming_sessions query lost in merge ([2abed29](https://github.com/iamez/slomix/commit/2abed296bc111c9c2a9a73c84bbea4196fd0772b))
* eliminate ALL SQL string concat + object bracket access for Codacy ([bd1ed13](https://github.com/iamez/slomix/commit/bd1ed137f355502f7970bea79e9d3ff4491ac3ef))
* MomentumChart non-null assertion → guard check ([6d6e899](https://github.com/iamez/slomix/commit/6d6e8993ac06c6b5e6b8e880c47a6612691894cd))
* remaining Codacy issues — Protocol stubs + health check stack trace ([e44ee2c](https://github.com/iamez/slomix/commit/e44ee2c909403dd28768ae0fcc82750715331a29))
* resolve all 58 Codacy issues — XSS, TypeScript, SQL injection ([9086a13](https://github.com/iamez/slomix/commit/9086a134cd6e7b29bb739be83163c8334fbd05cc))
* resolve all CI lint failures (ruff F821, F841, unused imports) ([795a4b1](https://github.com/iamez/slomix/commit/795a4b1fdaa4e4f6f41be2d7cdb5f79904184b44))
* resolve all Codacy/CodeQL code scanning issues (no suppressions) ([ee168b3](https://github.com/iamez/slomix/commit/ee168b3c7e5f72efdb23de33b2188160c48a1be1))
* resolve all remaining Codacy/CodeQL alerts (30 issues, 0 suppressed) ([5790019](https://github.com/iamez/slomix/commit/57900191cca897f29d2d8a578a2cba6c80a01ec5))
* resolve final 17 Codacy issues — SQL concat, object injection, stack trace ([baef473](https://github.com/iamez/slomix/commit/baef473d1f32d1d7512ad4294024713ad41f04cb))
* **tests:** remove stale players/discord_users assertions from diagnostics test ([9a4ef52](https://github.com/iamez/slomix/commit/9a4ef52f3dd6f2ed1431eea222b1c11e8827be6e))
* **tests:** update mocks for endstats guard + diagnostics table rename ([7424857](https://github.com/iamez/slomix/commit/742485757adc9fa0df8bb17209fecc46d61bdf2e))

## [1.1.0](https://github.com/iamez/slomix/compare/v1.0.8...v1.1.0) (2026-03-25)

> **Stats accuracy audit + React 19 modernization + proximity v5 teamplay.** First release-please-tagged version. The stats-accuracy audit fixes long-standing bugs: R0 double-counting, missing `NULLIF` guards, accuracy formula (`SUM(hits)/SUM(shots)` not `AVG`), alive% / TMP normalization (TAB[8] now stored), headshot ratio computation. **React 19 frontend** modernization migrates 19/19 routes to the new website with game-assets integration. **Proximity v5 teamplay** lands kill outcomes, hit regions, combat heatmaps, movement analytics, composite scoring, and full v5.2 frontend panels. **Greatshot demo pipeline** completes Phase 2-5 (multi-file upload, player stats display, topshots API endpoints, demo-to-stats cross-reference matching). New systems: round correlation + match_id canonicalization, ET Rating skill system (experimental), AI matchup analytics, real-time stats notification via Discord webhook, lazy-loading pagination on `!leaderboard`. Lua: `gamestate` detection fix + timing-comparison service.

### Features

* add cumulative endstats to !last_session + fix race conditions ([2f5fb33](https://github.com/iamez/slomix/commit/2f5fb338634adffe11a795046b689afe5bf42754))
* add proximity tracker prototype ([f44f080](https://github.com/iamez/slomix/commit/f44f0808ff53d4495e7dda0c63078a946217060d))
* add proximity tracker prototype ([85355de](https://github.com/iamez/slomix/commit/85355de181f9f5d853a943b34becd2063dc1000e))
* add website prototype ([#27](https://github.com/iamez/slomix/issues/27)) ([b69d1b3](https://github.com/iamez/slomix/commit/b69d1b38fca5c1c4ebbd322910e3989af8e35301))
* **analytics:** Add player analytics commands (Phase 1) ([cee91a6](https://github.com/iamez/slomix/commit/cee91a6e404ccf9ca2e72194005b0338a3482406))
* Auto-detect active gaming sessions on bot startup ([832c175](https://github.com/iamez/slomix/commit/832c175d96be5c51f3a35b0d8671ff7e5e92a578))
* Auto-detect active gaming sessions on bot startup ([538257a](https://github.com/iamez/slomix/commit/538257acfd3895b38e7f929b1f2b8758aff06a84))
* **bot,website:** fix R2 lua webhook, add round visualizer, restore planning docs ([16d9412](https://github.com/iamez/slomix/commit/16d9412abfb3d7d022b8674201ddbf484135ee25))
* **bot,website:** WS2+WS3 timing join logging, diagnostics, embed validation ([eff63b9](https://github.com/iamez/slomix/commit/eff63b9fc732b75c3cfffd8bdb664e6ebfdca6fb))
* **bot:** add ADR/KPR/DPR metrics + clean remaining SQLite branches ([ac9369a](https://github.com/iamez/slomix/commit/ac9369a73c7ceea15e05a811dfb17baadca6581b))
* **bot:** add command_error_handler decorator to utils ([463aa59](https://github.com/iamez/slomix/commit/463aa59d56b5cac1551d9fc8cf12bdef25615ff8))
* **bot:** canonicalize match_id in stats import path via round correlation context ([8a9497f](https://github.com/iamez/slomix/commit/8a9497f4efeccd8dfb204a033ca0bcac2d69e694))
* **bot:** enhance correlation service and add linkage diagnostics ([39df70e](https://github.com/iamez/slomix/commit/39df70e3109b8139c377e5779de91f49d51c7a18))
* **bot:** round correlation system + match_id fix + ET:Legacy research ([d47a85c](https://github.com/iamez/slomix/commit/d47a85ccce2e1cd19cb14d33810b4abba2029b48))
* **db:** add SQL migrations 005-013 and website migrations ([48e9361](https://github.com/iamez/slomix/commit/48e9361a35c6b5f153007e6f4dc93d2f2fa68555))
* **db:** migrations 014/015 — proximity round_id columns + backfill ([10b51b8](https://github.com/iamez/slomix/commit/10b51b8b5e9595e050028eed49abec12573984f4))
* **greatshot:** complete Phase 2-5 + topshots API endpoints ([c3c9797](https://github.com/iamez/slomix/commit/c3c9797b7047370314a8cdfd1e4c6d72a8355809))
* **greatshot:** enhance demo-to-stats cross-reference matching ([f6e7bf1](https://github.com/iamez/slomix/commit/f6e7bf11ad95297ee35311f3fd7a89a9887aff76))
* **greatshot:** enrich highlight metadata and add DB cross-reference ([3e79f9b](https://github.com/iamez/slomix/commit/3e79f9bc968bf0e42ce80632b4fe4e7eac5f39a4))
* **greatshot:** multi-file upload + player stats display ([6814138](https://github.com/iamez/slomix/commit/6814138ab2a58ded5111c9aa0603c1b462591596))
* Implement lazy-loading pagination for !leaderboard command ([67de3be](https://github.com/iamez/slomix/commit/67de3be13d3746037ce2e2ab21f4ff2b17c86bdf))
* Implement lazy-loading pagination for !leaderboard command ([ab75869](https://github.com/iamez/slomix/commit/ab75869167fd86fe4f355d470d523e66f2c916d6))
* Implement SSH monitoring performance optimization + security fixes ([58ea5f6](https://github.com/iamez/slomix/commit/58ea5f6f16fd463d8ea6b2ae6d34a4de20edfea7))
* Implement SSH monitoring performance optimization + security fixes ([1f9d81f](https://github.com/iamez/slomix/commit/1f9d81fec9144cb3748ed6fee7ca33c8cb09ab61))
* **logging:** add comprehensive logging across bot and website ([fcbb4e5](https://github.com/iamez/slomix/commit/fcbb4e55d08c25aa9cfd93e8f1d9ffc8cf36b903))
* **matchup:** Add matchup analytics system for lineup vs lineup stats ([6a2fca3](https://github.com/iamez/slomix/commit/6a2fca32f761e5da7c5a2285d9e636ce5774b4d5))
* proximity v5.2 analytics, ET Rating, code quality fixes ([53f5050](https://github.com/iamez/slomix/commit/53f50508580c71ef619da373785d18013252057d))
* **proximity:** add canonical round_id linkage to all proximity tables ([bacbfc1](https://github.com/iamez/slomix/commit/bacbfc1052ed505aab46e6701be63346e58638bf))
* **proximity:** add composite scoring system + complete v5.2 frontend panels ([ebb5f18](https://github.com/iamez/slomix/commit/ebb5f187e9f47663dc2ce5ab451b9eab1535d999))
* **proximity:** add kill outcomes, hit regions, combat heatmaps & movement analytics (v5.2) ([b26b989](https://github.com/iamez/slomix/commit/b26b9896966e3df39bc02df2271e0b210a23dca9))
* **proximity:** add objective coord assets and web map data ([614e533](https://github.com/iamez/slomix/commit/614e53355aed18ee5b049987b120f1bf202462df))
* **proximity:** expand Lua tracker, objective coords, and web analytics ([be76076](https://github.com/iamez/slomix/commit/be76076f23d9c861814aa1a91609552f5279973a))
* **proximity:** upgrade gameserver Lua to v5.0 with full teamplay sections ([7cbc3eb](https://github.com/iamez/slomix/commit/7cbc3eb49dc79e352ccc4281fa0d0bc729975ded))
* **proximity:** v6.01 objective intelligence + full frontend coverage + bot GUID fix ([#53](https://github.com/iamez/slomix/issues/53)) ([83bfd1e](https://github.com/iamez/slomix/commit/83bfd1ec1b9a6c3c69f764b6ba3b5bbb962d50c6))
* **proximity:** v6.01 objective intelligence + missing panels + bot GUID fix ([83bfd1e](https://github.com/iamez/slomix/commit/83bfd1ec1b9a6c3c69f764b6ba3b5bbb962d50c6))
* **proximity:** v6.01 objective intelligence + missing panels + bot GUID fix ([73ad6ef](https://github.com/iamez/slomix/commit/73ad6ef0f027b759d5f47b2d08bedeb4593b92c0))
* reconcile local work — sessions redesign, proximity, deploy tooling ([52ba75f](https://github.com/iamez/slomix/commit/52ba75f0c3656fc87bcc3ac1e379e9ea3eae6231))
* **scoring+teams:** Map-based stopwatch scoring + real-time team tracking ([64dc2ab](https://github.com/iamez/slomix/commit/64dc2ab9598798c7df4815a092a7e2207853d2e2))
* **scripts:** add backfill, gate, smoke test, and deployment scripts ([cb0dad6](https://github.com/iamez/slomix/commit/cb0dad6d4b70d02dfb2aa9b3c279a965e49d2ca9))
* Security fixes, bug fixes, and interactive pagination ([3bdc2ed](https://github.com/iamez/slomix/commit/3bdc2ed0015b27809766064389c4a98a185576d7))
* Security fixes, bug fixes, and interactive pagination ([ddf305d](https://github.com/iamez/slomix/commit/ddf305d430778562f46f4630eba18cf94ab3389e))
* **session-embed:** add team detection confidence indicator ([b0cb46d](https://github.com/iamez/slomix/commit/b0cb46de779d2eec322a98464369588e40979403))
* **team-detection:** enhance with defender_team validation and confidence scoring ([65c633e](https://github.com/iamez/slomix/commit/65c633e541c14c331ded12fefb6dd950b2ae3e83))
* **timing-comparison:** add timing legend to embed description ([4fa4aa3](https://github.com/iamez/slomix/commit/4fa4aa3aacc50cdd89145ef7d2b49572bda5d2e3))
* **tools:** add pipeline verification script (WS1-007 gate check) ([1b12edb](https://github.com/iamez/slomix/commit/1b12edb41ce9acb945225b3c45f0bb55a35b4398))
* v1.0.6 - analytics, matchup system, website overhaul, proximity tracker ([33a2468](https://github.com/iamez/slomix/commit/33a24683a128fccaf9de5bc005341b2e2e8e616b))
* v1.0.7 - greatshot demo pipeline, DB manager overhaul, README rewrite ([a925cb8](https://github.com/iamez/slomix/commit/a925cb8007a6b22ef5cefba34a6ffd4d9b96499e))
* v1.1.0 — stats accuracy audit, React 19 frontend, proximity v5 ([d5aec31](https://github.com/iamez/slomix/commit/d5aec31e444e26ecd9f9b9b76b840b7080598df6))
* v1.1.0 — stats accuracy audit, React 19 frontend, proximity v5 teamplay ([674cee9](https://github.com/iamez/slomix/commit/674cee9f5c8d2ac5b114711ea8f9f5103372d322))
* **webhook:** add real-time stats notification via Discord webhook ([4ee9609](https://github.com/iamez/slomix/commit/4ee960953026bd84e5dd7628563662d4893879e1))
* **webhook:** fix Lua gamestate detection + timing comparison service ([622dc65](https://github.com/iamez/slomix/commit/622dc65528257e48edd31c36a4506bda385401a5))
* **web:** prefer exact round_id join with fuzzy fallback in proximity API ([f70253e](https://github.com/iamez/slomix/commit/f70253ec94a211c176f4b618d6b0d6c3f786dc2f))
* **website:** add ET Rating skill system (experimental) ([aa2c514](https://github.com/iamez/slomix/commit/aa2c514c156a94ea935e34e36e7d4e462def4834))
* **website:** add ET Rating to navigation menu ([fe578af](https://github.com/iamez/slomix/commit/fe578af19b117d64c38f26704fc1ea3d48f91640))
* **website:** admin System Overview redesign + proximity color code fix ([8af0840](https://github.com/iamez/slomix/commit/8af0840111cd4b93bcb75c52e5c1d88fc35564e0))
* **website:** React 19 modernization with game assets integration ([2bc069f](https://github.com/iamez/slomix/commit/2bc069f3ed4cc73ec494b76497d0ef03c335c3dd))
* **website:** redesign Admin System Overview page ([96df809](https://github.com/iamez/slomix/commit/96df809a7dc26b2f2bafc82d3328573b68d497cd))
* **website:** sessions redesign, proximity fixes, deploy script updates ([955f52f](https://github.com/iamez/slomix/commit/955f52f157a1e57ebaa4316b642fad9e7f518eb2))


### Bug Fixes

* !sync_month error and document SQL query safety ([4a69ac5](https://github.com/iamez/slomix/commit/4a69ac57f9627552b5900d204d751b7def514e61))
* !sync_month error and document SQL query safety ([8dd1229](https://github.com/iamez/slomix/commit/8dd12298d82a2433caf0f6c5322f412d5f7f0336))
* address codacy findings for availability notifications ([e0b84c5](https://github.com/iamez/slomix/commit/e0b84c5291818153be712e618a275902d6ec53fb))
* Address Codacy warnings - remove unused import, replace silent exceptions with logging ([c6f0de6](https://github.com/iamez/slomix/commit/c6f0de63b6767922a10d6a164c9b53edd5e7f47f))
* Address Codacy warnings - remove unused import, replace silent exceptions with logging ([d713a28](https://github.com/iamez/slomix/commit/d713a283c85802bd06c68e4595bb899284ccc327))
* address Codex P1/P2 review findings ([1d2f946](https://github.com/iamez/slomix/commit/1d2f946d5fcef8cc77d71a1d3095b7ec92dd8626))
* address PR [#35](https://github.com/iamez/slomix/issues/35) review comments ([04cc599](https://github.com/iamez/slomix/commit/04cc5991e79c48295568e7d23cb487a2a97b60c3))
* address PR31 regressions and weapons/analytics runtime issues ([dd98a17](https://github.com/iamez/slomix/commit/dd98a17e92922de8a8be322ec6c0c6760934b285))
* address remaining Codex findings for legacy JS ([266c05a](https://github.com/iamez/slomix/commit/266c05a96dc9b97bacae849a45236be5c1af42dd))
* Apply bug patches from code audit - memory leaks, bounds checking, race conditions ([aad613a](https://github.com/iamez/slomix/commit/aad613aaa15c6fefb2281f5ab40d4dae1f551574))
* Apply bug patches from code audit - memory leaks, bounds checking, race conditions ([f7cec30](https://github.com/iamez/slomix/commit/f7cec30612df271d9110f9d98a002a89671ba760))
* **bot,docs:** ghost round filter, round linker delay, warning fatigue, SQLite doc cleanup ([bb3cd79](https://github.com/iamez/slomix/commit/bb3cd796721616f5cf748b5e7cf37397f766a97b))
* **bot,lua,web:** multi-phase bugfix sweep from super prompt audit ([64d6f57](https://github.com/iamez/slomix/commit/64d6f5707ba93d36a8d8405e8acc66ef7c1b1774))
* **bot,proximity,greatshot:** execute WS runbook tasks — reconnect, proximity, crossref ([20d84e6](https://github.com/iamez/slomix/commit/20d84e6270852618f14930538b62aa5f1d918468))
* **bot,web:** correct headshot %, denied playtime display, and website formula alignment ([aa116a6](https://github.com/iamez/slomix/commit/aa116a6d1b0ef1e9a4889a61d95c1f8547e2b998))
* **bot:** add Discord posting error alerting and fix health monitor ([3c840d2](https://github.com/iamez/slomix/commit/3c840d2d5dceffa6863580c000307e9e0e7a2392))
* **bot:** Discord posting error alerting + health monitor fix ([e4771dc](https://github.com/iamez/slomix/commit/e4771dc9f9d6ba52d957830cb93c3d1e76ed3d97))
* **bot:** final sprint — session finalization, embed overflow, SQLite guards, matchup SQL ([6d24d2f](https://github.com/iamez/slomix/commit/6d24d2f4cea062567aeed5ea13462d5f0ea9c334))
* **bot:** remove hard dependency on tools.stopwatch_scoring in session cog ([d23f51a](https://github.com/iamez/slomix/commit/d23f51ae76e98aad15118430fd6fb838752e6e26))
* **bot:** resolve Lua round_id linkage race condition ([e216b92](https://github.com/iamez/slomix/commit/e216b92f87b9313477cc925904938c195c588bbf))
* **bot:** SQL param count mismatch and placeholder consistency ([cc94275](https://github.com/iamez/slomix/commit/cc9427511468b63d71e8b834247036c4013ebdbe))
* **bot:** WS0 column cache refresh, restart detection gap guard, sprint closure ([3f42952](https://github.com/iamez/slomix/commit/3f42952872ba370d9394a521d32ff6ceafe01f08))
* **ci-security:** unblock test imports and harden retro viz rendering ([2988da8](https://github.com/iamez/slomix/commit/2988da8e69d72d58d09f7e6401153b511a8b2344))
* **ci-tests:** use postgres schema and align db adapter tests ([e3bfdd6](https://github.com/iamez/slomix/commit/e3bfdd6cae82618735832126bf07f074ed69b253))
* **ci:** add all required env vars for Docker Build ([453cf32](https://github.com/iamez/slomix/commit/453cf322a4b33c722a757844a8f57a6edc44fc94))
* **ci:** add schema files and restore adapter/test compatibility ([4f447fa](https://github.com/iamez/slomix/commit/4f447fa7bdbe586df744aec96fcec58a0bb0a8f5))
* **ci:** Docker Build needs .env placeholder + empty except comment ([706c352](https://github.com/iamez/slomix/commit/706c3522d9f6a3c1cb55235868c5dbfd56475f94))
* **ci:** f-string prefix lint + exclude game assets from size check ([e9efcd2](https://github.com/iamez/slomix/commit/e9efcd2dea3692a7c70b83de0e13593648f90df0))
* **ci:** make Codecov non-blocking, exclude build artifacts from Codacy/CodeQL ([f17fd9e](https://github.com/iamez/slomix/commit/f17fd9ed75cf08939ba6d9f65707bdb0f6e5e8a8))
* **ci:** migrate CodeQL action to v4 ([7ab90da](https://github.com/iamez/slomix/commit/7ab90da04e3d2c4496d1d6772a801fbd7996f389))
* **ci:** remove redundant SARIF upload step from CodeQL workflow ([f80e008](https://github.com/iamez/slomix/commit/f80e0083b1515f6d37d11e47276e51c943002ce9))
* **ci:** resolve file-checks and JavaScript lint failures ([3107d7c](https://github.com/iamez/slomix/commit/3107d7cd736031d64cfaac497797a841733f5880))
* **ci:** restore pytest deps and reduce legacy lint noise ([7ad4b74](https://github.com/iamez/slomix/commit/7ad4b74e98185e12e1103870f6e9bd798485738d))
* **codacy:** resolve static analysis issues blocking PR gate ([ea488a0](https://github.com/iamez/slomix/commit/ea488a0ed5f7787443cdfbedc64a854a037f9b2c))
* **codeql:** address remaining code quality and security alerts ([f34f0b5](https://github.com/iamez/slomix/commit/f34f0b5fee71f9aff030b2657d85c245ed74abeb))
* **codeql:** resolve PR34 security alerts and remaining empty-except ([5aaadb0](https://github.com/iamez/slomix/commit/5aaadb00b9f44506e6204facc6bcda6aef575d29))
* correct 3 critical bugs in unified CLI tools (P1, P2, P3) ([100ffe0](https://github.com/iamez/slomix/commit/100ffe0238a1b1861baeab961f4ef272e0a5eb2d))
* **critical:** production audit fixes - data accuracy, race conditions, performance ([21169df](https://github.com/iamez/slomix/commit/21169dfb6ed9ecb90ac1b215203eca503850696d))
* **db:** execute queries on active transaction connection ([bf28d7f](https://github.com/iamez/slomix/commit/bf28d7f9dcbcf68f619637202c765e2574f0628f))
* disable legacy gaming_sessions table queries ([ea84c9c](https://github.com/iamez/slomix/commit/ea84c9c57d4d0fc09aaea5586d2d56d28d31898e))
* disable legacy gaming_sessions table queries ([ec60537](https://github.com/iamez/slomix/commit/ec605371cc04dbcff62c108cf7181ef1fc75b932))
* **docs:** correct stale 30-minute references to match actual config ([d13e3f5](https://github.com/iamez/slomix/commit/d13e3f58d935e515851bc97e12298d0706c0086d))
* **docs:** untrack investigation/scratch docs added by mistake ([d3bdb8c](https://github.com/iamez/slomix/commit/d3bdb8cc2692ca23a9fc1c8c4cf06afde7821f5e))
* eliminate all innerHTML XSS patterns flagged by Codacy ([f2b0e98](https://github.com/iamez/slomix/commit/f2b0e98643c5862571aac346e920a55795aee36b))
* **greatshot:** resolve remaining PR31 review regressions ([0d66002](https://github.com/iamez/slomix/commit/0d6600208e5c5aad67fa24bb63b43872553ebb18))
* **greatshot:** scope topshots to authenticated user and fix player_count ([e3af0e3](https://github.com/iamez/slomix/commit/e3af0e347aac54c8070fb0884bf2c4ceebc13da0))
* **greatshot:** serialize clip extraction and rank topshots across all demos ([bade215](https://github.com/iamez/slomix/commit/bade215b832b3cf46fef05bb2de256c05e46c7a1))
* handle None player names in PLAYSTYLE ANALYSIS graphs ([de29ba6](https://github.com/iamez/slomix/commit/de29ba67879ac39337c31eea47e5aba34c4d6be5))
* headshot% = hits/total_hits, revert accuracy to simple avg ([dadf622](https://github.com/iamez/slomix/commit/dadf622d47e95bacc19b48892375a9df79d65ef6))
* implement Copilot review suggestions for proximity prototype ([76b5a39](https://github.com/iamez/slomix/commit/76b5a39ed5c08ac998d2ce109f80fdb8b4d84a5d))
* **lint:** resolve CI failures — unused vars and imports ([a27b33a](https://github.com/iamez/slomix/commit/a27b33a6009c0b1d6aad2aecdecb611d813c6596))
* **lint:** resolve remaining CI review findings ([52cdad9](https://github.com/iamez/slomix/commit/52cdad9ef4819248c650f9b87e0cd0d652ae8363))
* **lint:** resolve remaining E701/F541/F821 violations ([1af8139](https://github.com/iamez/slomix/commit/1af8139b51bf8aa02939177a63b8ffd41636c74e))
* **parser+dpm:** expand R2_ONLY_FIELDS and standardize DPM calculation ([88a0551](https://github.com/iamez/slomix/commit/88a05511832573d7217281aa47ea4c78c1e914f1))
* **parser:** correct match summary R2_ONLY_FIELDS and add timing reconciliation ([a26aed2](https://github.com/iamez/slomix/commit/a26aed229eb6c0941334151b485144bcd21f81a9))
* **parser:** correct Round 2 time_dead calculation ([a58331e](https://github.com/iamez/slomix/commit/a58331eee9eb20d2f524c15894ba65797fe676c4))
* **proximity:** upgrade cog from ParserV3 to ParserV4 ([e5d9b13](https://github.com/iamez/slomix/commit/e5d9b13525ce5a6da4a86f82c23646aa8db2d0ed))
* **proximity:** upgrade cog to ParserV4 for v6 section support ([a166a84](https://github.com/iamez/slomix/commit/a166a844be6985df8247a2618ec980676b205f5e))
* Relaxed duration matching as first step ([f6e7bf1](https://github.com/iamez/slomix/commit/f6e7bf11ad95297ee35311f3fd7a89a9887aff76))
* remove all exception information exposure in proximity_router.py ([684a21b](https://github.com/iamez/slomix/commit/684a21be230197360cc824b6932cce0dba471783))
* Remove invalid max_preload_pages param and fix page indexing for LazyPaginationView ([4707294](https://github.com/iamez/slomix/commit/47072942188da699c3a31c34971472007cb7d988))
* Remove invalid max_preload_pages param and fix page indexing for LazyPaginationView ([baf1b7c](https://github.com/iamez/slomix/commit/baf1b7c1979a19f3b6bfd008e5c0867d67293f6d))
* remove unnecessary optional chain in Proximity.tsx (last Codacy issue) ([8bf2f6e](https://github.com/iamez/slomix/commit/8bf2f6e0a03df7414dff3654cbf35081a148f70b))
* remove unused date_obj variable in players_router.py ([5d9e1b5](https://github.com/iamez/slomix/commit/5d9e1b5c4b4b44566306a156f87e761dffe4f7fd))
* replace innerHTML with DOM APIs for kill outcomes + hit regions (XSS) ([533682b](https://github.com/iamez/slomix/commit/533682b9aa72c36345b4a38c204624cf6d3dda3e))
* replace remaining 4 innerHTML blocks with DOM APIs (Codacy XSS) ([bf08322](https://github.com/iamez/slomix/commit/bf083223ea180a2f1a37540924289b669818f620))
* resolve 12 Codacy findings (MD5 security, XSS innerHTML, truthy conditional) ([fd431e1](https://github.com/iamez/slomix/commit/fd431e1878071ed7371f17d414395d53d937e2fa))
* resolve 2 admin command bugs ([6a1b454](https://github.com/iamez/slomix/commit/6a1b4548946b7d39a5ee79c8f3b385db1e955a4f))
* resolve 3 bugs blocking proximity v6 deploy ([4d45384](https://github.com/iamez/slomix/commit/4d45384ecbe5a071901cc4c5dd5514393dff4711))
* resolve 39 Codacy static analysis warnings ([030cbe1](https://github.com/iamez/slomix/commit/030cbe1e1c2b6df0c93c5d9c2ec0257dcc306d2b))
* resolve 6 command bugs from systematic audit ([eab30f0](https://github.com/iamez/slomix/commit/eab30f09703006a2ece4ea94eb55e20a587e1d00))
* resolve CI lint failures (unused imports + variables) ([bc148ca](https://github.com/iamez/slomix/commit/bc148ca7a88b78c506dfeb788315f3887f4ab1e2))
* resolve Codacy static analysis warnings in PR [#53](https://github.com/iamez/slomix/issues/53) ([f4b1d0a](https://github.com/iamez/slomix/commit/f4b1d0a21e713e98dd8c34f981c63926f104acf7))
* resolve remaining 10 Codacy issues ([7c5a478](https://github.com/iamez/slomix/commit/7c5a47856b46dc47928558a4324c42049a80b46b))
* resolve ruff lint errors for CI compliance ([cbea046](https://github.com/iamez/slomix/commit/cbea0463f061d20d7fbc2805fbe336b33e0b1856))
* restore StatsCalculator module and apply codebase review fixes ([d0539ed](https://github.com/iamez/slomix/commit/d0539ed0c4e6cd429acb3f3a82d99e9efe69d8b8))
* restore StatsCalculator module and apply codebase review fixes ([aa564f6](https://github.com/iamez/slomix/commit/aa564f62171df6994f8754a1b5452995d1f30dc7))
* ruff F841 unused var + processed_at updates on file retry ([4f8e244](https://github.com/iamez/slomix/commit/4f8e244c80e5e1b3a223b08dbe272204cefdb77b))
* security audit - 9 critical/high fixes + secrets management system ([d796457](https://github.com/iamez/slomix/commit/d796457b653f33ce5d388ba01e4a03c08313ba04))
* **security:** address CodeQL scanning alerts across codebase ([e96fd61](https://github.com/iamez/slomix/commit/e96fd61a00fa5acfa4181109dd9765e9ccd45dbf))
* **security:** close final CodeQL/Codacy findings ([c4902b4](https://github.com/iamez/slomix/commit/c4902b4c7f749d278de5bf20096c12254d01dffe))
* **security:** stop exposing internal errors in API responses + clean imports ([3d27224](https://github.com/iamez/slomix/commit/3d27224d4b21aa04f843cd7753f7c6a5d75966eb))
* standardize round_time format to HHMMSS across all code paths ([cfd00f5](https://github.com/iamez/slomix/commit/cfd00f5e67a160f2e7875f40cf3616c4b8c2480f))
* standardize round_time format to HHMMSS across all code paths ([1290d56](https://github.com/iamez/slomix/commit/1290d56d24e4e476e5313d7e8db6ab1b337fff4a))
* **tests:** correct column name file_hash → sha256_hash in db adapter test ([7c8b762](https://github.com/iamez/slomix/commit/7c8b762589cea72c4c2ff91ab1c32dfb9ff2ce28))
* **tests:** create minimal schema in CI test database ([806cdaf](https://github.com/iamez/slomix/commit/806cdafd0ee28c582629345f20a37b09d189e545))
* **tests:** resolve all 53 test failures across 22 files ([aacd8e2](https://github.com/iamez/slomix/commit/aacd8e278359b80102401cf52a87c902f42d27c5))
* **tests:** restore broken test imports after scripts consolidation ([0a1139f](https://github.com/iamez/slomix/commit/0a1139f65dc25f33c264bc8cecf3fef234a92454))
* **tests:** skip tests when dependencies are unavailable ([ad4b747](https://github.com/iamez/slomix/commit/ad4b747d2a4d8da63f891d043d8e81cb92ff5a47))
* Use column expressions instead of aliases in ORDER BY for accuracy/headshots ([9da910a](https://github.com/iamez/slomix/commit/9da910a80f83bd14b7e91fd621a1284a24f419a3))
* Use column expressions instead of aliases in ORDER BY for accuracy/headshots ([9785c60](https://github.com/iamez/slomix/commit/9785c6041a66767ed45f52591a5284820c6c829d))
* **web,proximity:** dropdown click propagation and midnight session linking ([9d45d3f](https://github.com/iamez/slomix/commit/9d45d3fc54ace0e196261aee232bb13b693f1419))
* **web:** add unsafe-inline to CSP script-src to unblock onclick handlers ([cafeb02](https://github.com/iamez/slomix/commit/cafeb026a8a5927fcf038d3931e09d550ffa3b25))
* **webhook:** consume pending Lua metadata in all file processing paths ([fb472c2](https://github.com/iamez/slomix/commit/fb472c220b4b1eceeebb6d6b09864cb1a26ead3a))
* **web:** sessions nav highlighting and stats dropdown membership ([9d80594](https://github.com/iamez/slomix/commit/9d805940e4ee6d16a52799d6187786e191e20129))
* **website,db:** resolve 3 bugs blocking proximity v6 deploy ([f20268d](https://github.com/iamez/slomix/commit/f20268ddaaef104d9efd25bd5980ef1343f0335e))
* **website:** add view-skill-rating container to index.html ([8711a57](https://github.com/iamez/slomix/commit/8711a5768b87949083f04c574f18d9dc8f81bb1d))
* **website:** bump BUILD_VERSION to bust browser cache for skill-rating ([a1db7ae](https://github.com/iamez/slomix/commit/a1db7aed3a5a61d0c331fd1a3ac16b964d8811ac))
* **website:** correct table names in diagnostics and records routers ([9325a0f](https://github.com/iamez/slomix/commit/9325a0f1b46d6bdcdc645ce9c3c8164cdf536a6d))
* **website:** correct table names in diagnostics/records routers ([4033833](https://github.com/iamez/slomix/commit/403383348b38b3e262848c6a35b5515126279928))
* **website:** gaming_sessions is not a table, query rounds instead ([9b43b42](https://github.com/iamez/slomix/commit/9b43b42d9f80c6a6c6631919103adb2bfa837425))
* **website:** gaming_sessions query in diagnostics ([26704b3](https://github.com/iamez/slomix/commit/26704b3015712d8b90c0a74eb9b5aa528fcffcd8))
* **website:** round_id JOIN, error logging, and Chart.js guards ([7dc8ea2](https://github.com/iamez/slomix/commit/7dc8ea2daa7543fd14b042de4fdb3efd3a406659))
* **website:** strip ET color codes from proximity names, fix TS errors ([b95d713](https://github.com/iamez/slomix/commit/b95d713bf960a61c580f62cae346cb119d26874b))

## [1.1.0] - 2026-03-20

### Stats Accuracy Audit
- **fix(api):** R0 match summary rows double-counting kills/damage across 7+ endpoints — 94% inflation fixed
- **fix(api):** KD leaderboard: `NULLIF(deaths, 1)` → `CASE WHEN deaths > 0` — undefeated players no longer disappear
- **fix(api):** Accuracy now weighted by shots fired instead of naive per-round average
- **fix(api):** Headshots leaderboard uses `headshot_kills` (actual kills) instead of `headshots` (hit events)
- **fix(api):** `survival_rate` now uses engine TAB[8] alive% (excludes dead + limbo time)
- **fix(api):** `played_pct` capped at 100% (engine vs Lua timer ±1-3 sec per round)
- **fix(api):** weapon_stats CTE on `/stats/maps` now excludes R0 rows
- **fix(bot):** Headshot % formula in `!stats` — was `headshot_kills / weapon_hits`, now `headshot_kills / kills`
- **fix(bot):** `await` on sync methods in `advanced_team_detector.py` — runtime TypeError crash
- **fix(bot):** Achievement help text thresholds now match actual `achievement_system.py` values
- **fix(bot):** `avg_dpm` f-string format crash in Career Overview embed

### alive% / TMP (Time Played Percent)
- **feat(parser):** R2 differential for `time_played_percent` — converts cumulative percentage to R2-only via absolute alive time
- **feat(bot):** `time_played_percent` (TAB[8]) now stored in DB INSERT (57 columns)
- **feat(api):** Dual-mode alive% — engine value as primary, computed as fallback, with drift detection
- **feat(backfill):** Backfilled 8,799 rows from VPS raw stats files (99.9% coverage)

### FragPotential Hidden
- **refactor(api):** FragPotential removed from user-facing displays (kept internally for aggression model)
- **refactor(bot):** Session graph FP chart replaced with K/D Ratio; playstyle panel uses DPM
- **refactor(website):** SessionDetail shows Damage Efficiency instead of FragPotential

### React 19 Frontend Modernization
- **feat(website):** React 19 + TypeScript 5.9 + Vite 7 + Tailwind CSS v4 + Framer Motion
- **feat(website):** 19 route pages migrated from legacy JS to React (strangler pattern, 71% code reduction)
- **feat(website):** Game assets extracted from ET:Legacy pk3 files — 121 PNGs (weapons, classes, medals, ranks, levelshots)
- **feat(website):** New components: InfoTip, PlayerLookup, ProximityIntro
- **feat(website):** New pages: ProximityPlayer, ProximityReplay, ProximityTeams
- **feat(website):** Bridge layer: `modern-route-host.js` + `route-registry.js` for vanilla↔React coexistence

### Proximity v5.0 Teamplay Analytics
- **feat(proximity):** Lua tracker v5.0 with 5 new teamplay systems:
  - Spawn Timing (`proximity_spawn_timing` table, `!pse` command)
  - Team Cohesion (`proximity_team_cohesion` table, `!pco` command, Canvas timeline)
  - Crossfire Opportunities (`proximity_crossfire_opportunity` table, `!pxa` command)
  - Team Pushes (`proximity_team_push` table, `!ppu` command)
  - Trade Kills (`proximity_lua_trade_kill` table, `!ptl` command)
- **feat(bot):** New `proximity_session_score_service.py` — composite session scoring
- **fix(proximity):** 8 Lua bug fixes: team-damage filter, crossfire dedup, LOS mask, cache, teamkill filter, round_start_unix fallback, engagement timeout, cohesion guard
- **fix(proximity):** Focus-fire score credits attackers (coordinators) not victims
- **fix(proximity):** Roster seed includes both targets AND attackers

### Parser & Pipeline
- **fix(parser):** `time_played_percent` R2 differential — percentage→absolute time→subtract→reconvert
- **fix(parser):** R0 match summary correctly uses R2 cumulative TAB[8] as match-level alive%
- **fix(parser):** R2_ONLY_FIELDS audit — timing reconciliation for repeated maps

### Legacy JS Fixes
- **fix(website):** Session detail date path now resolves session ID before loading detail
- **fix(website):** Proximity scoped requests fall back to map_name/round_number when round_start_unix missing
- **fix(website):** `played_pct_lua` field added for frontend compatibility

### Tests
- **fix(tests):** Resolved all 53 pre-existing test failures across 22 files
- **test:** 313 tests passing, 45 skipped, 0 failures

### Cleanup
- **chore:** Removed 33 stale docs from `docs/instructions/` and `docs/reports/`
- **chore:** Removed obsolete `freshinstall.sh` and `update_bot.sh`
- **ci:** Excluded `website/assets/` from large file check (game levelshots are legitimate >500KB)

---

## [1.0.8] - 2026-02-27

### Round Correlation System
- **feat(bot):** Round correlation service (live mode) — tracks data completeness for each match (R1+R2)
  - New table: `round_correlations` (23 columns, 8 completeness boolean flags)
  - Admin command: `!correlation_status`
  - Config: `CORRELATION_ENABLED`, `CORRELATION_DRY_RUN`, `CORRELATION_WRITE_ERROR_THRESHOLD`
  - Schema preflight check and circuit breaker on write errors
- **fix(db):** Critical match_id generation fix — `filename.replace('.txt', '')` produced unique IDs per round (485 orphan R1s). Changed to extract shared `{date}-{time}` prefix.

### Round Linkage Anomaly Detection
- **feat(bot):** `round_linkage_anomaly_service.py` — detects linkage drift across lua_round_teams, rounds, round_correlations
- **feat(api):** `GET /diagnostics/round-linkage` — thresholded anomaly report
- **fix(bot):** Lua round linkage race condition — added second pass detecting stale linkages when closer match imported later

### Proximity Objective Coordinates
- **feat(proximity):** Template-driven objective coords for 8 high-impact maps
- **feat(ci):** WS11 Objective Coordinate Gate — prevents regressions on map coverage
- **feat(ci):** WS12 Single Trigger Path Enforcement — canonical webhook trigger flow

### Website Fixes
- **fix(api):** Round JOIN fragility — replaced composite key fallback with direct `round_id` JOIN
- **fix(api):** Hardened 3 silent error handlers with logging
- **fix(website):** Chart.js crash prevention with `hasChartJs()` guards and visible fallback text

### Scripts/Tools Consolidation
- **refactor:** 5 unified CLI tools replacing scattered scripts (68% file reduction)
  - `slomix_backfill.py`, `slomix_audit.py`, `slomix_rcon.py`, `slomix_proximity.py`, `slomix_retro.py`
- **fix:** 3 bugs found and fixed during consolidation

---

## [1.0.7] - 2026-02-22

### Greatshot Highlight Enrichment
- **feat(greatshot):** Enriched highlight metadata — kill sequences, weapon breakdowns, timing rhythm
- **feat(greatshot):** Player match stats attached to each highlight
- **feat(greatshot):** Database cross-reference — auto-match demos to rounds (confidence scoring)
- **feat(greatshot):** Scout-friendly UI — kill sequences, weapon badges, DB crossref panel
- **feat(greatshot):** New service: `greatshot_crossref.py`

---

## [1.0.6] - 2026-02-07

### Greatshot Demo Pipeline
- **feat(greatshot):** Upload `.dm_84` demos, auto-analyze with highlight detection
- **feat(greatshot):** Multi-kill, killing spree, quick headshot chain detectors
- **feat(greatshot):** Clip extraction via UDT_cutter at exact timestamps
- **feat(greatshot):** 4 new tables: `greatshot_demos`, `greatshot_analysis`, `greatshot_highlights`, `greatshot_renders`
- **feat(greatshot):** UDT parser built from source with ET:Legacy protocol 84 support

### Player Analytics
- **feat(bot):** `!consistency`, `!map_stats`, `!playstyle`, `!awards`, `!fatigue` commands
- **feat(bot):** `!matchup A vs B`, `!duo_perf`, `!nemesis` — lineup analytics with confidence scoring
- **feat(bot):** Map-based stopwatch scoring — session scores count MAP wins (not rounds)
- **feat(bot):** Real-time team tracking — teams grow dynamically (3v3 → 4v4 → 6v6)

### Website SPA Overhaul
- **feat(website):** Sessions, matches, profiles, leaderboards, admin, proximity, season stats pages
- **feat(bot):** Server control cog — RCON, status, map management

### Lua Webhook v1.6.0
- **feat(lua):** Spawn/death tracking, safe gentity access (crash fix)
- **feat(proximity):** Proximity Tracker v3 — crossfire detection, trade kill support

---

## [1.0.5] - 2026-01-25

- **feat(lua):** Webhook v1.3.0 — pause event timestamps, warmup end tracking, timing legend
- **feat(lua):** Webhook v1.2.0 — warmup phase tracking

## [1.0.4] - 2026-01-22

- **feat(lua):** Real-time round notifications (~3s after round end vs 60s SSH polling)
- **feat(lua):** `lua_round_teams` table — team composition, pause tracking, surrender timing fix
- **fix(lua):** R2 webhook rejection — `round_number=0` was incorrectly rejected

## [1.0.3] - 2026-01-14

- **feat(bot):** EndStats processing — 7 award categories, VS stats tracking
- **feat(bot):** Discord follow-up embeds with awards
- **feat(db):** 3 new tables: `round_awards`, `round_vs_stats`, `processed_endstats_files`

---

## Version Summary

| Version | Date | Highlights |
|---------|------|------------|
| **1.1.0** | 2026-03-20 | Stats audit (R0 fix, 14 bugs), React 19 (19 routes), Proximity v5 (5 systems), alive% engine value |
| **1.0.8** | 2026-02-27 | Round correlation, match_id fix, linkage anomaly detection, objective coords |
| **1.0.7** | 2026-02-22 | Greatshot highlight enrichment, database cross-reference |
| **1.0.6** | 2026-02-07 | Greatshot demo pipeline, player analytics, matchup system, website SPA |
| **1.0.5** | 2026-01-25 | Lua webhook pause/warmup tracking |
| **1.0.4** | 2026-01-22 | Real-time Lua webhook, surrender timing fix |
| **1.0.3** | 2026-01-14 | EndStats awards, VS stats, Discord follow-ups |
