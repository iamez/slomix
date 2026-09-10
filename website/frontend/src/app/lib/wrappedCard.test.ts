import { describe, expect, it } from 'vitest';
import { CARD_H, CARD_W, DEFAULT_PALETTE, drawWrapped, type CardContext } from './wrappedCard';
import wrapped from '../pages/__fixtures__/api_players_identifier_wrapped.json';
import type { Wrapped } from './types';

/** A context that records every call — and exposes, via a Proxy, any
 *  member the drawing touches that the CardContext contract does not offer.
 *  That is the design rule as a test: a gradient, an arc (rounded corner) or
 *  a shadow is not a style choice on this site, it is a defect. */
function recorder() {
  const calls: Array<[string, unknown[]]> = [];
  const forbidden: string[] = [];
  const state: Record<string, unknown> = { fillStyle: '', font: '', textAlign: 'left' };
  const ctx = new Proxy({} as CardContext, {
    get(_t, prop: string) {
      if (prop in state) return state[prop];
      if (prop === 'fillRect' || prop === 'fillText') {
        return (...args: unknown[]) => { calls.push([prop, args]); };
      }
      forbidden.push(prop);
      return () => undefined;
    },
    set(_t, prop: string, value) { state[prop] = value; return true; },
  });
  return { ctx, calls, forbidden };
}

describe('drawWrapped', () => {
  it('draws the ground, the head, eight tiles with hairlines and the footer — in that order', () => {
    const { ctx, calls, forbidden } = recorder();
    drawWrapped(ctx, wrapped as Wrapped);
    expect(forbidden).toEqual([]);
    expect(calls[0]).toEqual(['fillRect', [0, 0, CARD_W, CARD_H]]);
    const texts = calls.filter(([m]) => m === 'fillText').map(([, a]) => a[0] as string);
    expect(texts[0]).toBe('SLOMIX WRAPPED');
    expect(texts[1]).toBe('.LGZ');
    expect(texts[2]).toBe('2026 Fall (Q3)');
    // every card's label (upper-cased) and value are on the canvas
    // values are clipped to 14 characters on the card (a name can be long);
    // the full value lives in the text list beside the canvas
    for (const c of (wrapped as Wrapped).cards) {
      expect(texts).toContain(c.label.toUpperCase());
      expect(texts).toContain(c.value.slice(0, 14));
    }
    expect(texts.at(-1)).toBe('slomix.fyi');
    // hairlines: one under the head + one per tile, all 1 px tall
    const rules = calls.filter(([m, a]) => m === 'fillRect' && a[3] === 1);
    expect(rules).toHaveLength(1 + 8);
  });

  it('refuses gradients, rounded corners and shadows by construction (the rule of docs/design/03)', () => {
    // A drawing that reached for createLinearGradient/arcTo/shadowBlur would
    // touch a member the contract does not have — the recorder lists it.
    const { ctx, forbidden } = recorder();
    drawWrapped(ctx, { ...(wrapped as Wrapped), cards: [] });
    expect(forbidden).toEqual([]);
    expect(Object.keys(DEFAULT_PALETTE)).toEqual(['ground', 'rule', 'label', 'text', 'accent', 'muted', 'cond', 'mono']);
  });

  it('caps at eight cards and survives an empty list', () => {
    const many = { ...(wrapped as Wrapped), cards: Array.from({ length: 12 }, (_, i) => ({ key: `k${i}`, label: `L${i}`, value: `${i}` })) };
    const { ctx, calls } = recorder();
    drawWrapped(ctx, many);
    const labels = calls.filter(([m, a]) => m === 'fillText' && /^L\d+$/.test(String(a[0])));
    expect(labels).toHaveLength(8);
    const empty = recorder();
    drawWrapped(empty.ctx, { ...(wrapped as Wrapped), cards: [] });
    expect(empty.calls.filter(([m]) => m === 'fillText')).toHaveLength(4); // head ×3 + footer
  });
});
