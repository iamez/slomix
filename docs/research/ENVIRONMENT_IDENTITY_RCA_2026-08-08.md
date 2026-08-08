# Environment Identity — Mandelbrot RCA v2.0

Research pass only, per Mandelbrot RCA v2.0 (Discovery → Dependency Mapping →
Contract Extraction → Mandelbrot Zoom → RCA Deep Dive → Fix + Verify). This
document covers phases 0-4. **No code was changed.** Phase 5 (fix + verify)
is a separate, later step pending owner review of this document.

Scope: the "environment identity" gap first flagged in
`docs/research/DISCORD_ROUTING_AUDIT_2026-08-06.md` §5 — no code-level
mechanism exists anywhere in this system that knows or asserts "this process
is dev" vs. "this process is production."

---

## Phase 0 — Discovery: what exists today

Checked every place that currently distinguishes dev from production, on
this host, right now:

| Layer | Mechanism | Reaches the app process? |
|---|---|---|
| systemd unit name | `etlegacy-bot`/`etlegacy-web` (dev) vs `slomix-bot`/`slomix-web` (prod) | No — the name is metadata, never read by the running code |
| systemd unit file | `/etc/systemd/system/etlegacy-bot.service` — `WorkingDirectory`, `User=samba`, no `Environment=` identity var | No |
| `deploy_release.sh` | Hardcoded to `slomix-web`/`slomix-bot` only — it **is** the prod-only deploy script, not a shared script parametrized by environment | No — the script "knows" by being prod-only, but never tells the app |
| `scripts/health_check.sh` | `check_service_pair()` **probes both** possible unit names and uses whichever exists (`etlegacy-*` / `slomix-*`), rather than reading a known value | No — this is a workaround for the same absence, not a fix |
| `.env` (bot) vs `website/.env` | Two separate files per host, hand-maintained | Indirectly — every individual setting inside them, but nothing asserts *why* a value was chosen |
| `.env.example` | Documents a safe default (`SSH_ENABLED=false`, placeholder host) | No — dev's real `.env` has already drifted from it |

**Conclusion:** environment identity exists only as *metadata about the
deployment* (host, unit name, which script you ran) — it never becomes a
*fact the running process itself knows*. Every config value that should
differ between dev and prod does so purely by accident of which `.env` file
happens to be sitting in the working directory.

### A precedent already exists — and it shows the failure mode directly

`website/backend/security_utils.py:338-360` `resolve_trusted_hosts()`:

```
Fail-fast rule: SESSION_HTTPS_ONLY=true is this app's production posture
(dev opts out for local HTTP). Running that posture without an explicit
trusted-host list would silently accept any Host value, so it is a
startup error rather than a warning nobody reads.
```

Someone already had the right instinct — validate a dangerous combination at
startup instead of hoping someone reads a warning. But it infers "is this
production" from a **side-effect proxy** (`SESSION_HTTPS_ONLY`) rather than a
first-class signal. That is fragile in a specific, already-demonstrated way:
it only catches *inconsistent* configuration (https-only with no trusted
hosts), not *mislabeled* configuration (someone sets `SESSION_HTTPS_ONLY=true`
on dev, or `false` on prod, by mistake — the check has no opinion, because it
doesn't actually know which environment it's in, only what `SESSION_HTTPS_ONLY`
says).

This same proxy-signal pattern **does not exist at all on the bot side** —
`bot/config.py` has no equivalent check anywhere for `SSH_ENABLED`,
`AUTOMATION_ENABLED`, or any of the other 15 SSH-/automation-related settings.

---

## Phase 1 — Dependency Mapping

Every place currently relying on implicit, unvalidated per-host `.env`
correctness to distinguish dev from production behavior:

**Bot side (`bot/config.py`):** 15 distinct `SSH_*`/`AUTOMATION_*` settings
gate whether the bot polls the real game server and posts to Discord.
Confirmed live on this dev host: `SSH_ENABLED=true`, `SSH_HOST=puran.hehe.si`
(the real production game server), `AUTOMATION_ENABLED=true`. None of these
are validated against anything — they are simply read.

**Website side (`website/backend/main.py`):**
- `SESSION_HTTPS_ONLY` (line 118) — has the `resolve_trusted_hosts` guard
  above, but only for its *own* consistency, not for whether it's the
  *correct* value for this host. This is the exact setting that broke dev
  login on 2026-08-05 (`dev_login_broken_https_only` — confirmed unset
  anywhere, defaulted to the production-safe `true`, and dev serves plain
  HTTP, so the auth cookie was silently dropped by the browser).
- `CORS_ORIGINS` (line 119-121) — defaults to `localhost:7000`, must be
  overridden with the real domain in production; no check that it was.
- `TRUSTED_HOSTS` — validated for internal consistency (above), not for
  correctness against the actual host.

