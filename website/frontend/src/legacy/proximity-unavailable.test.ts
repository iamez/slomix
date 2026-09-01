/**
 * ⛔ THE LEGACY PAGE COUNTED ONLY ONE KIND OF FAILURE.
 *
 * Eleven proximity endpoints used to answer `{"status": "ok", ...empty}` during
 * a database outage. They now answer `unavailable` with a `reason` — and this
 * page does NOT use `responseStatus.ts`. Every gate in `website/js/proximity.js`
 * tested `status === 'error'` alone, so the new status fell straight through to
 * the empty-render path and the outage was STILL presented as "no data yet",
 * with the panel painted in a healthy tone.
 *
 * ⭐ Same trap as the snowflake change earlier this week: the schema and the new
 * SPA were counted, and the third client was not. Codex on #862.
 *
 * ⚠️ Vitest reaches the module directly — `proximity.js` is an ES module — so
 * these are behaviour tests on the real functions, not a grep over the source.
 */

import { beforeEach, describe, expect, it } from 'vitest';

import {
  getQualityTone, proximityFailed, proximityShowFailure, proximityUnavailableNote,
  // @ts-expect-error plain-JS module with no declaration file of its own
} from '../../../js/proximity.js';

describe('proximityFailed', () => {
  it('counts an outage as a failure, not as an empty answer', () => {
    expect(proximityFailed({ status: 'unavailable', reason: 'db did not answer' })).toBe(true);
  });

  it('still counts the old error status', () => {
    // CONTROL: widening must not drop what already worked.
    expect(proximityFailed({ status: 'error' })).toBe(true);
  });

  it('treats a missing payload as a failure', () => {
    expect(proximityFailed(null)).toBe(true);
    expect(proximityFailed(undefined)).toBe(true);
  });

  it('does NOT call a genuinely empty answer a failure', () => {
    // ⛔ THE HALF THAT KEEPS THE OTHER HALF HONEST. A page that treats every
    // empty answer as broken puts a failure banner over every feature that
    // simply has no data yet.
    expect(proximityFailed({ status: 'ok', carriers: [] })).toBe(false);
    expect(proximityFailed({ status: 'prototype' })).toBe(false);
  });
});

describe('proximityUnavailableNote', () => {
  it('says WHY when the reason is carried', () => {
    const note = proximityUnavailableNote({ status: 'unavailable', reason: 'the database did not answer' });
    expect(note).toContain('Temporarily unavailable');
    expect(note).toContain('the database did not answer');
  });

  it('still says something when no reason came with it', () => {
    expect(proximityUnavailableNote({ status: 'unavailable' })).toContain('Temporarily unavailable');
  });

  it('returns null for anything that is not an outage', () => {
    // CONTROL: callers fall back to their own "no data yet" wording, which is
    // correct for the case it actually describes.
    expect(proximityUnavailableNote({ status: 'error' })).toBeNull();
    expect(proximityUnavailableNote({ status: 'ok' })).toBeNull();
    expect(proximityUnavailableNote(null)).toBeNull();
  });
});

describe('getQualityTone', () => {
  it('paints an unmeasurable panel as failed, not as fine', () => {
    expect(getQualityTone('unavailable')).toBe('rose');
  });

  it('keeps the tones it already had', () => {
    // CONTROL for the surrounding table, which is a long if-chain.
    expect(getQualityTone('error')).toBe('rose');
    expect(getQualityTone('partial')).toBe('amber');
    expect(getQualityTone('experimental')).toBe('purple');
  });
});

describe('proximityShowFailure', () => {
  const ids = ['carrier-summary', 'carrier-leaders'];

  beforeEach(() => {
    document.body.innerHTML = ids
      .map((id) => `<div id="${id}">No carrier data yet.</div>`)
      .join('');
  });

  it('replaces the stale placeholder instead of leaving it', () => {
    // ⛔ THE DEFECT: the first version returned without touching the DOM, so an
    // outage left "No carrier data yet" — or, after a reload, the PREVIOUS
    // scope's numbers, which look current and are not.
    const stopped = proximityShowFailure(
      { status: 'unavailable', reason: 'the database did not answer' }, ...ids);
    expect(stopped).toBe(true);
    for (const id of ids) {
      const el = document.getElementById(id)!;
      expect(el.innerHTML).not.toContain('No carrier data yet');
      expect(el.innerHTML).toContain('Temporarily unavailable');
      expect(el.innerHTML).toContain('the database did not answer');
    }
  });

  it('says something even when no reason came with the failure', () => {
    proximityShowFailure({ status: 'error' }, ...ids);
    expect(document.getElementById(ids[0])!.innerHTML).toContain('Unavailable');
  });

  it('leaves a successful answer alone and lets the renderer run', () => {
    // CONTROL: a helper that painted every response would erase real data.
    const stopped = proximityShowFailure({ status: 'ok', carriers: [] }, ...ids);
    expect(stopped).toBe(false);
    expect(document.getElementById(ids[0])!.innerHTML).toContain('No carrier data yet');
  });

  it('does not fall over on an element that is not on this page', () => {
    expect(proximityShowFailure({ status: 'unavailable' }, 'no-such-element')).toBe(true);
  });
});
