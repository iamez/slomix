import { render, screen, waitFor, within } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeQueryClient } from '../lib/queries';
import { PlayerDrilldown } from './PlayerDrilldown';
import type { PlayerVsStats } from '../lib/types';
import vsJson from '../pages/__fixtures__/api_player_guid_vs_stats.json';

// Recorded from the dev server: session 156, one real player.
const vs = vsJson satisfies PlayerVsStats;

/** Every other instrument in this panel answers empty; each declares its own
 *  state, so the duels section can be tested without standing up five more. */
function stub(vsBody: unknown, vsStatus = 200) {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL): Promise<Response> => {
    const path = String(input).split('?')[0];
    if (path === '/api/player/AAAA1111/vs-stats') {
      return Promise.resolve({
        ok: vsStatus < 400, status: vsStatus, json: () => Promise.resolve(vsBody),
      } as Response);
    }
    // Shapes the other five instruments can survive: `{}` made PerMap throw
    // on `rounds.data.rounds`. Each of them then renders its own empty state,
    // which is exactly the isolation this panel's header promises.
    return Promise.resolve({
      ok: true, status: 200, json: () => Promise.resolve({ rounds: [], players: [], lives: [], verdicts: [], weapons: [] }),
    } as Response);
  }));
}

function renderPanel() {
  const client = makeQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <PlayerDrilldown sessionId={156} guid8="AAAA1111" name="alpha" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe('PlayerDrilldown — duels', () => {
  it('both sides render, and an opponent on both is not a duplicate', async () => {
    stub(vs);
    const { container } = renderPanel();
    await waitFor(() => expect(screen.getByText('easiest preys')).toBeInTheDocument());
    const section = container.querySelector('[data-parity="session.player.duels"]') as HTMLElement;
    // `.olz` is prey AND enemy — the same duel from each end. A panel that
    // deduplicated opponents would show one of these, which is the wrong shape.
    expect(within(section).getAllByText('.olz')).toHaveLength(2);
    expect(within(section).getByText(/51k · 69d · 0\.74/)).toBeInTheDocument();
    expect(within(section).getByText(/69k · 51d · 1\.35/)).toBeInTheDocument();
  });

  it('⛔ opponents link by guid, not by name', async () => {
    // Legacy links `#/profile/<name>`; a renamed player then lands nowhere.
    stub(vs);
    const { container } = renderPanel();
    await waitFor(() => expect(screen.getByText('easiest preys')).toBeInTheDocument());
    const section = container.querySelector('[data-parity="session.player.duels"]') as HTMLElement;
    const link = within(section).getAllByText('.olz')[0].closest('a');
    expect(link).toHaveAttribute('href', '/profile/5D989160');
  });

  it('a player with no duels tonight says so', async () => {
    stub({ ...vs, easiest_preys: [], worst_enemies: [] });
    renderPanel();
    await waitFor(() => expect(screen.getByText(/no duels recorded for this player tonight/)).toBeInTheDocument());
  });

  it('one empty side is named, not blank', async () => {
    // A player who lost every duel has preys: [] and enemies: [...]. The empty
    // side must say which it is, or the reader reads "no data" for both.
    stub({ ...vs, easiest_preys: [] });
    const { container } = renderPanel();
    await waitFor(() => expect(screen.getByText(/nobody they came out ahead against/)).toBeInTheDocument());
    const section = container.querySelector('[data-parity="session.player.duels"]') as HTMLElement;
    expect(within(section).getAllByText('.lgz').length).toBeGreaterThan(0);
  });

  it('a failed request is unavailable, which is not the same as empty', async () => {
    stub({ detail: 'boom' }, 500);
    renderPanel();
    await waitFor(() => expect(screen.getByText(/duels: unavailable/i)).toBeInTheDocument());
    expect(screen.queryByText(/no duels recorded/)).not.toBeInTheDocument();
  });

  it('⛔ the request carries scope AND session_id', async () => {
    // The handler's branch is `elif scope == "session" and session_id`
    // (records_player.py:36): a scope without its id falls through to the
    // ALL-TIME query. Measured: 51 kills this session against 938 all-time.
    // A panel labelled "this session" showing 938 is a lie the code never
    // announces, so the call is pinned here.
    const spy = vi.fn((input: RequestInfo | URL): Promise<Response> => {
      const path = String(input).split('?')[0];
      const body = path === '/api/player/AAAA1111/vs-stats' ? vs
        : { rounds: [], players: [], lives: [], verdicts: [], weapons: [] };
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
    });
    vi.stubGlobal('fetch', spy);
    renderPanel();
    await waitFor(() => expect(screen.getByText('easiest preys')).toBeInTheDocument());
    const url = spy.mock.calls.map((c) => String(c[0])).find((u) => u.includes('/vs-stats'));
    expect(url).toContain('scope=session');
    expect(url).toContain('session_id=156');
  });
});
