import { Fragment, isValidElement } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import { Link } from 'react-router';

/**
 * The design vocabulary as components (docs/design/11 §A) — born in Landing,
 * promoted here the moment a second page needed them. Rules these enforce so
 * pages don't have to remember them: labels are the smallest text on the page
 * (10px caps, wide tracking, --color-text-500 after the contrast amendment);
 * every figure renders mono with tabular digits; a pending section says so
 * and a failed one says "unavailable" — never an invented number, never an
 * empty box.
 */

export const lblStyle: CSSProperties = {
  fontSize: 'var(--fs-label)',
  letterSpacing: '0.24em',
  textTransform: 'uppercase',
  color: 'var(--color-text-500)',
};

export const actStyle: CSSProperties = {
  fontSize: 'var(--fs-value)',
  letterSpacing: '0.14em',
  textTransform: 'uppercase',
  color: 'var(--color-text-200)',
  textDecoration: 'none',
  borderBottom: '1px solid #45433d',
  paddingBottom: 'var(--space-1)',
};

export const rowStyle: CSSProperties = { borderBottom: '1px solid var(--color-rule-900)' };

export function Lbl({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return <div style={{ ...lblStyle, ...style }}>{children}</div>;
}

export function ActLink({ to, children, style }: { to: string; children: ReactNode; style?: CSSProperties }) {
  const external = to.startsWith('/auth') || to.startsWith('http');
  if (external) {
    return <a href={to} style={{ ...actStyle, ...style }}>{children}</a>;
  }
  return <Link to={to} style={{ ...actStyle, ...style }}>{children}</Link>;
}

/** `parity` renders as data-parity="route.panel" (docs/design/16:59) — the
 * frozen-inventory diff and the H3 sweep key on these attributes, so every
 * section head can carry its identity without extra markup. */
export function SectionHead({ label, aside, parity }: { label: ReactNode; aside?: ReactNode; parity?: string }) {
  return (
    <div data-parity={parity} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
      <span style={{ ...lblStyle, fontSize: 'var(--fs-caption)' }}>{label}</span>
      {aside}
    </div>
  );
}

/** BigScore (docs/design/11 §A): the BOX result, mono at hero size, team A
 *  in the accent, team B in the warm accent — the one place team B is warm.
 *  The separator is a label so it never reads as a third number. */
export function BigScore({ a, b, note }: {
  a: { name: ReactNode; score: ReactNode };
  b: { name: ReactNode; score: ReactNode };
  note?: ReactNode;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 'var(--space-4)' }}>
      <div>
        <Lbl>{a.name}</Lbl>
        <div className="m" style={{ fontSize: 'var(--fs-hero)', lineHeight: 0.84, color: 'var(--color-accent)' }}>{a.score}</div>
      </div>
      <Lbl style={{ fontSize: 'var(--fs-kpi)', paddingBottom: 'var(--space-2)' }}>/</Lbl>
      <div>
        <Lbl>{b.name}</Lbl>
        <div className="m" style={{ fontSize: 'var(--fs-hero)', lineHeight: 0.84, color: 'var(--color-accent-warm)' }}>{b.score}</div>
      </div>
      {note != null && <Lbl style={{ paddingBottom: 'var(--space-2)' }}>{note}</Lbl>}
    </div>
  );
}

/** A row of KpiTiles on hairlines — a grid without boxes (docs/design/11). */
export function FigureRow({ figures, parity }: {
  figures: readonly { value: ReactNode; label: ReactNode }[];
  parity?: string;
}) {
  return (
    <div
      data-parity={parity}
      style={{
        display: 'grid', gridTemplateColumns: `repeat(${figures.length}, minmax(0, 1fr))`,
        borderTop: '1px solid var(--color-rule-900)', borderBottom: '1px solid var(--color-rule-900)',
      }}
    >
      {figures.map((f, i) => <KpiTile key={i} value={f.value} label={f.label} />)}
    </div>
  );
}

