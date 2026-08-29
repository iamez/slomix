import { useState } from 'react';
import { Link } from 'react-router';
import { useFormMovers } from '../lib/queries';
import type { SkillMoverRow } from '../lib/types';
import { Lbl, Pending, SectionHead, Unavailable, lblStyle, rowStyle } from '../components/ui';

/**
 * Form (docs/design/12 row 5) — legacy form.js carried over: seven metric
 * tabs over /api/skill/movers?full=true, three sections (heating up,
 * cooling off, first night), a sparkline per row and breakdown chips in
 * the Overall view. Rank-vs-self, never a global ladder — that sentence is
 * load-bearing (VISION anti-goal) and stays on the page.
 */

const METRICS: { key: string; label: string }[] = [
  { key: 'overall', label: 'Overall' },
  { key: 'dpm', label: 'Damage / min' },
  { key: 'kd', label: 'Kills / death' },
  { key: 'obj', label: 'Objectives' },
  { key: 'acc', label: 'Accuracy' },
  { key: 'kills', label: 'Kills' },
  { key: 'impact', label: 'Impact' },
];

function sparkPath(values: number[], w: number, h: number, pad: number): string {
  if (values.length < 2) return '';
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  return values
    .map((v, i) => {
      const x = pad + (i / (values.length - 1)) * (w - 2 * pad);
      const y = h - pad - ((v - min) / span) * (h - 2 * pad);
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(' ');
}

function MoverRow({ row, metric, tone }: { row: SkillMoverRow; metric: string; tone: 'up' | 'down' | 'new' }) {
  const color = tone === 'up' ? 'var(--color-pos)' : tone === 'down' ? 'var(--color-neg)' : 'var(--color-text-400)';
  const flat = row.delta_pct === 0;
  // A null value is a MISSING one — the legacy view omitted the comparison
  // rather than printing "vs null"; likewise a newcomer's null composite
  // must not read as "—% vs 100%".
  const baseline = metric === 'overall'
    ? row.latest != null ? `${row.latest}% vs 100%` : '—'
    : row.baseline != null
      ? `${row.latest ?? '—'} vs ${row.baseline}`
      : `${row.latest ?? '—'}`;
  return (
    <div style={rowStyle}>
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto 90px auto', gap: 'var(--space-3)', alignItems: 'center', padding: 'var(--space-2) 0' }}>
        <span>
          <Link to={`/profile/${row.guid}`} className="m" style={{ fontSize: 'var(--fs-value)', textDecoration: 'none', color: 'var(--color-text-100)' }}>
            {row.sick_leave ? `${row.name} · alt of ${row.sick_leave.primary_name}` : row.name}
          </Link>
        </span>
        <span className="m" style={{ ...lblStyle, fontSize: 'var(--fs-caption)' }}>{baseline}</span>
        {row.series.length > 1 ? (
          <svg viewBox="0 0 84 22" style={{ width: 84, height: 22 }}>
            <path d={sparkPath(row.series, 84, 22, 2)} fill="none" stroke={flat || row.is_new ? '#a78bfa' : color} strokeWidth="1.2" />
          </svg>
        ) : <span />}
        <span className="m" style={{ fontSize: 'var(--fs-micro)', color: flat ? 'var(--color-text-400)' : color, textAlign: 'right' }}>
          {row.is_new
            /* A linked sick-leave alternate must never read as a genuine
             * newcomer — the backend attaches the link for exactly this
             * (skill_router:927). Gated on `active === true`, parity with
             * home.js:69: a historical link (period_end set) arrives marked
             * inactive, and an ABSENT flag must not claim a sick leave we
             * do not know about (the type allows absence for a reason). */
            ? row.sick_leave?.active === true ? 'on sick leave' : 'first night'
            : flat
              ? '±0%'
              : row.delta_pct != null
                ? `${row.delta_pct > 0 ? '▲ +' : '▼ '}${Math.abs(row.delta_pct).toFixed(1)}%`
                : '—'}
        </span>
      </div>
      {metric === 'overall' && row.breakdown.length > 0 && (
        <div className="m" style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap', fontSize: 'var(--fs-caption)', color: 'var(--color-text-500)', padding: '0 0 var(--space-2)' }}>
          {row.breakdown.map((b) => (
            <span key={b.metric}>
              {b.label.toLowerCase()}{' '}
              {b.delta_pct != null ? `${b.delta_pct > 0 ? '+' : ''}${b.delta_pct.toFixed(1)}%` : '—'}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function FormPage() {
  const [metric, setMetric] = useState('overall');
  const movers = useFormMovers(metric);
  const data = movers.isError ? undefined : movers.data;
  const sections = data
    ? [
        { label: 'heating up · above own average', rows: data.movers_up, tone: 'up' as const },
        { label: 'cooling off · below own average', rows: data.movers_down, tone: 'down' as const },
        { label: 'first night', rows: data.new_players, tone: 'new' as const },
      ].filter((s) => s.rows.length > 0)
    : [];
  return (
    <div style={{ paddingTop: 'var(--space-7)', paddingBottom: 'var(--space-7)', maxWidth: 760 }}>
      <Lbl>form · each player against their own trailing average</Lbl>
      <h1 style={{ fontSize: 'var(--fs-title)', letterSpacing: '0.03em', textTransform: 'uppercase', margin: 'var(--space-3) 0 0', fontWeight: 500 }}>
        Who is heating up, and who is cooling off.
      </h1>
      <div data-parity="form.tabs" style={{ display: 'flex', gap: 'var(--space-2)', marginTop: 'var(--space-4)', flexWrap: 'wrap' }}>
        {METRICS.map((m) => (
          <button
            key={m.key}
            type="button"
            onClick={() => { setMetric(m.key); }}
            style={{
              fontSize: 'var(--fs-small)', letterSpacing: '0.08em', textTransform: 'uppercase', cursor: 'pointer',
              border: `1px solid ${metric === m.key ? '#4a5a66' : 'var(--color-rule-700)'}`,
              background: metric === m.key ? '#151a1e' : 'transparent',
              color: metric === m.key ? 'var(--color-text-100)' : 'var(--color-text-400)',
              padding: 'var(--space-1) var(--space-2)',
            }}
          >
            {m.label}
          </button>
        ))}
      </div>
      <div data-parity="form.sections" style={{ marginTop: 'var(--space-4)' }}>
        {movers.isPending && <Pending label="form" />}
        {movers.isError && <Unavailable what="form" />}
        {data && sections.length === 0 && (
          <div className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>
            form data appears after the next session
          </div>
        )}
        {sections.map((s) => (
          <div key={s.label} style={{ marginTop: 'var(--space-4)' }}>
            <SectionHead label={s.label} />
            <div style={{ marginTop: 'var(--space-2)' }}>
              {s.rows.map((row) => <MoverRow key={row.guid} row={row} metric={metric} tone={s.tone} />)}
            </div>
          </div>
        ))}
        {data && metric === 'overall' && (
          <Lbl style={{ fontSize: 'var(--fs-caption)', marginTop: 'var(--space-4)', lineHeight: 1.7 }}>
            composite: damage 25% · impact 25% · k/d 20% · objectives 15% · accuracy 10% · kills 5% —
            measured against each player's own ~10-session average. rank-vs-self, not a ranking.
          </Lbl>
        )}
      </div>
    </div>
  );
}
