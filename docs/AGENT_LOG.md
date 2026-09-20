# AGENT_LOG — durable lessons for the next agent

One entry per fact. Format: date · fact · why it matters · how to apply.
Newest first. This is the repo-side memory that any agent (Codex, Claude,
Copilot) can read and append to; private agent memories are not visible
across tools, this file is. Never put credentials, private names or raw
data here.

- **2026-09-20 · Explicit configuration is not enough if imports initialize the process.**
  The manager previously imported dotenv and configured root logging before its
  constructor could inspect supplied config. R04d moves legacy setup behind
  the default loader while preserving dotenv-before-log-path selection. Test in
  fresh processes with forbidden imports; also pin unchanged sys.path and root
  handlers. Import-only callers intentionally no longer initialize logging.


- **2026-09-19 · Lint modified legacy files as well as new modules.**
  R04c's new files passed Ruff but its legacy re-export block failed CI I001.
  Include every changed Python path in local lint. Module-attribute aliases
  retain the legacy function identities without unused-import ambiguity;
  mutation-test the export identity rather than assuming an alias is correct.

- **2026-09-19 · Parser parity needs nonempty players and a controlled clock.**
  The committed legacy sample_stats_files parse headers but zero player rows.
  Header parity alone cannot certify R2 player calculations. Supply valid player
  lines with a known differential and freeze the parser's generated timestamp
  when comparing subprocess outputs. A blocked-import subprocess proves absence
  of Discord/config dependencies more strongly than checking imports in pytest.

- **2026-09-19 · A neutral process needs neutral configuration.**
  shared.config reexports BotConfig and its validation requires Discord. The
  cache entrypoint reads explicit environment without dotenv or that validator,
  defaults OFF before network, and owns its native pool/task. Prove independence
  by actual subprocess imports, catch-up and signals, not just a coroutine test.
  A dev label/local host is not attestation that the chosen database is dev.


- **2026-09-19 · Logging emission is separate from process setup.**
  Importing bot.logging_config creates its log directory. Runtime-only callers
  can use shared.database_logging without that side effect; legacy exports stay
  compatible. Prove the boundary in a fresh subprocess with forbidden-import
  hooks, then mutate an import after definitions so a circular-import collection
  error does not masquerade as an executed boundary guard. Manager startup still
  needs its own extraction; moving dotenv imports can change log-directory order.

- **2026-09-18 · Verify release registration from the evaluated array.**
  A migration filename appearing somewhere in a shell config does not prove
  membership in MIGRATIONS: even a comment passes a substring assertion.
  Inspect the evaluated Bash array and compare exact entries. Commenting out
  migration 090 reproduced the missing-registration failure; restore with cmp.

- **2026-09-18 · Every new round_id table needs a linkage decision.**
  The schema-driven coverage contract also applies to runtime receipt tables.
  lua_correction_receipts records the target of a committed correction, so
  generic relinking must not rewrite its historical provenance. Add a justified
  exemption and run test_round_id_coverage_contract.py alongside PG proofs;
  focused transaction tests alone did not catch this CI failure.

- **2026-09-18 · Measure the pre-push hook's actual comparison range.**
  New branches compare with the main merge-base; existing branches compare
  with their previous remote tip, intersected with paths changed vs main.
  A three-file update can correctly pass while its dependent stack has26files.
  Do not mistake total stack size for the hook's update size or bypass the hook.

- **2026-09-18 · Test retention against the actual normalized producer.**
  Lua correction metadata uses END_REASON_ENUM (uppercase), not raw webhook
  text. A lowercase-only inbox validator rejected valid producer output while
  synthetic fixtures without end_reason passed. Reuse the canonical enum and
  exercise WebhookRoundMetadataService before retaining input; raw timelimit
  normalizes to NORMAL, not a new TIMELIMIT value.

- **2026-09-18 · Correction fixtures must preserve integer seconds.**
  A REAL fixture accepted values the live INTEGER player-duration column
  rejects. Use INTEGER in boundary proofs; validate finite, nonnegative,
  integral durations before SQL. Canonical helpers that swallow collisions
  cannot establish atomic correction success: enforce conflicts in the same
  native transaction as metadata, DPM and its journal event.

- **2026-09-18 · Post-import correction failure is not import failure.**
  The importer and bot mark the file successful before Lua overrides; ingress
  RAM/DB/session gates can skip any retry and pending metadata is popped.
  Rethrowing or moving only the bot marker cannot guarantee recovery. Give
  corrections their own atomic boundary and retained-input retry contract;
  do not misclassify an already committed import as RetryableImportFailure.

- **2026-09-15 · Retry ownership must travel with the chain.** Capture the
  original webhook claim explicitly when scheduling, retain it across attempts,
  and release it only on retryable terminal exits. Looking up the current alias
  owner at cleanup time can release a replacement. Immediate release while a
  retry is pending instead permits competing polling publication. Prove both
  pending exclusion and terminal alias cleanup with actual asyncio tasks.

