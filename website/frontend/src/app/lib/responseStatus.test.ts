import { describe, expect, it } from 'vitest';
import {
  FAILURE_STATUSES,
  NOT_FAILURE_STATUSES,
  hasFailed,
  isFailureStatus,
} from './responseStatus';

/**
 * These endpoints answer HTTP 200 whether they succeeded or not, so the
 * in-band `status` is the only thing that separates "no data" from "the
 * query fell over". Getting it wrong in either direction hides something:
 * miss a failure and an outage renders as an empty section; over-report and
 * a page blacks out a correct answer.
 */
describe('the response-status vocabulary', () => {
  it('treats both spellings of failure as failure', () => {
    for (const status of FAILURE_STATUSES) {
      expect(isFailureStatus(status)).toBe(true);
    }
  });

  it('does NOT treat the look-alikes as failure', () => {
    // Each of these is a real answer with its own rendering; blanking them
    // would hide something true. `no_data` painted three red boards for a
    // date nobody played (Codex on #809) — that is the failure mode.
    for (const status of NOT_FAILURE_STATUSES) {
      expect(isFailureStatus(status), `${status} must not read as a failure`).toBe(false);
    }
  });

  it('does not treat a missing status as a failure', () => {
    // Most endpoints do not carry the field. Treating its absence as a fault
    // would black out the API.
    expect(isFailureStatus(undefined)).toBe(false);
    expect(isFailureStatus(null)).toBe(false);
    expect(hasFailed({ isError: false }, undefined)).toBe(false);
    expect(hasFailed({ isError: false }, {})).toBe(false);
  });

  it('catches a failure arriving by either route', () => {
    // ⛔ BOTH HALVES. The transport half is a non-2xx that `apiGet` threw on;
    // the in-band half arrives with a 200 and would otherwise render as an
    // ordinary empty result.
    expect(hasFailed({ isError: true }, undefined)).toBe(true);
    expect(hasFailed({ isError: false }, { status: 'error' })).toBe(true);
    expect(hasFailed({ isError: false }, { status: 'unavailable' })).toBe(true);
    expect(hasFailed({ isError: false }, { status: 'ok' })).toBe(false);
  });

  it('rejects values that merely contain a failure word', () => {
    // A substring test would have matched all of these. `status` carries 30
    // distinct values across this API, including a formula's maturity and an
    // upload's lifecycle.
    for (const status of ['errored', 'no_error', 'unavailability', 'ERROR', 'queued', 'live']) {
      expect(isFailureStatus(status), `${status} must not read as a failure`).toBe(false);
    }
  });

  it('can fail', () => {
    // A control: a predicate that answered true for everything, or false for
    // everything, would pass some of the assertions above but not this pair.
    const seen = [...FAILURE_STATUSES, ...NOT_FAILURE_STATUSES].map(isFailureStatus);
    expect(seen).toContain(true);
    expect(seen).toContain(false);
  });
});
