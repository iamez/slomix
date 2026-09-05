import { useDiagnostics } from '../lib/queries';
import { ApiError } from '../lib/api';
import type { Diagnostics, DiagnosticsTable } from '../lib/types';
import { Absent, Lbl, Pending, SectionHead, StatusDot, Unavailable, lblStyle, rowStyle } from '../components/ui';

/**
 * Backend diagnostics (/api/diagnostics, admin only) — legacy diagnostics.js
 * carried over: one page that answers "can the API read what it needs?".
 *
 * Three things this page refuses to blur, all of them measured on the wire
 * rather than assumed (2026-09-04):
 *
 *  1. THE AUTH TIERS ARE STATES. Anonymous gets 401 "Authentication required",
 *     an authenticated non-admin gets 403 "Admin privileges required", an
 *     admin gets 200. A page that renders both refusals as "failed to load"
 *     tells a signed-in player to sign in.
 *  2. A TABLE WITHOUT A COUNT IS NOT A TABLE WITH ZERO ROWS. `row_count` is
 *     present only on `status: "ok"`; the other three statuses carry an
 *     `error` instead. Printing 0 for a table nobody could read invents a
 *     fact about the database.
 *  3. AN EMPTY `time` BLOCK IS A FAILED QUERY, not a quiet one. The handler
 *     leaves `time` as `{}` and pushes the reason into `warnings`.
 */

const TABLE_DOT: Record<string, string> = {
  ok: 'ok',
  permission_denied: 'warn',
  not_found: 'error',
  error: 'error',
};

const OVERALL: Record<string, string> = {
  ok: 'The API can read everything it needs',
  warning: 'Readable, with something worth a look',
  error: 'Something the API needs is missing',
};

function seconds(total: number): string {
  if (!Number.isFinite(total)) return '—';
  const h = Math.floor(total / 3600);
  const m = Math.round((total % 3600) / 60);
  return h > 0 ? `${h} h ${m} min` : `${m} min`;
}

/** The count, or why there is no count. Never a substituted zero. */
function tableReading(t: DiagnosticsTable) {
  if (t.status === 'ok' && typeof t.row_count === 'number') {
    return <span>{t.row_count.toLocaleString('en-GB')} rows</span>;
  }
  return <Absent reason={t.error ?? `status ${t.status}, and the handler sent no reason`} />;
}

function Report({ d }: { d: Diagnostics }) {
  const time = d.time ?? {};
  const timeMeasured = typeof time.raw_dead_seconds === 'number';
  const pool = d.pool;
  return (
    <>
      <SectionHead label="overall" parity="diagnostics.status" />
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', margin: '0.5rem 0 1rem' }}>
        <StatusDot state={d.status === 'ok' ? 'ok' : d.status === 'warning' ? 'warn' : 'error'} />
        <span>{OVERALL[d.status] ?? `State ${d.status}`}</span>
      </div>
      {d.timestamp ? <Lbl>measured {d.timestamp}</Lbl> : <Absent reason="the handler sent no timestamp" />}

      <SectionHead label="tables the api reads" parity="diagnostics.tables" />
      {d.tables.length === 0 ? (
        <Absent block reason="the handler checked no tables — its own list is empty" />
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <tbody>
            {d.tables.map((t) => (
              <tr key={t.name} style={rowStyle}>
                <td style={{ padding: '0.35rem 0' }}>
                  <StatusDot state={TABLE_DOT[t.status] ?? 'idle'} />{' '}
                  <span style={{ marginLeft: '0.4rem' }}>{t.name}</span>
                  {!t.required && <span style={lblStyle}> optional</span>}
                </td>
                <td style={{ textAlign: 'right', padding: '0.35rem 0' }}>{tableReading(t)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <SectionHead label="issues" parity="diagnostics.issues" />
      {d.issues.length === 0
        ? <Absent block reason="nothing the API needs is missing" />
        : <ul>{d.issues.map((i) => <li key={i}>{i}</li>)}</ul>}

      <SectionHead label="warnings" parity="diagnostics.warnings" />
      {d.warnings.length === 0
        ? <Absent block reason="nothing worth a look" />
        : <ul>{d.warnings.map((w) => <li key={w}>{w}</li>)}</ul>}

      <SectionHead label="time accounting" parity="diagnostics.time" />
      {timeMeasured ? (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <tbody>
            <tr style={rowStyle}>
              <td style={{ padding: '0.35rem 0' }}>dead time, as stored</td>
              <td style={{ textAlign: 'right' }}>{seconds(time.raw_dead_seconds ?? 0)}</td>
            </tr>
            <tr style={rowStyle}>
              <td style={{ padding: '0.35rem 0' }}>dead time, capped at time played</td>
              <td style={{ textAlign: 'right' }}>{seconds(time.agg_dead_seconds ?? 0)}</td>
            </tr>
            <tr style={rowStyle}>
              <td style={{ padding: '0.35rem 0' }}>removed by the cap</td>
              <td style={{ textAlign: 'right' }}>
                {seconds(time.cap_seconds ?? 0)} over {(time.cap_hits ?? 0).toLocaleString('en-GB')} rows
              </td>
            </tr>
            <tr style={rowStyle}>
              <td style={{ padding: '0.35rem 0' }}>playtime denied to opponents</td>
              <td style={{ textAlign: 'right' }}>{seconds(time.raw_denied_seconds ?? 0)}</td>
            </tr>
          </tbody>
        </table>
      ) : (
        <Absent block reason="the timing query did not run — its reason is in the warnings above" />
      )}

      <SectionHead label="monitoring history" parity="diagnostics.monitoring" />
      {(['server', 'voice'] as const).map((key) => {
        const m = d.monitoring?.[key];
        return (
          <div key={key} style={{ ...rowStyle, padding: '0.35rem 0', display: 'flex', justifyContent: 'space-between' }}>
            <span>{key}</span>
            {!m ? (
              <Absent reason="the handler did not report this table" />
            ) : m.error ? (
              <Unavailable what={m.error} />
            ) : (
              <span>
                {m.count.toLocaleString('en-GB')} rows
                {m.last_recorded_at
                  ? <span style={lblStyle}> · last {m.last_recorded_at}</span>
                  : <Absent reason=" · nothing recorded yet" />}
              </span>
            )}
          </div>
        );
      })}

      <SectionHead label="connection pool" parity="diagnostics.pool" />
      {!pool ? (
        <Absent block reason="the handler did not report a pool" />
      ) : !pool.connected ? (
        <Absent block reason={pool.error ?? pool.reason ?? 'the adapter reports no pool'} />
      ) : (
        <div style={{ padding: '0.35rem 0' }}>
          {pool.in_use ?? 0} in use, {pool.idle ?? 0} idle of {pool.size ?? 0}
          <span style={lblStyle}> · limits {pool.min_size ?? '?'}–{pool.max_size ?? '?'} · {pool.utilisation_pct ?? 0}% used</span>
        </div>
      )}
    </>
  );
}

export function DiagnosticsPage() {
  const q = useDiagnostics();

  if (q.isPending) return <Pending label="reading the backend" />;

  if (q.error) {
    // 401 and 403 are ANSWERS. Only everything else is a failure.
    const status = q.error instanceof ApiError ? q.error.status : 0;
    if (status === 401) {
      return <Absent block reason="Diagnostics is an admin page and you are not signed in." />;
    }
    if (status === 403) {
      return <Absent block reason="You are signed in, but this page is for admins only." />;
    }
    return <Unavailable what="diagnostics" />;
  }

  return q.data ? <Report d={q.data} /> : <Absent block reason="the backend answered with no body" />;
}
