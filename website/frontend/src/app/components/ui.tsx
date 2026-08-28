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
  fontSize: 10,
  letterSpacing: '0.24em',
  textTransform: 'uppercase',
  color: 'var(--color-text-500)',
};

export const actStyle: CSSProperties = {
  fontSize: 13,
  letterSpacing: '0.14em',
  textTransform: 'uppercase',
  color: 'var(--color-text-200)',
  textDecoration: 'none',
  borderBottom: '1px solid #45433d',
  paddingBottom: 3,
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
      <span style={{ ...lblStyle, fontSize: 9 }}>{label}</span>
      {aside}
    </div>
  );
}

export function KpiTile({ value, label }: { value: ReactNode; label: ReactNode }) {
  return (
    <div style={{ padding: '18px 0 16px' }}>
      <div className="m" style={{ fontSize: 28, lineHeight: 1 }}>{value}</div>
      <div style={{ ...lblStyle, marginTop: 6 }}>{label}</div>
    </div>
  );
}

/** ok -> positive, warn -> warm, error -> negative, anything else -> idle grey. */
export function StatusDot({ state }: { state: 'ok' | 'warn' | 'error' | 'idle' | string }) {
  const color =
    state === 'ok' ? 'var(--color-pos)'
    : state === 'warn' ? 'var(--color-accent-warm)'
    : state === 'error' ? 'var(--color-neg)'
    : '#454340';
  return (
    <span
      style={{ width: 6, height: 6, borderRadius: '50%', flex: 'none', alignSelf: 'center', background: color, display: 'inline-block' }}
    />
  );
}

export function Pending({ label }: { label: string }) {
  return <span className="m" style={{ fontSize: 11, color: 'var(--color-text-500)' }}>{label}…</span>;
}

export function Unavailable({ what }: { what: string }) {
  return (
    <span className="m" style={{ fontSize: 11, color: 'var(--color-neg)' }}>
      {what}: unavailable
    </span>
  );
}

/** Integer figures grouped, non-integers to one decimal — columns must not dance. */
export function figure(value: number): string {
  return Number.isInteger(value) ? value.toLocaleString('en-US') : value.toFixed(1);
}