- **2026-09-15 · A post-await duplicate needs the same trigger cleanup.**
  Another endstats attempt can claim a filename during DB preflight. The
  losing webhook must delete its notification just like the initial duplicate
  path, but must not release the winner's marker. Inject ownership during the
  awaited DB call and exercise both successful and failed Discord deletion.

- **2026-09-15 · A filename is not an attempt identity.** Polling cleanup
  must compare its claim object with the current owner before removing a RAM
  marker. A later retry may own the same filename, and richer selection may
  select an alias already owned elsewhere. Exception and soft-failure paths
  both need the identity guard; a raw set.discard silently defeats it.

- **2026-09-15 · Test the gate before the handler too.** Endstats had four
  filename gates, including monitor preflight in webhook_handler_mixin.
  A direct handler retry passed while real polling still rejected the failed
  filename. Exercise preflight plus handler/storage; preserve terminal and
  NULL/unknown states when narrowly allowing explicit publication failures.

- **2026-09-14 · Best-effort catches are unsafe around opt-in journal writes.**
  Restart detection used to swallow errors. With the status producer enabled,
  failures must reach the canonical import rollback; actual status update,
  event and notification share that transaction. Guard completed status in
  the UPDATE, not only the earlier SELECT, to avoid journaling stale no-ops.
  Atomic recording does not prove the restart heuristic itself correct.

- **2026-09-14 · Lock the selected source, not only the destination.** A
  NULL-only timing fill can commit stale Lua values if its source changes
  concurrently. Lock both selected rows with SKIP LOCKED until commit; prove
  both source-first skip/retry and fill-first blocked relinking on real PG.
  This is not a guarantee against later changes or newly inserted sources.

- **2026-09-14 · Initial-event dedup is not update-event dedup.** A timing
  source can undergo value -> NULL -> value across a repair. A permanent
  round/type or content-hash key would hide the later real transition. R02a
  keeps only the initial import key unique; row-locked NULL-to-value fills
  emit each actual transition and repeated successful fills are no-ops.
  Consumers still cannot use sequence ID as commit order.

- **2026-09-14 · Rollback is not retry eligibility.** FileTracker treats
  success=false processed_files rows as terminal too; UltimateBot also cached
  them in RAM. DB/preflight/transaction failures must return a structured
  retryable result without either marker. Keep deterministic parse failures
  separate. R01 proves a failed journal import can retry and commit; existing
  activity/lookback windows still limit automatic recovery.

- **2026-09-10 · A migration has three installation paths to keep aligned.**
  R01 initially added SQL alone, omitting the latest release config and the
  canonical dump used before deploy_clean's baseline. Register it in the
  release array and mirror DDL in the dump; run release-contract and real
  fresh-bootstrap parity tests. A local opt-in PG test also needs an explicit
  CI path or its only real SQL coverage silently skips in the matrix.

- **2026-09-08 · Import success must be logged after transaction exit.**
  `pg_notify` participates in the import transaction and can fail at COMMIT;
  the emitter returning does not prove persistence. R01 moves success counts
  and logs after COMMIT; a canonical-import test injects commit failure and
  checks that no success is reported. Updated 2026-09-14: transient failures
  now leave no terminal processed-file marker, so a later poll can retry. This mock is
  wiring evidence, not real PostgreSQL transaction proof. Initial journal
  events are not final-round events: validation warnings and post-commit
  correlation/Lua/endstats changes remain distinct facts.

- **2026-09-07 · A directory's mtime is not its contents' mtime.** `ls -la
  <dir>` reports when the directory entry list last changed (a file added or
  removed), not when files inside were written; a rebuilt bundle that reuses
  its file names leaves the directory mtime untouched. Ask the files:
  `find <dir> -type f -printf '%T@ %p\n' | sort -n | tail -1`. This is how a
  13-hour-old SPA bundle looked fresh on 2026-09-07 (sister session).
- **2026-09-07 · A cold cache changes how many calls a measurer sees, not
  only how long they take.** The same page produced 2 observed API calls in
  one window and 40 in another, depending on whether the backbone was warm.
  Every recorded number states cold/warm, and nothing is compared with a
  number taken right after a restart (sister session; see also
  `docs/AGENT_LOG.md` 2026-08-29 "second call is not a measurement").
- **2026-09-07 · `git stash list` before `git stash pop`.** A stash left by
  another session on the same working tree pops into a clean tree as
  conflicts that look like your own. On a shared box, list first and pop by
  index, or do not stash at all — commit to the branch (sister session).
- **2026-09-07 · An artefact is not a commit.** `/api/build` reports the git
  commit the process runs from; the SPA bundle it serves is a build product
  with its own age. Both were checked on 2026-09-07 and only the commit was
  current. `scripts/dev_deploy.sh` now refuses a bundle older than its
  source (exit 3, #960); when a deploy "looks right", also compare the
  bundle's newest file against the last commit touching `src/app`.
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
