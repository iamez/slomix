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
function age(seconds: unknown): string {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds)) return '';
  if (seconds < 90) return 'just now';
  if (seconds < 5400) return `${Math.round(seconds / 60)} min ago`;
  if (seconds < 172800) return `${Math.round(seconds / 3600)} h ago`;
  return `${Math.round(seconds / 86400)} d ago`;
}

/** The one detail line per stage that is worth reading at a glance —
 * legacy's _stageFacts, same keys, same order. */
function stageFacts(stage: SystemStage): string[] {
  const d = stage.detail ?? {};
  const facts: string[] = [];
  switch (stage.key) {
    case 'game_server':
      if (d.ping_ms != null) facts.push(`${d.ping_ms} ms`);
      break;
    case 'capture':
      if (d.age_seconds != null) facts.push(`last capture ${age(d.age_seconds)}`);
      if (d.unlinked_last_48h) facts.push(`${d.unlinked_last_48h} unlinked`);
      break;
    case 'parser':
      if (d.age_seconds != null) facts.push(`last round ${age(d.age_seconds)}`);
      if (d.last_round_at) facts.push(String(d.last_round_at).replace('T', ' ').slice(0, 16));
      break;
    case 'derived':
      if (d.gaming_session_id != null) facts.push(`session ${d.gaming_session_id}`);
      if (d.rounds != null) facts.push(`${d.rounds} rounds`);
      if (d.kill_impact_rows != null) facts.push(`${d.kill_impact_rows} KIS rows`);
      if (d.proximity_kills != null) facts.push(`${d.proximity_kills} tracked kills`);
      break;
    default:
      break;
  }
  return facts;
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
  if (!linkage || linkage.available !== true) {
    return (
      <div style={{ marginTop: 40 }}>
        <SectionHead label="data integrity" parity="system.linkage" />
        <div style={{ marginTop: 10 }}><Unavailable what="linkage check" /></div>
      </div>
    );
  }
  const m = linkage.metrics ?? {};
  const ratio = Number(m.unlinked_lua_ratio);
  const cells: { k: string; v: string }[] = [];
  if (Number.isFinite(ratio)) cells.push({ k: 'unlinked captures', v: `${(ratio * 100).toFixed(1)}%` });
  if (m.total_lua_rows != null) cells.push({ k: 'captured rounds', v: String(m.total_lua_rows) });
  if (m.wrong_start_lua_rows != null) cells.push({ k: 'wrong-round links', v: String(m.wrong_start_lua_rows) });
  const breaches = linkage.breaches ?? [];
  return (
    <div style={{ marginTop: 40 }}>
      <SectionHead label="data integrity" parity="system.linkage" />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', marginTop: 10, borderTop: '1px solid var(--color-rule-800)', borderBottom: '1px solid var(--color-rule-800)' }}>
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
      {overview.data && (
        <>
          <h1 style={{ fontSize: 34, letterSpacing: '0.03em', textTransform: 'uppercase', margin: '12px 0 0', fontWeight: 500 }}>
            {OVERALL_HEADLINE[overview.data.overall] ?? OVERALL_HEADLINE.unknown}
          </h1>
          <div className="m" style={{ fontSize: 11, color: 'var(--color-text-500)', marginTop: 6 }}>
            checked {String(overview.data.generated_at).replace('T', ' ').slice(0, 19)} utc
          </div>
          <div style={{ marginTop: 28 }}>
            <SectionHead label="the chain · game server → capture → parser → smart stats → api" parity="system.chain" />
            <div style={{ marginTop: 6 }}>
              {overview.data.stages.length === 0
                ? <div style={{ marginTop: 10 }}><Unavailable what="stages" /></div>
                : overview.data.stages.map((s) => <StageRow key={s.key} stage={s} />)}
            </div>
          </div>
          <Linkage linkage={overview.data.linkage} />
        </>
      )}
    </div>
  );
}
