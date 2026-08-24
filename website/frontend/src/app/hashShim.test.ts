import { describe, expect, it } from 'vitest';
import { hashToPath } from './routes';
import { isLegacyHash } from './hashShim';

/**
 * Every legacy hash shape a producer can emit (docs/design/06 §3 — the eight
 * producers: bot/services/session_digest_service.py:96/166/184/185/233/306,
 * bot/cogs/last_session_cog.py:183, main.py /share redirect) plus the three
 * aliases the registry keeps alive. The shim is permanent — old Discord
 * messages never expire.
 */
const PRODUCER_CASES: Array<[string, string]> = [
  ['#/session-detail/date/2026-08-20', '/session-detail/date/2026-08-20'],
  ['#/session-detail/150', '/session-detail/150'],
  ['#/session-detail/150/players', '/session-detail/150/players'],
  ['#/session-detail/150/summary', '/session-detail/150'],
  ['#/story', '/story'],
  ['#/story/session/150', '/story/session/150'],
  ['#/story/date/2026-08-20', '/story/date/2026-08-20'],
  ['#/leaderboards', '/leaderboards'],
  ['#/availability', '/availability'],
  ['#/profile/E587CA5F', '/profile/E587CA5F'],
  ['#/uploads/de4f8d8628c148e5a8756a522aeb43b0', '/uploads/de4f8d8628c148e5a8756a522aeb43b0'],
  ['#/tonight', '/live'],
  ['#/records', '/record-book?tab=records'],
  // Legacy tab value is 'hof' (route-registry.js:286).
  ['#/hall-of-fame', '/record-book?tab=hof'],
  ['#/', '/'],
  ['#/proximity/player/1C747DF1', '/proximity/player/1C747DF1'],
  ['#/proximity/round/11277', '/proximity/round/11277'],
  ['#/proximity/round/11277/teams', '/proximity/round/11277/teams'],
  ['#/greatshot', '/greatshot/demos'],
  ['#/greatshot/highlights', '/greatshot/highlights'],
  ['#/greatshot/bogus-section', '/greatshot/demos'],
  ['#/greatshot/demo/abc123', '/greatshot/demo/abc123'],
  ['#/sessions2?range=30d', '/sessions2?range=30d'],
];

describe('hashToPath', () => {
  for (const [hash, path] of PRODUCER_CASES) {
    it(`${hash} -> ${path}`, () => {
      expect(hashToPath(hash)).toBe(path);
    });
  }

  it('empty hash resolves to root', () => {
    expect(hashToPath('')).toBe('/');
    expect(hashToPath('#')).toBe('/');
  });

  it('ordinary in-page anchors are NOT legacy hashes and stay untouched', () => {
    expect(isLegacyHash('#section')).toBe(false);
    expect(isLegacyHash('#snapshot-integrity')).toBe(false);
    expect(isLegacyHash('')).toBe(false);
    expect(isLegacyHash('#/live')).toBe(true);
  });

  it('never returns an empty string for any registry-shaped hash', () => {
    for (const [hash] of PRODUCER_CASES) {
      expect(hashToPath(hash)).toBeTruthy();
    }
  });
});
