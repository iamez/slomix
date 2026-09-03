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

/**
 * The grey secondary line, however it is spelled inline.
 *
 * ⛔ ORDER-INSENSITIVE ON PURPOSE (Codex on #845). The first version matched
 * the pair only as `fontSize, color` adjacent — so a hand-written note with
 * the properties reversed, or with `whiteSpace` between them, slid past the
 * ratchet unseen. Property order in an object literal is incidental; the
 * VOCABULARY is the pair. Two patterns, one per order, each confined to a
 * single object literal by `[^{}]*?` so a fontSize in one style and a color
 * in the next cannot pair up across a brace.
 */
const FS = String.raw`fontSize:\s*'var\(--fs-(?:micro|caption)\)'`;
const COL = String.raw`color:\s*'var\(--color-text-500\)'`;
const GREY_NOTE_PATTERNS = [
  new RegExp(`${FS}[^{}]*?${COL}`, 'g'),
  new RegExp(`${COL}[^{}]*?${FS}`, 'g'),
];

function countGreyNotes(text: string): number {
  return GREY_NOTE_PATTERNS.reduce((n, re) => n + [...text.matchAll(re)].length, 0);
}

/** Everything except the tests and the one file where the pattern is
 *  DEFINED: ui.tsx spells it three times, in Pending, Absent and Meta, and a
 *  guard that counts its own component's body pushes the next person to
 *  hand-write the fourth copy somewhere else. */
function appSources(): [string, string][] {
  return Object.entries(SOURCES)
    .filter(([file]) => !file.endsWith('.test.ts') && !file.endsWith('.test.tsx'))
    .filter(([file]) => file !== './components/ui.tsx')
    // ErrorBoundary's grey <pre> is the crash screen showing error.message —
    // neither an absent answer (Absent would claim the request succeeded) nor
    // a value beside something present (Meta renders a span, this needs a
    // pre with pre-wrap). It is a third thing: diagnostic text on the failure
    // surface itself, deliberately subordinate to the headline. Excluded with
    // this stated reason rather than counted, because the alternative was
    // raising BUDGET by one — an allowance, which is the failure mode #823
    // named. If a second file ever needs this exemption, that is the signal
    // to design the component, not to lengthen this list.
    .filter(([file]) => file !== './components/ErrorBoundary.tsx')
    .map(([file, text]) => [file, stripJsComments(text)]);
}

describe('design vocabulary', () => {
  it('keeps the hand-written grey note at exactly the budget', () => {
    // 66 on this branch's base before Absent and Meta existed; 43 now, after
    // 24 conversions — the 24th surfaced only when the matcher above became
    // order-insensitive: Home's map-count span interleaved `textAlign`
    // between the pair and the original regex never saw it. What remains is
    // the absence notes on the four pages
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
    const BUDGET = 41;

    let count = 0;
    const perFile = new Map<string, number>();
    for (const [file, text] of appSources()) {
      const n = countGreyNotes(text);
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
    expect(signature).toMatch(/reason:\s*NonNullable<ReactNode>/);
    expect(signature).not.toMatch(/reason\?:/);
    expect(signature).not.toMatch(/reason\s*=\s*['"]/);
  });

  it('counts a grey note whichever way its properties are ordered', () => {
    // The controls for the matcher itself, each seen failing against the
    // old single-order regex before this shipped. A ratchet with a blind
    // spot is worse than none: it certifies the pile is not growing while
    // the pile grows in the one spelling it cannot see.
    const forward = "style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}";
    const reversed = "style={{ color: 'var(--color-text-500)', fontSize: 'var(--fs-micro)' }}";
    const interleaved =
      "style={{ fontSize: 'var(--fs-caption)', whiteSpace: 'pre-wrap', color: 'var(--color-text-500)' }}";
    expect(countGreyNotes(forward)).toBe(1);
    expect(countGreyNotes(reversed)).toBe(1);
    expect(countGreyNotes(interleaved)).toBe(1);
    // …and one of each across TWO style objects is not a pair: the brace
    // boundary must stop the match, or every page with one grey fontSize
    // and one unrelated grey color would count as a note it never wrote.
    const acrossObjects =
      "style={{ fontSize: 'var(--fs-micro)' }} … style={{ color: 'var(--color-text-500)' }}";
    expect(countGreyNotes(acrossObjects)).toBe(0);
  });
});