**Both sides:** `DISCORD_GUILD_ID` vs. dev's `.env` using the wrong key name
`GUILD_ID` (found and left as a known fragility in
`docs/research/DISCORD_ROUTING_AUDIT_2026-08-06.md` §4) — currently papered
over by a second config layer (`bot_config.json`) supplying the correct key,
which is itself an accident of what happens to exist on this specific host.

**Architectural constraint on the fix:** `website/` was deliberately
decoupled from `bot/` recently (PR #603, "web↔bot decoupling" —
`web_bot_decoupling_pr603` in memory) specifically to stop the website
transitively importing `discord.py`/`matplotlib` and cut ~500 modules from
its import graph. **Any fix here must not reintroduce that coupling** — a
shared environment-identity module that both sides import needs to be
trivially small (no heavier than `os` + a few lines) to avoid relitigating
that decoupling work, or each side implements its own copy of ~10 lines
independently. This is a real design fork, not a detail — recorded as an
open question in Phase 4.

---

## Phase 2 — Contract Extraction (sketch, not final)

What the mechanism needs to guarantee, if built:

- **Precondition:** the variable must be set. No default that silently picks
  either dev or prod.
- **Postcondition:** at process startup, before any automation
  (`SSH_ENABLED`, `AUTOMATION_ENABLED`) is allowed to activate, the resolved
  environment value is validated against a closed set (`dev` / `production`
  — not a boolean, so a future third environment isn't a breaking change)
  and logged prominently (matches this project's own logging convention —
  every other config section logs what it resolved to).
- **Invariant:** `SSH_ENABLED=true` requires `BOT_ENVIRONMENT=production`
  (or an explicit, separately-named override flag for the rare legitimate
  case of testing SSH from dev — not the same variable, so it can't be
  set-and-forgotten the way `SSH_ENABLED` itself was).
- **Failure mode:** missing or invalid value → refuse to start (fail closed),
  not fall back to a guess. This mirrors `resolve_trusted_hosts`'s existing
  philosophy (raise at startup, not a log line nobody reads) rather than
  inventing a new failure posture.

---

## Phase 3 — Mandelbrot Zoom (12-point check against this design, before writing any code)

Points most relevant here (full 12-point list is generic; these are the ones
that actually bite for this specific mechanism):

1. **Correctness** — a string enum (`dev`/`production`), not a boolean.
   Booleans forecloses ever adding `staging` without a breaking rename.
2. **Edge cases — measured, not estimated (2026-08-08).** CI already copies
   `.env.example` → `.env` fresh every run (`tests.yml:244`) and appends a
   few placeholder secrets, so CI **already inherits whatever safe defaults
   live in the template** — a new `BOT_ENVIRONMENT` line in `.env.example`
   flows into CI automatically, no separate CI-specific handling needed.
   Grepped every test file that constructs `BotConfig()` or launches the
   website app directly, rather than guessing:
   - **Bot side, 3 files** construct `BotConfig()` directly:
     `test_config_loading.py` and `test_round_publisher_autopost_toggle.py`
     already `monkeypatch.setenv(...)` several vars before constructing —
     one more line each. `test_data_integrity.py` has 4 bare
     `BotConfig()` calls with no explicit env setup — these ride on
     whatever `.env` exists on the host running them, which the CI fix
     above already covers; only this dev box's own `.env` needs the line
     once (already an open question in this doc, not new scope).
   - `tests/conftest.py`'s `mock_config` fixture — used by exactly 1 test;
     one line covers it.
   - **Website side, 4 files** (`test_route_contract.py`,
     `test_web_does_not_import_bot_discord.py`,
     `test_real_stack_security.py`, `test_security_headers_middleware.py`)
     launch the app as a subprocess with an explicit, minimal env dict —
     each needs exactly one new key added.
   - Confirmed NOT affected: `bot/ultimate_bot.py` does not construct
     `BotConfig()` at module level, so the 8 test files that import it do
     not transitively trigger the new check.
   - **Total measured scope: ~8 test files, one line each, plus both
     `.env.example` templates.** Smaller than this document originally
     speculated — corrected here rather than silently.
3. **Security** — this is explicitly a security-adjacent control (it's what
   should have prevented dev from polling the live game server). Must fail
   closed, per Phase 2.
4. **Error masking** — don't catch-and-log-warning on an invalid value; that
   is exactly the "warning nobody reads" failure mode the existing
   `resolve_trusted_hosts` comment already identifies and rejects.
5. **Duplication** — bot and website currently have zero shared config code
   (confirmed, Phase 1). Decide once, explicitly, whether this becomes the
   first shared module or two independent small implementations, rather
   than discovering the answer mid-implementation.
6. **Concurrency/blast radius** — `deploy_release.sh` and `install.sh` both
   write `.env` files to hosts; either would need a one-line addition
   (`BOT_ENVIRONMENT=production`) to their respective provisioning steps,
   or every future deploy fails closed on a host that predates this change.
7. **Failure modes / fault tree** — see Phase 4 below; the mechanism closes
   some but not all instances of this bug class (see fault tree).

---

## Phase 4 — RCA Deep Dive

### 5 Whys

1. **Why** is the dev bot currently polling the real production game server
   with production channel IDs configured? — Because dev's `.env` sets
   `SSH_HOST=puran.hehe.si`/`SSH_ENABLED=true`, diverging from
   `.env.example`'s safe placeholder default.
2. **Why** does dev's `.env` diverge from the safe template? — Unknown from
   code alone; plausibly set up for real-data testing at some point and
   never reset, or dating from before dev/prod were operated as genuinely
   separate deployments.
3. **Why** did nothing catch this drift? — No code path anywhere checks
   whether `SSH_ENABLED=true` is *appropriate* for the host it's running on.
4. **Why** wasn't the one validation pattern that *does* exist
   (`resolve_trusted_hosts`) reused or generalized for this? — It lives in
   `website/backend/`, a codebase deliberately decoupled from `bot/`
   (PR #603); nothing currently bridges a pattern invented on one side to
   the other.
5. **Why** is there no shared way to bridge it? — **Root cause:** no
   first-class "what environment am I" concept exists anywhere in this
   system. Every component independently reinvents its own partial,
   inconsistent proxy for the same underlying fact (`SESSION_HTTPS_ONLY` on
   the website; nothing at all on the bot; unit-name probing in
   `health_check.sh`; hardcoded-to-prod scripts in `deploy_release.sh`), and
   none of them assert it explicitly or fail loudly when a proxy signal
   disagrees with reality.

### Ishikawa (fishbone)

- **People/process:** dev and prod were very likely configured at different
  times by different sessions/people, with no provisioning checklist
  enforcing dev-safe defaults as a gate.
- **Tools:** `.env` files are freeform text with zero schema validation
  beyond individual `int()`/`bool()` parsing per field — nothing validates
  *cross-field* consistency ("does this combination make sense for an
  environment") anywhere in this codebase.
- **Infrastructure:** dev and prod are separate hosts sharing one repo and
  one `.env.example` — safe defaults can drift silently the moment someone
  hand-edits a local `.env` for a legitimate short-term reason and never
  reverts it.
- **Architecture:** bot and website evolved as increasingly separate
  codebases (PR #603 decoupling), so a safety pattern invented in one
  doesn't propagate to the other by default.

### Fault tree — top event: "a dev process behaves like, or interferes with, production"

```
Dev process affects production
├── OR: dev bot polls production SSH source          [CONFIRMED, currently true]
│   ├── OR: .env copied/never reset                  [current apparent cause]
│   └── OR: no startup check catches the combination  [root cause — Phase 0]
├── OR: dev bot posts to production Discord channels  [structurally possible,
│                                                        not confirmed happening —
│                                                        see DISCORD_ROUTING_AUDIT §2]
├── OR: dev web session breaks on a prod-postured default
│   └── [CONFIRMED — dev_login_broken_https_only, 2026-08-05, independent incident]
└── OR: some future setting gets the same treatment
    └── [not preventable by fixing this one instance — see below]
```

**Important limit on what this fix actually buys:** an explicit
`BOT_ENVIRONMENT` variable, enforced only where it's wired in, prevents *this
specific* branch of the fault tree (the ones enumerated above) but does
**not** structurally prevent the general pattern from recurring for some
future setting nobody thought to gate. What it changes is that a *new*
config value can be written to check `environment.is_production` the same
way `TRUSTED_HOSTS` already checks `https_only` — turning "someone has to
remember" into "the pattern already exists to copy." That is a meaningfully
smaller guarantee than "this class of bug is now impossible," and should be
described to the owner as such rather than oversold.

---

## Open questions for the owner before Phase 5 (implementation)

1. **Shared module or two independent copies?** (Phase 1/3.5) — a real
   architectural fork given the recent bot/website decoupling. Recommend:
   two small independent implementations (~10 lines each), not a shared
   import, to stay consistent with PR #603's direction — but this is a
   judgment call, not a fact, and worth a second opinion.
2. ~~What breaks in the test suite~~ — **measured 2026-08-08**: ~8 files,
   one line each (see Phase 3, point 2 above). Smaller than initially
   feared; no longer a blocker for deciding whether to proceed.
3. **Retrofitting existing hosts** — dev's and prod's `.env` files both need
   the new variable added manually, once, outside of any script (or
   `deploy_release.sh`/`install.sh` need a step added). Who does this and
   when is an owner decision, not something to automate silently.
4. Given points 2-3 add real scope beyond "add one variable," is this still
   worth doing now, or does it make more sense to schedule as its own
   focused piece of work rather than folding into workstream A?
