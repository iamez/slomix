import { render, screen, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { ProximityTeamsPage } from './ProximityTeamsPage';
import type { ProxTeamComparison } from '../lib/types';
import comparisonJson from './__fixtures__/api_proximity_round_round_id_team_comparison.json';
import nullFormJson from './__fixtures__/api_proximity_team_comparison_null_form.json';

// Both recorded forms must satisfy the type: the captured round and the
// all-null answer (which the wire returns for an uncaptured round AND for
// a nonexistent id — measured on rounds 10472 and 99999999, identical).
const comparison = comparisonJson satisfies ProxTeamComparison;
const nullForm = nullFormJson satisfies ProxTeamComparison;

function renderAt(roundId: string, body: unknown) {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL): Promise<Response> => {
    const pathname = String(input).split('?')[0];
    if (pathname === `/api/proximity/round/${roundId}/team-comparison`) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
    }
    return Promise.reject(new Error(`unexpected endpoint: ${pathname}`));
  }));
  return render(
    <QueryClientProvider client={makeQueryClient()}>
      <MemoryRouter initialEntries={[`/proximity/round/${roundId}/teams`]}>
        <Routes>
          <Route path="/proximity/round/:roundId/teams" element={<ProximityTeamsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe('ProximityTeamsPage', () => {
  it('renders both sides and the crossfire execution from the recorded wire', async () => {
    renderAt('11312', comparison);
    // Cohesion, recorded: axis dispersion 416.3 u, allies 464.1 u.
    await waitFor(() => expect(screen.getByText('416.3 u')).toBeInTheDocument());
    expect(screen.getByText('464.1 u')).toBeInTheDocument();
    // Pushes: axis 141, allies 101.
    expect(screen.getByText('141')).toBeInTheDocument();
    expect(screen.getByText('101')).toBeInTheDocument();
    // Crossfire: 7 of 36 chances against allies → 19.4%.
    expect(screen.getByText(/7 of 36 chances/)).toBeInTheDocument();
    expect(screen.getByText('19.4%')).toBeInTheDocument();
  });

  it('renders the all-null form as absence and names the ambiguity', async () => {
    renderAt('10472', nullForm);
    await waitFor(() => expect(screen.getByText(/no proximity capture for this round/)).toBeInTheDocument());
    // The wire cannot tell "uncaptured" from "no such round" — the page
    // must say so rather than assert either.
    expect(screen.getByText(/no round has this id/)).toBeInTheDocument();
    expect(screen.queryByText('dispersion')).not.toBeInTheDocument();
  });

  it('refuses a non-numeric round id without calling the wire', async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);
    render(
      <QueryClientProvider client={makeQueryClient()}>
        <MemoryRouter initialEntries={['/proximity/round/abc/teams']}>
          <Routes>
            <Route path="/proximity/round/:roundId/teams" element={<ProximityTeamsPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByText(/no round named/)).toBeInTheDocument());
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
