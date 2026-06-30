# Dual-frontend + React build/deploy — researched plan (2026-06-29)

**Decision (owner):** delete nothing — everything is kept; archive only if needed.
Fix the *deploy* so the React side is always built (no "Modern Route Offline"),
and research the right/professional way so nothing that works gets turned off.

---

## 1. How it actually works today (verified on main `d576a2d`)

- **Pattern = strangler-fig.** `website/js/route-registry.js` routes each of the 29
  views to either `VIEW_MODE.LEGACY` (25 routes, plain JS) or `VIEW_MODE.MODERN`
  (4 routes: `proximity-player`, `proximity-replay`, `proximity-teams`,
  `skill-rating`). This per-route switch IS the professional incremental-migration
  pattern (Fowler / MS Azure) — the architecture is sound, not the problem.
- **React = a Vite *library* build.** `website/frontend/vite.config.ts` builds a
  single ES entry `src/route-host.tsx` → `website/static/modern/route-host.js`
  (+ `route-host.css`, `chunks/`). 25 `.tsx` pages, ~13.6k LOC; only the 4 MODERN
  routes are actually mounted, the other ~21 pages are built-but-not-routed.
- **The loader.** `website/js/modern-route-host.js` dynamically
  `import('/static/modern/route-host.js?v=BUILD_VERSION')`. The 4 MODERN routes
  have `load: () => undefined` — i.e. **no legacy fallback**, they depend entirely
  on that build existing.
- **Root cause of "Modern Route Offline":**
  1. `website/static/modern/` is **gitignored** (`.gitignore:49`) — never committed.
  2. **No deploy/install script builds it** (`grep` across `*.sh`/`scripts/*.sh`
     for `npm/vite build`/`static/modern` → nothing). So unless someone manually
     runs the Vite build on the server, the 4 routes 404 → "Offline".
  3. `BUILD_VERSION = '20260323-skill-rating-v1'` is a **hand-edited** cache-bust
     string → same stale-`?v=` drift class as the Cloudflare incident in memory.

So: the *pattern* is fine; the **build is gitignored + never produced by deploy +
manually cache-busted**. That trio is the fragility.

## 2. What professionals do (web research, sourced)

- **Build in CI/deploy; don't commit `dist`.** Vite's own deploy guide and the
  2025 consensus: run `npm ci && npm run build` in the pipeline, keep generated
  output out of git. (Committing dist is the quick hack, not the norm.)
- **Strangler-fig is the right coexistence model** — route a few features to the
  new stack, keep the rest legacy, migrate incrementally; users never notice.
  Slomix already does this per-route. Keep it.
- **Cache-bust by content hash + manifest, not a manual version string.** A
  `[contenthash]` in the filename (or an emitted `manifest.json` the loader reads)
  means the URL changes only when content changes → no stale cache, no missing-
  asset mismatch. Manual `?v=` strings rot.
- **Atomic deploy.** Build into a fresh dir, verify it, then swap (symlink/rename)
  in one step — never serve a half-written build dir. Prevents the partial-deploy
  "Offline"/missing-module class (the 2026-06-25 incident).

## 3. Recommended implementation — staged, nothing breaks

Order matters: each step is independently safe and verifiable.

### Step A — make deploy build React (fixes "Offline"; owner picked this)
Add a frontend-build step to the deploy path (`scripts/deploy_release.sh` and/or
`install.sh`), not a one-off:
```
( cd website/frontend && npm ci && npm run build )   # → website/static/modern/
```
- Guard on Node availability (the build needs Node ≥20.20 per package.json engines).
- **Build-verify before going live:** assert `website/static/modern/route-host.js`
  exists and is non-trivial (> a few hundred bytes) *before* the deploy swaps the
  served dir; if the build fails, **keep the previous build** (atomic — don't
  replace a working modern dir with a broken/empty one).
- Result: the 4 MODERN routes are always present after a deploy.

### Step B — automate cache-busting (kills stale `?v=` drift)
Replace the hand-edited `BUILD_VERSION` with a value derived from the build:
- simplest: have the build write `website/static/modern/version.txt` (timestamp or
  `git rev-parse --short HEAD`), and `modern-route-host.js` fetches it once and uses
  it as the `?v=` — so every deploy auto-busts; **or**