export function KpiTile({ value, label }: { value: ReactNode; label: ReactNode }) {
  return (
    <div style={{ padding: 'var(--space-4) 0 var(--space-4)' }}>
      <div className="m" style={{ fontSize: 'var(--fs-kpi)', lineHeight: 1 }}>{value}</div>
      <div style={{ ...lblStyle, marginTop: 'var(--space-2)' }}>{label}</div>
    </div>
  );
}

/** ok -> positive, warn -> warm, error -> negative, anything else -> idle grey. */
export function StatusDot({ state }: { state: 'ok' | 'warn' | 'error' | 'idle' | string }) {
  const color =
    state === 'ok' ? 'var(--color-pos)'
    : state === 'warn' ? 'var(--color-accent-warm)'
    : state === 'error' ? 'var(--color-neg)'
    : 'var(--color-idle)';
  return (
    <span
      style={{ width: 6, height: 6, borderRadius: '50%', flex: 'none', alignSelf: 'center', background: color, display: 'inline-block' }}
    />
  );
}

/**
 * A framed toggle. This shape existed five times — byte-for-byte identical
 * `Pill` functions in Awards, Leaderboards, MapsPage, RecordBook and
 * WeaponsPage — which is five places to edit when the owner reworks the
 * controls, and five chances for one of them to drift.
 *
 * The pressed state rides on `aria-pressed`, so what a screen reader is told
 * and what the eye sees cannot disagree; the styling is the `.chip` class,
 * so a rework happens in the stylesheet rather than in five files.
 */
export function Chip({
  active, label, onClick, title,
}: { active: boolean; label: ReactNode; onClick: () => void; title?: string }) {
  return (
    <button type="button" className="chip" aria-pressed={active} onClick={onClick} title={title}>
      {label}
    </button>
  );
}

/**
 * Tabs — one selected at a time, the underline carrying the state. Same
 * decision as a Chip, worn differently, so it takes the same shape of props
 * rather than inventing a second one.
 *
 * `aria-selected` on a `tablist` is what makes the group announce itself as
 * a set with one chosen member; a row of independent buttons does not.
 */
