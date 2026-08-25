import { useState } from 'react';
import { useSessions, useStorytellingCompleteness, type DiagScope } from '../lib/queries';
import type { StorytellingCompleteness } from '../lib/types';
import { Lbl, Pending, SectionHead, StatusDot, Unavailable, lblStyle, rowStyle } from '../components/ui';

/**
 * Smart Stats diagnostics (docs/design/12 row 29) — legacy
 * smart-stats-diag.js carried over: per-session health of the derived
 * layer — KIS completeness, kill→round linkage, R1+R2 correlation — with
 * the legacy thresholds kept verbatim. The endpoint requires a scope
 * (measured live: no params → 422), so the default date is the latest
 * session's from /api/sessions — same meaning as legacy's
 * /api/proximity/scopes detour, one already-covered endpoint instead of a
 * new one.
 */

function fmtPct(ratio: number | null): string {
  if (ratio == null || Number.isNaN(ratio)) return '—';
  return `${(ratio * 100).toFixed(1)}%`;
}

/** Legacy ratioBadge thresholds, per metric, unchanged. */
function ratioState(ratio: number | null, good: number, warn: number): string {
  if (ratio == null || Number.isNaN(ratio)) return 'idle';
  if (ratio >= good) return 'ok';
  if (ratio >= warn) return 'warn';
  return 'error';
}

interface Board {
  label: string;
  have: number;
  of: number;
  ratio: number | null;
  state: string;
  note: string;
}

function boards(d: StorytellingCompleteness): Board[] {
  return [
    {
      label: 'kis coverage',
      have: d.kis_rows, of: d.kills_total,
      ratio: d.completeness_ratio,
      state: ratioState(d.completeness_ratio, 0.95, 0.8),
      note: 'kills with a computed KIS row',
    },
    {
      label: 'round linkage',
      have: d.kills_with_round, of: d.kills_total,
      ratio: d.linkage_ratio,
      state: ratioState(d.linkage_ratio, 0.99, 0.9),
      note: 'kills linked to a round_id',
    },
    {
      label: 'r1+r2 correlation',
      have: d.rounds_correlated, of: d.rounds_total,
      ratio: d.correlation_ratio,
      state: ratioState(d.correlation_ratio, 0.9, 0.6),
      note: 'rounds with a match correlation',
    },
  ];
}

