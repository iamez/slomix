import { describe, expect, it } from 'vitest';
import { stripJsComments } from './testing/sourceText';

/**
 * The panel ratchet — the third sibling of tokens.test.ts and
 * vocabulary.test.ts, for the same reason: a page stays movable only while
 * there is ONE of each thing.
 *
 * The 2026-09-07 modularity audit (docs/SPA_MODULARITY.md) measured the
 * loading / error / failure-status / absent branch of a data panel
 * hand-written 58 times across the non-proximity pages, while the proximity
 * pages spelled it once, in `ProxPanel`. Nothing was broken; every copy was
 * slightly different, which is what makes "change how a panel looks" a
 * 38-file edit instead of a one-file edit. `ProxPanel` is now
 * `components/Panel.tsx`; this counts the HAND-WRITTEN opening of that
 * branch and holds it. The number may fall and must never rise, and BUDGET
 * has to be lowered in the same commit that lowers the count — a `<=` would
 * let the pile grow back under an allowance nobody is forced to update.
 */

const SOURCES = import.meta.glob('./**/*.{ts,tsx}', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

/** The hand-written first branch of the four: a query's pending flag gating
 *  a `<Pending`. Panel spells it exactly once, in its own body, which is why
 *  that file is excluded — a guard that counts the component's definition
 *  pushes the next person to hand-write the copy somewhere else. */
const HAND_WRITTEN_PENDING = /\bisPending\s*&&\s*<Pending\b/g;

function pageSources(): [string, string][] {
  return Object.entries(SOURCES)
    .filter(([file]) => !file.endsWith('.test.ts') && !file.endsWith('.test.tsx'))
    .filter(([file]) => file !== './components/Panel.tsx')
    .map(([file, text]) => [file, stripJsComments(text)]);
}

describe('data panels', () => {
  it('keeps the hand-written pending branch at exactly the budget', () => {
    // 61 measured on 2026-09-07 at main e91875cf with this exact matcher:
    // 58 in pages/ (`grep -o` over pages/*.tsx agrees) plus 4 in components
    // (PickPlayer, PlayerDrilldown, TeamplayTab ×2), minus nothing — the one
    // in PlayerProfile is its rating card, not the new SessionForm panel,
    // which is the first non-proximity consumer of <Panel>. Every one is a
    // candidate for <Panel>; slice 2 of
    // docs/SPA_MODULARITY.md converts Story (9), Home (7), SessionDetail (5),
    // AvailabilityPage (5) and SkillRating (4) first.
    const BUDGET = 61;
    let count = 0;
    // A Map, not an object written by a computed key — the scanners here
    // read `obj[file] = n` as an injection sink even for a glob path.
    const perFile = new Map<string, number>();
    for (const [file, text] of pageSources()) {
      const n = [...text.matchAll(HAND_WRITTEN_PENDING)].length;
      if (n) perFile.set(file, n);
      count += n;
    }
    expect(
      count,
      count > BUDGET
        ? `hand-written pending branches rose to ${count}; wrap the panel in <Panel> from components/Panel.tsx instead (${JSON.stringify(Object.fromEntries(perFile))})`
        : `hand-written pending branches are down to ${count} — lower BUDGET to ${count} in this commit`,
    ).toBe(BUDGET);
  });

  it('has exactly one definition of the frame', () => {
    const defs = Object.entries(SOURCES)
      .filter(([file]) => !file.endsWith('.test.ts') && !file.endsWith('.test.tsx'))
      .filter(([, text]) => /export function Panel</.test(text) || /export function ProxPanel</.test(text))
      .map(([file]) => file);
    expect(defs).toEqual(['./components/Panel.tsx']);
  });
});
