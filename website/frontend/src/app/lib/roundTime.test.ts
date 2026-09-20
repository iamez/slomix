import { describe, expect, it } from 'vitest';
import { fmtRoundTime } from './roundTime';

describe('fmtRoundTime', () => {
  it('reads both forms and the short digit strings', () => {
    expect(fmtRoundTime('21:44:22')).toBe('21:44');
    expect(fmtRoundTime('214422')).toBe('21:44');
    expect(fmtRoundTime('4918')).toBe('00:49');
    expect(fmtRoundTime(4918)).toBe('00:49');
  });
  it('is null without digits or with too many', () => {
    expect(fmtRoundTime(null)).toBeNull();
    expect(fmtRoundTime('')).toBeNull();
    expect(fmtRoundTime('1234567')).toBeNull();
  });
});
