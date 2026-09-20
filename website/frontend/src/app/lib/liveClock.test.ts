import { describe, expect, it } from 'vitest';
import { tickedSeconds } from './liveClock';

describe('tickedSeconds — the clock between polls', () => {
  it('adds the whole seconds since the answer arrived while the round runs', () => {
    expect(tickedSeconds(72, 1_000, 1_000, true)).toBe(72);
    expect(tickedSeconds(72, 1_000, 13_999, true)).toBe(84);
  });
  it('returns the snapshot untouched when nothing is running, and null for no clock', () => {
    expect(tickedSeconds(72, 1_000, 40_000, false)).toBe(72);
    expect(tickedSeconds(null, 1_000, 40_000, true)).toBeNull();
  });
  it('never runs backwards when the clocks disagree', () => {
    expect(tickedSeconds(72, 5_000, 1_000, true)).toBe(72);
  });
});
