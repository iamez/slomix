import { describe, expect, it } from 'vitest';
import { stripJsComments } from './testing/sourceText';

/**
 * The vocabulary ratchet — a sibling of the one in tokens.test.ts, and for
 * the same reason: the pieces stay movable only while there is one of each.
 *
 * The design inventory (docs/design/11 §A) lists a component for "the answer
 * arrived and it is empty". It was never built, so nineteen page files spelled
 * it by hand — forty-four times, in two shapes (`<span>` and `<div>`), with
 * the workshop page among them. Nothing was broken; everything was slightly
 * different, which is how a page becomes unmovable: a rework has to find and
 * re-decide every copy instead of editing one component.
 *
 * So this counts the HAND-WRITTEN form and holds it. The number may fall and
 * must never rise, and the budget has to be lowered in the same commit that
 * lowers the count — a `<=` would let the pile grow back under an allowance
 * nobody is forced to update (the lesson Codex left on #823).
 */

const SOURCES = import.meta.glob('./**/*.{ts,tsx}', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

/** The grey secondary line, however it is spelled inline. */
const GREY_NOTE = /fontSize:\s*'var\(--fs-(?:micro|caption)\)',\s*color:\s*'var\(--color-text-500\)'/g;

/** Everything except the tests and the one file where the pattern is
 *  DEFINED: ui.tsx spells it three times, in Pending, Absent and Meta, and a
 *  guard that counts its own component's body pushes the next person to
 *  hand-write the fourth copy somewhere else. */
function appSources(): [string, string][] {
  return Object.entries(SOURCES)
    .filter(([file]) => !file.endsWith('.test.ts') && !file.endsWith('.test.tsx'))
    .filter(([file]) => file !== './components/ui.tsx')
    .map(([file, text]) => [file, stripJsComments(text)]);
}

describe('design vocabulary', () => {
  it('keeps the hand-written grey note at exactly the budget', () => {
    // 66 on this branch's base before Absent and Meta existed; 43 now, after
    // the 23 conversions. What remains is the absence notes on the four pages
    // open in review right now (Home, Story, SessionDetail, Rivalries), which
    // a sweeping refactor would only turn into conflicts, plus the lines that
    // are not absence at all — a ping, a timestamp, the map under a match
    // row. Those want `Meta`, and converting them is a second pass.
    //
    // The budget is what main has, not what main plus the open branches have.
    // That is deliberate and it has a consequence worth stating: once this
    // lands, a PR that adds a hand-written grey line fails here — including
    // my own #842 and #844, which each add a few and will need one commit to
    // use the component. A ratchet that leaves headroom for work already in
    // flight is an allowance nobody is forced to spend down, which is the
    // failure mode #823 named.
    const BUDGET = 43;

    let count = 0;
    const perFile = new Map<string, number>();
    for (const [file, text] of appSources()) {
      const n = [...text.matchAll(GREY_NOTE)].length;
      if (n > 0) perFile.set(file, n);
      count += n;
    }

    const worst = [...perFile.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5)
      .map(([f, n]) => `${f} (${n})`).join(', ');
    expect(
      count,
      count > BUDGET
        ? `hand-written grey notes rose to ${count} — use <Absent reason=…> for an empty answer, <Meta> for a value. Heaviest: ${worst}`
        : `hand-written grey notes are down to ${count} — lower BUDGET to ${count} in this commit`,
    ).toBe(BUDGET);
  });

  it('never lets the two grey states collapse into one', () => {
    // Absent and Unavailable answer different questions, and a page that
    // reaches for the wrong one tells the reader a broken query is an empty
    // season. The colour is the tell: absence is grey like every other
    // secondary line, a failure is --color-neg. Pin both, because the day
    // they share a colour is the day the distinction stops being visible.
    const ui = SOURCES['./components/ui.tsx'];
    expect(ui).toBeDefined();
    const absent = ui.slice(ui.indexOf('export function Absent'), ui.indexOf('export function Meta'));
    const unavailable = ui.slice(ui.indexOf('export function Unavailable'), ui.indexOf('/**', ui.indexOf('export function Unavailable')));
    expect(absent).toContain('--color-text-500');
    expect(absent).not.toContain('--color-neg');
    expect(unavailable).toContain('--color-neg');
    expect(unavailable).not.toContain('--color-text-500');
  });

  it('requires a reason, so absence can never be generic', () => {
    // The older React tree's EmptyState defaulted to "No data available."
    // That default is the whole defect: it made "nobody cleared the
    // threshold" and "the query broke" read the same. A default value here
    // would silently reintroduce it, so the prop must stay required — and
    // this asserts the TYPE, since a runtime test cannot see an optional
    // prop that nobody passed.
    const ui = SOURCES['./components/ui.tsx'];
    const signature = ui.slice(ui.indexOf('export function Absent'), ui.indexOf('export function Meta'));
    expect(signature).toMatch(/reason:\s*ReactNode/);
    expect(signature).not.toMatch(/reason\?:/);
    expect(signature).not.toMatch(/reason\s*=\s*['"]/);
  });
});
