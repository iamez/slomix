import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { UploadsPage, UploadDetailPage, preflight } from './UploadsPage';
import type { ResumableInitResponse, UploadCreated, UploadDeleteResponse, UploadDetail, UploadsList } from '../lib/types';
import listJson from './__fixtures__/api_uploads.json';
import detailJson from './__fixtures__/api_uploads_upload_id.json';
import ownerJson from './__fixtures__/api_uploads_upload_id_owner.json';
import tagsJson from './__fixtures__/api_uploads_tags_popular.json';
import createdJson from './__fixtures__/api_uploads_post.json';
import initJson from './__fixtures__/api_uploads_resumable.json';
import finalizedJson from './__fixtures__/api_uploads_resumable_session_id_finalize.json';
import deletedJson from './__fixtures__/api_uploads_upload_id_delete.json';

// The snowflake pin: uploader_discord_id is a STRING on the wire — an
// 18-digit id loses its last digit as a JS number. If a backend change
// ever ships it as a number again, these satisfies lines fail.
const list = listJson satisfies UploadsList;
const detail = detailJson satisfies UploadDetail;
const owner = ownerJson satisfies UploadDetail;
const created = createdJson satisfies UploadCreated;
const init = initJson satisfies ResumableInitResponse;
const finalized = finalizedJson satisfies UploadCreated;
const deleted = deletedJson satisfies UploadDeleteResponse;

