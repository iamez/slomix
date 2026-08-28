import { useSystemOverview } from '../lib/queries';
import type { SystemStage } from '../lib/types';
import { Lbl, Pending, SectionHead, StatusDot, Unavailable, lblStyle, rowStyle } from '../components/ui';

/**
 * System overview (docs/design/12 row 28) — legacy system.js carried over:
 * one page that answers "is the chain running?" (game server → Lua capture →
 * parser → Smart Stats → website API) from /api/system/overview. Every stage
 * renders on its own, so one dead source greys out one row instead of
 * blanking the page. Deliberately NOT here, same as legacy: systemd units,
 * prod-vs-main drift, Lua hashes — the web process cannot see them and a
 * status page that guesses is worse than one that says nothing.
 */

const OVERALL_HEADLINE: Record<string, string> = {
  ok: 'Everything is running',
  idle: 'Everything is running — nobody has played lately',
  warn: 'Running, with something worth a look',
  down: 'Something is down',
  unknown: 'State unknown',
};

/** Map the API's stage states onto the dot vocabulary. */
function dotState(state: string): string {
  if (state === 'ok') return 'ok';
  if (state === 'warn') return 'warn';
  if (state === 'down') return 'error';
  return 'idle';
}

/** "2 h ago" / "3 d ago" from a seconds count the API already computed. */
function age(seconds: number): string {
  if (!Number.isFinite(seconds)) return '';
  if (seconds < 90) return 'just now';
  if (seconds < 5400) return `${Math.round(seconds / 60)} min ago`;
  if (seconds < 172800) return `${Math.round(seconds / 3600)} h ago`;
  return `${Math.round(seconds / 86400)} d ago`;
}

/** The one detail line per stage that is worth reading at a glance —
 * legacy's _stageFacts, same keys, same order. */
function stageFacts(stage: SystemStage): string[] {
  // detail values are `unknown` on purpose (the shape differs per stage and
  // has no response_model) — every read narrows by typeof, so a backend
  // shape change degrades to a missing fact, never to '[object Object]'.
  const d = stage.detail;
  const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
  const facts: string[] = [];
  const push = (v: number | null, render: (n: number) => string) => {
    if (v != null) facts.push(render(v));
  };
  switch (stage.key) {
    case 'game_server':
      push(num(d.ping_ms), (n) => `${n} ms`);
      break;
    case 'capture':
      push(num(d.age_seconds), (n) => `last capture ${age(n)}`);
      push(num(d.unlinked_last_48h), (n) => (n > 0 ? `${n} unlinked` : ''));
      break;
    case 'parser':
      push(num(d.age_seconds), (n) => `last round ${age(n)}`);
      if (typeof d.last_round_at === 'string') facts.push(d.last_round_at.replace('T', ' ').slice(0, 16));
      break;
    case 'derived':
      push(num(d.gaming_session_id), (n) => `session ${n}`);
      push(num(d.rounds), (n) => `${n} rounds`);
      push(num(d.kill_impact_rows), (n) => `${n} KIS rows`);
      push(num(d.proximity_kills), (n) => `${n} tracked kills`);
      break;
    default:
      break;
  }
  return facts.filter(Boolean);
}

