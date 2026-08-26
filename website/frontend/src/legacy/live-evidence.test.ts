// @ts-expect-error plain-JS module with no declaration file of its own
import { mapEvidence } from '../../../js/live-state.js';
// @ts-expect-error plain-JS module with no declaration file of its own
import { voiceRowKind } from '../../../js/live-status.js';
import { describe, expect, it } from 'vitest';

/**
 * The two live surfaces used to present a failure as a fact.
 *
 * The backend fixes (PR #808) gave both of them a field to doubt with, and
 * these pin the READING of those fields — the half Codex pointed out was
 * missing when the payload changed and the renderer did not.
 */

describe('mapEvidence', () => {
  it('says nothing about a map an event just confirmed', () => {
    const e = mapEvidence({ current_map: 'supply', map_confirmed: true, map_age_seconds: 12 });
    expect(e.unconfirmed).toBe(false);
    expect(e.ageMinutes).toBeNull();
  });

  it('marks a map that survived a session boundary', () => {
    // The exact shape the reducer produces after >600 s of silence and a
    // CONNECT: live again, seconds old, and still the previous map.
    const e = mapEvidence({ current_map: 'supply', map_confirmed: false, map_age_seconds: null });
    expect(e.unconfirmed).toBe(true);
  });

  it('keeps quiet about an age that is not yet worth saying', () => {
    expect(mapEvidence({ map_confirmed: true, map_age_seconds: 300 }).ageMinutes).toBeNull();
    expect(mapEvidence({ map_confirmed: true, map_age_seconds: 301 }).ageMinutes).toBe(5);
  });

  it('treats a payload without the fields as the old behaviour, not as doubt', () => {
    // ⛔ `=== false`, not falsy. A backend that predates #808 sends neither
    // field; labelling every map UNCONFIRMED during that window would be a
    // regression dressed as caution.
    const e = mapEvidence({ current_map: 'supply' });
    expect(e.unconfirmed).toBe(false);
    expect(e.ageMinutes).toBeNull();
  });

  it('survives a missing snapshot', () => {
    expect(mapEvidence(null).unconfirmed).toBe(false);
  });
});

describe('voiceRowKind', () => {
  it('reads status before count', () => {
    // ⭐ The whole finding in one assertion: an unavailable report carries
    // total_count 0, and the count must not get to answer first.
    expect(voiceRowKind({ status: 'unavailable', reason: 'no row', total_count: 0 }))
      .toBe('unavailable');
  });

  it('still calls a genuinely empty channel empty', () => {
    expect(voiceRowKind({ status: 'ok', total_count: 0 })).toBe('empty');
  });

  it('reports members when there are members', () => {
    expect(voiceRowKind({ status: 'ok', total_count: 3 })).toBe('members');
  });

  it('stops a stale report from being counted as the present', () => {
    // ⛔ The bot writes every 30 s and its last row stays in the table. With
    // only `ok` and `unavailable`, an hours-old member list rendered as
    // "3 in voice" indefinitely (Codex, PR #808).
    expect(voiceRowKind({ status: 'stale', total_count: 3, age_seconds: 3600 }))
      .toBe('stale');
    expect(voiceRowKind({ status: 'stale', total_count: 0 })).toBe('stale');
  });

  it('keeps stale and unavailable apart', () => {
    // Read-but-old and could-not-read need different fixes: the bot stopped,
    // versus the row is unreadable.
    expect(voiceRowKind({ status: 'stale', total_count: 3 }))
      .not.toBe(voiceRowKind({ status: 'unavailable', total_count: 0 }));
  });

  it('treats a payload without status as the old behaviour', () => {
    expect(voiceRowKind({ total_count: 0 })).toBe('empty');
    expect(voiceRowKind({ total_count: 2 })).toBe('members');
  });

  it('survives a missing payload', () => {
    expect(voiceRowKind(null)).toBe('empty');
  });
});
