import { Absent, Lbl, StatusDot, Unavailable, lblStyle, rowStyle } from './ui';
import { figure } from './ui';
import type { Diagnostics, DiagnosticsTable } from '../lib/types';

/**
 * The backend diagnostics report (/api/diagnostics), as the admin panel on
 * About renders it. Carried over from the closed #911 on 2026-09-06 — the
 * four things the handler's shape makes easy to blur, each a branch of
 * website/backend/routers/diagnostics_router.py get_diagnostics():
 *
 *  1. A TABLE WITHOUT A COUNT IS NOT A TABLE WITH ZERO ROWS. `row_count` is
 *     present only on `status: "ok"`; the other statuses carry an `error`.
 *     A real `row_count: 0` still prints "0 rows".
 *  2. AN EMPTY `time` BLOCK IS A QUERY THAT DID NOT RUN. The handler leaves
 *     `time` as `{}` and pushes the reason into `warnings` (usually).
 *  3. A MONITORING TABLE THAT FAILED IS `unavailable`, NOT "0 rows". The
 *     handler sends `{count: 0, last_recorded_at: null, error: "query
 *     failed"}` — `error` has to be read BEFORE `count`. Until this port the
 *     panel printed "voice 0 rows" for exactly that payload.
 *  4. Monitoring and pool never change the top-level `status`: the handler
 *     computes it from issues/warnings before it collects them.
 */

const TABLE_DOT: Record<string, string> = {
  ok: 'ok',
  permission_denied: 'warn',
  not_found: 'error',
  error: 'error',
};

const OVERALL: Record<string, string> = {
  ok: 'the api can read everything it needs',
  warning: 'readable, with something worth a look',
  error: 'something the api needs is missing',
};

export function seconds(total: number): string {
  if (!Number.isFinite(total)) return '—';
  const h = Math.floor(total / 3600);
  const m = Math.round((total % 3600) / 60);
  return h > 0 ? `${h} h ${m} min` : `${m} min`;
}

/** The count, or why there is no count. Never a substituted zero. */
export function tableReading(t: DiagnosticsTable) {
  if (t.status === 'ok' && typeof t.row_count === 'number') {
    return <span className="m">{figure(t.row_count)} rows</span>;
  }
  return <Absent reason={t.error ?? `status ${t.status}, and the handler sent no reason`} />;
}

const cell = { padding: 'var(--space-2) 0' } as const;
const right = { ...cell, textAlign: 'right' as const };

export function DiagnosticsReport({ d }: { d: Diagnostics }) {
  const time = d.time ?? {};
  const timeMeasured = typeof time.raw_dead_seconds === 'number';
  const pool = d.pool;
  return (
    <div data-parity="admin.diagnostics.report">
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', margin: 'var(--space-2) 0 var(--space-3)' }}>
        <StatusDot state={d.status === 'ok' ? 'ok' : d.status === 'warning' ? 'warn' : 'error'} />
        <span className="m" style={{ fontSize: 'var(--fs-row)' }}>{OVERALL[d.status] ?? `state ${d.status}`}</span>
        <Lbl style={{ fontSize: 'var(--fs-caption)' }}>· database {d.database.status}</Lbl>
      </div>

      <Lbl>tables the api reads</Lbl>
      {d.tables.length === 0 ? (
        <Absent block reason="the handler checked no tables — its own list is empty" />
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <tbody>
            {d.tables.map((t) => (
              <tr key={t.name} style={rowStyle}>
                <td style={cell}>
                  <StatusDot state={TABLE_DOT[t.status] ?? 'idle'} />
                  <span className="m" style={{ marginLeft: 'var(--space-2)', fontSize: 'var(--fs-row)', color: 'var(--color-text-300)' }}>{t.name}</span>
                  {!t.required && <span style={lblStyle}> optional</span>}
                </td>
                <td style={right}>{tableReading(t)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {d.issues.length > 0 && (
        <div style={{ marginTop: 'var(--space-3)' }}>
          {d.issues.map((i) => (
            <div key={i} style={{ fontSize: 'var(--fs-small)', color: 'var(--color-neg)' }}>{i}</div>
          ))}
        </div>
      )}
      {d.warnings.length > 0 && (
        <div style={{ marginTop: 'var(--space-2)' }}>
          {d.warnings.map((w) => (
            <div key={w} style={{ fontSize: 'var(--fs-small)', color: 'var(--color-accent-warm)' }}>{w}</div>
          ))}
        </div>
      )}

      <Lbl style={{ marginTop: 'var(--space-4)' }}>time accounting</Lbl>
      {timeMeasured ? (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <tbody>
            <tr style={rowStyle}><td style={cell}>dead time, as stored</td><td style={right}>{seconds(time.raw_dead_seconds ?? 0)}</td></tr>
            <tr style={rowStyle}><td style={cell}>dead time, capped at time played</td><td style={right}>{seconds(time.agg_dead_seconds ?? 0)}</td></tr>
            <tr style={rowStyle}>
              <td style={cell}>removed by the cap</td>
              <td style={right}>{seconds(time.cap_seconds ?? 0)} over {figure(time.cap_hits ?? 0)} rows</td>
            </tr>
            <tr style={rowStyle}><td style={cell}>playtime denied to opponents</td><td style={right}>{seconds(time.raw_denied_seconds ?? 0)}</td></tr>
          </tbody>
        </table>
      ) : (
        <Absent block reason="the timing query did not run — its reason, when the handler had one, is in the warnings above" />
      )}

      <Lbl style={{ marginTop: 'var(--space-4)' }}>monitoring history</Lbl>
      {(['server', 'voice'] as const).map((key) => {
        const m = d.monitoring?.[key];
        return (
          <div key={key} style={{ ...rowStyle, ...cell, display: 'flex', justifyContent: 'space-between', gap: 'var(--space-2)' }}>
            <span className="m" style={{ fontSize: 'var(--fs-row)' }}>{key}</span>
            {!m ? (
              <Absent reason="the handler did not report this table" />
            ) : m.error ? (
              <Unavailable what={m.error} />
            ) : (
              <span className="m" style={{ fontSize: 'var(--fs-row)' }}>
                {figure(m.count)} rows
                {m.last_recorded_at
                  ? <span style={lblStyle}> · last {m.last_recorded_at.replace('T', ' ').slice(0, 19)}</span>
                  : <Absent reason=" · nothing recorded yet" />}
              </span>
            )}
          </div>
        );
      })}

      <Lbl style={{ marginTop: 'var(--space-4)' }}>connection pool</Lbl>
      {!pool ? (
        <Absent block reason="the handler did not report a pool" />
      ) : !pool.connected ? (
        <Absent block reason={pool.error ?? pool.reason ?? 'the adapter reports no pool'} />
      ) : (
        <div className="m" style={{ ...cell, fontSize: 'var(--fs-row)' }}>
          {pool.in_use ?? 0} in use, {pool.idle ?? 0} idle of {pool.size ?? 0}
          <span style={lblStyle}> · limits {pool.min_size ?? '?'}–{pool.max_size ?? '?'} · {pool.utilisation_pct ?? 0}% used</span>
        </div>
      )}
      <Lbl style={{ fontSize: 'var(--fs-caption)', marginTop: 'var(--space-3)' }}>
        the overall state is computed from issues and warnings only — a failed monitoring table or a missing pool does not change it
      </Lbl>
    </div>
  );
}