function StageRow({ stage }: { stage: SystemStage }) {
  const facts = stageFacts(stage);
  return (
    <div style={{ ...rowStyle, display: 'flex', alignItems: 'baseline', gap: 12, padding: '13px 0' }}>
      <StatusDot state={dotState(stage.state)} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 17, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
            {stage.label || stage.key}
          </span>
          <span className="m" style={{ ...lblStyle, fontSize: 10 }}>{stage.state}</span>
        </div>
        <div style={{ fontSize: 14, color: 'var(--color-text-400)', marginTop: 2 }}>{stage.summary}</div>
        {facts.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 4 }}>
            {facts.map((f) => (
              <span key={f} className="m" style={{ fontSize: 11, color: 'var(--color-text-500)' }}>{f}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Linkage({ linkage }: { linkage: import('../lib/types').SystemOverview['linkage'] }) {
  // status 'error' means a subquery failed and the metrics are PARTIAL —
  // an empty breaches list then proves nothing, so the card says
  // unavailable instead of 'no thresholds breached' (Codex on #809).
  if (linkage.available !== true || linkage.status === 'error') {
    return (
      <div style={{ marginTop: 40 }}>
        <SectionHead label="data integrity" parity="system.linkage" />
        <div style={{ marginTop: 10 }}><Unavailable what="linkage check" /></div>
      </div>
    );
  }
  const m = linkage.metrics ?? {};
  const ratio = m.unlinked_lua_ratio;
  const cells: { k: string; v: string }[] = [];
  if (typeof ratio === 'number' && Number.isFinite(ratio)) cells.push({ k: 'unlinked captures', v: `${(ratio * 100).toFixed(1)}%` });
  if (typeof m.total_lua_rows === 'number') cells.push({ k: 'captured rounds', v: String(m.total_lua_rows) });
  if (typeof m.wrong_start_lua_rows === 'number') cells.push({ k: 'wrong-round links', v: String(m.wrong_start_lua_rows) });
  const breaches = linkage.breaches ?? [];
  return (
    <div style={{ marginTop: 40 }}>
      <SectionHead label="data integrity" parity="system.linkage" />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', marginTop: 10, borderTop: '1px solid var(--color-rule-900)', borderBottom: '1px solid var(--color-rule-900)' }}>
        {cells.map((c) => (
          <div key={c.k} style={{ padding: '14px 0 12px' }}>
            <div className="m" style={{ fontSize: 22, lineHeight: 1 }}>{c.v}</div>
            <Lbl style={{ marginTop: 6 }}>{c.k}</Lbl>
          </div>
        ))}
      </div>
      {breaches.length === 0 ? (
        <div className="m" style={{ fontSize: 11, color: 'var(--color-pos)', marginTop: 10 }}>
          no thresholds breached
        </div>
      ) : (
        <div style={{ marginTop: 10 }}>
          {breaches.map((b) => (
            <div key={b.metric} className="m" style={{ fontSize: 12, color: 'var(--color-accent-warm)' }}>
              {b.metric}: {b.value} (threshold {b.threshold})
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function SystemPage() {
  const overview = useSystemOverview();
  // A failed 30 s refetch must not show the stale healthy chain under the
  // error message — same derived-value rule as every landing panel.
  const data = overview.isError ? undefined : overview.data;

  return (
    <div data-parity="system.headline" style={{ paddingTop: 44, paddingBottom: 40, maxWidth: 760 }}>
      <Lbl>system · refreshed every 30 s · never from a cache</Lbl>
      {overview.isPending && <div style={{ marginTop: 16 }}><Pending label="checking the chain" /></div>}
      {overview.isError && (
        <div style={{ marginTop: 16 }}>
          <h1 style={{ fontSize: 34, letterSpacing: '0.03em', textTransform: 'uppercase', margin: 0, fontWeight: 500 }}>
            The website API did not answer.
          </h1>
          <p style={{ color: 'var(--color-text-400)', maxWidth: '44em' }}>
            That itself is the status: this page is served, the data endpoint behind it is not.
          </p>
        </div>
      )}
      {data && (
        <>
          <h1 style={{ fontSize: 34, letterSpacing: '0.03em', textTransform: 'uppercase', margin: '12px 0 0', fontWeight: 500 }}>
            {OVERALL_HEADLINE[data.overall] ?? OVERALL_HEADLINE.unknown}
          </h1>
          <div className="m" style={{ fontSize: 11, color: 'var(--color-text-500)', marginTop: 6 }}>
            checked {String(data.generated_at).replace('T', ' ').slice(0, 19)} utc
          </div>
          <div style={{ marginTop: 28 }}>
            <SectionHead label="the chain · game server → capture → parser → smart stats → api" parity="system.chain" />
            <div style={{ marginTop: 6 }}>
              {data.stages.length === 0
                ? <div style={{ marginTop: 10 }}><Unavailable what="stages" /></div>
                : data.stages.map((s) => <StageRow key={s.key} stage={s} />)}
            </div>
          </div>
          <Linkage linkage={data.linkage} />
        </>
      )}
    </div>
  );
}
