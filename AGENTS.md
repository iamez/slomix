# AGENTS.md — how an agent works in this repository

Read this first. It is the distilled contract for any coding agent (Codex,
Claude, Copilot). The long-form rules live in `docs/CLAUDE.md` and the nested
`CLAUDE.md` files; this file is what must never be violated and where to look
next. The owner (iamez) is Slovenian: **talk to the owner in Slovenian with
correct diacritics (č š ž)**; code, comments, commit messages and PR text stay
in English.

## 1. Hard rules (⛔ = never, no exceptions without the owner saying so *for that action*)

- ⛔ **Never merge a pull request** without the owner's explicit permission
  for *that* PR number. Permission for one PR does not carry to the next.
  Merges go through `~/slomix-ops/cycle.sh <pr> <branch> "<squash title>"
  <body.md>` (waits for CI, 7-minute pause, refuses a branch behind `main`).
- ⛔ **Never restart, stop, start or deploy a service**: `etlegacy-bot`,
  `etlegacy-web` (dev), `slomix-bot`, `slomix-web` (production), the game
  server (puran), its Lua (`lua_restart` is forbidden). Propose the command;
  the owner runs it. Production is **frozen at v1.39.0** — deploy is not a
  task.
- ⛔ **Never commit directly to `main`.** Feature branch + PR, Conventional
  Commits (`feat|fix|docs|chore|refactor|test|security|perf(scope): …`,
  scopes `bot website proximity greatshot ci db lua`).
- ⛔ **`git add` by file name only.** Never `git add -A`, `git add .`,
  `git commit -a`. Never `git clean`, `git checkout -- .`, `git stash -u`,
  `git reset --hard`, `git push --force`, `git push --no-verify`. The
  pre-push hook refuses > 25 files across the pushed commits and scans for
  credentials; do not work around it — split the PR.
- ⛔ **No secrets, logs, backups, dumps, spreadsheets or raw data in git.**
  The repo is public. Local-only paths (gitignored, visible in this checkout,
  absent from a fresh clone): `docs/design/` (except the committed subset),
  `docs/research/`, `docs/archive/`, `docs/OMNIBOT_PROJECT.md`,
  `server/omnibot/`. New research documents stay local; ask before committing.
- ⛔ **Never paste a password into chat or into a file that git tracks.**
  Credentials come from `.env`; `sudo -n -l` before assuming sudo.
- ⛔ **Do not type into other agents' terminals** (tmux `send-keys` into a
  Claude session lands in the owner's prompt). Their answers are in
  `docs/HANDOFF-next.md`, `docs/PLAN.md`, `docs/BACKLOG.md`.
- ⛔ **RAM is 2 GB and shared.** Only the owner's dev server on `:8000` runs
  unasked. An agent's own server (`:8056`) and any Playwright/chromium run
  need the owner's OK; never two browser runs in parallel; find your own
  process with `ss -ltnp | grep :8056`, never `pkill -f` / `pgrep -f` (they
  match your own shell and kill it).
- ⛔ Migrations are immutable once merged; a fix is a new migration.

## 2. Evidence before claims

- Green tests are **not** proof. Every change needs a runtime proof
  (endpoint response, rendered page, log line) *and* at least one mutation of
  the guard you added that was **seen failing**, then restored (`cmp` the
  file after restoring).
- Measure important numbers twice, by two paths. An impossible result means
  a broken measurement — including yours. Say hot vs cold for any timing.
- Before sampling a live server: `ps -o lstart= -p <pid>` versus
  `git log -1 -- <handler>`. A server older than the code proves the build,
  not the code.
- A claim about data (what the DB holds) and a claim about code (what a
  handler does) are different facts; label which one you measured.
- Absence is not consent: an empty set and an unmeasured set have the same
  shape. UI keeps `no_data` / `unavailable` / `loading` apart; every filter
  names what it excludes.
- Report the outcome first, then the details; failures verbatim with output.
  A negative result is a result — write it down.

## 3. How work flows

