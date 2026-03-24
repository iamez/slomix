import { describe, it, expect } from 'vitest';
import {
  formatNumber,
  formatDurationHM,
  formatDurationMS,
  formatSec,
} from './format';

describe('formatNumber', () => {
  it('rounds integers', () => {
    expect(formatNumber(42)).toBe('42');
  });

  it('formats decimals to 2 places', () => {
    expect(formatNumber(3.14159)).toBe('3.14');
  });

  it('handles zero', () => {
    expect(formatNumber(0)).toBe('0');
  });
});

describe('formatDurationHM', () => {
  it('returns -- for zero', () => {
    expect(formatDurationHM(0)).toBe('--');
  });

  it('returns -- for negative', () => {
    expect(formatDurationHM(-10)).toBe('--');
  });

  it('formats minutes only', () => {
    expect(formatDurationHM(300)).toBe('5m');
  });

  it('formats hours and minutes', () => {
    expect(formatDurationHM(3900)).toBe('1h 5m');
  });

  it('formats exact hours', () => {
    expect(formatDurationHM(7200)).toBe('2h 0m');
  });
});

describe('formatDurationMS', () => {
  it('returns 0:00 for zero', () => {
    expect(formatDurationMS(0)).toBe('0:00');
  });

  it('returns 0:00 for null', () => {
    expect(formatDurationMS(null)).toBe('0:00');
  });

  it('returns 0:00 for undefined', () => {
    expect(formatDurationMS(undefined)).toBe('0:00');
  });

  it('formats seconds with zero padding', () => {
    expect(formatDurationMS(65)).toBe('1:05');
  });

  it('formats larger values', () => {
    expect(formatDurationMS(725)).toBe('12:05');
  });
});

describe('formatSec', () => {
  it('returns -- for null', () => {
    expect(formatSec(null)).toBe('--');
  });

  it('returns -- for undefined', () => {
    expect(formatSec(undefined)).toBe('--');
  });

  it('formats minutes:seconds', () => {
    expect(formatSec(125)).toBe('2:05');
  });

  it('formats hours:minutes:seconds', () => {
    expect(formatSec(3725)).toBe('1:02:05');
  });

  it('handles negative values', () => {
    expect(formatSec(-125)).toBe('-2:05');
  });

  it('formats zero as 0:00', () => {
    expect(formatSec(0)).toBe('0:00');
  });
});
