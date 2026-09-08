import { describe, expect, it } from 'vitest';
import { weaponLabel } from './weapons';

describe('weaponLabel', () => {
  it('names the tokens the round details carry', () => {
    expect(weaponLabel('WS_THOMPSON')).toBe('Thompson');
    expect(weaponLabel('WS_KNIFE_KBAR')).toBe('Ka-Bar knife');
    expect(weaponLabel('WS_MP40')).toBe('MP40');
  });
  it('keeps an unknown token readable instead of raw', () => {
    expect(weaponLabel('WS_NEW_THING')).toBe('New thing');
    expect(weaponLabel('Syringe')).toBe('Syringe');
  });
});