1. `docs/PLAN.md` is the single plan of record; update it at every step.
   `docs/BACKLOG.md`: before jumping to an unrelated request, write where you
   stopped; after the detour, write what you changed.
2. One slice = one branch = one PR, with proofs in the PR body. Commit after
   every completed step. Before push:
   `git diff --check origin/main...HEAD -- . ':(exclude)*.md'` (CI fails on a
   blank line at end of file, with exit code 2 and no pytest output).
3. After push: self-review the diff (what exactly changed, what could break).
   Then wait for the owner's merge decision. Codex/CodeRabbit review threads
   must be answered; silence is not approval.
4. Ask the owner concrete questions with options, one decision at a time,
   and mark your recommendation.
5. Durable lessons that a future agent needs go to `docs/AGENT_LOG.md`
   (one dated entry per fact: fact, why, how to apply). Claude sessions keep
   a private memory under `~/.claude/projects/-home-samba-share-slomix-discord/memory/`
   — its `MEMORY.md` is an index worth reading, **but never copy from it into
   the repo** (it can contain credentials).
6. Sub-agents: at most 2 concurrent, never two writers in one working tree
   (use `git worktree`), none running a browser while another does.

## 4. Where things are

| need | file |
|---|---|
| where we are, what is next, how to prove it | `docs/HANDOFF-next.md` |
| the full-project handoff to Astra (work package §C, do-nots §D, measured answers §G–§I) and the open-work inventory | `docs/HANDOFF-astra.md`, `docs/HANDOFF-astra-inventory.md` |
| how the new SPA must be extended (panel, rows, formatters, tokens, ratchets) and the owner's visual complaints | `docs/SPA_MODULARITY.md`, `website/frontend/AGENTS.md`, `docs/DESIGN_PUNCHLIST.md` |
| plan of record / open positions | `docs/PLAN.md`, `docs/BACKLOG.md` |
| rules per package | `docs/CLAUDE.md`, `bot/CLAUDE.md`, `bot/{core,cogs,services,automation}/CLAUDE.md`, `website/backend/CLAUDE.md`, `tests/CLAUDE.md`, `docs/WEBSITE_CLAUDE.md`, `docs/PROXIMITY_CLAUDE.md`, `docs/GAMESERVER_CLAUDE.md`, `website/frontend/AGENTS.md` |
| known issues | `docs/KNOWN_ISSUES.md` |
| infra / CI / deploy | `docs/INFRA_HANDOFF_2026-02-18.md`, `scripts/deploy_release.sh`, `scripts/health_check.sh` |
| what belongs in git | `docs/REPO_BOUNDARY.md` |
| review conventions (what is deliberate) | `docs/REVIEW_GUIDE.md` |
| working loop for any task | `docs/process/MANDELBROT_RCA.md` |
| spider web (positional stats) status | `docs/SPIDERWEB_STATUS.md`, `docs/PROXIMITY_SPIDER_WEB_SPEC_2026-07.md` |
| new-site design (committed subset) | `docs/design/README.md` → 05 → 06 → 09 → 12 → 17 |

Architecture in one line: game server → Lua tracker + stats files → SSH
poll (bot) → parser → PostgreSQL (`etlegacy`, 101 tables) → Discord bot
(`bot/`, 21 cogs) and FastAPI website (`website/backend`, port 8000) → legacy
JS (`website/js`, production) and the new React SPA (`website/frontend/src/app`,
served at `/app`, dev only).

## 5. Commands that are the proofs

```bash
venv/bin/python -m pytest tests/unit tests/integration -q -x          # Python
venv/bin/ruff check bot/ website/backend/                             # lint
(cd website/frontend && npm run typecheck && npx vitest run)          # SPA
bash scripts/lint-js.sh                                               # legacy JS
(cd website/frontend && npm run build:app)                            # SPA build (NOT `npm run build`)
# own dev server (owner's OK first), then e2e
nohup ./venv/bin/python -m uvicorn website.backend.main:app --host 0.0.0.0 --port 8056 > /tmp/uvicorn8056.log 2>&1 &
(cd website/frontend && SMOKE_BASE_URL=http://127.0.0.1:8056 npx playwright test --project=anon)
venv/bin/python scripts/apply_migrations.py --status                  # migrations (see pitfall below)
bash scripts/health_check.sh                                          # read-only host check
```
Unit names differ per host: dev `etlegacy-bot`/`etlegacy-web`, production
`slomix-bot`/`slomix-web` — `systemctl list-units --all 'etlegacy-*' 'slomix-*'`
before believing "inactive".