export function SmartStatsDiag() {
  const [pickedDate, setPickedDate] = useState<string | null>(null);
  const sessions = useSessions(1);
  // The DEFAULT scope is the latest session's ID, not its date: the
  // endpoint treats session_date as date-wide and merges every session on
  // that calendar day (Codex on #809). A user-picked date keeps date
  // semantics — that is what a date input asks for.
  const defaultGsid = sessions.data?.[0]?.session_id;
  const scope: DiagScope | null = pickedDate
    ? { session_date: pickedDate }
    : defaultGsid != null
      ? { gaming_session_id: defaultGsid }
      : null;
  const sessionDate = pickedDate ?? sessions.data?.[0]?.date ?? null;
  const diag = useStorytellingCompleteness(scope);
  const d = diag.data;
  const sessionsEmpty = sessions.isSuccess && sessions.data.length === 0;

  return (
    <div style={{ paddingTop: 44, paddingBottom: 40, maxWidth: 760 }}>
      <Lbl>smart stats · per-session health of the derived layer</Lbl>
      <h1 style={{ fontSize: 34, letterSpacing: '0.03em', textTransform: 'uppercase', margin: '12px 0 0', fontWeight: 500 }}>
        Is the storytelling data complete?
      </h1>

      <div data-parity="smart-stats-diag.picker" style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginTop: 18, flexWrap: 'wrap' }}>
        <Lbl style={{ fontSize: 9 }}>session date</Lbl>
        <input
          type="date"
          value={sessionDate ?? ''}
          onChange={(e) => { if (e.target.value) setPickedDate(e.target.value); }}
          aria-label="Session date"
          className="m"
          style={{
            background: 'var(--color-ink-800)', color: 'var(--color-text-100)',
            border: '1px solid var(--color-rule-700)', fontSize: 13, padding: '6px 10px',
          }}
        />
        {d && d.gaming_session_id != null && (
          <span className="m" style={{ fontSize: 11, color: 'var(--color-text-500)' }}>
            gaming_session_id {d.gaming_session_id}
            {d.session_dates.length > 1 ? ` · crosses midnight (${d.session_dates.join(' → ')})` : ''}
          </span>
        )}
      </div>

      {sessionDate === null && sessions.isError && (
        <div style={{ marginTop: 20 }}><Unavailable what="latest session date" /></div>
      )}
      {/* A successful [] is an empty state, not eternal pending: with no
        * default scope the diag query stays disabled, and disabled reads
        * as isPending forever (Codex on #809). */}
      {sessionsEmpty && pickedDate === null && (
        <div className="m" style={{ fontSize: 11, color: 'var(--color-text-500)', marginTop: 20 }}>
          no sessions recorded yet — pick a date to query one directly
        </div>
      )}
      {((diag.isPending && scope !== null) || (sessionDate === null && sessions.isPending)) && (
        <div style={{ marginTop: 20 }}><Pending label="diagnostics" /></div>
      )}
      {diag.isError && <div style={{ marginTop: 20 }}><Unavailable what="diagnostics" /></div>}

      {/* status 'no_data' is a valid answer, not a failure: zeros through
        * ratioState would paint three red boards for a date nobody played
        * (Codex on #809). */}
      {d && d.status === 'no_data' && (
        <div style={{ ...rowStyle, display: 'flex', alignItems: 'baseline', gap: 10, padding: '16px 0', marginTop: 20 }}>
          <StatusDot state="idle" />
          <span style={{ fontSize: 15, color: 'var(--color-text-300)' }}>
            No kill records for this scope — nothing to diagnose.
          </span>
        </div>
      )}
      {d && d.status !== 'no_data' && (
        <>
          <div data-parity="smart-stats-diag.boards" className="diag-boards" style={{ marginTop: 26, borderTop: '1px solid var(--color-rule-800)' }}>
            {boards(d).map((b) => (
              <div key={b.label} style={{ paddingTop: 16 }}>
                <SectionHead label={b.label} aside={<StatusDot state={b.state} />} />
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 10 }}>
                  <span className="m" style={{ fontSize: 30, lineHeight: 1 }}>{b.have.toLocaleString('en-US')}</span>
                  <span className="m" style={{ fontSize: 14, color: 'var(--color-text-500)' }}>/ {b.of.toLocaleString('en-US')}</span>
                </div>
                <div className="m" style={{ fontSize: 13, marginTop: 8, color: b.state === 'ok' ? 'var(--color-pos)' : b.state === 'warn' ? 'var(--color-accent-warm)' : b.state === 'error' ? 'var(--color-neg)' : 'var(--color-text-400)' }}>
                  {fmtPct(b.ratio)}
                </div>
                <Lbl style={{ fontSize: 9, marginTop: 8 }}>{b.note}</Lbl>
              </div>
            ))}
          </div>

          <div data-parity="smart-stats-diag.warnings" style={{ marginTop: 30 }}>
            {d.warnings.length === 0 ? (
              <div style={{ ...rowStyle, display: 'flex', alignItems: 'baseline', gap: 10, padding: '10px 0' }}>
                <StatusDot state="ok" />
                <span style={{ fontSize: 15, color: 'var(--color-text-300)' }}>
                  No warnings — Smart Stats for this session are complete and linked.
                </span>
              </div>
            ) : (
              d.warnings.map((w) => (
                <div key={w.message} style={{ ...rowStyle, display: 'flex', alignItems: 'baseline', gap: 10, padding: '10px 0' }}>
                  <StatusDot state={w.level === 'warning' ? 'warn' : 'idle'} />
                  <span className="m" style={{ ...lblStyle, fontSize: 10 }}>{w.level}</span>
                  <span style={{ fontSize: 15, color: 'var(--color-text-300)' }}>{w.message}</span>
                </div>
              ))
            )}
          </div>

          {d.known_issues.length > 0 && (
            <div style={{ marginTop: 34 }}>
              <SectionHead label="systemic caveats · affect every date" parity="smart-stats-diag.known-issues" />
              <div style={{ marginTop: 6 }}>
                {d.known_issues.map((issue) => (
                  <div key={issue.key} style={{ ...rowStyle, padding: '12px 0' }}>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 16, letterSpacing: '0.03em', textTransform: 'uppercase' }}>{issue.title}</span>
                      <span className="m" style={{ ...lblStyle, fontSize: 9 }}>{issue.key}</span>
                    </div>
                    <div style={{ fontSize: 14, color: 'var(--color-text-400)', marginTop: 4, maxWidth: '62ch' }}>{issue.detail}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <details data-parity="smart-stats-diag.raw" style={{ marginTop: 34 }}>
            <summary style={{ ...lblStyle, fontSize: 9, cursor: 'pointer' }}>raw json response</summary>
            <pre className="m" style={{ fontSize: 11, color: 'var(--color-text-300)', overflowX: 'auto', marginTop: 10, border: '1px solid var(--color-rule-700)', padding: 12 }}>
              {JSON.stringify(d, null, 2)}
            </pre>
          </details>
        </>
      )}
    </div>
  );
}
