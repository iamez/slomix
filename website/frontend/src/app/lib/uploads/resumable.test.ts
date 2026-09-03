import { afterEach, describe, expect, it, vi } from 'vitest';
import { resumableUpload, RESUMABLE_THRESHOLD } from './resumable';
import type { ResumableInitResponse, UploadCreated } from '../types';
import initJson from '../../pages/__fixtures__/api_uploads_resumable.json';
import finalizeJson from '../../pages/__fixtures__/api_uploads_resumable_session_id_finalize.json';

const init = initJson satisfies ResumableInitResponse;
const finalized = finalizeJson satisfies UploadCreated;
const SESSION = `/api/uploads/resumable/${init.session_id}`;

type Call = { url: string; method: string; offset: string | null; size: number };

function res(status: number, headers: Record<string, string> = {}, body?: unknown): Response {
  return {
    ok: status >= 200 && status < 300, status,
    headers: { get: (k: string) => headers[k] ?? headers[k.toLowerCase()] ?? null },
    json: () => Promise.resolve(body ?? { detail: 'x' }),
  } as unknown as Response;
}

/** A fetch double that plays a script of PATCH answers in order and records
 *  every call. Non-PATCH routes are answered from the recorded fixtures. */
function wire(patchScript: ((offset: number, size: number, n: number) => Response)[], opts: { head?: number | null; chunk?: number } = {}) {
  const calls: Call[] = [];
  let n = 0;
  const spy = vi.fn(async (input: RequestInfo | URL, reqInit?: RequestInit): Promise<Response> => {
    const url = String(input);
    const method = reqInit?.method ?? 'GET';
    const headers = (reqInit?.headers ?? {}) as Record<string, string>;
    const body = reqInit?.body as Blob | undefined;
    calls.push({ url, method, offset: headers['Upload-Offset'] ?? null, size: body instanceof Blob ? body.size : 0 });
    if (url === '/api/uploads/resumable' && method === 'POST') return res(200, {}, { ...init, chunk_size: opts.chunk ?? init.chunk_size });
    if (url === SESSION && method === 'PATCH') {
      const step = patchScript[Math.min(n, patchScript.length - 1)];
      n += 1;
      return step(Number(headers['Upload-Offset']), body instanceof Blob ? body.size : 0, n);
    }
    if (url === SESSION && method === 'HEAD') return opts.head === null ? res(404) : res(200, { 'Upload-Offset': String(opts.head ?? 0) });
    if (url === SESSION && method === 'DELETE') return res(200, {}, { success: true });
    if (url === `${SESSION}/finalize` && method === 'POST') return res(200, {}, finalized);
    throw new Error(`unexpected ${method} ${url}`);
  });
  vi.stubGlobal('fetch', spy);
  return { calls, spy };
}

const noSleep = () => Promise.resolve();
const file = (size: number, name = 'clip.mp4') => new File([new Uint8Array(size)], name);

afterEach(() => vi.unstubAllGlobals());

