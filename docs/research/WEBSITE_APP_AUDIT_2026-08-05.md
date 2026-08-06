# Slomix browser audit — 2026-08-05

Every route, four viewports, anonymous **and signed in**. 232 checks, driven by
`scripts/audit_website_browser.mjs` (committed, so the next pass is a diff).

This is the first audit of this app that could actually open a browser: Chromium
was installed on the dev box today. It is also the first that could see the
signed-in surfaces, because the owner could not log in until this morning —
see *The blocker* below.

**Baseline:** `main` at the time of the run, with PRs #604–#607 open and NOT
included. Findings are marked accordingly so nothing already solved competes for
attention.

---

## The blocker that came first

The owner reported, in passing, that Discord login failed. It was two problems
stacked, and either alone would have kept them out:

1. **Server.** `SESSION_HTTPS_ONLY` defaults to `true` (`main.py:118`) and was set
   in neither env file, so the session cookie carried `secure`. The dev box
   serves plain HTTP, so the browser discarded it — taking `oauth_state` and the
   PKCE verifier with it. `auth.py:381-393` then rejected every callback.
   `security_utils.py:345` documents the intent: *"dev opts out for local HTTP"*.
   This box never had. Fixed in `website/.env`.

   Proof, from `logs/web.log`:
   ```
   before  OAuth callback rejected: valid=False expired=True  verifier=False  (400)
   after   OAuth callback rejected: valid=False expired=False verifier=True
   ```
   `verifier=True` is the session surviving; `valid=False` only because the test
   sent a deliberately wrong `state`.

2. **Browser.** Firefox was upgrading to HTTPS (`SSL_ERROR_RX_RECORD_TOO_LONG`).
   Not the server's doing — it sends no HSTS and speaks no TLS on 8000. No code
   change can fix this one; the owner allowed plain HTTP for the host.

Nobody caught this because agents test with `curl`, which does not care about
cookie flags, and the owner had no way to tell a config problem from a broken
feature.

---

## Part A — technical findings

### A1. Record Book renders 18 `[object Object]` — fixed in #607

Confirmed on `main`: 18 occurrences on both `#/record-book` and its `#/records`
alias, all inside `<option>` of `#records-map-filter`. `/api/stats/maps` returns
objects and the filter interpolated them whole.

Not cosmetic: the option `value` was `[object Object]` too, so choosing a map
filtered by that literal string and matched nothing. **The map filter has never
worked.**

### A2. A panel that never loads — NEW

`#/profile/<guid>` shows **"Loading achievements…" forever** — verified at 2s, 5s
and 10s on every profile.

`profile-achievements-unlocked` exists only as static markup in
`index.html:4680`. **No JavaScript anywhere references that id.** It is a
placeholder that was never wired up.

Checked systematically: of 36 elements in `index.html` carrying a "Loading"
placeholder, this is the **only** one no code ever touches. So it is a single
forgotten panel, not a pattern.

### A3. Three finished pages nobody can reach — NEW

`#/maps`, `#/weapons` and `#/awards` are complete, working pages with **zero**
navigation entries — not in the nav bar, and no `navigateTo('maps'|'weapons'|
'awards')` anywhere in HTML, JS or TSX. They are reachable only by typing the URL.

The nav offers 14 destinations; the registry defines 30. Most of the gap is
legitimate (detail pages opened by clicking a row, the `records` alias, the
`hall-of-fame` tab). These three are not.

Worth noting against our own recent work: #598 fixed the `HS` mislabel on the
Weapons page — a page users cannot click to.

### A4. Signed-in session-detail never settles — NEW, mechanism partly proven

On a multi-session date (`2026-08-04`), `#/session-detail`:

| | to network idle |
|---|---|
| anonymous | 3.0 s, OK |
| **signed in** | **35 s, timeout** |

Traced to two requests. Both return 409 in ~8 ms — that part is correct and
deliberate (see A5) — but the lifecycle differs:

```
anonymous   /api/storytelling/moments     req → resp409 → finished
signed in   /api/storytelling/moments     req → resp409            (never finished)
```

Same for `best-lives`. The response arrives and the request never completes, so
the connection lingers. Browsers cap connections per host at ~6.

Suspect: `fetchJSON` throws on `!res.ok` **without reading the body**
(`utils.js`), leaving the stream unconsumed. That helper is shared by everything,
so the same shape applies to any non-OK response.

**Not proven:** why it only manifests when signed in, and whether a user ever
notices. What *is* reproducible is the 3 s vs 35 s difference. Network idle is a
test concept; the page does render. Treat this as a lead with solid evidence, not
a confirmed user-facing defect.

### A5. Two endpoints disagree about what an ambiguous date means — NEW

`/api/storytelling/*` answers honestly and well:

```json
409 {"code":"AMBIGUOUS_SESSION_DATE",
     "message":"2026-08-04 has 2 gaming sessions — specify gaming_session_id.",
     "candidates":[{"gaming_session_id":143, ...}]}
```

`/api/sessions/{date}` **silently merges** the sessions instead and returns no
identifier at all. Two answers to the same question, and the frontend swallows
the 409 (`session-detail.js:581`, `:703` both say so in comments), so the user
just sees panels that do not appear.

