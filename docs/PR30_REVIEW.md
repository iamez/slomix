# PR #30 Code Review - feature/lua-webhook-realtime-stats

**Reviewed**: 2026-02-08
**Commits**: 20 | **Lines**: +68,533 / -8,083
**Codacy**: 1,926 issues flagged | **CodeQL**: 20+ potential problems

---

## CRITICAL - Fix Immediately

### 1. SQL Injection: INTERVAL interpolation from user input

**File**: `website/backend/routers/api.py:5300`
```python
if days > 0:
    where_clauses.append(f"ra.created_at >= NOW() - INTERVAL '{days} days'")
```
`days` is an HTTP query parameter (`days: int = 0` at line 5263). While FastAPI enforces `int`, this is a dangerous pattern. The same file already has the safe version at line 4985.

**Fix**: Use parameterized interval:
```python
where_clauses.append(f"ra.created_at >= NOW() - (${param_idx} * INTERVAL '1 day')")
params.append(days)
param_idx += 1
```

### 2. SQL Injection: Column name interpolation without whitelist

**File**: `website/backend/routers/greatshot.py:339`
```python
async def _artifact_for_user(db, demo_id: str, user_id: int, field_name: str) -> str:
    row = await db.fetch_one(
        f"SELECT {field_name} FROM greatshot_demos WHERE id = $1 AND user_id = $2",
        (demo_id, user_id),
    )
```
Currently only called with hardcoded strings (`"analysis_json_path"`, `"report_txt_path"`), but no validation prevents future misuse.

**Fix**: Add whitelist:
```python
ALLOWED_FIELDS = {"analysis_json_path", "report_txt_path"}
if field_name not in ALLOWED_FIELDS:
    raise ValueError(f"Invalid field: {field_name}")
```

### 3. SQL Injection: Table name interpolation in monitoring service

**File**: `bot/services/monitoring_service.py:174`
```python
await self.db.execute(
    f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({index_expr})"
)
```

**File**: `bot/services/monitoring_service.py:312`
```python
await self.db.execute(
    f"DELETE FROM {table_name} WHERE recorded_at < $1",
    (cutoff,),
)
```
Both called from hardcoded callers only (`"server_status_history"`, `"voice_status_history"`). Low immediate risk but Codacy flags them.

**Fix**: Add whitelist validation in `_cleanup_table` and `_ensure_index`:
```python
MONITORING_TABLES = {"server_status_history", "voice_status_history"}
if table_name not in MONITORING_TABLES:
    raise ValueError(f"Invalid monitoring table: {table_name}")
```

### 4. SQL Injection: Table name in team_manager.py

**File**: `bot/core/team_manager.py:1064-1087`
The f-string SQL here is building SET clauses dynamically from `set_fields_a`/`set_fields_b`. The field names come from a hardcoded `"color"` check against column list. Values are properly parameterized. **Risk: LOW** (internal code only).

---

## HIGH - XSS Issues

### 5. Unescaped server error in innerHTML

**File**: `website/js/live-status.js:88-91`
```javascript
const errorMsg = server.error || 'Server is not responding';
serverDetails.innerHTML = `...
    <span class="text-red-400/70">${errorMsg}</span>
`;
```
`server.error` from API response inserted raw into HTML. If game server returns crafted error messages, XSS is possible.

**Fix**: `escapeHtml(errorMsg)`

### 6. escapeHtml() used in JavaScript string context (onclick handlers)

Multiple files use `escapeHtml()` for values inserted into `onclick="func('${escapeHtml(value)}')"` handlers. `escapeHtml()` does NOT escape single quotes, so a value containing `')` can break out of the JS string context.

| File | Line | Value |
|------|------|-------|
| `website/js/awards.js` | 336 | player names |
| `website/js/greatshot.js` | 107, 140, 164, 189, 320 | demo/highlight IDs |
| `website/js/sessions.js` | 1421, 1433-1449 | date strings |

**Fix**: Use `escapeJsString()` (already exists in utils.js) instead of `escapeHtml()` for onclick handler values. Or better: use `addEventListener` instead of inline handlers.

