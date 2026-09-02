import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { AvailabilityPage } from './AvailabilityPage';
import type {
  AvailabilityAccess, AvailabilityOverview, BetsMarketCurrent, PlanningToday,
  PromotionCampaign, PromotionPreferences,
} from '../lib/types';
import accessAnon from './__fixtures__/api_availability_access.json';
import accessAuthed from './__fixtures__/api_availability_access_authed_form.json';
import weekAnon from './__fixtures__/api_availability.json';
import weekAuthed from './__fixtures__/api_availability_authed_form.json';
import planningToday from './__fixtures__/api_planning_today.json';
import marketCurrent from './__fixtures__/api_bets_market_current.json';
import promoPrefs from './__fixtures__/api_availability_promotion_preferences.json';
import promoCampaign from './__fixtures__/api_availability_promotions_campaign.json';

// Both recorded auth tiers of access and of the week satisfy their types.
const anonAccess = accessAnon satisfies AvailabilityAccess;
const authedAccess = accessAuthed satisfies AvailabilityAccess;
const anonWeek = weekAnon satisfies AvailabilityOverview;
const authedWeek = weekAuthed satisfies AvailabilityOverview;
const planning = planningToday satisfies PlanningToday;
const market = marketCurrent satisfies BetsMarketCurrent;
const prefs = promoPrefs satisfies PromotionPreferences;
const campaign = promoCampaign satisfies PromotionCampaign;

type Stub = { body?: unknown; status?: number };
function stub(map: Record<string, Stub>) {
  const spy = vi.fn((input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const pathname = String(input).split('?')[0];
    const key = `${init?.method ?? 'GET'} ${pathname}`;
    const hit = map[key] ?? map[pathname];
    if (hit === undefined) return Promise.reject(new Error(`unexpected: ${key}`));
    const status = hit.status ?? 200;
    return Promise.resolve({
      ok: status < 400, status, json: () => Promise.resolve(hit.body ?? { detail: 'x' }),
    } as Response);
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}

function renderPage() {
  return render(
    <QueryClientProvider client={makeQueryClient()}>
      <MemoryRouter initialEntries={['/availability']}>
        <AvailabilityPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe('AvailabilityPage', () => {
  it('anonymous: counts render, gated panels stay quiet, and a write asks for sign-in', async () => {
    const spy = stub({
      '/api/availability/access': { body: anonAccess },
      '/api/availability': { body: anonWeek },
      '/api/planning/today': { body: planning },
      '/api/bets/market/current': { body: market },
      'POST /api/availability': { status: 401 },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText(/browsing anonymously/)).toBeInTheDocument());
    // Recorded week: seven day rows with zero counts still render as rows.
    expect(screen.getAllByText(/^2026-09-0/).length).toBeGreaterThanOrEqual(7);
    // Mock planning data is NAMED, not hidden (recorded is_mock: true).
    expect(screen.getByText(/MOCK planning data/)).toBeInTheDocument();
    expect(screen.getByText(/no market is open right now/)).toBeInTheDocument();
    // Anonymous never calls the gated endpoints.
    const urls = spy.mock.calls.map((c) => String(c[0]));
    for (const gated of ['/settings', '/subscriptions', '/promotion-preferences', '/promotions/campaign', '/bets/wallet']) {
      expect(urls.some((u) => u.includes(gated)), `anonymous called ${gated}`).toBe(false);
    }
    // The write fails closed with the sign-in prompt, not a dead error.
    fireEvent.click(screen.getAllByRole('button', { name: 'looking' })[0]);
    await waitFor(() => expect(screen.getByText(/sign in with CONNECT ID to submit/)).toBeInTheDocument());
  });

  it('authenticated-but-unlinked: the 403 renders as the backend-worded state', { timeout: 20000 }, async () => {
    stub({
      '/api/availability/access': { body: authedAccess },
      '/api/availability': { body: authedWeek },
      '/api/planning/today': { body: planning },
      '/api/bets/market/current': { body: market },
      '/api/bets/wallet': { status: 500 },
      '/api/availability/promotions/campaign': { body: campaign },
      '/api/availability/promotion-preferences': { body: prefs },
      '/api/availability/settings': { status: 403 },
      '/api/availability/subscriptions': { status: 403 },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText(/Discord not linked/)).toBeInTheDocument());
    // 403 = a state with the gate's meaning; 500 (wallet) = unavailable.
    await waitFor(() => expect(screen.getAllByText(/needs a linked Discord account/).length).toBeGreaterThanOrEqual(2));
    await waitFor(() => expect(screen.getByText(/your wallet: unavailable/)).toBeInTheDocument(),
      { timeout: 15000 }); // the 500 exhausts react-query's retries first
    // Recorded prefs render as the one-line summary.
    expect(screen.getByText(/promotions off · channel any · timezone Europe\/Ljubljana/)).toBeInTheDocument();
    expect(screen.getByText(/no promotion campaign is running/)).toBeInTheDocument();
  });
});
