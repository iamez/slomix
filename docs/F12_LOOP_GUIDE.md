# The F12 loop — correlating a browser error to server logs and code

Task W9 from a session working-doc (`docs/TASKS_FOR_SONNET_2026-07-29.md` — not tracked in
this repo, not a citable source; every claim below is checked against tracked code directly).
The owner's usual workflow is: open a page, hit F12, paste whatever the console/network tab
shows. This guide is what to do with that paste — how to find the request in the logs, what
each log file actually holds, and how to land on the file that served the broken route.

## What a paste should always carry

**The failing request's METHOD and URL, the page's address-bar URL (including its `#/hash`),
and the timestamp — and note the timestamp's timezone.** All four matter:

- **Method + URL** drive Steps 1-2. The method isn't optional: the same mounted path can carry
  different handlers per method — `GET /api/challenges` and `POST /api/challenges` are separate
  functions (`challenges_router.py:51,63`) — so a URL alone can't identify which one failed, and
  Step 4 can't replay a non-GET without knowing to send one (Codex review on #576). DevTools'
  Network tab shows it in the request's Method column.
- **The page hash** is what Step 3's frontend lookup is keyed on; it can't be derived from an
  `/api/...` request path, and shared endpoints are called from several pages.
- **The timestamp** is what everything else greps on. Browser devtools show the client's local time; the backend's default
plain-text formatter (`StandardFormatter`, `logging_config.py:176`) writes the **backend
host's** local time (naive, no offset); the optional JSON formatter (off by default,
`LOG_FORMAT_JSON` unset) writes UTC instead. If the browser and backend host are in different
timezones, searching the pasted timestamp literally can miss the entry entirely — convert
first, or search a wider window (`grep` a few minutes on either side) if the timezone isn't
known.

## Step 1 — find the request in `logs/access.log`

Format (from `website/backend/middleware/logging_middleware.py`):

```
TIMESTAMP | LEVEL | access | dispatch:LINENO | → METHOD /path                       (request)
TIMESTAMP | LEVEL | access | dispatch:LINENO | ← METHOD /path → STATUS (Xms)         (response)
```

Search by path and the timestamp from the paste. The separator differs by formatter — the
default plain-text `StandardFormatter` writes `2026-07-29 14:20:...` (space), but the optional
JSON formatter (`LOG_FORMAT_JSON=true`) writes ISO-8601 (`2026-07-29T14:20:...`, `T` separator)
— a space-separated grep against a JSON-formatted log matches nothing even though the record is
there:

