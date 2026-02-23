# Phase 4: Technical Debt & Code Quality Scan

**Date**: 2026-02-23
**Auditor**: Code Quality Auditor Agent
**Scope**: Full project Python codebase — bot, website backend, services, cogs, core modules

---

## Executive Summary

The Slomix ET:Legacy Discord Bot codebase is generally well-structured, production-ready, and
demonstrates strong awareness of security concerns (parameterized queries, sanitized filenames,
CSRF protection). However, the audit found several issues worth addressing, organized below by
severity. The most pressing concerns are: SQLite residue in production-path code, N+1 query
patterns in the website API, deprecated `asyncio.get_event_loop()` calls, and a debug
diagnostic block left in production code.

---

## [CRITICAL] Issues

### C1 — Broken SQL Placeholder in `team_history.py:75` (SQLite Residue)

**File**: `bot/core/team_history.py:71-76`

```python
placeholders = ','.join('?' * len(guids))
cursor.execute("""
    SELECT guid, alias
    FROM player_aliases
    WHERE guid IN ({placeholders})   # <-- NEVER INTERPOLATED — literal string
    ...
""", guids)
```

**Problem**: The f-string prefix is missing. `{placeholders}` is a literal string in the SQL,
not the generated `?,?,?` list. This query will always fail at runtime with a SQL syntax error.
The module's own docstring acknowledges it is SQLite-only and silently returns empty results when
the SQLite file doesn't exist (PostgreSQL mode), which masks the bug in production. If the
`team_history` module is exercised against a SQLite file (e.g. in testing or a future rollback),
`get_lineup_stats()` will raise.

**Recommendation**: Fix to `f"""..."""` or use `IN ({placeholders})` with the variable properly
in scope.

---

### C2 — SQLite Syntax `INSERT OR REPLACE` Retained in `link_cog.py`

**File**: `bot/cogs/link_cog.py:118-139`, `link_cog.py:979-993`, `link_cog.py:1335-1349`

```python
if self.bot.config.database_type == 'sqlite':
    await self.bot.db_adapter.execute(
        "INSERT OR REPLACE INTO player_links ...",  # SQLite-only syntax
        ...
    )
else:  # PostgreSQL
    ...
```

**Problem**: Three separate places in `link_cog.py` contain SQLite-branch `INSERT OR REPLACE`
code and conditional logic. Since PostgreSQL is the only supported production database (per
CLAUDE.md), the SQLite branch is dead code that adds complexity and maintenance surface. The
conditional also reads `self.bot.config.database_type == 'sqlite'`, which should never be true
in production.

**Recommendation**: Remove the SQLite branches entirely. Leave only the PostgreSQL
`ON CONFLICT DO UPDATE` path. This reduces each site to ~8 lines instead of ~20.

---

### C3 — Dead SQLite-Only Modules Imported into Production Path

**Files**:
- `bot/core/team_history.py` — Entirely SQLite (`sqlite3` import, `sqlite3.connect()`)
- `bot/core/team_detector_integration.py:13,26,32,112,185,248,322` — Entire class depends on `sqlite3.Connection`

**Problem**: Both modules use synchronous `sqlite3` connections, hardcoded `db_path` defaults
pointing to the old `bot/etlegacy_production.db` file, and contain no async code. The docstring
in `team_history.py` explicitly warns "SQLite-only module." These are imported by the
team management system. In PostgreSQL mode they silently return empty results (graceful
degradation), but they represent unmaintained legacy code that will never work in production and
could confuse future developers.

**Recommendation**: Archive or delete both modules if no SQLite path is planned. If kept for
future reference, move to `bot/archive/` and remove imports from any production code path.

---

## [HIGH] Issues

### H1 — N+1 Query Pattern in Website API `resolve_display_name()`

**File**: `website/backend/routers/api.py:267-310` (function), called at lines:
1940, 1946, 3032, 3149, 3403, 3676, 3748, 3873, 4191, 5221, 5266, 5441, 5475, 5707, 5954,
8045, 8072, 8099, 8154 (19 call sites)

**Problem**: `resolve_display_name()` executes 2-3 DB queries per player (check `player_links`,
then `player_aliases`, then fallback). Many endpoints iterate over all players in a result set and
call this function per-player in a `for row in rows` loop, resulting in N+1 (actually N×3 at
worst) queries per request:

