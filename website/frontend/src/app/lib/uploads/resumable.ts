/**
 * The resumable uploader — a port of website/js/uploads.js:347-416 with
 * types and an AbortSignal (docs/design/08 §uploads: "add AbortSignal —
 * today leaving the page lets the chunk loop run on").
 *
 * Protocol (website/backend/routers/uploads.py:337-457, measured live):
 *  - POST /api/uploads/resumable {filename, size, …}  → {session_id, offset: 0, chunk_size, category}
 *  - PATCH …/{session_id} with header Upload-Offset and the raw chunk → 204 + Upload-Offset
 *    409 "Offset mismatch: server is at N" carries Upload-Offset too → resync
 *  - HEAD …/{session_id} → Upload-Offset / Upload-Length (legacy never used it;
 *    here it resyncs after a network error, which the 409 path cannot see)
 *  - POST …/{session_id}/finalize → the same body as the single-shot upload
 *  - DELETE …/{session_id} → {success: true}, idempotent (cancel)
 */
import type { paths } from '../../../api/generated/openapi.d';
import { ApiError, apiErrorFrom, apiPost, fillPath } from '../api';
import type { ResumableInitResponse, UploadCreated } from '../types';

/** Above this the page takes the chunked path; at or below, one POST with
 *  XHR progress (legacy uploads.js:341, kept — the single-shot POST is the
 *  one that accepts a poster, so small clips keep that door). */
export const RESUMABLE_THRESHOLD = 50 * 1024 * 1024;
export const DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024;
const MAX_RETRIES = 3;
const STALL_LIMIT = 3;
const SESSION_ID_RE = /^[0-9a-f]{32}$/;

// Typed path literals: a typo here fails the build, like every apiGet path.
const SESSION_PATH = '/api/uploads/resumable/{session_id}' satisfies keyof paths;
const FINALIZE_PATH = '/api/uploads/resumable/{session_id}/finalize' satisfies keyof paths;

export interface UploadMeta {
  title?: string;
  description?: string;
  tags?: string;
  retention_days?: number | null;
}

export interface ResumableOptions {
  onProgress?: (sent: number, total: number) => void;
  signal?: AbortSignal;
  /** Test hook: the backoff sleeper (500 ms × attempt in production). */
  sleep?: (ms: number) => Promise<void>;
}

const CSRF = { 'X-Requested-With': 'XMLHttpRequest' } as const;

function abortError(): DOMException {
  return new DOMException('upload aborted', 'AbortError');
}

function offsetFromHeader(res: Response): number | null {
  const raw = res.headers.get('Upload-Offset');
  if (raw == null) return null;
  const n = Number(raw);
  return Number.isInteger(n) && n >= 0 ? n : null;
}

/** The server's offset after a 409 — from the header, else the first
 *  integer in its own sentence ("Offset mismatch: server is at 83"). */
function offsetFromConflict(res: Response, err: ApiError): number | null {
  const fromHeader = offsetFromHeader(res);
  if (fromHeader != null) return fromHeader;
  const m = err.detail?.match(/\d+/);
  return m ? Number(m[0]) : null;
}

async function headOffset(url: string, signal?: AbortSignal): Promise<number | null> {
  try {
    // nosemgrep
    const res = await fetch(url, { method: 'HEAD', credentials: 'same-origin', signal });
    return res.ok ? offsetFromHeader(res) : null;
  } catch {
    return null;
  }
}

async function abortSession(url: string): Promise<void> {
  try {
    // nosemgrep
    await fetch(url, { method: 'DELETE', credentials: 'same-origin', headers: CSRF });
  } catch { /* best effort — the server sweeps stale sessions after 24 h */ }
}

export async function resumableUpload(file: File, meta: UploadMeta, options: ResumableOptions = {}): Promise<UploadCreated> {
  const { signal, onProgress } = options;
  const sleep = options.sleep ?? ((ms: number) => new Promise<void>((r) => { setTimeout(r, ms); }));
  if (signal?.aborted) throw abortError();

  const init = await apiPost('/api/uploads/resumable', {
    filename: file.name, size: file.size,
    title: meta.title ?? '', description: meta.description ?? '', tags: meta.tags ?? '',
    retention_days: meta.retention_days ?? null,
  }) as ResumableInitResponse;

  // A session id goes into a URL: it must be exactly what the server mints
  // (32 hex chars), never something a response could steer.
  if (typeof init.session_id !== 'string' || !SESSION_ID_RE.test(init.session_id)) {
    throw new Error('the server answered with an invalid upload session id');
  }
  const url = fillPath(SESSION_PATH, { session_id: init.session_id });
  const chunkSize = init.chunk_size > 0 ? init.chunk_size : DEFAULT_CHUNK_SIZE;
  let offset = typeof init.offset === 'number' && init.offset >= 0 ? init.offset : 0;
  let stalls = 0;

  // Cancel must reach the UI at once: the session DELETE is fire-and-forget
  // (the server sweeps stale sessions after 24 h anyway) — awaiting it on a
  // stalled network would hold the "cancelled" state hostage (Copilot on #896).
  const bail = (): never => { void abortSession(url); throw abortError(); };

  while (offset < file.size) {
    if (signal?.aborted) bail();
    const before = offset;
    const blob = file.slice(offset, Math.min(offset + chunkSize, file.size));
    let attempt = 0;
    for (;;) {
      attempt += 1;
      try {
        // nosemgrep
        const res = await fetch(url, {
          method: 'PATCH', credentials: 'same-origin', signal,
          headers: { ...CSRF, 'Upload-Offset': String(offset), 'Content-Type': 'application/offset+octet-stream' },
          body: blob,
        });
        if (res.status === 204 || res.ok) {
          offset = offsetFromHeader(res) ?? offset + blob.size;
          break;
        }
        const err = await apiErrorFrom(res, url);
        if (res.status === 409) {
          const server = offsetFromConflict(res, err);
          if (server != null) { offset = server; break; } // resync, then loop re-slices
        }
        throw err;
      } catch (e) {
        if (signal?.aborted || (e instanceof DOMException && e.name === 'AbortError')) bail();
        if (e instanceof ApiError) {
          if (e.status === 0 || e.status >= 500) {
            if (attempt >= MAX_RETRIES) throw e;
          } else {
            throw e; // 4xx other than 409 is the server's verdict
          }
        } else if (attempt >= MAX_RETRIES) {
          throw e;
        }
        // Network error or 5xx: the server may have kept bytes we never
        // heard about — ask it where it is before sending again.
        await sleep(500 * attempt);
        const server = await headOffset(url, signal);
        if (server != null) offset = server;
      }
    }
    if (offset <= before) {
      stalls += 1;
      if (stalls >= STALL_LIMIT) {
        await abortSession(url);
        throw new Error('Upload stalled — server offset is not advancing');
      }
    } else {
      stalls = 0;
    }
    onProgress?.(offset, file.size);
  }

  if (signal?.aborted) bail();
  return await apiPost(FINALIZE_PATH, {}, { pathParams: { session_id: init.session_id } }) as UploadCreated;
}
