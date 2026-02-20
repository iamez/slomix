# Upload Library Security Model

Threat model and red-team checklist for the community file upload system.

**Applies to:** `website/backend/routers/uploads.py`, `website/backend/services/upload_store.py`, `website/backend/services/upload_validators.py`

---

## 1. Attack Surfaces

### 1.1 File Upload (`POST /api/uploads`)

| Threat | Risk | Description |
|--------|------|-------------|
| Malicious executable upload | High | Attacker uploads `.exe`, `.sh`, or polyglot file disguised with allowed extension |
| Zip bomb | Medium | Compressed archive with extreme expansion ratio exhausts disk |
| Path traversal in filename | High | Filename like `../../etc/passwd` writes outside storage root |
| Oversized upload (DoS) | Medium | Streaming large payload to exhaust disk or memory |
| Content-type mismatch | Medium | File claims `.zip` extension but contains executable content |

### 1.2 File Download (`GET /api/uploads/{id}/download`)

| Threat | Risk | Description |
|--------|------|-------------|
| Content-type sniffing (XSS) | High | Browser interprets served file as HTML, executing embedded scripts |
| Directory traversal on read | High | Crafted `stored_path` in DB resolves outside storage root |
| Symlink follow (TOCTOU) | Medium | Symlink planted in storage root leads to arbitrary file read |

### 1.3 Authentication & Authorization

| Threat | Risk | Description |
|--------|------|-------------|
| Unauthenticated upload | High | Bypassing session check to upload arbitrary files |
| CSRF on upload/delete | Medium | Tricking authenticated user into uploading or deleting via cross-site form |
| IDOR on delete | Medium | Deleting another user's upload by guessing UUID |

### 1.4 Rate Limiting & Resource Exhaustion

| Threat | Risk | Description |
|--------|------|-------------|
| Upload flood (single user) | Medium | Rapid uploads to fill disk |
| Distributed upload flood | Medium | Multiple accounts uploading simultaneously |
| Storage exhaustion | Medium | Many maximum-size uploads filling disk over time |
| Memory exhaustion | Low | Streaming chunks prevent full-file buffering, but many concurrent uploads could strain memory |

### 1.5 Metadata Injection

| Threat | Risk | Description |
|--------|------|-------------|
| SQL injection via title/description/tags | High | Malicious SQL in metadata fields |
| XSS via title/description/tags | Medium | Script injection rendered in browser |
| Tag pollution | Low | Flooding tag namespace with garbage |

---

## 2. Existing Mitigations

### 2.1 Extension Allowlist (upload_validators.py:18-22)

**Status: Implemented**

Only 7 extensions are accepted, mapped to 3 categories:

| Category | Allowed Extensions | Size Limit |
|----------|--------------------|------------|
| `config` | `.cfg`, `.hud` | 2 MB |
| `archive` | `.zip`, `.rar` | 50 MB |
| `clip` | `.mp4`, `.avi`, `.mkv` | 500 MB |

All other extensions are rejected with a `400` error. Extension is extracted from `Path(filename).suffix.lower()`, which takes only the final suffix (e.g., `file.pk3.exe` yields `.exe` and is rejected).

### 2.2 Magic Byte Validation (upload_validators.py:105-145)

**Status: Implemented**

Binary files are checked against known signatures:

| Extension | Signature | Offset |
|-----------|-----------|--------|
| `.zip` | `PK\x03\x04` / `PK\x05\x06` / `PK\x07\x08` | 0 |
| `.rar` | `Rar!\x1a\x07` / `Rar!\x1a` | 0 |
| `.mp4` | `ftyp` | 4 |
| `.avi` | `RIFF` + `AVI `/`AVIX` | 0/8 |
| `.mkv` | `\x1a\x45\xdf\xa3` (EBML) | 0 |

Text files (`.cfg`, `.hud`) are validated as UTF-8 with no null bytes (upload_validators.py:148-166).

First 512 bytes are collected during streaming for verification (upload_store.py:207-210). If magic bytes don't match, the file is deleted and a `400` is returned.

### 2.3 Streaming Size Enforcement (upload_store.py:185-205)

