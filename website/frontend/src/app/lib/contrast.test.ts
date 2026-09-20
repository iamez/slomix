import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { AA_BODY, contrastRatio, luminance } from './contrast';

function tokens(): Map<string, string> {
  const css = readFileSync('src/app/tokens.css', 'utf8');
  const map = new Map<string, string>();
  for (const [, name, value] of css.matchAll(/(--color-[a-z0-9-]+):\s*(#[0-9a-fA-F]{3,8});/g)) {
    map.set(name, value);
  }
  return map;
}

describe('contrast', () => {
  it('computes the ratios WCAG defines', () => {
    expect(luminance('#ffffff')).toBeCloseTo(1, 5);
    expect(luminance('#000000')).toBeCloseTo(0, 5);
    expect(contrastRatio('#ffffff', '#000000')).toBeCloseTo(21, 2);
    expect(contrastRatio('#808080', '#808080')).toBeCloseTo(1, 5);
    // Order does not matter.
    expect(contrastRatio('#eae7e1', '#0b0b0a')).toBeCloseTo(contrastRatio('#0b0b0a', '#eae7e1'), 10);
  });

  /**
   * ⛔ Every token the pages use for TEXT must clear AA body on every ground
   * the app paints. `--color-text-600` measured 2.2 against all three inks —
   * below AA large as well — which is why nothing renders text in it any
   * more; it stays in the palette as a rule/ornament colour and is listed
   * here so a future use has to face this test.
   */
  const TEXT_TOKENS = ['--color-text-100', '--color-text-200', '--color-text-300', '--color-text-400',
    '--color-text-500', '--color-accent', '--color-accent-warm', '--color-pos', '--color-neg'];
  const GROUNDS = ['--color-ink-950', '--color-ink-900', '--color-ink-800'];
  const NOT_FOR_TEXT = ['--color-text-600'];

  it('every text token clears AA body on every ground the app paints', () => {
    const t = tokens();
    const failures: string[] = [];
    for (const fg of TEXT_TOKENS) {
      for (const bg of GROUNDS) {
        const a = t.get(fg); const b = t.get(bg);
        expect(a, `${fg} missing from tokens.css`).toBeDefined();
        expect(b, `${bg} missing from tokens.css`).toBeDefined();
        const r = contrastRatio(a!, b!);
        if (r < AA_BODY) failures.push(`${fg} on ${bg}: ${r.toFixed(2)}`);
      }
    }
    expect(failures).toEqual([]);
  });

  it('names the token that is NOT for text, with its measurement', () => {
    const t = tokens();
    for (const fg of NOT_FOR_TEXT) {
      const r = contrastRatio(t.get(fg)!, t.get('--color-ink-950')!);
      // If someone lightens it enough to pass, move it into TEXT_TOKENS
      // rather than leaving a stale exception here.
      expect(r, `${fg} now passes AA — move it into TEXT_TOKENS`).toBeLessThan(AA_BODY);
    }
  });
});