**First, find out WHERE the logs are.** `logging_config.py:27-29` resolves every website file
handler under `WEB_LOG_DIR` when that variable is set, falling back to the repo's `logs/` only
when it isn't — so on a deployment that sets it, every command in this guide would grep an
empty or stale default directory and report no evidence (Codex review on #576):

```bash
LOGDIR="${WEB_LOG_DIR:-$(grep -E '^\s*WEB_LOG_DIR=' website/.env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d "\"' ")}"
# A RELATIVE value resolves against the server's working directory, not yours.
# logging_config.py does Path(os.getenv("WEB_LOG_DIR", …)).resolve(), and the
# documented startup is `cd website && … uvicorn`, so WEB_LOG_DIR=logs means
# website/logs — while this shell (at the repo root) would read ./logs, a
# different directory (Codex review on #576).
case "$LOGDIR" in
  "")   LOGDIR="logs" ;;                 # unset -> logging_config's own default
  /*)   ;;                               # absolute -> use as-is
  *)    LOGDIR="website/$LOGDIR" ;;      # relative -> resolved from website/
esac
echo "using: $LOGDIR"
```

Substitute `$LOGDIR` for `logs` in every command below (this guide writes `logs/` for
readability, since that's the default).

Search the rotated backups too, not just the active file: `LOG_FILES["access"]` keeps 7
(`access.log.1`–`.7`), so anything more than a few hours old on a busy day may well have moved
out of `access.log` while the evidence is still perfectly well retained. `grep` the glob:

```bash
# StandardFormatter (default)
grep -F "/api/proximity/prox-scores" logs/access.log logs/access.log.* 2>/dev/null | grep "2026-07-29 14:2"

# JSON formatter (LOG_FORMAT_JSON=true) — note the "T", and the path is inside a JSON string
# field rather than free text, so grep -F on the path still works but the timestamp grep needs
# the ISO form
grep -F "/api/proximity/prox-scores" logs/access.log logs/access.log.* 2>/dev/null | grep "2026-07-29T14:2"
```

**Decode the path before grepping it.** DevTools shows the URL as sent —
percent-encoded — while `routed_path()` logs the *decoded* ASGI
`scope["path"]`. `client.ts` puts player names through `encodeURIComponent()`,
so a name with a space or `#` appears as `/api/stats/player/Bob%20Smith` in the
paste and as `/api/stats/player/Bob Smith` in the log, and a literal grep finds
nothing (Codex review on #576):

```bash
python3 -c 'import sys,urllib.parse; print(urllib.parse.unquote(sys.argv[1]))' \
  '/api/stats/player/Bob%20Smith'
# -> /api/stats/player/Bob Smith   <- grep for THIS
```

Only conclude "no access record exists" after the glob comes back empty.

**This pairing doesn't cover every request.** `QUIET_PATHS`
(`logging_middleware.py:33-40` — `/health`, `/favicon.ico`, `/static`, `/js/`, `/css/`,
`/assets/`) never get a `→` line, and get a `←` line only when they **fail** (`is_quiet and
status_code < 400` is suppressed entirely). So a runtime error from a successfully-served
script has **no access.log entry at all**, and a failed asset request has only the response
half, not a pair. If the failing resource is under one of those paths, don't expect to find it
here.

**Known gap — no query string.** The `→`/`←` lines never include the query string
(`routed_path()` in `security_utils.py` deliberately logs only `request.scope["path"]`).

**If `LOG_FORMAT_JSON=true`, the request ID narrows the search a lot — but it is not a
guaranteed unique key, and it does not reach tracebacks.** The middleware generates
`str(uuid.uuid4())[:8]` — an **8-character UUID4 prefix, not a full UUID** — and returns it as
the `X-Request-ID` response header, visible in the browser's Network tab. `JSONFormatter`
includes `request_id` in its allowlisted extras (`logging_config.py:153`), so in that
configuration both access entries carry it:

```bash
grep -F '"request_id": "a1b2c3d4"' logs/access.log logs/access.log.* logs/errors.log 2>/dev/null
```

Two limits to keep in mind, both from Codex review on #576:

- **It's 32 bits, so collisions are real.** By the birthday bound, retained logs containing
  ~77,000 requests have roughly a 50% chance of some duplicated prefix. If the grep returns
  more than one request's worth of lines, fall back to the timestamp to pick the right one —
  don't assume a single match.
- **The traceback usually won't carry it.** Handled failures log via bare
  `logger.exception("…")` with no `extra={"request_id": …}` — e.g.
  `proximity_player.py:118,342`, the very endpoint this guide's worked example uses. So the ID
  joins the *access* records to each other, not the access record to its traceback; for that
  hop you still correlate by timestamp (Step 2).

Timestamp matching is also the fallback for the two cases where the ID isn't available at all:

- **Plain-text formatter (the default).** `StandardFormatter`'s format string has no
  `%(request_id)s` placeholder, so the ID never reaches the log text even though the header
  exists.
- **Unhandled exceptions**, regardless of formatter. The middleware's `finally` block only sets
  the header `if response:` (`logging_middleware.py:151-152`), and an unhandled exception leaves
  `response` as `None` — so the primary 500 scenario this guide exists for may have no header to
  copy in the first place.

In those cases, matching a `→` line to its `←` line is by nearest path+timestamp, not a hard
join.

**Don't rely on `access.log` being pure access traffic.** Because
`website/backend/logging_config.py` attaches all 5 file handlers to the root logger with no
per-handler logger-name filter, every INFO+ message from *any* logger in the process — not
just the `access` logger — lands in `access.log` too. Expect to see `bot.services.*`,
`bot.core.*`, and `api.*` lines interleaved with the `→`/`←` pairs; that's normal, not a sign
something's misconfigured.

## Step 2 — find the traceback in `logs/errors.log`

```bash
# active file (StandardFormatter — default; use "2026-07-29T14:2" instead if
# LOG_FORMAT_JSON=true, same separator difference as Step 1)
grep -B2 -A40 "2026-07-29 14:2" logs/errors.log
# rotated backups too — RotatingFileHandler keeps 10 (errors.log.1 .. .10);
# a traceback that rotated out of the active file may still be in one of these
grep -B2 -A40 "2026-07-29 14:2" logs/errors.log.* 2>/dev/null
```

`errors.log` receives **ERROR and above only** (`LOG_FILES["error"]["level"]` is
`logging.ERROR`, not `WARNING` — a plain warning won't be here at all; check `logs/web.log`
for those). `-A40` rather than a smaller number: a traceback through the Starlette/FastAPI
middleware stack commonly runs past 20 lines, and a truncated grep can cut off the exception
type and root-cause message at the bottom — the most diagnostic part.

Rotation isn't the only reason a traceback might be missing, either: several 500 paths raise
`HTTPException` directly without logging an exception at all, and some handlers call
`logger.error(...)` without `exc_info=`, writing only a one-line message with no stack. Check
for **any** line at the right timestamp before concluding rotation ate it — an absent
traceback sometimes means the code path never emitted one in the first place, not that it aged
out (see W1, which hit the rotation case for 6 of 7 historical 500s, but don't assume that's
always why).

## Step 3 — find the file that served the route

- **Backend** (which handler served `/api/...`): the checked-in route is a **decorator with
  the parameter name**, not the literal value from the paste — e.g.
  `/proximity/player/{guid}/radar`, not `/proximity/player/FB0EC8.../radar`. Grepping the
  literal path from the log won't find it; normalize the dynamic segment first (strip the GUID/
  ID back to `{param}` or just grep the stable prefix, e.g. `/proximity/player/`). Search **all
  of `website/backend/`, not just `routers/`** — not every `/api/...` endpoint lives in a router
  module, e.g. `/api/build` is declared straight on the app in `main.py:348` (Codex review on
  #576):
  ```bash
  grep -rn '"/proximity/player/' website/backend/ --include='*.py'
  ```
  Router prefixes are documented in `website/backend/CLAUDE.md`; remember `/api` is mounted
  separately from the router's own path.
- **Frontend** (which JS/TSX rendered the page): this lookup is keyed by the **page's hash
  route**, which is *not* derivable from the failing request URL — a Network-tab failure is
  normally an `/api/...` path, and shared endpoints like `/api/search` are called from several
  pages. So the paste has to include the address-bar URL (e.g. `.../#/proximity`) as well as the
  failing request; without it, this step can't be completed for a shared endpoint (Codex review
  on #576). With the hash in hand, look it up in `docs/ROUTE_MAP_2026-07.md` (generated by
  `scripts/generate_route_map.mjs` from `website/js/route-registry.js`, the actual routing source
  of truth — added alongside this guide) to get "React" or "Legacy JS" plus the exact serving
  file. Re-run the generator if the route map looks stale; don't hand-edit it.

## Step 4 — reproduce

`backend.main` refuses to import without certain env vars — it's not enough to have the runbook's
listed variables, because that list omits some of these. `main.py:138-148` raises
`ValueError` on an empty (or placeholder) `INTERNAL_API_SECRET` at import time, and the same
module gates `SESSION_SECRET`, with `TRUSTED_HOSTS` required under the production
(`SESSION_HTTPS_ONLY=true`) posture. Without them Uvicorn never reaches readiness and Terminal B
has nothing to talk to (Codex review on #576). Easiest is to use the existing `.env` the services
already read; otherwise export them for the shell:

```bash
# Terminal A — env first. A website/.env copied from the tracked .env.example does NOT
# satisfy this: that file ships `INTERNAL_API_SECRET=` (empty) and
# `SESSION_SECRET=change-this-to-a-secure-random-string-in-production`, and main.py
# rejects BOTH the empty value and that exact placeholder. So check the VALUES, not
# just that the keys exist — a `grep -c` presence test would say 1 and be wrong
# (Codex review on #576):
# Reports only whether each value is usable — never prints the value itself, so
# this is safe to run in a recorded or shared terminal (Codex review on #576):
for k in SESSION_SECRET INTERNAL_API_SECRET; do
  v=$(grep -E "^\s*$k=" website/.env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d "\"' ")
  case "$v" in
    "")                 echo "$k: EMPTY — must be set" ;;
    change-this-*|super-secret-*) echo "$k: PLACEHOLDER — must be replaced" ;;
    *)                  echo "$k: looks set (${#v} chars)" ;;
  esac
done
# Anything not "looks set" needs replacing. Generate real ones:
export SESSION_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export INTERNAL_API_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export SESSION_HTTPS_ONLY=false     # local HTTP; otherwise TRUSTED_HOSTS is mandatory too

# The documented local setup (docs/RUNBOOK_LOCAL_LINUX.md) creates a single venv/ at the repo
# root, not one under website/ — so from website/ it's ../venv/bin/uvicorn, not venv/bin/uvicorn
# (some boxes additionally have a website/venv from a different setup path; if
# `../venv/bin/uvicorn` doesn't exist on yours, check which one your box actually has).
cd website && ../venv/bin/uvicorn backend.main:app --reload   # must run from website/ — backend
                                                                # is a package under it, not repo root
# leave this running in the foreground — it doesn't return until stopped. Wait for
# "Application startup complete." before using Terminal B; an import-time ValueError about a
# missing secret shows up here instead.
```

```bash
# Terminal B — uvicorn above never returns, so run the request from a second shell (or
# background/nohup it from the first and wait for the "Application startup complete" line)
# -sS, not -s: bare -s silences curl's own error message too, so a refused
# connection/malformed URL/DNS failure collapses to a bare "000" with no
# explanation of why nothing came back. -S keeps the diagnostic while still
# suppressing the progress meter (Codex review on #576).
curl -sS -w '\n%{http_code}\n' 'http://127.0.0.1:8000/api/proximity/prox-scores?<params-if-known>'
```

Deliberately **not** `-o /dev/null`: a FastAPI validation error (bad/missing query param) is a
handled response, not an exception — Step 2 already notes several 500 paths raise
`HTTPException` without logging anything, and a validation failure is the same shape one level
earlier (a 422 that never reaches `logger.error` at all). Its `detail` field, which names the
exact missing/invalid parameter, only exists in the response body — discarding it with
`-o /dev/null` throws away the one piece of diagnostic information a request like that has.

Run against the local dev backend, not production. If you don't know the query params (common
— see Step 1), try the endpoint bare first, then with whatever params the page under
investigation would plausibly send; note explicitly which combinations you tried.

## Worked example (from W1)

Paste: *"proximity page threw an error around 2026-07-19 11am, radar chart was
blank for player FB0EC84076637A9F55D579085A3225C4."*

The GUID alone matches several days' worth of (successful) requests, so filter by the date too:

```bash
$ grep -F "FB0EC84076637A9F55D579085A3225C4" logs/access.log | grep "2026-07-19"
2026-07-19 11:03:51 | INFO     | access | dispatch:97 | → GET /api/proximity/player/FB0EC84076637A9F55D579085A3225C4/radar
2026-07-19 11:03:51 | WARNING  | access | dispatch:136 | ← GET /api/proximity/player/FB0EC84076637A9F55D579085A3225C4/radar → 500 (182.7ms)
```

That's the request/response pair — but note what it does *not* show. The handler's own error line
carries no GUID (it logs `Proximity endpoint error` and nothing else), so a plain `grep` for the
GUID can never print it. Add `-A1` to pick up what was logged in between — this is where the
"access.log holds every logger's INFO+, not just access traffic" note from Step 1 pays off:

```bash
$ grep -F -A1 "FB0EC84076637A9F55D579085A3225C4" logs/access.log | grep -A1 "2026-07-19 11:03" | head -2
2026-07-19 11:03:51 | INFO     | access | dispatch:97 | → GET /api/proximity/player/FB0EC84076637A9F55D579085A3225C4/radar
2026-07-19 11:03:51 | ERROR    | api.proximity | get_proximity_player_radar:232 | Proximity endpoint error
```

No query string needed here (the guid is in the path), traceback had already rotated out of
`errors.log` (and its backups) by 2026-07-29, so the next step was reading tracked code +
a live replay — see `docs/W1_500_TRIAGE_2026-07-29.md` for the full result (a diagnosed,
already-fixed dev-process-staleness cause, not a live bug). That doc is task W1's own
deliverable, from a companion PR in this same backlog sweep — if you're reading this before
that PR has merged, the file won't be in this tree yet; it will be once both land on `main`.

## Closing the gap long-term

W4 (client-side error reporting, `POST /api/client-error`) carries the failed request's own
URL — including its query string, since the frontend already knows what it asked for —
directly from the browser to a dedicated log. Prefer that over grepping `access.log` for
anything that happens after it lands; this guide's Steps 1-2 remain the right approach for
anything that predates it or bypasses the frontend (e.g. a direct API script hitting a stale
bookmark).
