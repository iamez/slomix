/**
 * The About page's endpoint probes — the legacy diagnostics.js API table
 * (website/js/diagnostics.js:15-26) carried over verbatim: same endpoints,
 * same required flags.
 *
 * This file is EXCLUDED from the endpoint-gap ratchet's extractor by name
 * (tests/integration/test_endpoint_gap.py), and that exclusion is the point,
 * not a loophole: a probe pings an endpoint to report whether it answers —
 * it does not render its data, so it must not count as parity coverage.
 * Without the exclusion this single table would silently clear ~10 gap
 * lines (measured while building the About page) for pages that do not
 * exist yet. Two guards keep the exclusion honest: a repo test asserts
 * every probe path exists in the committed OpenAPI spec, and the probes run
 * as real GETs on the live page — a rotten path shows up as a red row.
 */

export interface Probe {
  name: string;
  endpoint: string;
  required: boolean;
}

export const API_PROBES: Probe[] = [
  { name: 'API Status', endpoint: '/api/status', required: true },
  { name: 'Stats Overview', endpoint: '/api/stats/overview', required: true },
  { name: 'Leaderboard', endpoint: '/api/stats/leaderboard?limit=5', required: true },
  { name: 'Recent Matches', endpoint: '/api/stats/matches?limit=5', required: true },
  { name: 'Sessions List', endpoint: '/api/sessions?limit=5', required: true },
  { name: 'Live Status', endpoint: '/api/live-status', required: true },
  { name: 'Server Activity', endpoint: '/api/server-activity/history?hours=24', required: false },
  { name: 'Current Season', endpoint: '/api/seasons/current', required: false },
  { name: 'Last Session', endpoint: '/api/stats/last-session', required: false },
  { name: 'Live Session', endpoint: '/api/stats/live-session', required: false },
  { name: 'Records', endpoint: '/api/stats/records', required: false },
  { name: 'Predictions', endpoint: '/api/predictions/recent?limit=3', required: false },
];

export interface ProbeResult {
  probe: Probe;
  state: 'ok' | 'fail' | 'pending';
  status: number | null;
  ms: number | null;
}

/** Fire every probe in parallel; report per row, never throw. */
export async function runProbes(
  onResult: (result: ProbeResult) => void,
  fetcher: typeof fetch = fetch,
): Promise<void> {
  await Promise.all(
    API_PROBES.map(async (probe) => {
      const started = performance.now();
      try {
        const res = await fetcher(probe.endpoint, { cache: 'no-store' });
        onResult({
          probe,
          state: res.ok ? 'ok' : 'fail',
          status: res.status,
          ms: Math.round(performance.now() - started),
        });
      } catch {
        onResult({ probe, state: 'fail', status: null, ms: null });
      }
    }),
  );
}