export function Tabs<T extends string>({
  tabs, current, onSelect, parity,
}: {
  tabs: readonly { key: T; label: ReactNode }[];
  current: T;
  onSelect: (key: T) => void;
  parity?: string;
}) {
  return (
    <div role="tablist" data-parity={parity} style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
      {tabs.map((t) => (
        <button
          key={t.key}
          type="button"
          role="tab"
          className="tab"
          aria-selected={t.key === current}
          onClick={() => { onSelect(t.key); }}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function Pending({ label }: { label: string }) {
  return <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>{label}…</span>;
}

export function Unavailable({ what }: { what: string }) {
  return (
    <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-neg)' }}>
      {what}: unavailable
    </span>
  );
}

/**
 * The third state, and the one this project keeps getting wrong: the request
 * succeeded, and the answer is empty.
 *
 * `Pending` says a request is out and `Unavailable` says one failed. Until
 * now there was nothing for "the server answered, and the answer is
 * nothing" — so nineteen page files hand-wrote the same grey span forty-four
 * times, the workshop page among them, which exists precisely to show every
 * piece in every state (docs/design/11 §A lists this as EmptyState; it was
 * never built).
 *
 * The older React tree DID have an EmptyState, and it defaulted to "No data
 * available." with an emoji — which is the failure this one exists to
 * prevent: a generic message makes "nobody cleared the threshold", "this
 * window is empty" and "the query broke" read the same. So `reason` is
 * REQUIRED rather than defaulted, and the type enforces it instead of a
 * convention somebody has to remember (docs/design/11 §C: rules a component
 * enforces in place of discipline).
 *
 * Write the reason as a fact about the DATA, not about the request: "no map
 * has been played twice in this window", never "no results".
 */
export function Absent({ reason, block, style }: {
  /** ⛔ Not `ReactNode`: that set includes null, undefined and booleans, so a
   *  caller forwarding optional data could satisfy the type while rendering
   *  no explanation at all — which is the one thing this component exists to
   *  make impossible. `NonNullable` closes the type-level half; the runtime
   *  half below catches booleans and whitespace-only strings, which the type
   *  system cannot. */
  reason: NonNullable<ReactNode>;
  /** Render a <div> rather than a <span>. The call sites that were divs
   *  before this component existed pass it, so extracting them could not
   *  move a pixel — a refactor that also relayouts is two changes wearing
   *  one diff. */
  block?: boolean;
  style?: CSSProperties;
}) {
  // ⛔ Semantic styles AFTER the caller's, not before. `style` exists for
  // LAYOUT — every call site passes spacing only — but the prop accepts any
  // CSSProperties, and with the spread last a caller could repaint absence
  // in the failure colour and make it indistinguishable from Unavailable.
  // The grey IS the meaning; layout is the only thing a caller may vary.
  // (The colour goes unnamed here on purpose: the vocabulary test reads this
  // function's RAW source and rightly forbids the failure token inside it.)
  const s: CSSProperties = { ...style, fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' };
  const shown = hasSubstance(reason)
    ? reason
    // A page that reaches this line has a bug, and the honest render is one
    // that says so — not silence, which would quietly reintroduce the
    // reason-less absence this component was built to end.
    : 'absent — and the page gave no reason (page bug)';
  return block
    ? <div className="m" style={s}>{shown}</div>
    : <span className="m" style={s}>{shown}</span>;
}

/** The runtime half of Absent's required-reason guarantee: booleans render
 *  as nothing, and a whitespace-only string is a reason in name only.
 *
 *  ⛔ It has to RECURSE. The first version returned true for everything that
 *  was not null, a boolean, or a blank string, which quietly meant that
 *  `reason={items.map(...)}` over an empty collection passed the guarantee and
 *  rendered nothing — a reason-less absence, the exact thing this component
 *  exists to end, arriving through the check meant to prevent it. An empty
 *  array and an empty fragment are as silent as `null`; they just do not look
 *  it. Codex on #845, after the null/boolean/blank cases were already handled:
 *  a compound node is only as substantial as what it contains. */
function hasSubstance(node: ReactNode): boolean {
  if (node == null || typeof node === 'boolean') return false;
  if (typeof node === 'string') return node.trim().length > 0;
  if (typeof node === 'number' || typeof node === 'bigint') return true;
  if (Array.isArray(node)) return node.some(hasSubstance);
  if (isValidElement(node)) {
    // A fragment renders exactly its children and nothing of its own, so an
    // empty one is silence wearing element clothes. Any other element paints
    // something we cannot see from here — assume it speaks.
    return node.type === Fragment
      ? hasSubstance((node.props as { children?: ReactNode }).children)
      : true;
  }
  // ⚠️ A non-array iterable (a generator) is a ReactNode too, and we do NOT
  // look inside it: reading a one-shot iterator to judge it would leave React
  // an exhausted one and render the empty reason we are trying to forbid.
  // Checking it would CAUSE the failure it detects, so it counts as substance.
  return true;
}

/**
 * Secondary detail beside something that is there — a ping, a timestamp, the
 * map and round under a match row. Same grey as `Absent` and a different
 * job: this one carries a VALUE, so it never means absence. Keeping the two
 * apart in the source is what stops "no data" and "43 ms" from being the
 * same anonymous span with different children.
 */
export function Meta({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  // Same ordering rule as Absent, same reason: the grey is the identity.
  return (
    <span className="m" style={{ ...style, fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>
      {children}
    </span>
  );
}

/** Integer figures grouped, non-integers to one decimal — columns must not dance. */
export function figure(value: number): string {
  return Number.isInteger(value) ? value.toLocaleString('en-US') : value.toFixed(1);
}
