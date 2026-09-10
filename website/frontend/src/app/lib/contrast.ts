/**
 * WCAG 2.1 relative luminance and contrast ratio.
 *
 * Here because the visitor review of 2026-09-07 listed the text tokens'
 * contrast as UNMEASURED — the one a11y item that could be settled with
 * arithmetic instead of an opinion. `tokens.test.ts` runs it over the real
 * palette, so a colour that stops being readable fails a test rather than
 * waiting for someone to notice.
 */

function channel(value: number): number {
  const c = value / 255;
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

/** #rgb or #rrggbb → relative luminance (0 = black, 1 = white). */
export function luminance(hex: string): number {
  const h = hex.trim().replace('#', '');
  const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h;
  if (!/^[0-9a-fA-F]{6}$/.test(full)) throw new Error(`not a hex colour: ${hex}`);
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16));
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

/** The WCAG ratio between two colours: 1 (identical) to 21 (black on white). */
export function contrastRatio(a: string, b: string): number {
  const [la, lb] = [luminance(a), luminance(b)];
  const [hi, lo] = la > lb ? [la, lb] : [lb, la];
  return (hi + 0.05) / (lo + 0.05);
}

/** AA thresholds: 4.5 for body text, 3.0 for large text and UI edges. */
export const AA_BODY = 4.5;
export const AA_LARGE = 3;
