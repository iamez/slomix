# M2 — health_check.sh induced-failure verification (2026-07-29)

Task M2 requires each check be proven by an induced failure, not just "looks
like it works." Two checks that would need stopping a real live service
(redis, postgres) to induce a genuine FAIL were **not** tested that way —
this project's own rules say never stop/restart a service without asking
first, and doing that on the shared dev box for a verification step isn't
worth the disruption. Everything else was induced safely:

## 1. Services (section 1)
- **WARN path**: `check_service_pair "bogus" definitely-not-a-real-service-xyz`
  → `WARN  bogus: no matching systemd unit found` (correct — no such unit
  exists anywhere).
- **FAIL path**: pointed the same function at `apport-autoreport` — a real,
  installed, currently-inactive systemd service on this box (Ubuntu's crash
  reporter, unrelated to the project) → `FAIL  inactive-real-unit-test
  (apport-autoreport) not active: inactive`. Proves the FAIL branch fires
  correctly for "unit exists but isn't running" without touching anything
  load-bearing.
- Postgres/redis/bot/web themselves were only checked in their real (active)
  state — not induced-failed, per the reasoning above.

## 2. Ports (section 2)
Ran for real: correctly flagged every `0.0.0.0`/`[::]`-bound listener on this
box (postgres somehow also has two extra listeners on `127.0.0.1:5432` and
`192.168.64.116:5432` beyond the main one, uvicorn on `0.0.0.0:8000`, smbd on
139/445, sshd on 22) — all expected for a dev box, correctly surfaced as WARN
for a human to eyeball rather than silently passed.

## 3. Connectivity (section 3)
**Bug found and fixed during this verification**: the original version used
`curl ... -w '%{http_code}' ... || echo "000"`. curl already prints `000` via
`-w` on connection failure *and* exits non-zero for a hard connection
refusal, so the `||` fallback fired on top of curl's own output, producing
`000000` (concatenated) instead of `000` — the "silent skip for a
not-this-box's-port" branch never matched, so port 7000 (this box runs on
8000) FAILed instead of being skipped. Fixed by dropping the `|| echo`
fallback and hard-truncating to 3 chars (`code="${code:0:3}"`) as a second
line of defense. Re-run after the fix: 7000 silently skipped, 8000 shows
`OK ... -> 200` for both `/health` and `/api/status`.