describe('resumableUpload', () => {
  it('threshold is the legacy 50 MiB', () => {
    expect(RESUMABLE_THRESHOLD).toBe(50 * 1024 * 1024);
  });

  it('inits, PATCHes each chunk at the server-advanced offset, reports progress, finalizes', async () => {
    const { calls } = wire([(o, s) => res(204, { 'Upload-Offset': String(o + s) })], { chunk: 4 });
    const seen: number[] = [];
    const out = await resumableUpload(file(10), { title: 't' }, { onProgress: (sent) => { seen.push(sent); }, sleep: noSleep });
    expect(out).toEqual(finalized);
    const patches = calls.filter((c) => c.method === 'PATCH');
    expect(patches.map((c) => [c.offset, c.size])).toEqual([['0', 4], ['4', 4], ['8', 2]]);
    expect(seen).toEqual([4, 8, 10]);
    expect(calls.at(-1)).toMatchObject({ url: `${SESSION}/finalize`, method: 'POST' });
    // The init body carries what the server's ResumableInit expects.
    const initCall = calls[0];
    expect(initCall).toMatchObject({ url: '/api/uploads/resumable', method: 'POST' });
  });

  it('a 409 resyncs to the server offset from the header, then continues', async () => {
    const { calls } = wire([
      (o, s) => res(204, { 'Upload-Offset': String(o + s) }),
      // The second chunk: the server says it is already further along.
      () => res(409, { 'Upload-Offset': '8' }, { detail: 'Offset mismatch: server is at 8' }),
      (o, s) => res(204, { 'Upload-Offset': String(o + s) }),
    ], { chunk: 4 });
    await resumableUpload(file(10), {}, { sleep: noSleep });
    const patches = calls.filter((c) => c.method === 'PATCH');
    expect(patches.map((c) => c.offset)).toEqual(['0', '4', '8']);
  });

  it('a 409 without the header reads the offset out of the sentence', async () => {
    const { calls } = wire([
      () => res(409, {}, { detail: 'Offset mismatch: server is at 6' }),
      (o, s) => res(204, { 'Upload-Offset': String(o + s) }),
    ], { chunk: 4 });
    await resumableUpload(file(10), {}, { sleep: noSleep });
    expect(calls.filter((c) => c.method === 'PATCH').map((c) => c.offset)).toEqual(['0', '6']);
  });

  it('a 5xx retries after a HEAD resync; the server kept the bytes', async () => {
    const { calls } = wire([
      () => res(503, {}, { detail: 'busy' }),
      (o, s) => res(204, { 'Upload-Offset': String(o + s) }),
    ], { chunk: 4, head: 4 });
    await resumableUpload(file(8), {}, { sleep: noSleep });
    const methods = calls.map((c) => c.method);
    expect(methods.filter((m) => m === 'HEAD').length).toBe(1);
    // After HEAD said 4, the retry starts at 4, not 0.
    expect(calls.filter((c) => c.method === 'PATCH').map((c) => c.offset)).toEqual(['0', '4', '8'].slice(0, 2));
  });

  it('stalls out after three non-advancing rounds and aborts the session', async () => {
    const { calls } = wire([() => res(409, { 'Upload-Offset': '0' }, { detail: 'Offset mismatch: server is at 0' })], { chunk: 4 });
    await expect(resumableUpload(file(8), {}, { sleep: noSleep })).rejects.toThrow(/Upload stalled/);
    expect(calls.some((c) => c.method === 'DELETE' && c.url === SESSION)).toBe(true);
    expect(calls.some((c) => c.url.endsWith('/finalize'))).toBe(false);
  });

  it('a 4xx verdict other than 409 is thrown with the backend words, no retry', async () => {
    const { calls } = wire([() => res(413, {}, { detail: 'Chunk too large' })], { chunk: 4 });
    await expect(resumableUpload(file(8), {}, { sleep: noSleep })).rejects.toMatchObject({ status: 413, detail: 'Chunk too large' });
    expect(calls.filter((c) => c.method === 'PATCH').length).toBe(1);
  });

  it('an aborted signal stops the loop, DELETEs the session and rejects with AbortError', async () => {
    const ctl = new AbortController();
    const { calls } = wire([(o, s) => { ctl.abort(); return res(204, { 'Upload-Offset': String(o + s) }); }], { chunk: 4 });
    await expect(resumableUpload(file(12), {}, { signal: ctl.signal, sleep: noSleep })).rejects.toMatchObject({ name: 'AbortError' });
    expect(calls.filter((c) => c.method === 'PATCH').length).toBe(1);
    expect(calls.some((c) => c.method === 'DELETE' && c.url === SESSION)).toBe(true);
    expect(calls.some((c) => c.url.endsWith('/finalize'))).toBe(false);
  });

  it('never puts a session id the server did not mint into a URL', async () => {
    const spy = vi.fn(async (input: RequestInfo | URL): Promise<Response> => {
      if (String(input) === '/api/uploads/resumable') return res(200, {}, { ...init, session_id: '../etc/passwd' });
      throw new Error(`unexpected ${String(input)}`);
    });
    vi.stubGlobal('fetch', spy);
    await expect(resumableUpload(file(8), {}, { sleep: noSleep })).rejects.toThrow(/invalid upload session id/);
    expect(spy).toHaveBeenCalledTimes(1);
  });
});