```python
for row in ordered_rows:
    name = await resolve_display_name(db, guid, row[1] or "Unknown")
    # ^^^ 2-3 DB round-trips inside, per player
```

In a session with 12 players this produces 24-36 additional queries per endpoint call.

**Recommendation**: Batch-resolve display names. Collect all GUIDs from the result set first,
run a single `IN (...)` query against `player_links` and `player_aliases`, build a lookup dict,
then substitute names in the iteration loop. This reduces N×3 queries to 2 queries total.

---

### H2 — `asyncio.get_event_loop()` Deprecated (Python 3.10+)

**Files and lines**:
- `bot/automation/ssh_handler.py:153, 254`
- `bot/services/automation/ssh_monitor.py:416, 548`
- `bot/services/monitoring_service.py:337`

**Problem**: `asyncio.get_event_loop()` is deprecated since Python 3.10 and raises a
`DeprecationWarning`. In Python 3.12 it emits a `DeprecationWarning` if there is no current
running loop. The project targets Python 3.11+. The correct replacement is
`asyncio.get_running_loop()` (already used correctly in `ultimate_bot.py:1079`).

**Recommendation**: Replace all `asyncio.get_event_loop()` calls with
`asyncio.get_running_loop()`. Existing fix in `ultimate_bot.py:1079` shows the correct pattern.

---

### H3 — Debug Diagnostic Block Left in Production Code

**File**: `bot/ultimate_bot.py:2488-2508`

```python
# Temporary diagnostic logging: capture the first few weapon INSERTs
# to verify column/value alignment (will be removed after debugging).
try:
    logged = getattr(self, "_weapon_diag_logged", 0)
    if logged < 5:
        logger.debug("DIAG WEAPON INSERT: round_id=%s player=%s", ...)
        logger.debug("  insert_cols: %s", insert_cols)
        logger.debug("  row_vals: %r", tuple(row_vals))
        logger.debug("  insert_sql: %s", insert_sql)
        self._weapon_diag_logged = logged + 1
except Exception:
    logger.exception("Failed to log weapon insert diagnostic")
```

**Problem**: A temporary diagnostic block with an explicit comment "will be removed after
debugging" remains in the hot path of every weapon stat insertion. This runs on every round
import, adds per-player-per-weapon try/except overhead, and stores debug state as a dynamic
attribute on the bot object (`self._weapon_diag_logged`).

**Recommendation**: Remove the entire diagnostic block. If needed later, use `logger.debug()`
without the multi-step exception wrapper.

---

### H4 — `print()` Calls in Production Module `website/backend/dependencies.py`

**File**: `website/backend/dependencies.py:44, 54`

```python
print(f"✅ Database pool initialized ({db_type})")
...
print("✅ Database pool closed")
```

**Problem**: `print()` bypasses the logging infrastructure. In production (systemd service), this
output goes to stdout which may not be captured. These are startup lifecycle events that should
use `logger.info()`.

