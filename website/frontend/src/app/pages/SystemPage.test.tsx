import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { SystemPage } from './SystemPage';
import systemOverview from './__fixtures__/api_system_overview.json';

/** Rendered against the RECORDED /api/system/overview response — every
 * asserted string is something the live backend really said. */

function testClient(): QueryClient {
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return client;
}

function renderPage() {
  return render(
    <QueryClientProvider client={testClient()}>
      <MemoryRouter>
        <SystemPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('SystemPage', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the chain, stage facts and the linkage card from recorded data', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const pathname = String(input).split('?')[0];
      if (pathname !== '/api/system/overview') {
        return Promise.reject(new Error(`SystemPage called an unexpected endpoint: ${pathname}`));
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve(systemOverview) } as Response);
    }));
    renderPage();

    // overall: "ok" in the recording.
    await waitFor(() => expect(screen.getByText('Everything is running')).toBeInTheDocument());

    // All five stages of the chain, with their recorded summaries.
    for (const label of ['Game server', 'Lua capture', 'Parser', 'Smart Stats', 'Website API']) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.getByText('0/16 players on te_escape2')).toBeInTheDocument();
    expect(screen.getByText('64 rounds parsed in the last 7 days')).toBeInTheDocument();

    // Stage facts — legacy _stageFacts carried over (session id, KIS rows).
    expect(screen.getByText('session 152')).toBeInTheDocument();
    expect(screen.getByText('604 KIS rows')).toBeInTheDocument();

    // Linkage: 72/1032 unlinked = 7.0%, no breaches in the recording.
    expect(screen.getByText('7.0%')).toBeInTheDocument();
    expect(screen.getByText('1032')).toBeInTheDocument();
    expect(screen.getByText('no thresholds breached')).toBeInTheDocument();
  });

  it('states that the API not answering IS the status', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: false, status: 503 } as Response)));
    renderPage();
    await waitFor(() =>
      expect(screen.getByText('The website API did not answer.')).toBeInTheDocument(),
    );
  });
});