type Stub = { body?: unknown; status?: number; headers?: Record<string, string> };
function stub(map: Record<string, Stub | ((init?: RequestInit) => Stub)>) {
  const spy = vi.fn((input: RequestInfo | URL, reqInit?: RequestInit): Promise<Response> => {
    const pathname = String(input).split('?')[0];
    const method = reqInit?.method ?? 'GET';
    const raw = map[`${method} ${pathname}`] ?? map[pathname];
    if (raw === undefined) return Promise.reject(new Error(`unexpected: ${method} ${pathname}`));
    const hit = typeof raw === 'function' ? raw(reqInit) : raw;
    const status = hit.status ?? 200;
    return Promise.resolve({
      ok: status < 400, status,
      headers: { get: (k: string) => hit.headers?.[k] ?? null },
      json: () => Promise.resolve(hit.body ?? { detail: 'x' }),
    } as unknown as Response);
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}

/** XMLHttpRequest double for the single-shot path. */
class FakeXhr {
  static last: FakeXhr | null = null;
  static answer: { status: number; body: unknown } = { status: 200, body: created };
  url = ''; headers: Record<string, string> = {}; sent: FormData | null = null; withCredentials = false; responseType = '';
  upload = { onprogress: null as null | ((e: { lengthComputable: boolean; loaded: number; total: number }) => void) };
  onload: null | (() => void) = null; onerror: null | (() => void) = null; onabort: null | (() => void) = null;
  status = 0; responseText = '';
  constructor() { FakeXhr.last = this; }
  open(_m: string, url: string) { this.url = url; }
  setRequestHeader(k: string, v: string) { this.headers[k] = v; }
  send(body: FormData) {
    this.sent = body;
    setTimeout(() => {
      this.upload.onprogress?.({ lengthComputable: true, loaded: 40, total: 83 });
      this.status = FakeXhr.answer.status; this.responseText = JSON.stringify(FakeXhr.answer.body);
      this.onload?.();
    }, 0);
  }
  abort() { this.onabort?.(); }
}

const BASE = {
  '/api/uploads': { body: list },
  '/api/uploads/tags/popular': { body: tagsJson },
};

function renderList() {
  return render(
    <QueryClientProvider client={makeQueryClient()}>
      <MemoryRouter initialEntries={['/uploads']}>
        <UploadsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function renderDetail(id: string) {
  return render(
    <QueryClientProvider client={makeQueryClient()}>
      <MemoryRouter initialEntries={[`/uploads/${id}`]}>
        <Routes>
          <Route path="/uploads/:uploadId" element={<UploadDetailPage />} />
          <Route path="/uploads" element={<div>the shelf again</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const cfg = (size = 83, name = 'sentinel.cfg') => new File([new Uint8Array(size)], name);

afterEach(() => { vi.unstubAllGlobals(); FakeXhr.answer = { status: 200, body: created }; FakeXhr.last = null; });

describe('UploadsPage', () => {
  it('renders the recorded shelf with sizes, uploaders and counts', async () => {
    stub({ ...BASE, [`/api/uploads/${detail.id}`]: { body: detail } });
    renderList();
    await waitFor(() => expect(screen.getByText(`${list.total.toLocaleString('en-US')} files`)).toBeInTheDocument());
    const first = list.items[0];
    expect(screen.getByText(first.title || first.filename)).toBeInTheDocument();
    expect(screen.getAllByText(/downloads/).length).toBeGreaterThan(0);
  });

  it('preflight speaks the allowlist and the per-category limit before any request', () => {
    expect(preflight(cfg(83, 'x.exe'))).toBe("Unsupported file type '.exe'. Allowed: .cfg .hud .zip .rar .mp4 .avi .mkv");
    expect(preflight(cfg(0))).toBe('Empty upload is not allowed.');
    expect(preflight(cfg(3 * 1024 * 1024))).toMatch(/over the 2 MB limit for config files/);
    expect(preflight(cfg(83))).toBeNull();
    expect(preflight(cfg(60 * 1024 * 1024, 'big.zip'))).toMatch(/over the 50 MB limit for archive files/);
    expect(preflight(cfg(60 * 1024 * 1024, 'big.mp4'))).toBeNull();
  });

  it('an unsupported file disables upload and nothing is sent', async () => {
    const spy = stub(BASE);
    vi.stubGlobal('XMLHttpRequest', FakeXhr);
    renderList();
    const input = await screen.findByLabelText('file');
    fireEvent.change(input, { target: { files: [cfg(83, 'virus.exe')] } });
    expect(screen.getByText(/Unsupported file type '\.exe'/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'upload' })).toBeDisabled();
    expect(FakeXhr.last).toBeNull();
    expect(spy.mock.calls.some((c) => c[1]?.method === 'POST')).toBe(false);
  });

  it('a small file goes in one XHR POST with the form fields, shows progress, then links the new upload', async () => {
    const spy = stub(BASE);
    vi.stubGlobal('XMLHttpRequest', FakeXhr);
    renderList();
    fireEvent.change(await screen.findByLabelText('file'), { target: { files: [cfg()] } });
    fireEvent.change(screen.getByLabelText('title'), { target: { value: 'my cfg' } });
    fireEvent.change(screen.getByLabelText('tags'), { target: { value: 'e2e' } });
    fireEvent.change(screen.getByLabelText('retention'), { target: { value: '30' } });
    expect(screen.getByText(/in one go/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'upload' }));
    await waitFor(() => expect(screen.getByText(/open it →/)).toBeInTheDocument());
    const xhr = FakeXhr.last;
    if (!xhr) throw new Error('no XHR was opened');
    expect(xhr.url).toBe('/api/uploads');
    expect(xhr.headers['X-Requested-With']).toBe('XMLHttpRequest');
    expect(xhr.sent?.get('title')).toBe('my cfg');
    expect(xhr.sent?.get('tags')).toBe('e2e');
    expect(xhr.sent?.get('retention_days')).toBe('30');
    expect((xhr.sent?.get('file') as File).name).toBe('sentinel.cfg');
    expect(screen.getByText(/open it →/).closest('a')).toHaveAttribute('href', `/uploads/${created.upload_id}`);
    // The shelf is refetched after the upload.
    await waitFor(() => expect(spy.mock.calls.filter((c) => String(c[0]).split('?')[0] === '/api/uploads').length).toBeGreaterThanOrEqual(2));
  });

  it("a 413/429/401 on the single-shot path renders the backend's words or the sign-in prompt", async () => {
    stub(BASE);
    vi.stubGlobal('XMLHttpRequest', FakeXhr);
    FakeXhr.answer = { status: 429, body: { detail: 'Upload rate limit exceeded (10/hour)' } };
    renderList();
    fireEvent.change(await screen.findByLabelText('file'), { target: { files: [cfg()] } });
    fireEvent.click(screen.getByRole('button', { name: 'upload' }));
    await waitFor(() => expect(screen.getByText(/Upload rate limit exceeded \(10\/hour\)/)).toBeInTheDocument());
    FakeXhr.answer = { status: 401, body: {} };
    fireEvent.click(screen.getByRole('button', { name: 'upload' }));
    await waitFor(() => expect(screen.getByText(/sign in with CONNECT ID to upload/)).toBeInTheDocument());
  });

  it('a file over the threshold takes the chunked path: init, PATCHes, finalize', async () => {
    const session = `/api/uploads/resumable/${init.session_id}`;
    const spy = stub({
      ...BASE,
      'POST /api/uploads/resumable': { body: { ...init, chunk_size: 32 * 1024 * 1024 } },
      [`PATCH ${session}`]: (reqInit) => {
        const offset = Number((reqInit?.headers as Record<string, string>)['Upload-Offset']);
        const size = (reqInit?.body as Blob).size;
        return { status: 204, headers: { 'Upload-Offset': String(offset + size) } };
      },
      [`POST ${session}/finalize`]: { body: finalized },
    });
    vi.stubGlobal('XMLHttpRequest', FakeXhr);
    renderList();
    const big = new File([new Uint8Array(51 * 1024 * 1024)], 'big.mp4');
    fireEvent.change(await screen.findByLabelText('file'), { target: { files: [big] } });
    expect(screen.getByText(/in chunks/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'upload' }));
    await waitFor(() => expect(screen.getByText(/open it →/)).toBeInTheDocument(), { timeout: 15000 });
    expect(FakeXhr.last).toBeNull(); // never the single-shot path
    const patches = spy.mock.calls.filter((c) => c[1]?.method === 'PATCH');
    expect(patches.length).toBe(2); // 51 MiB in 32 MiB chunks
    expect(spy.mock.calls.some((c) => String(c[0]).endsWith('/finalize'))).toBe(true);
  }, 20000);

  it('cancel during a chunked upload aborts the session and says so', async () => {
    const session = `/api/uploads/resumable/${init.session_id}`;
    let released: (() => void) | null = null;
    const spy = stub({
      ...BASE,
      'POST /api/uploads/resumable': { body: { ...init, chunk_size: 32 * 1024 * 1024 } },
      [`DELETE ${session}`]: { body: { success: true } },
    });
    // The first PATCH hangs until the test releases it — long enough to click cancel.
    spy.mockImplementation((input: RequestInfo | URL, reqInit?: RequestInit) => {
      const pathname = String(input).split('?')[0];
      const method = reqInit?.method ?? 'GET';
      if (method === 'PATCH') {
        return new Promise<Response>((_resolve, reject) => {
          released = () => { reject(new DOMException('aborted', 'AbortError')); };
          reqInit?.signal?.addEventListener('abort', () => { released?.(); });
        });
      }
      if (pathname === '/api/uploads/resumable' && method === 'POST') return Promise.resolve({ ok: true, status: 200, headers: { get: () => null }, json: () => Promise.resolve({ ...init, chunk_size: 32 * 1024 * 1024 }) } as unknown as Response);
      if (pathname === session && method === 'DELETE') return Promise.resolve({ ok: true, status: 200, headers: { get: () => null }, json: () => Promise.resolve({ success: true }) } as unknown as Response);
      if (pathname === '/api/uploads') return Promise.resolve({ ok: true, status: 200, headers: { get: () => null }, json: () => Promise.resolve(list) } as unknown as Response);
      if (pathname === '/api/uploads/tags/popular') return Promise.resolve({ ok: true, status: 200, headers: { get: () => null }, json: () => Promise.resolve(tagsJson) } as unknown as Response);
      return Promise.reject(new Error(`unexpected: ${method} ${pathname}`));
    });
    renderList();
    const big = new File([new Uint8Array(51 * 1024 * 1024)], 'big.mp4');
    fireEvent.change(await screen.findByLabelText('file'), { target: { files: [big] } });
    fireEvent.click(screen.getByRole('button', { name: 'upload' }));
    const cancel = await screen.findByRole('button', { name: 'cancel' });
    fireEvent.click(cancel);
    await waitFor(() => expect(screen.getByText(/upload cancelled/)).toBeInTheDocument());
    await waitFor(() => expect(spy.mock.calls.some((c) => c[1]?.method === 'DELETE' && String(c[0]) === session)).toBe(true));
  }, 20000);

  it('the detail renders links as links; a stranger sees no delete', async () => {
    stub({ ...BASE, [`/api/uploads/${detail.id}`]: { body: detail } });
    renderDetail(detail.id);
    await waitFor(() => expect(screen.getByText('download →')).toBeInTheDocument());
    // A download is a LINK the browser follows, never a fetch.
    expect(screen.getByText('download →').closest('a')).toHaveAttribute('href', detail.download_url);
    expect(detail.can_delete).toBe(false);
    expect(screen.queryByRole('button', { name: /delete/ })).toBeNull();
  });

  it('the owner deletes in two clicks, the list is refetched and the shelf is shown', async () => {
    const spy = stub({
      ...BASE,
      [`/api/uploads/${owner.id}`]: { body: owner },
      [`DELETE /api/uploads/${owner.id}`]: { body: deleted },
    });
    renderDetail(owner.id);
    const first = await screen.findByRole('button', { name: /^delete/ });
    expect(spy.mock.calls.some((c) => c[1]?.method === 'DELETE')).toBe(false);
    fireEvent.click(first);
    expect(screen.getByText(/this cannot be undone/)).toBeInTheDocument();
    // One click is not a delete.
    expect(spy.mock.calls.some((c) => c[1]?.method === 'DELETE')).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'keep' }));
    expect(screen.queryByText(/this cannot be undone/)).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /^delete/ }));
    fireEvent.click(screen.getByRole('button', { name: 'really delete' }));
    await waitFor(() => expect(screen.getByText('the shelf again')).toBeInTheDocument());
    const del = spy.mock.calls.find((c) => c[1]?.method === 'DELETE');
    expect(String(del?.[0])).toBe(`/api/uploads/${owner.id}`);
    expect((del?.[1]?.headers as Record<string, string>)['X-Requested-With']).toBe('XMLHttpRequest');
  });

  it("a refused delete shows the backend's words and disarms", async () => {
    stub({
      ...BASE,
      [`/api/uploads/${owner.id}`]: { body: owner },
      [`DELETE /api/uploads/${owner.id}`]: { status: 403, body: { detail: 'Not authorized to delete this upload' } },
    });
    renderDetail(owner.id);
    fireEvent.click(await screen.findByRole('button', { name: /^delete/ }));
    fireEvent.click(screen.getByRole('button', { name: 'really delete' }));
    await waitFor(() => expect(screen.getByText(/Not authorized to delete this upload/)).toBeInTheDocument());
    expect(screen.queryByText(/this cannot be undone/)).toBeNull();
    cleanup();
  });
});