**Recommendation**: Replace both `print()` calls with `logger.info()`. Same issue exists in
`website/backend/init_db.py`, `check_bot_db.py`, `check_schema.py`, `check_stats_schema.py`
(diagnostic scripts — lower priority since they're run manually, but worth consistent style).

---

### H5 — f-string SQL Construction in Website `api.py` (Table Name Interpolation)

**File**: `website/backend/routers/api.py:574-575, 1089-1090`

```python
count = await db.fetch_val(f"SELECT COUNT(*) FROM {table}")
last = await db.fetch_val(f"SELECT MAX(recorded_at) FROM {table}")
```

**Problem**: `table` is a string interpolated directly into SQL. While `table` is sourced from a
hardcoded tuple `("server_status_history", ...)` at the call sites and not from user input, the
pattern is fragile. If the loop or its input ever changes, it becomes an injection vector. The
linter flag `nosec B608` is absent here.

**Recommendation**: Validate `table` against an explicit allowlist before interpolation, and add
a `# nosec B608` comment to document that the value is controlled. The pattern in
`monitoring_service.py:315-317` (`if table_name not in self._MONITORING_TABLES`) is the correct
model.

Also at `api.py:1532-1577`: `round_filter` is an f-string built from a conditional but contains
no user input — document this explicitly.

---

### H6 — `ensure_player_name_alias()` in `ultimate_bot.py` Uses SQLite PRAGMA Syntax

**File**: `bot/ultimate_bot.py:86-136`

```python
async with db.execute(
    "PRAGMA table_info('player_comprehensive_stats')"
) as cur:
```

**Problem**: This standalone function at the top of `ultimate_bot.py` uses `PRAGMA` (SQLite-only
syntax) and `.commit()`, which are not valid PostgreSQL operations. The identical feature is
correctly implemented in `bot/core/database_adapter.py:350-421` using
`information_schema.columns` for PostgreSQL. The `ultimate_bot.py` version is dead code in
production but would cause a confusing failure if called.

**Recommendation**: Remove the duplicate `ensure_player_name_alias()` from `ultimate_bot.py`.
Use the canonical implementation from `bot/core/database_adapter.py`.

---

## [MEDIUM] Issues

### M1 — StatsCache Is Only Used by 2 Cogs

**File**: `bot/core/stats_cache.py`, used by `bot/cogs/leaderboard_cog.py` and `bot/cogs/stats_cog.py`

**Problem**: The `StatsCache` (5-minute TTL) is initialized for the entire bot but only actively
used in `leaderboard_cog.py` (lines 214, 290) and `stats_cog.py` (line 61, for displaying stats
only). The 18 other cogs access the database directly without caching. Expensive queries in
`session_cog.py`, `analytics_cog.py`, `last_session_cog.py`, and `matchup_cog.py` bypass the
cache entirely.

**Recommendation**: Either extend cache usage to high-frequency queries (e.g., session player
lists, leaderboard data), or document clearly which queries are intentionally uncached and why.
The 5-minute TTL is appropriate for leaderboard data; for live-session data it may be too long
(consider shorter TTL or cache invalidation on round import).

---

### M2 — `team_history.py:138` Full Table Scan in `find_similar_lineups()`

**File**: `bot/core/team_history.py:138`

```python
cursor.execute("SELECT * FROM team_lineups")
for row in cursor.fetchall():
    lineup_guids = set(json.loads(row['player_guids']))
    overlap = len(player_set & lineup_guids)
```

**Problem**: Fetches the entire `team_lineups` table into Python memory then computes set
intersections. This is O(N × M) where N = lineups and M = players per lineup. For any reasonably
large dataset this is slow and memory-wasteful.

**Recommendation**: Since this module is SQLite-only and silently returns empty results in
production (PostgreSQL mode), the immediate risk is low. If ever ported to PostgreSQL, replace
with a proper overlap query using `jsonb` containment operators or a normalized `team_lineup_players`
join table.

---

### M3 — Synchronous Blocking File I/O Inside `ServerControl.log_action()`

**File**: `bot/cogs/server_control.py:200-203`

```python
with open(self.audit_log_path, 'a', encoding='utf-8') as f:
    f.write(log_entry + '\n')
```

**Problem**: `log_action()` is called from async Discord command handlers. The synchronous
`open()` + `write()` blocks the event loop. For audit log entries (small writes to local disk)
this is usually fast, but under load or on a slow filesystem it can cause Discord heartbeat
delays.

**Recommendation**: Use `asyncio.to_thread()` (Python 3.9+) or the standard logging system
(which handles I/O in its own thread) for the audit file write.

---

### M4 — Hardcoded Server Paths in `ServerControl`

**File**: `bot/cogs/server_control.py:164-168`

```python
self.server_install_path = '/home/et/etlegacy-v2.83.1-x86_64'
self.maps_path = f"{self.server_install_path}/etmain"
self.screen_name = 'vektor'
self.server_binary = './etlded.x86_64'
self.server_config = 'vektor.cfg'
```

**Problem**: Server paths, screen session name, binary name, and config file are hardcoded. If
the server install location changes (e.g. version upgrade from v2.83.1), the bot requires a code
change rather than a config change.

**Recommendation**: Move these to `.env` variables: `SERVER_INSTALL_PATH`, `SERVER_SCREEN_NAME`,
`SERVER_BINARY`, `SERVER_CONFIG`. Add defaults matching current values.

---

### M5 — `ServerControl` Reads SSH Config via `os.getenv()` Instead of `bot.config`

**File**: `bot/cogs/server_control.py:149-152`

```python
self.ssh_host = os.getenv('SSH_HOST')
self.ssh_port = int(os.getenv('SSH_PORT', 22))
self.ssh_user = os.getenv('SSH_USER')
self.ssh_key_path = os.path.expanduser(os.getenv('SSH_KEY_PATH', '~/.ssh/id_rsa'))
```

**Problem**: These duplicate SSH config already parsed into `bot.config` (`config.ssh_host`,
`config.ssh_port`, etc.). Two separate `os.getenv()` reads means the cog can diverge from the
config object used by the rest of the bot.

**Recommendation**: Replace with `bot.config.ssh_host`, `bot.config.ssh_port`, etc.

---

### M6 — `metrics_logger.py` Uses `aiosqlite` (Separate SQLite Database in Production)

**File**: `bot/services/automation/metrics_logger.py:17, 65, 74, 88-123, 151, 154`

**Problem**: The `MetricsLogger` maintains its own separate SQLite database (`metrics.db`) even
in PostgreSQL production mode. The startup logic in `ultimate_bot.py:810-828` specifically
detects this case and routes metrics to a dedicated file. This means the production system uses
two different databases: PostgreSQL for all game data and SQLite for bot metrics. While
intentional, it creates a maintenance split and requires `aiosqlite` as a dependency even in
PostgreSQL-only deployments.

**Recommendation**: Either migrate metrics logging to PostgreSQL (add a `bot_metrics` schema),
or document this architectural decision explicitly in CLAUDE.md and ensure `aiosqlite` is in
`requirements.txt`. Currently `aiosqlite` is imported but may not be listed as an explicit
dependency.

---

### M7 — `api.py` Uses `print()` for Error Fallback in Production Endpoint

**File**: `website/backend/routers/api.py:1568`

```python
print(f"[overview] round_status filter failed, retrying fallback: {e}")
```

**Problem**: A `print()` call inside a production API endpoint handler. This will appear on
stdout of the web server process, not in the structured log.

**Recommendation**: Replace with `logger.warning(...)`.

---

### M8 — `StatsCache` Uses `datetime.now()` Without Timezone Awareness

**File**: `bot/core/stats_cache.py:63, 82, 100`

```python
age = (datetime.now() - self.timestamps[key]).total_seconds()
```

**Problem**: `datetime.now()` returns a naive datetime. If system clock adjustment (NTP sync, DST
change) occurs while the bot is running, cached item ages can be calculated incorrectly. Unlikely
to cause real issues in practice, but technically incorrect.

**Recommendation**: Use `datetime.now(timezone.utc)` for all cache timestamps. Low priority but
worth fixing for correctness.

---

### M9 — `link_cog.py` Queries by `player_name` Instead of `player_guid`

**File**: `website/backend/routers/api.py:3056-3061`

```python
stats = await db.fetch_one(
    "SELECT 1 FROM player_comprehensive_stats WHERE player_name = ? LIMIT 1",
    (payload.player_name,),
)
```

**Problem**: CLAUDE.md explicitly warns "Don't group by player_name" (players change names). This
query validates a link by `player_name` lookup, which could fail for players who have changed
names since their first appearance, or incorrectly match a different player who adopted a
previous name.

**Recommendation**: The link flow should search by `player_guid` or require a GUID as part of
the link payload, similar to how `link_cog.py` in the bot cog works.

---

## [LOW] Issues

### L1 — Dead Commented-Out Import Lines

**Files and lines**:
- `bot/cogs/admin_cog.py:25`: `# import aiosqlite  # Removed - using database adapter`
- `bot/cogs/synergy_analytics.py:16`: `# import aiosqlite  # Removed - using database adapter`
- `bot/cogs/team_management_cog.py:16`: `# import aiosqlite  # Removed - using database adapter`
- `bot/services/automation/database_maintenance.py:20`: same

**Problem**: Commented-out imports are dead code. They serve no purpose now that the migration
is complete.

**Recommendation**: Remove all commented-out import lines.

---

### L2 — `ultimate_bot.py` Is 5,989 Lines

**File**: `bot/ultimate_bot.py`

**Problem**: Despite significant refactoring efforts, the main bot file remains nearly 6,000
lines. It still contains: the `UltimateETLegacyBot` class (lines 176–5989), helper functions,
all Cog loading logic, SSH file listing (`_list_remote_files()` method), the `endstats_monitor`
task loop, webhook handling, and the `main()` entry point.

**Recommendation**: This is a long-term refactoring concern, not an immediate bug. The
`endstats_monitor` task loop (which is the largest single component) could be extracted to a
dedicated `EndstatsMonitorService`. The immediate action is to not add more logic to this file.

---

### L3 — `api.py` Is 8,453 Lines

**File**: `website/backend/routers/api.py`

**Problem**: The website's primary API router is 8,453 lines with 80+ endpoints. This is
extremely difficult to navigate and review.

**Recommendation**: Organize endpoints into sub-routers by domain (player stats, session stats,
leaderboard, awards, diagnostics, overview). This is a refactoring task and should not block
current work.

---

### L4 — `asyncio.create_subprocess_exec` Without Timeout

**File**: `bot/services/automation/database_maintenance.py:144`
**File**: `bot/services/signal_connector.py:135`

```python
process = await asyncio.create_subprocess_exec(...)
```

**Problem**: Neither call sets a timeout. If the subprocess hangs (e.g. database backup process
or signal gateway connection), the coroutine will block indefinitely.

**Recommendation**: Wrap with `asyncio.wait_for(..., timeout=...)`.

---

### L5 — `server_control.py:201` Synchronous `open()` in Async Context for Audit Log

Already noted as M3 above; cross-referenced here for completeness.

---

### L6 — `community_stats_parser.py` Imports `glob` Inside a Method

**File**: `bot/community_stats_parser.py:426`

```python
def find_corresponding_round_1_file(self, round_2_file_path: str) -> Optional[str]:
    import glob
    from datetime import datetime, timedelta
    ...
```

**Problem**: Importing inside a method is a Python antipattern. `glob` and `datetime` should be
module-level imports. While not a bug, it slightly increases method call overhead and reduces
readability.

**Recommendation**: Move imports to the top of the file.

---

### L7 — `ultimate_bot.py:201` Redundant `import os` Inside `__init__`

**File**: `bot/ultimate_bot.py:201`

```python
def __init__(self):
    ...
    import os
```

**Problem**: `os` is already imported at module level (line 10). The in-method import is
redundant.

**Recommendation**: Remove the in-method `import os`.

---

### L8 — Token Exposed in Public Channel Fallback

**File**: `bot/cogs/availability_poll_cog.py:2073`

```python
await ctx.send(f"⚠️ Couldn't DM you. Here is the token (delete after use): `{token}`")
```

**Problem**: If a user's DMs are closed, the one-time link token (for Telegram/Signal linking) is
sent to the Discord channel in plaintext. While the token expires, anyone who sees the message
can use it before deletion.

**Recommendation**: Instead of posting to the channel, instruct the user to open DMs and retry,
or encrypt/shorten the display. Do not post authentication tokens to channels.

---

### L9 — `team_history.py` Full-Table `SELECT * FROM team_lineups` Without Connection Close Guard

**File**: `bot/core/team_history.py:138-153`

```python
cursor.execute("SELECT * FROM team_lineups")
similar = []
...
for row in cursor.fetchall():
    ...
conn.close()
```

**Problem**: If `json.loads(row['player_guids'])` raises (malformed JSON), the `conn.close()` is
never reached, leaking the connection. Same pattern in several other methods in the file.

**Recommendation**: Use `try/finally` or a context manager to ensure `conn.close()` is always
called.

---

## 4B — Security Audit

### Security Positives (Good)

- CSRF middleware (`main.py:106-142`) with origin-check guard — well implemented
- `SESSION_SECRET` enforced at startup with explicit error on default value (`main.py:149-153`)
- Rate limiting middleware present on website
- `sanitize_filename()` in `server_control.py:36-77` — strips path separators, rejects traversal
- `shlex.quote()` used for all SSH-executed remote paths (`server_control.py:653`)
- `escape_like_pattern()` in `bot/core/utils.py` — escapes SQL LIKE wildcards
- Magic bytes validation on file uploads (`upload_validators.py:32-38`)
- Extension allowlists on uploads (strict, rejects all unlisted)
- `sanitize_rcon_input()` in `server_control.py:694-697` for RCON command filtering
- Webhook rate limiting with deque-based sliding window (`ultimate_bot.py:301-309`)
- No credentials hardcoded in source (all via `.env`)
- CORS configured to explicit origin list, not `*`

### Security Concerns

**S1** — `availability_poll_cog.py:2073`: Token posted to channel (see L8 above). Medium risk.

**S2** — `bot/core/utils.py:34` has a comment showing an unsafe LIKE pattern as an example:
```python
query = f"SELECT * FROM players WHERE name LIKE '%{escaped}%' ESCAPE '\\'"
```
This is in a docstring example, not live code, but a developer reading quickly could copy the
f-string pattern instead of the safe parameterized pattern on line 38. The comment is misleading.

**S3** — The `resolve_display_name()` function in `api.py:284` catches only `(OSError, RuntimeError)`.
PostgreSQL-specific exceptions (`asyncpg.PostgresError`, `asyncpg.UndefinedTableError`) are not
caught, meaning DB schema issues could propagate as 500 errors to API callers rather than
graceful fallback.

**S4** — `server_control.py:124`: RCON password sent over UDP in plaintext (per the ET:Legacy
RCON protocol design). This is a protocol limitation, not a code bug, but worth documenting.

---

## 4C — Performance Review

### Cache Coverage

The `StatsCache` (5-minute TTL) is only used by 2 of 21 cogs. High-frequency commands in
`session_cog.py` and `analytics_cog.py` re-query the database on every invocation. For a small
server this is acceptable; for concurrent bot usage, extending the cache to cover common session
queries would reduce DB load.

The 5-minute TTL is well-chosen for leaderboard data. For live session data (current session
players, round-by-round stats), consider a shorter TTL (60 seconds) or explicit cache
invalidation on round import.

### N+1 Queries

Identified in H1 above. The `resolve_display_name()` in `website/backend/routers/api.py` is the
most impactful performance issue in the website backend.

### Blocking Calls

All SSH operations correctly use `run_in_executor()`. The only remaining blocking concern is the
synchronous audit log write in `server_control.py` (see M3).

### Connection Pool

Pool is configured with `min=10, max=30` (config.py:80-81). For a 21-cog bot with 4 background
tasks, this is generous and appropriate.

### Query Design

Queries in `leaderboard_cog.py` correctly use `JOIN rounds r ON p.round_id = r.id` and filter
by `round_number IN (1, 2)` to exclude R0 summary rows. The `GROUP BY player_guid` pattern is
consistently applied throughout the bot cogs.

---

## 4D — Algorithm & Pipeline Improvements

### Round Matching Window Discrepancy

**Documented in bot/automation/CLAUDE.md but worth emphasizing**:

| Location | Window |
|----------|--------|
| `community_stats_parser.py:384` comment (R1-R2 matching) | 30 minutes |
| `bot/core/round_linker.py:47` default (`window_minutes`) | 45 minutes |
| `config.py` `SESSION_GAP_MINUTES` | 60 minutes |

The R1-R2 pairing logic in `community_stats_parser.py` references a 30-minute window in
comments. The `round_linker.py` uses 45 minutes. These should be consolidated to one
configurable constant to avoid edge-case mismatches for long-running rounds.

### `find_similar_lineups()` Algorithm

See M2. O(N) full table scan + Python-side set intersection. Acceptable for the current scale
(SQLite, small dataset) but would need rewrite before any PostgreSQL port.

### Session Graph Generation (matplotlib in async context)

**File**: `bot/services/session_graph_generator.py:17`

```python
matplotlib.use('Agg')
```

`matplotlib` is a heavy synchronous library. Graph generation calls `plt.show()` and rendering
operations in async context. While the `Agg` backend avoids GUI calls, the CPU-intensive
rendering still blocks the event loop. For large sessions with many players, this could cause
Discord heartbeat timeouts.

**Recommendation**: Wrap graph generation in `asyncio.to_thread()` to run it in a thread pool
executor.

### `_translate_placeholders()` in `database_adapter.py`

**File**: `bot/core/database_adapter.py:276-297`

```python
while i < len(query):
    if query[i] == '?':
        result.append(f'${param_num}')
        param_num += 1
    else:
        result.append(query[i])
    i += 1
return ''.join(result)
```

**Problem**: Character-by-character iteration via Python loop is O(N) where N is query string
length. For a more efficient implementation, use `re.sub()` with a counter:

```python
import re
_placeholder_re = re.compile(r'\?')
counter = [0]
def _replace(m):
    counter[0] += 1
    return f'${counter[0]}'
return _placeholder_re.sub(_replace, query)
```

This is a micro-optimization — the queries are small strings so real-world impact is minimal.
Document as low-priority.

---

## Summary Table

| Severity | ID | Description | File |
|----------|----|-------------|------|
| CRITICAL | C1 | Broken SQL placeholder in `find_similar_lineups()` | `bot/core/team_history.py:71` |
| CRITICAL | C2 | SQLite `INSERT OR REPLACE` dead code in `link_cog.py` | `bot/cogs/link_cog.py:118` |
| CRITICAL | C3 | Dead SQLite-only modules in production path | `bot/core/team_history.py`, `team_detector_integration.py` |
| HIGH | H1 | N+1 queries via `resolve_display_name()` | `website/backend/routers/api.py:267+` |
| HIGH | H2 | `asyncio.get_event_loop()` deprecated | `bot/automation/ssh_handler.py:153`, `ssh_monitor.py:416` |
| HIGH | H3 | Debug diagnostic block in production hot path | `bot/ultimate_bot.py:2488-2508` |
| HIGH | H4 | `print()` in production lifecycle code | `website/backend/dependencies.py:44,54` |
| HIGH | H5 | f-string SQL with table name interpolation | `website/backend/routers/api.py:574-575` |
| HIGH | H6 | Duplicate `ensure_player_name_alias()` uses SQLite PRAGMA | `bot/ultimate_bot.py:86-136` |
| MEDIUM | M1 | `StatsCache` underused (2/21 cogs) | `bot/core/stats_cache.py` |
| MEDIUM | M2 | Full table scan in `find_similar_lineups()` | `bot/core/team_history.py:138` |
| MEDIUM | M3 | Blocking file I/O in async context (audit log) | `bot/cogs/server_control.py:201` |
| MEDIUM | M4 | Hardcoded server paths in `ServerControl` | `bot/cogs/server_control.py:164-168` |
| MEDIUM | M5 | `ServerControl` reads SSH config via `os.getenv()` bypassing `bot.config` | `bot/cogs/server_control.py:149` |
| MEDIUM | M6 | Metrics logger uses separate SQLite DB in PostgreSQL production | `bot/services/automation/metrics_logger.py` |
| MEDIUM | M7 | `print()` in production API endpoint | `website/backend/routers/api.py:1568` |
| MEDIUM | M8 | Timezone-naive `datetime.now()` in `StatsCache` | `bot/core/stats_cache.py:63,82,100` |
| MEDIUM | M9 | Link validation by `player_name` instead of GUID | `website/backend/routers/api.py:3056` |
| LOW | L1 | Dead commented-out import lines | Multiple cogs |
| LOW | L2 | `ultimate_bot.py` is 5,989 lines | `bot/ultimate_bot.py` |
| LOW | L3 | `api.py` is 8,453 lines | `website/backend/routers/api.py` |
| LOW | L4 | `create_subprocess_exec` without timeout | `bot/services/automation/database_maintenance.py:144` |
| LOW | L6 | Import inside method body | `bot/community_stats_parser.py:426` |
| LOW | L7 | Redundant `import os` inside `__init__` | `bot/ultimate_bot.py:201` |
| LOW | L8 | Token exposed to channel if DM fails | `bot/cogs/availability_poll_cog.py:2073` |
| LOW | L9 | Missing `finally` on SQLite connection in team_history | `bot/core/team_history.py:138+` |

---

## Recommended Priority Order for Fixes

1. **H3** — Remove debug diagnostic block (5-minute fix, high impact on code clarity)
2. **H2** — Fix `asyncio.get_event_loop()` → `get_running_loop()` (10-minute fix per site)
3. **H4 + M7** — Replace `print()` with `logger.info/warning()` (5-minute fix)
4. **C2** — Remove SQLite branches from `link_cog.py` (30-minute cleanup)
5. **H6** — Remove duplicate `ensure_player_name_alias()` from `ultimate_bot.py`
6. **C1** — Fix broken f-string SQL placeholder in `team_history.py` (even if module is archived)
7. **H1** — Batch `resolve_display_name()` calls in `api.py` (1-2 hour refactor, high perf gain)
8. **L8** — Fix token channel leakage in `availability_poll_cog.py`
9. **M3** — Wrap audit log write in `asyncio.to_thread()`
10. **M4 + M5** — Move hardcoded server paths and SSH config to `bot.config`

---

*Generated by Code Quality Auditor Agent | Phase 4 of Slomix Mega Cleanup | 2026-02-23*
