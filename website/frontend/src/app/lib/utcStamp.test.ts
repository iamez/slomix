import { describe, expect, it } from 'vitest';
import { utcStamp } from './utcStamp';

describe('utcStamp', () => {
  it('keeps the offset and names the clock', () => {
    // 22:05 UTC with an explicit offset stays 22:05, and says UTC
    expect(utcStamp('2026-09-08T22:05:41.123456+00:00')).toBe('2026-09-08 22:05 UTC');
    // an offset is applied, not sliced away: 00:05+02:00 is 22:05 UTC the day before
    expect(utcStamp('2026-09-09T00:05:00+02:00')).toBe('2026-09-08 22:05 UTC');
  });
  it('reads a naive database stamp as UTC and an epoch as seconds', () => {
    expect(utcStamp('2026-09-08 22:05:41')).toBe('2026-09-08 22:05 UTC');
    expect(utcStamp(1788905141)).toBe('2026-09-08 22:05 UTC');
  });
  it('returns what it cannot parse, rather than "Invalid Date"', () => {
    expect(utcStamp('yesterday')).toBe('yesterday');
  });
});
