/** Opt-in actual hook/DOM proof from privately exported native ASGI responses.
 * No invented fallback payload; this is not real-game/browser acceptance.
 */
import { readFileSync } from 'node:fs';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { expect, it, vi } from 'vitest';
import { RoundsTab, roundsReason } from './RoundsTab';
import { useSessionRounds } from '../lib/queries';
import type { SessionRounds } from '../lib/types';

const artifactPath = process.env.SLOMIX_NATIVE_ROUNDS_PROOF;
function NativeRounds({ sessionId }: { sessionId: number }) {
  const query = useSessionRounds(sessionId);
  return <RoundsTab rounds={query.data} reason={roundsReason(query)} />;
}

it.skipIf(!artifactPath)('renders SQL-verified native /rounds through hook and tab (requires SLOMIX_NATIVE_ROUNDS_PROOF)', async () => {
  // The envelope labels scope, not cryptographic provenance. The native
  // producer separately verifies these exact responses against committed SQL.
  const artifact = JSON.parse(readFileSync(artifactPath!, 'utf8')) as {
    schema_version: number; kind: string; source_revision: string; snapshots: SessionRounds[];
  };
  expect(artifact.schema_version).toBe(1);
  expect(artifact.kind).toBe('synthetic_native_runtime_rounds');
  expect(artifact.source_revision).toMatch(/^[a-f0-9]{40}$/);
  expect(artifact.snapshots).toHaveLength(3);
  const first = artifact.snapshots[0]!;
  expect(Number.isSafeInteger(first.gaming_session_id)).toBe(true);
  expect(first.gaming_session_id).toBeGreaterThan(0);
  for (const snapshot of artifact.snapshots) {
    expect(snapshot).toEqual(first);
    expect(snapshot.total_rounds).toBe(2);
    expect(snapshot.rounds.map(r => r.round_number).sort()).toEqual([1, 2]);
    expect(new Set(snapshot.rounds.map(r => r.round_id)).size).toBe(2);
    for (const round of snapshot.rounds) {
      expect(Number.isSafeInteger(round.round_id)).toBe(true);
      expect(round.round_id).toBeGreaterThan(0);
      expect(round.players.map(p => p.player_guid).sort()).toEqual(['12345678', '87654321']);
      for (const player of round.players) {
        expect(typeof player.player_name).toBe('string');
        expect(player.player_name.length).toBeGreaterThan(0);
        for (const number of [player.kills, player.damage_given, player.deaths]) {
          expect(Number.isSafeInteger(number)).toBe(true);
          expect(number).toBeGreaterThanOrEqual(0);
        }
      }
    }
  }
  let index = 0;
  const fetcher = vi.fn(async (input: RequestInfo | URL) => {
    expect(new URL(String(input), 'http://fixture').pathname)
      .toBe(`/api/stats/session/${first.gaming_session_id}/rounds`);
    return new Response(JSON.stringify(artifact.snapshots[index]), {
      status: 200, headers: { 'Content-Type': 'application/json' },
    });
  });
  vi.stubGlobal('fetch', fetcher);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  const view = render(<QueryClientProvider client={client}><MemoryRouter>
    <NativeRounds sessionId={first.gaming_session_id} />
  </MemoryRouter></QueryClientProvider>);
  try {
    await waitFor(() => expect(view.container.querySelectorAll('[data-round-id]')).toHaveLength(2));
    const assertRendered = () => {
      const sections = view.container.querySelectorAll<HTMLElement>('[data-round-id]');
      expect([...sections].map(s => Number(s.dataset.roundId)).sort()).toEqual(first.rounds.map(r => r.round_id).sort());
      for (const round of first.rounds) {
        const section = view.container.querySelector<HTMLElement>(`[data-round-id="${round.round_id}"]`)!;
        const headers = [...section.querySelectorAll('thead th')].map(h => h.textContent?.trim());
        for (const player of round.players) {
          const row = within(section).getByRole('button', { name: player.player_name }).closest('tr')!;
          const cells = [...row.querySelectorAll('td')];
          expect(cells[headers.indexOf('k')]?.textContent).toBe(player.kills.toLocaleString());
          expect(cells[headers.indexOf('d')]?.textContent).toBe(player.deaths.toLocaleString());
          expect(cells[headers.indexOf('given')]?.textContent).toBe(player.damage_given.toLocaleString());
        }
      }
    };
    assertRendered();
    const initial = view.container.textContent;
    for (index = 1; index < 3; index++) {
      await act(async () => { await client.refetchQueries({ queryKey: ['session-rounds', first.gaming_session_id] }); });
      expect(fetcher).toHaveBeenCalledTimes(index + 1);
      assertRendered();
      expect(view.container.textContent).toBe(initial);
    }
  } finally {
    view.unmount();
    client.clear();
    vi.unstubAllGlobals();
  }
});