- stronger: emit a tiny `manifest.json` and load the hashed entry name from it
  (full content-hash approach). Step B-simple is enough for this scale.

### Step C — graceful fallback instead of an error panel (resilience)
If the modern build is ever genuinely missing, degrade to a legacy view where one
exists rather than showing "Offline":
- `proximity-replay` → `replay.js` exists; `proximity-player` → `player-profile.js`
  already renders aim/hit-region/heatmap; `proximity-teams` → `proximity.js`.
- `skill-rating` has no full legacy page → keep a friendly "building…" panel for
  just that one. This removes the scary error for 3 of 4 routes.
(Optional, do after A; A alone removes the trigger.)

### Step D — archive, don't delete, the ~21 unreached React pages
Keep everything (owner: "vse rabimo"). Just make their status explicit so they're
not mistaken for dead code and don't silently drift:
- add `website/frontend/src/pages/README.md` listing which pages are **routed**
  (4) vs **dormant/archived** (the rest), or move the unrouted ones under
  `src/pages/_archive/` (still built? no — keep them OUT of the route-host import
  graph so they don't bloat the bundle, but kept in-repo for future routing).
- Nothing is removed from git history; everything stays recoverable and re-routable.

## 3b. Integration with the real deploy (`scripts/deploy_release.sh`) — verified
- The deploy host **has Node 20.20.0 + npm 11.17.0** (meets `engines` ≥20.20) →
  build-on-server is viable; no need to commit dist.
- The current `website/static/modern/` build is from **Mar 31** (~3 months stale),
  confirming it's rebuilt by hand, rarely.
- `deploy_release.sh` already does git-checkout deploy + a **clean-tree guard**
  that allow-lists only `website/index.html` + `website/js/*.js`, and an existing
  **auto cache-bust** step that `sed`-rewrites `?v=…` → `?v=$SHA` on those files.
  So **legacy cache-busting is already automated by git SHA.** Two implications:
  1. `static/modern/` is gitignored, so `git checkout -f` won't clobber it and it
     won't trip the clean-tree guard — a deploy-built modern dir is safe to add.
  2. `modern-route-host.js` uses `?v=${BUILD_VERSION}` (a JS const), which the
     `?v=[A-Za-z0-9._-]+` sed does **not** match → the modern entry never gets the
     `$SHA` bump. Fix: make the modern `?v=` use `$SHA` too — either have the build
     write `static/modern/version.txt=$SHA` and the loader read it, or extend the
     deploy to set `BUILD_VERSION` to `$SHA`. This folds the modern side into the
     same proven SHA cache-bust the legacy side already uses.

So Step A is literally: add `(cd website/frontend && npm ci && npm run build)` +
a presence check to `deploy_release.sh` (and `install.sh` for fresh installs),
and Step B reuses the existing `$SHA` so cache-busting is uniform.

## 4. Why not the alternatives
- **Commit the dist** — works, but fights the 2025 norm, bloats git with binaries,
  and still needs cache-bust discipline. Use only as a stop-gap if Node isn't on
  the deploy host.
- **Rebuild the 4 routes in legacy + delete React** — most "legacy=canonical", but
  it's real rewrite work (skill-rating leaderboard has no legacy twin) and the
  owner wants nothing deleted. Rejected.

## 5. Verification (so nothing that works goes dark)
- After Step A: on a clean checkout, run the deploy build → assert
  `static/modern/route-host.js` present; load each of the 4 MODERN routes → no
  "Offline"; load a few LEGACY routes → unchanged.
- Keep the previous `static/modern/` as `static/modern.prev/` during a deploy;
  roll back by swapping if the new build fails verification.
- No DB/migration involved; no bot impact; legacy routes untouched throughout.

## Sources
- Vite — Deploying a Static Site: https://vite.dev/guide/static-deploy
- Vite — Building for Production: https://vite.dev/guide/build
- Martin Fowler — Strangler Fig: https://martinfowler.com/bliki/StranglerFigApplication.html
- MS Azure Architecture — Strangler Fig: https://learn.microsoft.com/en-us/azure/architecture/patterns/strangler-fig
- Cache busting via content hash: https://www.alainschlesser.com/thinking/bust-cache-content-hash/
- Atomic deployments without tears: https://nystudio107.com/blog/executing-atomic-deployments
