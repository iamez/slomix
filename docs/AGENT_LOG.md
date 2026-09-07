# AGENT_LOG — durable lessons for the next agent

One entry per fact. Format: date · fact · why it matters · how to apply.
Newest first. This is the repo-side memory that any agent (Codex, Claude,
Copilot) can read and append to; private agent memories are not visible
across tools, this file is. Never put credentials, private names or raw
data here.

- **2026-09-06 · One row's age carries two meanings; say both.** (Review of
  #949 by the sister session.) `server_status_history` stops moving when the
  bot is down AND when its monitor loop fails on every tick (the loop survives
  its own exceptions, `monitoring_service.py:277-279`); it never moves at all
  when `MONITORING_ENABLED` is off; and `logs/bot_error_streaks.json`'s
  `written_at` moves only on errors and resets (the idle endstats loop returns
  before its SSH call nine ticks in ten), so it is not a heartbeat either.
  Apply: a liveness finding names every cause the signal cannot separate, an
  empty table is `unknown`, a database that cannot be asked is `unknown`, and
  a threshold is read from the config that sets the cadence, not hard-coded.
- **2026-09-06 · `systemctl is-active` on a unit that does not exist says
  "inactive".** The watchdog reads `LoadState` first: a unit that is not
  installed on this host is `unknown`, not down — dev runs `etlegacy-*`,
  production `slomix-*`. Why: "inactive" invited starting a second copy by
  hand (2026-08-05). Apply: never derive "not running" from `is-active`
  alone; the watchdog never starts anything, it proposes the command.
- **2026-09-06 · A register is three existing lists made one, not a fourth
  list.** The profile endpoint's section allowlist (with measured costs), the
  formula registry's entry shape and routes.data.json's page keys already
  existed; `services/dataset_registry.py` unifies them and the profile router
  now derives its allowlist from it. Why: two lists of the same thing drift
  the day one is edited. Apply: before adding a registry/allowlist, grep for
  `frozenset({` and `get_registry` — derive, then pin the derivation in a test.
- **2026-09-06 · A window must apply on READ, not only in memory** (sister
  session, #923). Persisted error streaks without the 30-minute window on
  load woke up with yesterday's streak and announced a recovery for an outage
  that ended before the restart. Apply: any persisted counter carries its
  window into the loader; absent key = never failed OR recovered OR expired.
- **2026-09-06 · A payload can carry a zero AND an error; read the error
  first.** `/api/diagnostics` reports a failed monitoring table as
  `{count: 0, last_recorded_at: null, error: "query failed"}`; the About panel
  checked `'count' in m` and printed "voice 0 rows". Why: the zero is a
  placeholder, the error is the fact. Apply: in every reader, branch on
  `error` before any count; keep a constructed degraded fixture next to the
  recorded healthy one so the branch has something to fail on.
- **2026-09-06 · Guid prefix collisions exist only among bots.** Across every
  proximity guid source, 34 full guids map to 23 prefixes and the two shared
  prefixes are `OMNIBOT0`/`OMNIBOT1`; every human prefix is unique. Why: an
  8-char key is therefore a lossless lookup for humans and an honest 400 for
  bots. Apply: `resolve_player_guid` in `proximity_helpers`; never push
  `LEFT(guid,8)=` or `LIKE` into a main query (seq scan, en_US collation) —
  resolve once through the indexed `*_guid_canonical` column, then bind `=`.
- **2026-09-07 · The services no longer run from the working tree.**
  `/home/samba/share/slomix-dev-run` is a clone kept on `main`; venvs and
  the big read-mostly corpora are symlinks into the agents' tree, `.env` is
  a copy whose four absolute paths point at the run dir, static bundles are
  copied by `scripts/dev_deploy.sh` (no vite build on a 1.8 GB box). Why: a
  checkout in the working tree was a silent deploy twice on 2026-09-06.
  Apply: deploy to dev with the script; unit files live in `deploy/systemd`;
  a fresh venv per service is the next isolation step.
- **2026-09-06 · Scripted edits: count the token before adding an offset.**
  `s.index("\n  };") + 4` on a five-character token slid a `;` past the
  inserted block: one statement lost it, an empty statement appeared later.
  Legal TypeScript, so typecheck and 675 tests stayed green; CodeQL saw one
  half. Apply: after a scripted edit, diff the neighbourhood, and grep
  `^;$` / the moved character, not only the test suite.
- **2026-09-06 · A hash in a document may predate the history rewrite.**
  `docs/HANDOFF-next.md` carried `19c61847` as the base for the review PR;
  the rewrite of 2026-08-27 changed every hash and the real #802 merge is
  `87a7063d`. Why: a PR with a non-ancestor base shows the whole history as
  its diff. Apply: `git merge-base --is-ancestor <hash> origin/main` before
  building on any quoted hash.
- **2026-09-06 · Ultra review accepts ≤ 8 000 changed lines / 500 files.**
  Code changed since production (v1.39.0) is ~93 k lines, so reviews are cut
  by area with `review-base/NN-<area>` branches (main with the area reverted
  to v1.39.0) → `main`. Apply: measure `git diff --numstat` before opening a
  review PR; never merge a review PR.
- **2026-09-06 · "Who is building this" is not "is it built".** A sister
  session rebuilt compare/wrapped because it searched open PRs for someone
  *building* the routes; the merged (squashed) work shows no diff against
  main. Apply: `git ls-tree -r origin/main <path>` and `git log
  HEAD..origin/main` first.
- **2026-09-06 · `openapi.d.ts` is regenerated by npm `pre*` hooks, not by
  merges.** `npx tsc` after a merge fails on other people's code because the
  gitignored file is stale; `npm run typecheck` regenerates it. Apply: use the
  npm scripts, or `npm run generate:api` before bare `npx`.
- **2026-09-06 · Codex CLI loads no project instructions unless `AGENTS.md`
  exists** (`codex debug prompt-input "ping"` renders the developer messages
  without a model call and showed zero). Apply: keep `AGENTS.md` under the
  `project_doc_max_bytes` limit and re-run that command after editing it.
- **2026-09-05 · The Lua damage hook fires at the top of `G_Damage`.** It
  sees the target's health *before* the hit and fires for every entity,
  including `script_mover`. Apply: vehicle-health logic must not treat the
  hook value as post-hit.
- **2026-09-03 · `website/.env` overrides `POSTGRES_USER`.** Admin tools
  (`apply_migrations.py`, backups) picked `website_app` and could not own or
  read 7 tables. Apply: run admin tools with the root `.env` role explicitly.
- **2026-09-02 · `npm run build` is the legacy host; the SPA is `build:app`.**
  A wrong target succeeds and a live sweep then measures the OLD bundle.
- **2026-08-30 · `pkill -f` / `pgrep -f` match the shell that runs them.**
  Find a process by port (`ss -ltnp`) and kill by PID.
- **2026-08-19 · R0 (`round_number = 0`) rows are still being written and
  are read by nothing.** Any unfiltered sum doubles kills and damage. Apply:
  `round_number IN (1, 2)` or the `player_match_stats` view, always.
- **2026-08-18 · `rounds.actual_time` is the stopwatch target, not the
  measured duration** (overstates ~15 % of rounds). Apply:
  `shared/round_time.py`.
