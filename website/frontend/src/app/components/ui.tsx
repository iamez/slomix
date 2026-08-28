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

/** Integer figures grouped, non-integers to one decimal — columns must not dance. */
export function figure(value: number): string {
  return Number.isInteger(value) ? value.toLocaleString('en-US') : value.toFixed(1);
}
