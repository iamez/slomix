import { render, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { UploadsPage, UploadDetailPage } from './UploadsPage';
import type { UploadDetail, UploadsList } from '../lib/types';
import listJson from './__fixtures__/api_uploads.json';
import detailJson from './__fixtures__/api_uploads_upload_id.json';
import tagsJson from './__fixtures__/api_uploads_tags_popular.json';

// The snowflake pin: uploader_discord_id is a STRING on the wire — an
// 18-digit id loses its last digit as a JS number. If a backend change
// ever ships it as a number again, these satisfies lines fail.
const list = listJson satisfies UploadsList;
const detail = detailJson satisfies UploadDetail;

function stub() {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL): Promise<Response> => {
    const pathname = String(input).split('?')[0];
    const body = pathname === '/api/uploads' ? list
      : pathname === '/api/uploads/tags/popular' ? tagsJson
      : pathname.startsWith('/api/uploads/') ? detail
      : undefined;
    if (body === undefined) return Promise.reject(new Error(`unexpected: ${pathname}`));
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
  }));
}

afterEach(() => vi.unstubAllGlobals());

describe('UploadsPage', () => {
  it('renders the recorded shelf with sizes, uploaders and counts', async () => {
    stub();
    render(
      <QueryClientProvider client={makeQueryClient()}>
        <MemoryRouter initialEntries={['/uploads']}>
          <UploadsPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByText(`${list.total.toLocaleString('en-US')} files`)).toBeInTheDocument());
    const first = list.items[0];
    expect(screen.getByText(first.title || first.filename)).toBeInTheDocument();
    expect(screen.getAllByText(/downloads/).length).toBeGreaterThan(0);
  });

  it('the detail renders links as links and names the uploader-owned state honestly', async () => {
    stub();
    render(
      <QueryClientProvider client={makeQueryClient()}>
        <MemoryRouter initialEntries={[`/uploads/${detail.id}`]}>
          <Routes>
            <Route path="/uploads/:uploadId" element={<UploadDetailPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByText('download →')).toBeInTheDocument());
    // A download is a LINK the browser follows, never a fetch.
    expect(screen.getByText('download →').closest('a')).toHaveAttribute('href', detail.download_url);
    if (detail.can_delete) {
      expect(screen.getByText(/you uploaded this/)).toBeInTheDocument();
    }
  });
});