#605 adds `gaming_session_ids` to the sessions payload, which is the right
direction — but it does not yet pass `gaming_session_id` **through** to the
storytelling calls, which is what would stop the 409 entirely. Worth folding in.

### A6. Phone-width overflow — NEW

| viewport | routes overflowing |
|---|---|
| 1920×1080 | none |
| 1366×768 | none |
| **768×1024** | **none** — #598's fix confirmed visually for the first time |
| 390×844 | `story` **+164 px**, `profile` **+23 px** |

The master review reported 390×844 as clean; it did not test `story` or a
profile at that width.

### A7. Greatshot: a main-nav button into a wall — known, still untouched

`link-greatshot` sits in the top-level public nav (`index.html:1331`) while
`/api/greatshot`, `/greatshot/demos` and `/greatshot/topshots` all return 401 to
anonymous visitors. This is the one item from
`WEBSITE_REVIEW_STATUS_2026-08-04.md` that no PR has addressed.

### A8. Accessibility

21 inputs without any label, `aria-label` or `placeholder`. Images and control
names came back clean; no duplicate ids.

### A9. Three CDNs on every page load

`cdn.tailwindcss.com` (which prints its own "should not be used in production"
warning on **every route** — that is the one console message the audit sees
everywhere), `unpkg.com` for Lucide, `cdn.jsdelivr.net` for Chart.js.

Tailwind compiles CSS in the browser on each load. For something people keep
open, every visit depends on three third-party hosts.

### What I got wrong, and corrected

Recorded because the wrong version is the memorable one:

- **The 429 storm was mine.** 232 back-to-back page loads tripped the global
  limiter (`rate_limit_middleware.py`, 180 req/60 s). Not a site defect.
- **"3.2 page loads per minute"** — wrong. I counted every request; the limiter
  counts only `/api/` and `/auth/` (`:251`). Honest figures per load:
  `sessions2` 4 API calls, `record-book` 5, `session-detail` 8, `profile` 15,
  `home` 20, `proximity` **54**. Against the standard 180 budget that is 9–45
  loads/min, and proximity has its own 450 bucket. **The limits are reasonably
  tuned.** Proximity's 54 API calls and 108 total requests per load is the real
  outlier.
- **The instrument was wrong twice**, and the self-test caught both. It flagged
  `#/profile` as dead while the page rendered 1,579 characters (unanchored
  regex), and it reported **0** `[object Object]` on Record Book where there are
  18 — `<option>` has no `offsetParent`, so the visibility filter skipped exactly
  where the bug lives. Both fixed before any result here was believed.

---

## Part B — the application lens

The owner's framing, which changes what "good" means:

> mi nismo spletna stran, mi smo aplikacija / operacijski sistem za naš community

A site is judged on the visit. A tool is judged on the second week.

**Can a returning user get where they are going in one action?** Nearly. `CTRL+K`
now focuses search (#606) — before that the badge was decoration. But search is
the *only* keyboard path, and it only finds players. There is no way to jump to
"last night's session" or a map without navigating there.

**Does the shell hold state?** No. Every route starts from nothing: no last
session, no "you were looking at", no unread marker. `_homeLoaded` is the only
persistence in the app and it lasts one page load. For a tool used several times
a week, that is the largest gap — and it is not a bug in any single route, which
is why no per-route audit has ever found it.

**What does the second visit look like?** Identical to the first. Nothing says
what changed since you last looked — no "3 sessions since your last visit", no
diff on your own rating. The data to answer that exists; nothing asks it.

**Density before answers.** The session page still leads with the trust block,
Good Night score, verdict strip, moments, objective pressure and life cards
before the tabs. The master review's storyboard proposal (PR 2 in its sequence)
is unstarted.

**Reachability as a product problem.** A3 is not really three bugs; it is the
absence of anyone owning "what is in the nav". Three finished pages sit outside
it, 21 React pages are dormant behind 4 live MODERN routes, and two session-list
surfaces exist where the older one (`sessions`, 2,360 lines) has no entry point.

### Benchmarks worth borrowing from, as applications

The master review covered stats sites (Leetify, Scope.gg, gibhub.gg). For a shell
people live in, the useful comparisons are different:

- **Discord** — a persistent shell with unread state. The one idea worth stealing
  is *what changed since you last looked*, per surface.
- **Linear** — the command palette as the primary navigation, not a search box.
  `CTRL+K` exists here; it could address routes, sessions and maps, not just
  players.
- **Steam** — the library as home. Slomix's home is a marketing hero; for a
  returning user it could be "your last session, your form, what's on tonight".

Explicitly **not** borrowed: their density. Slomix's depth is its advantage; the
argument is about sequencing, not removal.

---

## Limits of this pass

- Anonymous plus an owner session minted from `SESSION_SECRET` (the method
  `tests/security/test_real_stack_security.py` already uses). A real Discord
  OAuth round-trip was not automated.
- Dev data, dev box. Production may differ in volume and in timing.
- No fixes made. Findings only, by agreement.
- The four proximity contract items from the master review are untouched — Codex
  is working in that area.

## Reproducing

```bash
node scripts/audit_website_browser.mjs --out /tmp/slomix-audit
```

Results land as `results.json` plus JPEG screenshots. Two consecutive runs on an
unchanged tree should differ only in timings.