---

## MEDIUM - Code Quality

### 7. Unused imports (9 confirmed across 7 files)

| File | Unused Import |
|------|--------------|
| `bot/cogs/matchup_cog.py:13` | `Optional` |
| `bot/cogs/server_control.py:25` | `Optional` |
| `bot/core/endstats_pagination_view.py:16` | `Optional` |
| `bot/cogs/proximity_cog.py:21` | `List` |
| `bot/services/timing_comparison_service.py:24` | `List` |
| `bot/services/monitoring_service.py:17` | `Dict` |
| `website/backend/services/greatshot_store.py:10` | `Dict`, `Any` |
| `bot/services/player_analytics_service.py:14` | `Any` |

### 8. Unused variables (2 confirmed)

| File | Line | Variable |
|------|------|----------|
| `bot/services/matchup_analytics_service.py` | 672 | `kd_delta` - assigned, never used |
| `bot/services/timing_comparison_service.py` | 429 | `lua_end_unix` - assigned, never used |

**False positives** flagged by Codacy: `team_2_guids` (used on lines 405/420/451/471), `emoji` (used on line 236), `placeholders` (used in SQL).

### 9. F-strings without placeholders (~30+ instances)

Harmless but noisy. F-strings like `f"Not enough rounds"` with no `{}` should just be regular strings. Main offenders:
- `bot/ultimate_bot.py` - ~14 instances
- `postgresql_database_manager.py` - ~7 instances
- `bot/services/timing_comparison_service.py` - ~4 instances
- `bot/services/timing_debug_service.py` - ~2 instances
- `proximity/parser/parser.py` - ~4 instances

---

## LOW - Infrastructure

### 10. Missing Content-Security-Policy

**File**: `website/index.html`
No CSP meta tag or header. Third-party CDN scripts loaded without Subresource Integrity (SRI) hashes:
- `cdn.tailwindcss.com/3.4.17`
- `unpkg.com/lucide@0.563.0`
- `cdn.jsdelivr.net/npm/chart.js@4.4.7`

### 11. Client-side admin check

**File**: `website/index.html:7`
```html
<meta name="slomix-admin-discord-ids" content="231165917604741121">
```
Admin Discord ID hardcoded in HTML. Anyone can modify this in browser to show admin UI. Backend must validate permissions separately (it does via `user_permissions` table).

### 12. Table name interpolation in other locations (all from hardcoded lists)

| File | Line | Risk |
|------|------|------|
| `postgresql_database_manager.py` | 1221 | Hardcoded wipe list - LOW |
| `postgresql_database_manager.py` | 2412 | Hardcoded validation dict - LOW |
| `website/backend/routers/api.py` | 498-499, 877-878 | Hardcoded tuples - LOW |
| `tests/conftest.py` | 121 | Test code, hardcoded list - LOW |
| `bot/ultimate_bot.py` | 115, 2178 | Schema introspection - LOW |

### 13. Unsafe SQL example in docstring

**File**: `bot/core/utils.py:34`
```python
query = f"SELECT * FROM players WHERE name LIKE '%{escaped}%' ESCAPE '\\'"
```
This is inside a docstring (not executed), but could mislead developers.

---

## Summary by Priority

| Priority | Count | Action |
|----------|-------|--------|
| CRITICAL (SQL injection) | 4 | Fix before merge |
| HIGH (XSS) | 2 | Fix before merge |
| MEDIUM (unused code) | ~40 | Clean up |
| LOW (infrastructure) | 4 | Track for future |

### Recommended Fix Order

1. `api.py:5300` - INTERVAL parameterization (1 line)
2. `greatshot.py:339` - Add field whitelist (3 lines)
3. `monitoring_service.py:174,312` - Add table whitelist (3 lines)
4. `live-status.js:88` - Escape server error (1 line)
5. `awards.js:336`, `greatshot.js`, `sessions.js` - Switch to `escapeJsString()` (~8 lines)
6. Remove unused imports (9 files, 1 line each)
7. Remove unused variables (2 files)
8. Strip unnecessary `f` prefixes from plain strings (~30 files)
