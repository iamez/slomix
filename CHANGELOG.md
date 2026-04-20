# Changelog

All notable changes to Slomix are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

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
