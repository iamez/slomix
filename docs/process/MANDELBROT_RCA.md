# The working loop: Mandelbrot zoom + root-cause analysis

Every task in this repository — a feature slice, a bug, a review finding —
runs through the same six phases. The name comes from the audit framework
we adopted in 2026 (Mandelbrot RCA v2.0): zoom in until the picture stops
changing, and never fix what you have not first explained. The phases are
short; skipping one is how the same bug has been "fixed" three times here.

## 0. Discovery — what exists, who reads it

- Find every writer and every reader of the thing you are about to touch
  (`git grep`, the parity keymap, `docs/api/openapi.json`, the DB views).
- Check that it is not already built: `git ls-tree -r origin/main <path>`,
  `git log HEAD..origin/main`, open PRs. A squash-merged branch shows no diff.
- Read the entry for the area in `docs/BACKLOG.md` and `docs/KNOWN_ISSUES.md`.

## 1. Dependency map — follow the field to its writer

- For every number: who **writes** it, on what clock, with what unit. Not who
  displays it, not whose reputation says it is right. Two fields with one name
  are usually two measurements (`time_played` from Lua vs import; three
  assist counters; two "live" clocks).
- Discriminate across the **corpus**, not one sample: a rule that looks right
  on one session hides the short form that crashes on the next.

## 2. Contract — inputs, outputs, states

- Write the contract before the fix: preconditions, postconditions,
  invariants. Name the three absent states (`no_data` / `unavailable` /
  `loading`) and what each filter excludes.
- A schema is not the arbiter: it lies in both directions. Type from the
  union of observed shapes.

## 3. Zoom — the 12-point checklist

1 correctness · 2 edge cases (midnight crossover, name change, empty set,
`nan`, one-element tuple) · 3 security (no credentials, no injection, the
allowlist not the denylist) · 4 error masking (a silent `except` in the
critical path, a 200 with an empty body on DB outage) · 5 performance (cold
vs warm; the second call is not a measurement) · 6 types · 7 imports (no
cross-imports between bot and website) · 8 patterns (the repo's, not the
language's) · 9 concurrency (queues, TTLs, two processes and one cache) ·
10 contract compliance · 11 duplication (the same fix needed in a second
place — search for every occurrence of the class, not the one that led you
there) · 12 failure modes (fault tree: what happens when the DB, the SSH
poll, the Lua tracker, or Discord is down).

Zoom rules learned the hard way:
- A fix that stops one line too early: look at neighbouring fields and the
  other branch of the same `if`.
- A join on a window is an assumption about cardinality — measure it.
- Time invariance is a boundary property: a list that grows with `t` is a
  timeline, whatever it is called.
- A guard shaped like the last leak catches only the last leak.

## 4. Root cause — five whys, Ishikawa, fault tree

- Ask why until the answer is a mechanism, not a person. Record the chain.
- Ishikawa across: data (what was written), code (what read it), config
  (which `.env` won), process (which agent did what when), environment (which
  server was actually running, `ActiveEnterTimestamp`).
- Two wrongs cancelling in a median is a root cause with two branches; fix
  both or neither.

## 5. Fix + verify — proofs, not promises

- Contract test for the invariant; canary query against the corpus.
- **Mutation**: break the guard on purpose, watch the test fail, restore, `cmp`.
  A mutation that did not execute reports "holds".
- Runtime proof: the endpoint, the page, the log line — from a server that is
  newer than the code (`ps -o lstart=` vs `git log -1 -- <handler>`).
- Measure twice by two paths; give the denominator with every ratio.
- Review by measurement: run it across the corpus, verify by a second path.

## 6. Record

- `docs/PLAN.md` (plan of record), `docs/BACKLOG.md` (position, detours),
  `docs/AGENT_LOG.md` (one durable lesson per entry), the PR body (proofs).
- A negative result is a result. Write down what the mechanism cannot do.

## Quality ratchets (from v2.0 — floors, not goals)

hard-coded credentials = 0 · silent exceptions in the critical path = 0 ·
`print()` in routers = 0 · files > 1 500 lines: do not add one · cross-imports
bot ↔ website = 0 · coverage does not go down. The ratchet files under
`tests/data/` are the same idea for the new site: numbers move in one
direction and every move carries its reason in the file.