**Status: Implemented**

Size is checked during streaming, not after. If `total_bytes > size_limit` at any chunk boundary, the file is immediately deleted and a `413` is returned. This prevents disk exhaustion from oversized uploads.

### 2.4 UUID-Based Storage Paths (upload_store.py:173-178)

**Status: Implemented**

Files are stored as `{root}/{category}/{uuid4_hex}/original{ext}`. The original filename is never used in the filesystem path. UUIDs are generated server-side via `uuid.uuid4().hex` (cryptographically random, 32 hex chars).

### 2.5 SHA-256 Content Hashing (upload_store.py:180, 248)

**Status: Implemented**

A SHA-256 digest is computed during streaming and stored in the DB. This enables duplicate detection and integrity verification.

### 2.6 Filename Sanitization (upload_validators.py:169-215)

**Status: Implemented**

- Unicode NFKC normalization
- Path separators (`/`, `\`) replaced with `_`
- Only `\w`, `\s`, `.`, `-` characters retained
- Collapsed whitespace and underscores
- Truncated to 200 chars (preserving extension when possible)
- Fallback to `"upload"` if empty after sanitization

### 2.7 Path Traversal Prevention on Download (upload_store.py:281-329)

**Status: Implemented**

- `stored_path` is resolved relative to storage root via `(self.root / stored_path).resolve()`
- `resolved.relative_to(self.root)` rejects paths outside the root (raises `403`)
- Symlinks are explicitly rejected (`resolved.is_symlink()` check)
- File existence is verified before returning

### 2.8 Safe Download Headers (uploads.py:374-444)

**Status: Implemented**

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevents browser MIME sniffing |
| `Content-Security-Policy` | `default-src 'none'` (downloads) / `default-src 'none'; media-src 'self'` (MP4) | Blocks script execution in served files |
| `Content-Disposition` | `attachment` (non-MP4) / `inline` (MP4) | Forces download for non-video files |
| `X-Frame-Options` | `DENY` (non-MP4 only) | Prevents framing of downloaded content |

### 2.9 Rate Limiting (uploads.py:25-48)

**Status: Implemented**

- 10 uploads per hour per Discord user ID
- In-memory tracking with hourly cleanup
- Returns `429 Too Many Requests` when exceeded

**Limitation:** In-memory state resets on process restart. Sufficient for single-process deployment.

### 2.10 Authentication (uploads.py:54-67)

**Status: Implemented**

- Upload and delete require session-based Discord OAuth (`_require_user`)
- Session validated via `request.session.get("user")` with `"id"` field check
- Delete operations verify `uploader_discord_id` matches session user (uploads.py:464)
- Browse and download are public (no auth required)

### 2.11 SQL Parameterization (uploads.py:131-153, 216-278)

**Status: Implemented**

All database queries use positional parameters (`$1`, `$2`, ...). No string interpolation of user input into SQL.

### 2.12 Tag Sanitization (uploads.py:165-184)

**Status: Implemented**

- Tags normalized via NFKC, stripped of non-`\w\-\s` characters, lowercased, truncated to 50 chars
- Maximum 10 tags per upload
- Deduplicated before insert
- Inserted with `ON CONFLICT DO NOTHING`

### 2.13 Disk Space Check (upload_store.py:99-128)

**Status: Implemented**

Before accepting an upload, the service checks that at least 2x the category size limit is free on disk. Returns `507 Insufficient Storage` if not. Falls through (logs warning) if the check itself fails.

### 2.14 Storage Permissions (upload_store.py:70-80)

**Status: Implemented**

Storage root is created with `0o700` (owner read/write/execute only). Logs a warning if `chmod` fails.

### 2.15 Failed Upload Cleanup (upload_store.py:264-279)

**Status: Implemented**

On any validation failure, the partially-written file is `unlink()`ed and the parent directory removed if empty. Prevents orphaned files from accumulating.

---

## 3. Gaps and Recommendations

### 3.1 No Archive Extraction Protection

**Risk: Medium** | **Status: Not applicable (currently)**

The system stores `.zip`/`.rar` files as-is without extracting them. Zip bombs and Zip Slip are not a risk as long as files are never extracted server-side. If extraction is added in the future, implement:

- Decompressed size limits (e.g., 10x compressed size cap)
- Path validation on each entry before extraction
- Entry count limits

### 3.2 No CSRF Token on Upload Endpoint

**Risk: Low-Medium** | **Status: Partial mitigation**

The upload endpoint relies on session cookies without explicit CSRF tokens. The multipart `POST` form submission could potentially be triggered cross-site. However:

- Session is `httponly` and uses `SameSite` cookie attribute (via Starlette SessionMiddleware defaults)
- CORS policy restricts cross-origin requests

**Recommendation:** Add `SameSite=Lax` or `SameSite=Strict` explicitly to session cookies if not already set. Consider adding an `X-Requested-With` header check for upload/delete endpoints.

### 3.3 No Per-User Storage Quota

**Risk: Medium** | **Status: Not implemented**

A single user could upload 10 files/hour * 500 MB each = 5 GB/hour. Over time, this could exhaust storage.

**Recommendation:** Add a per-user total storage quota (e.g., 2 GB per user) enforced via a DB query summing `file_size_bytes` for active uploads.

### 3.4 Title/Description Not HTML-Escaped Server-Side

**Risk: Medium** | **Status: Relies on frontend**

Title is truncated to 200 chars, description to 2000 chars, but neither is HTML-escaped server-side. XSS prevention depends on the frontend rendering framework escaping output.

**Recommendation:** Ensure the frontend uses safe rendering (e.g., `textContent` in vanilla JS, or a framework with auto-escaping). Do not use `innerHTML` with user-supplied title/description.

### 3.5 Soft-Delete Does Not Remove Files from Disk

**Risk: Low** | **Status: By design**

`DELETE /api/uploads/{id}` sets `status = 'deleted'` in the DB but does not remove the file from disk. This allows admin recovery but means disk space is not reclaimed.

**Recommendation:** Implement a periodic cleanup job that removes files for uploads deleted more than N days ago.

### 3.6 No Admin Override for Delete

**Risk: Low** | **Status: Not implemented**

Only the original uploader can delete their uploads. There is no admin/moderator override.

**Recommendation:** Add an admin role check (e.g., specific Discord role ID) that allows moderators to delete any upload.

---

## 4. Red-Team Checklist

Use this checklist to verify upload security. Each test should be run against a staging or development instance.

### 4.1 Extension Validation

- [ ] **Double extension bypass:** Upload `config.pk3.exe` — verify rejected (only final `.exe` suffix is checked, not in allowlist)
- [ ] **No extension:** Upload file with no extension — verify rejected with "File must have an extension"
- [ ] **Case variation:** Upload `file.CFG` — verify accepted (extension is lowercased before check)
- [ ] **Null bytes in filename:** Upload `file.cfg%00.exe` — verify sanitizer strips null bytes; extension validation uses `Path().suffix`

### 4.2 Content Validation

- [ ] **Mismatched content-type:** Upload a `.zip` file that is actually a JPEG — verify rejected by magic byte check
- [ ] **EXE with .cfg extension:** Upload a PE binary as `config.cfg` — verify rejected (null bytes fail text validation)
- [ ] **Polyglot file:** Upload a file that is both a valid ZIP and contains HTML — verify `nosniff` and CSP headers prevent execution
- [ ] **Empty file:** Upload 0-byte file — verify rejected with "Empty upload is not allowed"

### 4.3 Size Limits

- [ ] **Oversized config:** Upload 3 MB `.cfg` file — verify `413` returned (limit is 2 MB)
- [ ] **Oversized clip:** Upload 501 MB `.mp4` — verify rejected during streaming before full upload completes
- [ ] **Exact limit:** Upload file at exactly the size limit — verify accepted

### 4.4 Path Traversal

- [ ] **Upload filename traversal:** Submit filename `../../etc/passwd.cfg` — verify stored path uses UUID, not original filename
- [ ] **Download path traversal:** Manually craft a DB record with `stored_path = "../../etc/passwd"` — verify `resolve_download_path` returns `403`
- [ ] **Symlink in storage:** Create symlink in storage directory pointing to `/etc/shadow` — verify rejected by symlink check

### 4.5 Authentication & Authorization

- [ ] **Unauthenticated upload:** `POST /api/uploads` without session cookie — verify `401`
- [ ] **Unauthenticated delete:** `DELETE /api/uploads/{id}` without session — verify `401`
- [ ] **Delete another user's upload:** Authenticate as user A, try to delete user B's upload — verify `403`
- [ ] **Unauthenticated download:** `GET /api/uploads/{id}/download` without session — verify allowed (downloads are public)

### 4.6 Rate Limiting

- [ ] **Basic rate limit:** Upload 10 files in 1 hour — verify 10th succeeds
- [ ] **Rate limit exceeded:** Upload 11th file in same hour — verify `429` returned
- [ ] **Rate limit reset:** Wait 1 hour, upload again — verify accepted
- [ ] **Different users:** Two users each upload 10 files — verify both succeed (limits are per-user)

### 4.7 Metadata Injection

- [ ] **SQL injection in title:** Upload with title `'; DROP TABLE uploads; --` — verify no SQL error (parameterized queries)
- [ ] **SQL injection in tags:** Upload with tags `tag1, '; DROP TABLE upload_tags; --` — verify sanitized
- [ ] **XSS in title:** Upload with title `<script>alert(1)</script>` — verify escaped when rendered in browser
- [ ] **XSS in description:** Upload with description `<img src=x onerror=alert(1)>` — verify escaped when rendered
- [ ] **Oversized title:** Submit 10,000-char title — verify truncated to 200 chars
- [ ] **Oversized description:** Submit 100,000-char description — verify truncated to 2,000 chars
- [ ] **Tag overflow:** Submit 50 comma-separated tags — verify only first 10 stored

### 4.8 Download Security

- [ ] **Content-type sniffing:** Download a `.cfg` file containing `<script>alert(1)</script>` — verify `X-Content-Type-Options: nosniff` header present and browser does not execute
- [ ] **CSP enforcement:** Download `.mp4` file — verify `Content-Security-Policy` header present
- [ ] **Forced download:** Download `.zip` file — verify `Content-Disposition: attachment` forces download
- [ ] **Range request for video:** Send `Range: bytes=0-1024` for `.mp4` — verify `206 Partial Content` response
- [ ] **Invalid range:** Send `Range: bytes=999999999-` for small file — verify `416 Range Not Satisfiable`

### 4.9 Resource Exhaustion

- [ ] **Concurrent uploads:** Upload 10 large files simultaneously from same user — verify rate limiter triggers after 10
- [ ] **Disk space exhaustion:** Fill disk to near capacity, then upload — verify `507 Insufficient Storage` returned
- [ ] **Slowloris-style upload:** Send upload data 1 byte at a time — verify server handles gracefully (FastAPI/uvicorn timeout)

---

## 5. Security Configuration Summary

| Control | Location | Value |
|---------|----------|-------|
| Extension allowlist | `upload_validators.py:18-22` | 7 extensions in 3 categories |
| Magic byte signatures | `upload_validators.py:32-38` | 5 binary formats verified |
| Max file size (config) | `upload_validators.py:26` | 2 MB |
| Max file size (archive) | `upload_validators.py:27` | 50 MB |
| Max file size (clip) | `upload_validators.py:28` | 500 MB |
| Rate limit | `uploads.py:27` | 10 uploads/hour/user |
| Max tags per upload | `uploads.py:176` | 10 |
| Max tag length | `uploads.py:172` | 50 chars |
| Max title length | `uploads.py:127` | 200 chars |
| Max description length | `uploads.py:128` | 2,000 chars |
| Storage permissions | `upload_store.py:76` | `0o700` |
| Disk space safety margin | `upload_store.py:115` | 2x file size |
| Max filename length | `upload_validators.py:169` | 200 chars |

---

*Last updated: 2026-02-16 | Covers upload system as of branch `fix/codebase-review-findings`*
