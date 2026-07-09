# PLAN: INTERNAL_API_SECRET Protection For DB-Writing GET Endpoints

Generated: 2026-07-09, Europe/Ljubljana

Status: implementation plan for `feat/internal-api-secret`. This plan was
updated after PR #482 introduced `_warm_kis_cache()` in
`bot/services/voice_session_service.py`.

## Decision

Use split read/write behavior.

- `/api/skill/s-effort` is strict internal-only because it computes and
  persists `player_skill_history`.
- Storytelling routes remain public for read-only UI reads.
- Storytelling routes only run compute/write paths when `X-Internal-Token`
  matches `INTERNAL_API_SECRET`.
- A missing internal header means public read-only mode.
- A present but invalid internal header returns `401`.

This keeps existing Story/Proximity UI working while preventing anonymous
internet users from triggering DB writes.

## Security Goal

The exposed risk is public GET endpoints that can trigger internal compute
paths with write side effects:

- `SEffortService.persist_session()` deletes/inserts
  `player_skill_history`.
- `StorytellingService.kis_compute_with_shadow()` can call
  `compute_session_kis()`, which deletes/inserts
  `storytelling_kill_impact`.
- Narrative endpoints call KIS compute before reading unless explicitly
  switched to read-only behavior.

After this change, only bot/server-side callers with the shared internal
secret can trigger those writes.

## Backend Changes

- Add `INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET")` in
  `website/backend/main.py`.
- Validate it at startup with the same fail-fast pattern as `SESSION_SECRET`.
- Add `require_internal_secret(request)` in `website/backend/dependencies.py`.
- Add `get_internal_request_mode(request)` in `website/backend/dependencies.py`.
- Use `secrets.compare_digest`, not `==`.
- Do not import `website.backend.main` from `dependencies.py`; that would risk
  circular imports because `main.py` imports routers and routers import
  dependencies.

## Endpoint Changes

Protect `GET /api/skill/s-effort` with `Depends(require_internal_secret)`.
Place the dependency before `db=Depends(get_db)` so unauthorized requests do
not initialize or touch the DB.

Apply split read/write behavior to:

- `GET /api/storytelling/kill-impact`
- `GET /api/storytelling/kill-impact/details`
- `GET /api/storytelling/narrative`
- `GET /api/storytelling/player-narratives`

For public storytelling requests, read existing cache/persisted rows only.
For internal requests, preserve the existing compute/write behavior.

Add `ensure_kis: bool = True` to:

- `generate_narrative()`
- `generate_player_narratives()`

Public routes call these with `ensure_kis=False`; internal routes call them
with `ensure_kis=True`.

## Bot Changes

Add `internal_api_secret` to `BotConfig`:

```python
self.internal_api_secret = self._get_config("INTERNAL_API_SECRET", "")
```

Send `X-Internal-Token` from all bot callers that hit protected write-through
website routes:

- `voice_session_service._persist_s_effort()`
- `voice_session_service._warm_kis_cache()` from PR #482
- `session_digest_service._fetch_kis_top()`

The `_warm_kis_cache()` caller is required. Without the header, the new
split read/write endpoint would become read-only and the PR #482 cache warm
fix would silently stop recomputing KIS after session end.

## Env, CI, Prod, Dev

Add `INTERNAL_API_SECRET` to:

- `.env.example`
- `website/.env.example`
- `.github/workflows/tests.yml`

Production rollout:

- Generate one value:
  `python -c 'import secrets; print(secrets.token_urlsafe(32))'`
- Set the same value in bot and website env.
- Restart both services after both envs are updated.
- Never expose this value to frontend JS, React env, HTML, or browser requests.

Development rollout:

- Use a throwaway local value.
- Local bot and local website must share the same value when testing internal
  calls.

## Tests

Required targeted tests:

- `/api/skill/s-effort` without header returns `401`.
- Unauthorized `/skill/s-effort` does not call DB or `SEffortService`.
- `/api/skill/s-effort` with correct header reaches mocked compute/persist.
- Public `/storytelling/kill-impact` does not call `kis_compute_with_shadow`.
- Internal `/storytelling/kill-impact` calls `kis_compute_with_shadow`.
- Wrong `X-Internal-Token` returns `401`.
- Public `/storytelling/narrative` and `/player-narratives` do not call KIS
  compute.
- `_persist_s_effort()`, `_warm_kis_cache()`, and `_fetch_kis_top()` send
  `X-Internal-Token`.

Run:

```bash
SESSION_SECRET=test-session-secret INTERNAL_API_SECRET=test-internal-secret PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_internal_api_secret.py tests/unit/test_s_effort_session_hook.py tests/unit/test_session_digest_service.py tests/unit/test_kis_cache_invalidation_hook.py -q
SESSION_SECRET=test-session-secret INTERNAL_API_SECRET=test-internal-secret PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/ -q
```

## Do Not Change

Do not protect or alter:

- `/api/skill/leaderboard`
- `/api/skill/formula`
- `/api/skill/adjusted-lifetime`
- `/api/storytelling/moments`

Do not:

- expose `INTERNAL_API_SECRET` to frontend code
- use Discord OAuth/admin cookies for bot-to-website calls
- convert endpoints to POST in this change
- add DB migrations

## Known Tradeoff

Public Story/Proximity UI can only display KIS/narrative data that already
exists in DB. If KIS was never computed, public UI should show the existing
empty/no-data states. PR #482's `_warm_kis_cache()` reduces this risk by
warming KIS after session end; this plan preserves that behavior by adding
the internal header to `_warm_kis_cache()`.