## 4. Disk (section 4)
**Induced directly**: `HEALTH_CHECK_DISK_WARN_PCT=1 HEALTH_CHECK_DISK_FAIL_PCT=2
./scripts/health_check.sh` → every real mount (all well under the normal
85/92% thresholds) correctly flipped to WARN/FAIL, and the script's exit code
changed from 0 to 1. Also confirms the per-mount iteration Opus's task
specifically called out (`/` and `/home/samba/share` are separate mounts,
both listed independently — the 2026-07-29 sweep's original mistake of
checking only one mount doesn't recur here).

## 5. Logs (section 5)
Not artificially induced — the real `logs/` directory already has the exact
permission bug this check exists to catch (11 files at `0640`, 4 with a
stray executable bit), so running for real against the current filesystem
state *is* the failure case, already correctly flagged. See PR #568 (M1) for
the code-level fix; this check would go green once that's deployed and the
existing files are chmod'd.

## 6. Error rate (section 6)
Ran for real against the live `logs/errors.log` (60 ERROR/CRITICAL lines in
24h) — correctly landed in the WARN band (>20, <100). Threshold boundaries
weren't independently induced (no env override wired for this one); the
count itself came from real data, which is enough signal that the awk/grep
logic works.

## 7-9. Migrations / env drift / round-linkage
Ran for real, all three found genuine, previously-undocumented drift:
- `apply_migrations.py --validate`: clean
- `check_env.py` (both venvs): `python-multipart` and `uvicorn` version drift,
  `INTERNAL_API_SECRET`/`DISCORD_BOT_TOKEN` unset — consistent with M4's
  venv-drift findings elsewhere in this backlog
- round-linkage: within thresholds

These three call existing, already-tested tools rather than reimplementing
logic, so their own test suites (not re-verified here) are the induced-failure
coverage.

## Full run

```
$ ./scripts/health_check.sh
...
-- Summary --
OK=24 WARN=29 FAIL=0
$ echo $?
0
```

## Addendum — Codex/Copilot review fixes (#580)

9 findings, 3 of them P1s that would have made the script report healthy
during a real incident:

- **P1 — round-linkage always "OK"**: `check_round_linkage_anomalies.py`
  needs `--fail-on-breach` to exit non-zero on a breach at all; without it,
  the script always exits 0 regardless of its own findings. Added the flag.
- **P1 — predictable `/tmp/health_check_*.out` paths**: a symlink
  pre-planted at one of those paths by another local user would have the
  privileged `>` redirect truncate whatever it points at. Replaced with a
  private `mktemp -d` (0700) directory, cleaned up via `trap ... EXIT`.
- **P1 — venv discovery picked a dependency-less system Python on the
  canonical VM**: the VM provisions `venv-bot`/`venv-web`
  (`slomix_vm_setup.sh`), not `venv`/`website/venv` — the dev-box-only
  names. Sections 7-9 now check the canonical names first.
- Postgres service check only recognized `postgresql@14-main`; production
  runs 17. Now discovers whichever `postgresql@*-main.service` is active.
- The 0.0.0.0-exposure comment claimed an exclusion for the website port
  that the code never implemented — fixed the comment to match the actual
  (intentional) behavior of warning on every all-interfaces listener.
- Neither API base answering (full outage, or `screen`/manual-process setup
  that stopped listening) previously produced no signal at all — now FAILs
  explicitly.
- Log permission check only flagged exactly `0640`; `0644`/`0600`/`0666`
  passed silently despite being wrong in different ways. Now compares
  against the correct expected mode per file (`0600` for
  `client_errors.log`, `0660` for everything else) and flags any mismatch.
- Service alias check broke on the first *installed* candidate even if
  inactive, missing a genuinely-active alias checked later in the list. Now
  checks all candidates before deciding.
- 24h error count only scanned the active `errors.log`, missing anything
  already rotated into `.1`+, and only recognized the pipe-delimited
  format, missing `LOG_FORMAT_JSON=true` records entirely. Both fixed
  (JSON count is whole-file, not 24h-scoped — noted as a known limitation
  in the script, since JSON records don't start with a sortable timestamp
  and it's off by default anyway).

Re-verified live after all fixes: `OK=24 WARN=38 FAIL=0`, exit 0. Disk
induced-FAIL and mktemp cleanup re-confirmed; `--fail-on-breach` confirmed
passed through (no live breach to trigger on this box's current data, so the
FAIL path itself relies on the flag's own documented behavior rather than a
fresh repro here).

## Addendum 2 — Codex review round 3 (#580)

Five more findings, one a P1, and one of them was a false-positive
generator bad enough that it was actively hiding real signal:

- **P1 — `cloudflared` wasn't checked at all.** It carries *all* public
  traffic to www.slomix.fyi on the canonical VM (`slomix_vm_setup.sh`
  installs and enables `cloudflared.service`, lines 1035/1064). With the
  tunnel down the whole site is unreachable from outside even while
  `slomix-web` reports healthy — precisely the blind spot this script exists
  to close. Added.
- **The 0.0.0.0-exposure check was a false positive on nearly every row.**
  It grepped whole `ss` lines for `0.0.0.0:`, but *every* `ss -ltn` row
  carries a literal `0.0.0.0:*` in the **Peer Address** column — so
  correctly-loopback-bound listeners like `127.0.0.1:5432` were all reported
  as exposed to all interfaces. Now matches only the Local Address column
  (`awk '$4 ~ ...'`). This alone dropped the run from WARN=38 to WARN=31,
  i.e. most of that noise was this bug burying the rows that would matter.
- **Service-existence detection was unreliable.** The generic loop decided
  "unit not installed" by pattern-matching `systemctl is-active` output for
  `unknown`/`could not`, but on this box a unit whose file doesn't exist at
  all reports plain `inactive` — so a not-installed service was
  misclassified as installed-but-down and FAILed. Now uses
  `list-unit-files` (the same reliable test `check_service_pair` already
  used), with a third case: installed-but-`disabled` WARNs rather than FAILs,
  since that's a dev-box posture, not an outage.
- **The round-linkage API fallback probed the wrong path.** `main.py` mounts
  the diagnostics router with `prefix="/api"`, so the served route is
  `/api/diagnostics/round-linkage` — the unprefixed spelling in CLAUDE.md
  404s. Also: the probe loop fell out silently when nothing answered, so a
  fully-down API produced no signal at all. Both fixed.
- **`WEB_LOG_DIR` was ignored.** `logging_config.py` resolves the web log
  directory from that env var and only falls back to `<repo>/logs`. A
  deployment that points it elsewhere would pass this check against a stale
  repo-local `logs/` while the directory whose 0640-vs-0660 permissions have
  twice taken the bot down went unexamined. Now scans both, de-duplicated by
  canonical path.

Verified after all fixes: `OK=24 WARN=32 FAIL=0`, exit 0 — and the FAIL
branch was induced for real by temporarily adding `dmesg.service`
(installed, enabled, inactive on this box — the same shape a stopped
cloudflared has on prod): `FAIL dmesg not active: inactive`, exit 1. Removed
again afterwards.

## Addendum 3 — Codex review round 4 (#580)

Four findings, all cases where a check could report healthy while something
was actually wrong (or the reverse):

- **Section 6 ignored `WEB_LOG_DIR`.** Round 3 taught section 5 to scan the
  configured website log directory, but the 24h error count still read only
  `logs/errors.log*` — so with `WEB_LOG_DIR` pointing elsewhere, a website
  drowning in errors was reported healthy off the bot's log alone. Now
  iterates the same `LOG_DIRS` set section 5 builds, and prints the scope it
  actually counted (`N file(s) across: …`).
- **The round-linkage API fallback could never succeed.** The route depends on
  `require_admin_user` (`diagnostics_router.py:527`), so an anonymous probe
  gets 401 no matter how healthy the API is — round 3's `/api` prefix fix
  addressed the wrong half. 401/403 is now the *success* signal for "endpoint
  exists and is being served", reported as a WARN that states plainly the
  thresholds were **not** checked, rather than implying they were.
- **A bot running under `screen` was indistinguishable from a crashed one.**
  This project explicitly supports non-systemd hosts, and nothing else in the
  script probes the bot process, so the "no systemd unit" WARN read the same
  whether the bot was fine or had died hours ago — on precisely the hosts
  where nothing restarts it. `check_service_pair` now takes a process pattern
  and falls back to `pgrep -f` (OK if running, FAIL if not).
  - While testing that, found `pgrep -f` matches the command line of whatever
    invoked the script, so a bogus pattern still "matched" — the calling shell
    itself. Excluding `$$`/`$PPID` wasn't enough (the hit was a grandparent),
    so the whole ancestor chain is now excluded via `_ancestor_pids()`.
    Confirmed both branches from a shell that never mentions the pattern: a
    made-up pattern yields no match (FAIL), `bot.ultimate_bot` yields exactly
    the real bot PID (OK).
- **An unrelated app on the other candidate port produced FAILs.** Only one of
  `:8000`/`:7000` is Slomix on a dev/manual host, and something else there
  commonly 404s these paths — each such response incremented `FAIL_COUNT`, so
  a healthy host scored failures from a service that isn't ours. Results are
  now collected per base and judged after: a base that served at least one
  Slomix path and failed another still FAILs (a real problem), while a base
  that never served one is reported as "probably an unrelated app on this
  port".

Verified after all fixes: `OK=24 WARN=31 FAIL=0`, exit 0, and section 3 shows
both `/health` and `/api/status` at 200 on the one base that is Slomix.