## 6. Pitfalls that cost a day each (verified, dated)

- PostgreSQL only; `?` placeholders; queries by `gaming_session_id` (never
  dates), group by `player_guid` (never name), session gap 60 min, filter
  `round_number IN (1, 2)` (R0 rows are still written and doubled every
  unfiltered sum), durations from `shared/round_time.py` (`actual_time` is a
  target, not a measurement). Never recompute the R2 differential.
- `website/.env` overrides `POSTGRES_USER` to `website_app` → admin tools run
  as the wrong role ("must be owner"); run them with
  `POSTGRES_USER=etlegacy_user POSTGRES_PASSWORD=…` from the root `.env`.
- `website/frontend/src/api/generated/openapi.d.ts` is GENERATED and
  gitignored — a merge does not refresh it. Use the npm scripts
  (`npm run typecheck` / `test` / `build:app`): their `pre*` hooks regenerate
  it. If you bypass them with `npx tsc` or `npx vitest`, run
  `npm run generate:api` first. `rm` is not a fix: before an npm script it is
  redundant, before `npx` it breaks typecheck with errors pointing at
  unrelated files.
- "Who is building this?" ≠ "is this already built?" — a squash-merged branch
  shows no diff against `main`. Check `git ls-tree -r origin/main <path>` and
  `git log HEAD..origin/main` before building a page twice.
- Proximity tables hold the 32-char guid; session/profile pages key on the
  8-char prefix. A link that passes the prefix to a proximity endpoint renders
  a valid "not tracked" page — the sweep cannot see it.
- Handlers answering **HTTP 200 with `{"status":"error"}`** (25 of them) are a
  deliberate convention, not a bug (owner, 2026-08-30; pinned by a test).
- `gh pr checks --json` does not exist here; CI rollup has two shapes
  (`CheckRun.conclusion`, `StatusContext.state`). Use
  `gh api repos/iamez/slomix/actions/runs?head_sha=$(git rev-parse origin/<branch>)`
  and `gh run view <id> --log-failed`.
- PostgreSQL `LIKE '06[78]%'` silently matches nothing; use `~ '^06[78]'`.
  Server logs contain NUL bytes: always `grep -a`.
- A guard must be seen failing before you trust it; a mutation that did not
  execute reports "guard holds". A regex over source text matches prose and
  comments — introspect the object, not the file.
- Scripted edits that compute a boundary with `str.index(token) + N`: count
  the token. A five-character token with `+4` moved a `;` past an inserted
  block — legal code, silent in typecheck and tests, seen only by static
  analysis and only at one of the two places (2026-09-06).
- The endpoint gap is a COUNT of `tests/data/endpoint_gap.txt`
  (`grep -vcE '^\s*(#|$)' tests/data/endpoint_gap.txt`), never a number
  copied from a document — PLAN quoted 3 and 16 on the same day while the
  file said 13; `test_plan_quotes_the_measured_gap.py` now refuses that.
- The dev bot and website run from `/home/samba/share/slomix-dev-run`, a
  clone kept on `main` (since 2026-09-07; before that they ran from this
  working tree and a `git checkout` here was a silent deploy). Deploy to dev
  with `scripts/dev_deploy.sh`; never edit or check out inside the run dir.
  Work in a `git worktree` (e.g. `../slomix-fable`), not in the primary tree.
- A hash quoted in a document may predate the history rewrite of 2026-08-27
  (all hashes changed); verify with `git merge-base --is-ancestor` before
  building on it.
