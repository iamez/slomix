import { cleanup, render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { AvailabilityPage } from './AvailabilityPage';
import type {
  AvailabilityAccess, AvailabilityOverview, AvailabilitySettings, AvailabilitySubscriptions,
  BetPlaceResponse, BetsMarketCurrent, BetsWallet, CampaignCreateResponse, LinkTokenResponse,
  MarketOpenResponse, MarketSettleResponse,
  PlanningToday, PromotionCampaign, PromotionPreferences, PromotionPreview,
  SubscriptionUnlinkResponse, SubscriptionWriteResponse,
} from '../lib/types';
import accessAnon from './__fixtures__/api_availability_access.json';
import accessAuthed from './__fixtures__/api_availability_access_authed_form.json';
import accessLinked from './__fixtures__/api_availability_access_linked.json';
import accessAdmin from './__fixtures__/api_availability_access_admin.json';
import weekAnon from './__fixtures__/api_availability.json';
import weekAuthed from './__fixtures__/api_availability_authed_form.json';
import planningToday from './__fixtures__/api_planning_today.json';
import marketCurrent from './__fixtures__/api_bets_market_current.json';
import marketOpen from './__fixtures__/api_bets_market_current_open.json';
import marketOpenNoBet from './__fixtures__/api_bets_market_current_open_no_bet.json';
import marketSettled from './__fixtures__/api_bets_market_current_settled.json';
import betPlaced from './__fixtures__/api_bets_market_market_id_bet.json';
import marketOpened from './__fixtures__/api_bets_market_open.json';
import marketSettleDone from './__fixtures__/api_bets_market_settle.json';
import walletLinked from './__fixtures__/api_bets_wallet_linked.json';
import promoPrefs from './__fixtures__/api_availability_promotion_preferences.json';
import promoCampaign from './__fixtures__/api_availability_promotions_campaign.json';
import promoCampaignActive from './__fixtures__/api_availability_promotions_campaign_active.json';
import promoPreview from './__fixtures__/api_availability_promotions_preview.json';
import promoPreviewRecipients from './__fixtures__/api_availability_promotions_preview_with_recipients.json';
import promoCreated from './__fixtures__/api_availability_promotions_campaigns.json';
import settingsLinked from './__fixtures__/api_availability_settings_linked.json';
import subsLinked from './__fixtures__/api_availability_subscriptions_linked.json';
import subsPost from './__fixtures__/api_availability_subscriptions_post.json';
import subsDelete from './__fixtures__/api_availability_subscriptions_channel_type_delete.json';
import linkToken from './__fixtures__/api_availability_link_token.json';

// Every recorded/replayed shape satisfies its hand-written type — the
// backend (live recording or harness replay, see
// tests/unit/test_availability_slice2_fixtures.py) is the arbiter.
const anonAccess = accessAnon satisfies AvailabilityAccess;
const authedAccess = accessAuthed satisfies AvailabilityAccess;
const linkedAccess = accessLinked satisfies AvailabilityAccess;
const adminAccess = accessAdmin satisfies AvailabilityAccess;
const anonWeek = weekAnon satisfies AvailabilityOverview;
const authedWeek = weekAuthed satisfies AvailabilityOverview;
const planning = planningToday satisfies PlanningToday;
const market = marketCurrent satisfies BetsMarketCurrent;
const openMarket = marketOpen satisfies BetsMarketCurrent;
const openMarketNoBet = marketOpenNoBet satisfies BetsMarketCurrent;
const settledMarket = marketSettled satisfies BetsMarketCurrent;
const placed = betPlaced satisfies BetPlaceResponse;
const opened = marketOpened satisfies MarketOpenResponse;
const settleDone = marketSettleDone satisfies MarketSettleResponse;
const wallet = walletLinked satisfies BetsWallet;
const prefs = promoPrefs satisfies PromotionPreferences;
const campaign = promoCampaign satisfies PromotionCampaign;
const activeCampaign = promoCampaignActive satisfies PromotionCampaign;
const preview = promoPreview satisfies PromotionPreview;
const previewWithRecipients = promoPreviewRecipients satisfies PromotionPreview;
const created = promoCreated satisfies CampaignCreateResponse;
const settings = settingsLinked satisfies AvailabilitySettings;
const subs = subsLinked satisfies AvailabilitySubscriptions;
const subWritten = subsPost satisfies SubscriptionWriteResponse;
const unlinked = subsDelete satisfies SubscriptionUnlinkResponse;
const token = linkToken satisfies LinkTokenResponse;
void subWritten;

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

function bodyOf(spy: ReturnType<typeof stub>, method: string, path: string): unknown {
  const call = spy.mock.calls.find((c) => String(c[0]).split('?')[0] === path && c[1]?.method === method);
  if (!call || !call[1]) throw new Error(`${method} ${path} was not called`);
  return JSON.parse(String(call[1].body));
}

const LINKED_BASE = {
  '/api/availability/access': { body: linkedAccess },
  '/api/availability': { body: authedWeek },
  '/api/planning/today': { body: planning },
  '/api/bets/market/current': { body: market },
  '/api/bets/wallet': { body: wallet },
  '/api/availability/promotions/campaign': { body: campaign },
  '/api/availability/promotion-preferences': { body: prefs },
  '/api/availability/settings': { body: settings },
  '/api/availability/subscriptions': { body: subs },
};

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
    for (const gated of ['/settings', '/subscriptions', '/promotion-preferences', '/promotions/campaign', '/promotions/preview', '/bets/wallet']) {
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
      '/api/availability/settings': { status: 403, body: { detail: 'Linked Discord account required' } },
      '/api/availability/subscriptions': { status: 403, body: { detail: 'Linked Discord account required' } },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText(/Discord not linked/)).toBeInTheDocument());
    // 403 = a state with the gate's meaning; 500 (wallet) = unavailable.
    // The backend's recorded words, VERBATIM (the fixture's own detail).
    await waitFor(() => expect(screen.getAllByText(/Linked Discord account required/).length).toBeGreaterThanOrEqual(2));
    await waitFor(() => expect(screen.getByText(/your wallet: unavailable/)).toBeInTheDocument(),
      { timeout: 15000 }); // the 500 exhausts react-query's retries first
    // Recorded prefs render as the one-line summary.
    expect(screen.getByText(/promotions off · channel any · timezone Europe\/Ljubljana/)).toBeInTheDocument();
    expect(screen.getByText(/no promotion campaign is running/)).toBeInTheDocument();
    // Unlinked is not a promoter: no preview call, no schedule button.
    expect(screen.queryByRole('button', { name: /schedule/ })).toBeNull();
  });

  it('linked: the settings form saves what the chips say, and the 403 on an unverified channel is verbatim', async () => {
    const spy = stub({
      ...LINKED_BASE,
      'POST /api/availability/settings': { status: 403, body: { detail: 'telegram channel must be linked and verified first' } },
      '/api/availability/promotions/preview': { body: preview },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText(/signed in with a linked Discord account/)).toBeInTheDocument());
    // The recorded linked settings seed the chips: discord on, telegram off.
    const telegram = await screen.findByRole('button', { name: 'telegram' });
    expect(screen.getByRole('button', { name: 'discord' })).toHaveAttribute('aria-pressed', 'true');
    expect(telegram).toHaveAttribute('aria-pressed', 'false');
    fireEvent.click(telegram);
    expect(telegram).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'save' }));
    await waitFor(() => expect(screen.getByText(/telegram channel must be linked and verified first/)).toBeInTheDocument());
    // The POST body carried the whole write shape with the toggled flag.
    expect(bodyOf(spy, 'POST', '/api/availability/settings')).toMatchObject({
      telegram_notify: true, discord_notify: true, timezone: settings.timezone,
      sound_cooldown_seconds: settings.sound_cooldown_seconds,
    });
    // Timezone and cooldown are shown, not edited (legacy has no inputs).
    expect(screen.getByText(/timezone UTC · sound cooldown 480 s/)).toBeInTheDocument();
  });

  it('linked: link issues a token to hand to the bot, 429 is the backend sentence, unlink is a DELETE', async () => {
    const spy = stub({
      ...LINKED_BASE,
      'POST /api/availability/link-token': { body: token },
      'DELETE /api/availability/subscriptions/telegram': { body: unlinked },
      '/api/availability/promotions/preview': { body: preview },
    });
    renderPage();
    const linkTelegram = await screen.findByRole('button', { name: 'link telegram' });
    expect(screen.getAllByText(/not linked/).length).toBe(2); // telegram + signal rows
    fireEvent.click(linkTelegram);
    await waitFor(() => expect(screen.getByText(/e2e-link-token-value/)).toBeInTheDocument());
    expect(screen.getByText(/token issued — waiting for the bot/)).toBeInTheDocument();
    expect(bodyOf(spy, 'POST', '/api/availability/link-token')).toEqual({ channel_type: 'telegram', ttl_minutes: 30 });

    // Second request inside the interval: the backend's own words.
    spy.mockImplementationOnce(() => Promise.resolve({
      ok: false, status: 429,
      json: () => Promise.resolve({ detail: 'Link token was generated recently. Try again in 27s' }),
    } as Response));
    fireEvent.click(screen.getByRole('button', { name: 'link telegram' }));
    await waitFor(() => expect(screen.getByText(/Try again in 27s/)).toBeInTheDocument());

    // Unlink goes out as a DELETE on the templated path and refetches.
    fireEvent.click(screen.getByRole('button', { name: 'unlink telegram' }));
    await waitFor(() => expect(spy.mock.calls.some((c) =>
      String(c[0]) === '/api/availability/subscriptions/telegram' && c[1]?.method === 'DELETE')).toBe(true));
    await waitFor(() => expect(screen.queryByText(/e2e-link-token-value/)).toBeNull());
  });

  it('promoter: the preview is fetched only with can_promote, names its recipients, and a 409 is verbatim', async () => {
    const spy = stub({
      ...LINKED_BASE,
      '/api/availability/promotions/campaign': { body: activeCampaign },
      '/api/availability/promotions/preview': { body: previewWithRecipients },
      'POST /api/availability/promotions/campaigns': { status: 409, body: { detail: 'A promotion campaign already exists for today' } },
    });
    renderPage();
    // The running campaign: aggregate metadata and its three jobs.
    await waitFor(() => expect(screen.getByText(/campaign 2026-02-19 · scheduled · 3 recipients/)).toBeInTheDocument());
    expect(screen.getByText(/send_reminder_2045 · pending/)).toBeInTheDocument();
    // Preview with the legacy-discarded recipient list, rendered.
    await waitFor(() => expect(screen.getByText(/Alpha · looking · discord/)).toBeInTheDocument());
    expect(screen.getByText(/Charlie · maybe · discord/)).toBeInTheDocument();
    // include_available defaults ON, include_maybe OFF — in the query string.
    const previewUrl = spy.mock.calls.map((c) => String(c[0])).find((u) => u.includes('/promotions/preview'));
    expect(previewUrl).toContain('include_available=true');
    expect(previewUrl).toContain('include_maybe=false');
    fireEvent.click(screen.getByRole('button', { name: 'schedule' }));
    await waitFor(() => expect(screen.getByText(/A promotion campaign already exists for today/)).toBeInTheDocument());
    expect(bodyOf(spy, 'POST', '/api/availability/promotions/campaigns')).toEqual({
      include_available: true, include_maybe: false, dry_run: false,
    });
  });

  it('promoter: a scheduled campaign reports its id, count and times', async () => {
    stub({
      ...LINKED_BASE,
      '/api/availability/promotions/preview': { body: preview },
      'POST /api/availability/promotions/campaigns': { body: created },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText(/nobody opted in matches these flags today/)).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'schedule' }));
    await waitFor(() => expect(screen.getByText(/campaign #1 scheduled — 2 recipients/)).toBeInTheDocument());
  });

  it('linked, open market: pools with multipliers, my bet, and a stake that POSTs {choice, amount}', async () => {
    const spy = stub({
      ...LINKED_BASE,
      '/api/bets/market/current': { body: openMarket },
      'POST /api/bets/market/7/bet': { body: placed },
      '/api/availability/promotions/preview': { body: preview },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText(/pool 120 · bets 3/)).toBeInTheDocument());
    expect(screen.getByText('60%')).toBeInTheDocument();
    expect(screen.getByText('1.67×')).toBeInTheDocument();
    expect(screen.getByText(/your bet: 20 on Axis side · change any time before lock/)).toBeInTheDocument();
    expect(screen.getByText(/balance 100 · lifetime earned 0/)).toBeInTheDocument();
    const stakeInput = screen.getByLabelText('stake') as HTMLInputElement;
    expect(stakeInput.value).toBe('20'); // seeded from my_bet
    fireEvent.change(stakeInput, { target: { value: '35' } });
    fireEvent.click(screen.getByRole('button', { name: 'bet on Allied side' }));
    await waitFor(() => expect(screen.getByText(/bet placed — 35 on Allied side/)).toBeInTheDocument());
    expect(bodyOf(spy, 'POST', '/api/bets/market/7/bet')).toEqual({ choice: 'team_b', amount: 35 });
  });

  it('open market: a 400 is the backend sentence; anonymous sees pools but no stake', async () => {
    stub({
      ...LINKED_BASE,
      '/api/bets/market/current': { body: openMarketNoBet },
      'POST /api/bets/market/7/bet': { status: 400, body: { detail: 'Insufficient points (have 100)' } },
      '/api/availability/promotions/preview': { body: preview },
    });
    renderPage();
    const stakeInput = await screen.findByLabelText('stake') as HTMLInputElement;
    expect(stakeInput.value).toBe('10'); // no bet yet: the legacy default
    fireEvent.change(stakeInput, { target: { value: '500' } });
    fireEvent.click(screen.getByRole('button', { name: 'bet on Axis side' }));
    await waitFor(() => expect(screen.getByText(/Insufficient points \(have 100\)/)).toBeInTheDocument());
    vi.unstubAllGlobals();
    cleanup();

    const spy = stub({
      '/api/availability/access': { body: anonAccess },
      '/api/availability': { body: anonWeek },
      '/api/planning/today': { body: planning },
      '/api/bets/market/current': { body: openMarketNoBet },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText(/pool 120 · bets 3/)).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText(/sign in with CONNECT ID to place a bet/)).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: /bet on/ })).toBeNull();
    expect(spy.mock.calls.some((c) => String(c[0]).includes('/bets/wallet'))).toBe(false);
  });

  it('open market: a non-integer stake is refused before any POST, and a new market reseeds the stake', async () => {
    const spy = stub({
      ...LINKED_BASE,
      '/api/bets/market/current': { body: openMarket },
      'POST /api/bets/market/7/bet': { body: placed },
      '/api/availability/promotions/preview': { body: preview },
    });
    renderPage();
    const stakeInput = await screen.findByLabelText('stake') as HTMLInputElement;
    for (const bad of ['2.5', '0', '-3', '']) {
      fireEvent.change(stakeInput, { target: { value: bad } });
      fireEvent.click(screen.getByRole('button', { name: 'bet on Axis side' }));
      await waitFor(() => expect(screen.getByText(/enter a whole positive stake/)).toBeInTheDocument());
    }
    expect(spy.mock.calls.some((c) => c[1]?.method === 'POST' && String(c[0]).includes('/bet'))).toBe(false);
    // '1e2' IS a whole number — 100, not parseInt's 1 (Copilot on #894).
    fireEvent.change(stakeInput, { target: { value: '1e2' } });
    fireEvent.click(screen.getByRole('button', { name: 'bet on Axis side' }));
    await waitFor(() => expect(screen.getByText(/bet placed — 100 on Axis side/)).toBeInTheDocument());
    expect(bodyOf(spy, 'POST', '/api/bets/market/7/bet')).toEqual({ choice: 'team_a', amount: 100 });

    // The server swaps in a different market underneath the placed bet: the
    // invalidation refetch brings market 8 with my_bet 60, and — the edit
    // having been submitted (dirty cleared) — the stake reseeds from it.
    const other = { ...openMarket, market: { ...openMarket.market, id: 8, my_bet: { ...openMarket.market.my_bet, amount: 60 } } };
    spy.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input).split('?')[0];
      const body = init?.method === 'POST' ? placed
        : path === '/api/bets/market/current' ? other
        : path === '/api/bets/wallet' ? wallet
        : path === '/api/availability/settings' ? settings
        : path === '/api/availability/subscriptions' ? subs
        : path === '/api/availability/promotions/campaign' ? campaign
        : path === '/api/availability/promotion-preferences' ? prefs
        : path === '/api/availability/promotions/preview' ? preview
        : path === '/api/availability/access' ? linkedAccess
        : path === '/api/availability' ? authedWeek
        : path === '/api/planning/today' ? planning : {};
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
    });
    fireEvent.change(stakeInput, { target: { value: '15' } });
    fireEvent.click(screen.getByRole('button', { name: 'bet on Axis side' }));
    await waitFor(() => expect(screen.getByText(/bet placed — 15 on Axis side/)).toBeInTheDocument());
    await waitFor(() => expect((screen.getByLabelText('stake') as HTMLInputElement).value).toBe('60'));
  });

  it('linked: a background refetch does not clobber unsaved toggles, and save sends dry_run-free settings', async () => {
    const spy = stub({
      ...LINKED_BASE,
      'POST /api/availability/settings': { body: { ...settings, sound_enabled: false } },
      '/api/availability/promotions/preview': { body: preview },
    });
    renderPage();
    const sound = await screen.findByRole('button', { name: 'get-ready sound' });
    expect(sound).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(sound);
    expect(sound).toHaveAttribute('aria-pressed', 'false');
    // The server now answers with a CHANGED settings body (someone linked a
    // channel from the bot side) while the toggle is unsaved.
    spy.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input).split('?')[0];
      if (path === '/api/availability/settings' && init?.method === 'POST') {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ ...settings, sound_enabled: false, telegram_notify: true }) } as Response);
      }
      const body = path === '/api/availability/settings' ? { ...settings, telegram_notify: true }
        : path === '/api/availability/subscriptions' ? subs
        : path === '/api/bets/wallet' ? wallet
        : path === '/api/availability/promotions/campaign' ? campaign
        : path === '/api/availability/promotion-preferences' ? prefs
        : path === '/api/availability/promotions/preview' ? preview
        : path === '/api/availability/access' ? linkedAccess
        : path === '/api/availability' ? authedWeek
        : path === '/api/planning/today' ? planning
        : path === '/api/bets/market/current' ? market : {};
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
    });
    // Force the settings query to refetch with the new answer.
    fireEvent(window, new Event('focus'));
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.getByRole('button', { name: 'get-ready sound' })).toHaveAttribute('aria-pressed', 'false');
    fireEvent.click(screen.getByRole('button', { name: 'save' }));
    await waitFor(() => expect(screen.getByText(/settings saved/)).toBeInTheDocument());
    expect(bodyOf(spy, 'POST', '/api/availability/settings')).toMatchObject({ sound_enabled: false });
    // After the save cleared `dirty`, the server's answer seeds the chips.
    await waitFor(() => expect(screen.getByRole('button', { name: 'telegram' })).toHaveAttribute('aria-pressed', 'true'));
  });

  it('promoter: the dry-run chip travels in the POST body', async () => {
    const spy = stub({
      ...LINKED_BASE,
      '/api/availability/promotions/preview': { body: preview },
      'POST /api/availability/promotions/campaigns': { body: { ...created, dry_run: true } },
    });
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'dry run' }));
    fireEvent.click(screen.getByRole('button', { name: 'include maybe' }));
    fireEvent.click(screen.getByRole('button', { name: 'schedule' }));
    await waitFor(() => expect(screen.getByText(/· dry run$/)).toBeInTheDocument());
    expect(bodyOf(spy, 'POST', '/api/availability/promotions/campaigns')).toEqual({
      include_available: true, include_maybe: true, dry_run: true,
    });
  });

  it('settled market: the result and my outcome, no stake', async () => {
    stub({
      ...LINKED_BASE,
      '/api/bets/market/current': { body: settledMarket },
      '/api/availability/promotions/preview': { body: preview },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText(/settled · result: Allied side/)).toBeInTheDocument());
    expect(screen.getByText(/your bet: 20 on Axis side — lost/)).toBeInTheDocument();
    expect(screen.getByText(/betting is settled for this market/)).toBeInTheDocument();
    expect(screen.queryByLabelText('stake')).toBeNull();
  });

  // -------------------------------------------------------------------------
  // slice 3 — the admin's half of the market

  const ADMIN_BASE = { ...LINKED_BASE, '/api/availability/access': { body: adminAccess },
    '/api/availability/promotions/preview': { body: preview } };

  it('admin, no market: the open control appears and POSTs an empty body to /api/bets/market', async () => {
    const spy = stub({ ...ADMIN_BASE, 'POST /api/bets/market': { body: opened } });
    renderPage();
    await waitFor(() => expect(screen.getByText(/no market is open right now/)).toBeInTheDocument());
    const btn = await screen.findByRole('button', { name: 'open session market' });
    fireEvent.click(btn);
    await waitFor(() => expect(screen.getByText(/market opened/)).toBeInTheDocument());
    // Empty body on purpose — legacy availability.js:2357-2358 posts {} and the
    // backend fills every column from defaults. Sending labels would be a new
    // behaviour, not parity.
    expect(bodyOf(spy, 'POST', '/api/bets/market')).toEqual({});
  });

  it('admin, open market: settle controls carry each label, and the click sends that outcome', async () => {
    const spy = stub({ ...ADMIN_BASE, '/api/bets/market/current': { body: openMarket },
      'POST /api/bets/market/7/settle': { body: settleDone } });
    renderPage();
    await waitFor(() => expect(screen.getByText(/pool 120 · bets 3/)).toBeInTheDocument());
    // The buttons name the TEAMS, not 'team_a' — an admin settling the wrong
    // side pays out the wrong people and it cannot be undone.
    expect(await screen.findByRole('button', { name: 'settle: Axis side' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'settle: Allied side' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'settle: Allied side' }));
    await waitFor(() => expect(screen.getByText(/settled — Allied side won/)).toBeInTheDocument());
    expect(bodyOf(spy, 'POST', '/api/bets/market/7/settle')).toEqual({ outcome: 'team_b' });
  });

  it('admin, open market: void sends void and says the stakes come back', async () => {
    const spy = stub({ ...ADMIN_BASE, '/api/bets/market/current': { body: openMarket },
      'POST /api/bets/market/7/settle': { body: settleDone } });
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'void market' }));
    await waitFor(() => expect(screen.getByText(/stakes refunded/)).toBeInTheDocument());
    expect(bodyOf(spy, 'POST', '/api/bets/market/7/settle')).toEqual({ outcome: 'void' });
  });

  it('admin, settled market: nothing left to administer', async () => {
    stub({ ...ADMIN_BASE, '/api/bets/market/current': { body: settledMarket } });
    renderPage();
    await waitFor(() => expect(screen.getByText(/betting is settled/)).toBeInTheDocument());
    // Settling twice is a 400 from the backend; offering the button would be
    // an affordance for an error.
    expect(screen.queryByRole('button', { name: /^settle: / })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'void market' })).not.toBeInTheDocument();
  });

  it('⛔ the control: a linked NON-admin sees no admin surface at all', async () => {
    // Without this the four cases above would still pass if `isAdmin` were
    // hardwired true — and the page would show every visitor a control that
    // only 401s. `is_admin` is false in every other access fixture, and it can
    // never be true for the house test user (-1 fails isdigit in
    // configured_admin_ids), which is why the admin fixture exists at all.
    stub({ ...LINKED_BASE, '/api/bets/market/current': { body: openMarket },
      '/api/availability/promotions/preview': { body: preview } });
    renderPage();
    await waitFor(() => expect(screen.getByText(/pool 120 · bets 3/)).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: 'open session market' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^settle: / })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'void market' })).not.toBeInTheDocument();
    // Not a disabled button and not an explanation: nothing. Naming the
    // operation would tell every visitor the surface exists.
    expect(screen.queryByText(/^admin$/)).not.toBeInTheDocument();
  });

});
