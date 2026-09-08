/**
 * Phase 6 — the live surface (route live): the server card whose roster
 * LINGERS through delivery gaps (dimmed by age, never oscillating
 * full↔empty — the backend's own contract), the event feed, 24 hours of
 * server and voice activity as sparklines, and the monitoring panel that
 * says out loud when its own data is stale.
 */
import { useEffect, useState } from 'react';
import { Cluster, Stack } from '../components/layout';
import { Absent, Lbl, Meta, Pending, SectionHead, Unavailable, figure } from '../components/ui';
import { Panel } from '../components/Panel';
import { mmss } from '../components/RoundsTable';
import { mapLabel } from '../lib/maps';
import { stripEtColors } from '../lib/names';
import {
  useApiHealth, useLiveFeed, useLiveState, useMonitoringStatus,
  useServerActivityHistory, useTonight, useVoiceActivityHistory,
} from '../lib/queries';
import type { LiveRosterMember, LiveState, TonightMap, TonightStatus } from '../lib/types';

function Spark({ pts, label }: { pts: { t: string; v: number }[]; label: string }) {
  if (pts.length < 2) return <Absent reason="not enough history for a line" />;
  const W = 640; const H = 80;
  const maxV = Math.max(1, ...pts.map((p) => p.v));
  const d = pts.map((p, i) => {
    const x = (i / (pts.length - 1)) * (W - 8) + 4;
    const y = H - 6 - (p.v / maxV) * (H - 14);
    return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`;
  }).join(' ');
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', maxWidth: W }} role="img" aria-label={label}>
      <path d={d} fill="none" stroke="var(--color-accent)" strokeWidth="1.2" />
    </svg>
  );
}

function RosterSide({ side, members }: { side: string; members: LiveRosterMember[] }) {
  if (members.length === 0) return null;
  return (
    <Stack gap={1} style={{ minWidth: 200 }}>
      <Lbl>{side}</Lbl>
      {members.map((m) => (
        <Cluster key={m.slot} gap={3} align="baseline" justify="between">
          <span style={{ fontSize: 'var(--fs-row)' }}>{stripEtColors(m.name)}</span>
          {m.live && (
            <Meta>{figure(m.live.kills)}/{figure(m.live.deaths)}{m.live.dpm != null && <> · {figure(m.live.dpm)} dpm</>}</Meta>
          )}
        </Cluster>
      ))}
    </Stack>
  );
}

const SIDE_WORD = { axis: 'Axis', allies: 'Allies' } as const;
const REASON_WORD = { timelimit: 'full hold', surrender: 'surrender', objective: 'objective taken', other: 'ended' } as const;

/** The one line a visitor reads first: which half, how far into it, what
 *  the attack must beat, who attacks — and what the LAST half ended on,
 *  so the seconds between rounds are not a blank WARMUP. All from
 *  /api/live/state (#977); `time_to_beat_seconds` is the reducer's own
 *  measurement of the first half, the tonight card's `beat_seconds` is the
 *  database's — both are shown when they exist, because they can differ
 *  by the pause handling and a reader should see that. */
function NowStrip({ state, beatFromDb }: { state: LiveState; beatFromDb: number | null }) {
  const last = state.last_round_result ?? null;
  const lastLine = last
    ? `last: R${last.round_number ?? '?'} ${REASON_WORD[last.reason] ?? last.reason} ${mmss(last.duration_seconds)}${last.winner_side ? ` (${SIDE_WORD[last.winner_side]})` : ''}${last.map != null && last.map !== state.current_map ? ` on ${mapLabel(last.map)}` : ''}`
    : null;
  const live = state.is_live && state.game_state === 'live' && state.round_number != null;
  const beat = state.time_to_beat_seconds ?? beatFromDb;
  return (
    <div data-parity="live.now">
      <Cluster gap={4} align="baseline" style={{ flexWrap: 'wrap' }}>
        {live ? (
          <span className="m" style={{ fontSize: 'var(--fs-value)' }}>
            R{figure(state.round_number!)} · {mmss(state.round_elapsed_seconds ?? 0)}
            {beat != null && <> / to beat {mmss(beat)}</>}
          </span>
        ) : (
          <span className="m" style={{ fontSize: 'var(--fs-value)' }}>{state.is_live ? state.game_state : 'idle'}</span>
        )}
        {state.attacking_side && <Meta>{SIDE_WORD[state.attacking_side]} attack</Meta>}
        {lastLine && <Meta>{lastLine}</Meta>}
        {state.previous_map != null && <Meta>before that {mapLabel(state.previous_map)}</Meta>}
        {state.session_start_seconds != null && <Meta>server up {mmss(state.session_start_seconds)}</Meta>}
      </Cluster>
      {(state.recent_objectives?.length ?? 0) > 0 && (
        <Stack gap={1} style={{ marginTop: 'var(--space-2)' }}>
          {state.recent_objectives!.slice(-4).map((o, i) => (
            <Meta key={`${o.verb}:${o.objective}:${i}`}>{o.player ?? (o.team ? SIDE_WORD[o.team as 'axis' | 'allies'] ?? o.team : 'someone')} {o.verb} {o.objective}</Meta>
          ))}
        </Stack>
      )}
      {(state.recent_roster_changes?.length ?? 0) > 0 && (
        <Stack gap={1} style={{ marginTop: 'var(--space-2)' }}>
          {state.recent_roster_changes!.slice(-4).map((c, i) => (
            <Meta key={`${c.name}:${c.action}:${i}`}>{stripEtColors(c.name)} {c.action}{c.side ? ` (${c.side})` : ''} · {figure(c.age_seconds)} s ago</Meta>
          ))}
        </Stack>
      )}
    </div>
  );
}

/** Historical chance the attack has completed by a given time, drawn WITH
 *  axes and a marker — the legacy canvas had neither, which made 40 % of
 *  the viewport decorative. `markerSeconds` is the time to beat (the
 *  second half) or the live clock (the first). */
function HoldCurve({ curve, markerSeconds, label }: { curve: { t: number; p: number }[]; markerSeconds: number | null; label: string }) {
  if (curve.length < 2) return <Absent reason="no historical holds on this map yet" />;
  const W = 640; const H = 110; const L = 36; const B = 18;
  const tMax = Math.max(1, ...curve.map((c) => c.t));
  const x = (t: number) => L + (t / tMax) * (W - L - 6);
  const y = (p: number) => 6 + (1 - p) * (H - B - 6);
  const d = curve.map((c, i) => `${i === 0 ? 'M' : 'L'}${x(c.t).toFixed(1)} ${y(c.p).toFixed(1)}`).join(' ');
  const at = markerSeconds != null ? curve.reduce((acc, c) => (c.t <= markerSeconds ? c : acc), curve[0]) : null;
  return (
    <Stack gap={1}>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', maxWidth: W }} role="img" aria-label={label}>
        {[0, 0.5, 1].map((p) => (
          <g key={p}>
            <line x1={L} x2={W - 6} y1={y(p)} y2={y(p)} stroke="var(--color-rule-900)" strokeWidth="1" />
            <text x={L - 4} y={y(p) + 3} textAnchor="end" fill="var(--color-text-500)" fontSize="9">{Math.round(p * 100)}%</text>
          </g>
        ))}
        {[0, tMax / 2, tMax].map((t) => (
          <text key={t} x={x(t)} y={H - 4} textAnchor="middle" fill="var(--color-text-500)" fontSize="9">{mmss(Math.round(t))}</text>
        ))}
        <path d={d} fill="none" stroke="var(--color-accent)" strokeWidth="1.2" />
        {markerSeconds != null && (
          <line x1={x(Math.min(markerSeconds, tMax))} x2={x(Math.min(markerSeconds, tMax))} y1={6} y2={H - B} stroke="var(--color-neg)" strokeWidth="1" strokeDasharray="3 3" />
        )}
      </svg>
      {at != null && markerSeconds != null && (
        <Meta>by {mmss(markerSeconds)} the attack had completed in {Math.round(at.p * 100)} % of recorded halves on this map</Meta>
      )}
    </Stack>
  );
}

/** Team momentum over the evening's halves — two lines with a legend and
 *  the last value, instead of an unlabelled canvas. */
function MomentumLines({ momentum, a, b }: { momentum: { a: number; b: number }[]; a: string; b: string }) {
  if (momentum.length < 2) return <Absent reason="momentum needs at least two halves" />;
  const W = 640; const H = 70;
  const path = (key: 'a' | 'b') => momentum.map((m, i) => `${i === 0 ? 'M' : 'L'}${((i / (momentum.length - 1)) * (W - 8) + 4).toFixed(1)} ${(H - 6 - (m[key] / 100) * (H - 12)).toFixed(1)}`).join(' ');
  const last = momentum[momentum.length - 1];
  return (
    <Stack gap={1}>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', maxWidth: W }} role="img" aria-label="team momentum">
        <path d={path('a')} fill="none" stroke="var(--color-accent)" strokeWidth="1.2" />
        <path d={path('b')} fill="none" stroke="var(--color-neg)" strokeWidth="1.2" />
      </svg>
      <Meta>{a} {figure(last.a)} % · {b} {figure(last.b)} % after {figure(momentum.length)} halves</Meta>
    </Stack>
  );
}

function MapCard({ m, a, b }: { m: TonightMap; a: string; b: string }) {
  const team = (w: string | null) => (w === 'a' ? a : w === 'b' ? b : w === 'draw' ? 'draw' : 'pending');
  return (
    <Stack gap={1} className="row" style={{ padding: 'var(--space-2) 0' }}>
      <Cluster gap={3} justify="between" align="baseline">
        <span style={{ fontSize: 'var(--fs-row)' }}>{mapLabel(m.map)} <Meta>#{figure(m.map_number)}</Meta></span>
        <span className="m" style={{ fontSize: 'var(--fs-row)' }}>{m.winner === 'pending' ? 'live' : `${figure(m.a_points)}–${figure(m.b_points)}`}{m.winner !== 'pending' && <Meta> · {team(m.winner)}</Meta>}</span>
      </Cluster>
      <Cluster gap={4} align="baseline" style={{ flexWrap: 'wrap' }}>
        {m.rounds.map((r) => (
          <Meta key={r.round}>
            R{figure(r.round)} {team(r.winner)}{r.duration != null && <> · {mmss(r.duration)}</>}
            {r.is_fullhold && ' · full hold'}
            {r.axis_score != null && r.allies_score != null && <> · axis {figure(r.axis_score)}–{figure(r.allies_score)} allies</>}
            {r.a_on_axis != null && <> · {a} on {r.a_on_axis ? 'axis' : 'allies'}</>}
          </Meta>
        ))}
      </Cluster>
    </Stack>
  );
}

/** Tonight's score board from /api/stats/tonight — the database's view of
 *  the evening (maps, halves, the R2 chase, the director's sentence, hold
 *  probability, momentum). The legacy page drew this; the new one fetched
 *  it for the Home card and showed one flag of it (ledger 2026-09-08). */
function TonightBoard({ q, liveElapsed }: { q: ReturnType<typeof useTonight>; liveElapsed: number | null }) {
  return (
    <Panel<TonightStatus>
      parity="live.tonight"
      label="tonight"
      aside={q.data?.current?.status ? `${q.data.current.status}${q.data.age_seconds != null ? ` · updated ${mmss(q.data.age_seconds)} ago` : ''}` : undefined}
      q={q}
      empty="no round has been imported today — the board wakes with the first"
      isEmpty={(d) => d.maps.length === 0}
    >
      {(d) => {
        const a = d.teams.a?.name ?? 'Team A';
        const b = d.teams.b?.name ?? 'Team B';
        const cur = d.current;
        return (
          <Stack gap={3}>
            {d.director && <span style={{ fontSize: 'var(--fs-lead)' }}>{d.director}</span>}
            <Cluster gap={5} align="baseline" style={{ flexWrap: 'wrap' }}>
              <span className="m" style={{ fontSize: 'var(--fs-value)' }}>{a} {figure(d.score.a_maps ?? 0)} – {figure(d.score.b_maps ?? 0)} {b}</span>
              <Meta>maps · rounds {figure(d.score.a_rounds ?? 0)}–{figure(d.score.b_rounds ?? 0)} · {figure(d.score.maps_completed ?? 0)} completed{d.active ? '' : ' · not live now'}</Meta>
            </Cluster>
            <Cluster gap={5} align="baseline" style={{ flexWrap: 'wrap' }}>
              {d.teams.a && <Meta>{a}: {d.teams.a.roster.map(stripEtColors).join(', ')}</Meta>}
              {d.teams.b && <Meta>{b}: {d.teams.b.roster.map(stripEtColors).join(', ')}</Meta>}
            </Cluster>
            {cur && (
              <Meta>
                now {mapLabel(cur.map)} R{figure(cur.round)} · {cur.status}
                {cur.r2_pending && cur.beat_seconds != null && <> · 🏁 attack must beat {mmss(cur.beat_seconds)}</>}
              </Meta>
            )}
            <Stack gap={1} className="rows">
              {d.maps.map((m) => <MapCard key={m.map_number} m={m} a={a} b={b} />)}
            </Stack>
            {d.hold_probability && (
              <Stack gap={1}>
                <Lbl>hold probability · {mapLabel(d.hold_probability.map)}</Lbl>
                <HoldCurve
                  curve={d.hold_probability.curve}
                  markerSeconds={cur?.r2_pending && cur.beat_seconds != null ? cur.beat_seconds : liveElapsed}
                  label={`hold probability on ${d.hold_probability.map}`}
                />
              </Stack>
            )}
            <Stack gap={1}>
              <Lbl>momentum</Lbl>
              <MomentumLines momentum={d.momentum} a={a} b={b} />
            </Stack>
            {d.last_update_unix != null && <Meta>last row {new Date(d.last_update_unix * 1000).toLocaleTimeString()}{d.current_map ? ` · ${mapLabel(d.current_map)}` : ''}</Meta>}
          </Stack>
        );
      }}
    </Panel>
  );
}

export function LivePage() {
  const state = useLiveState();
  const tonight = useTonight();
  // The feed cursor ADVANCES: since=0 fetches the newest ring page, every
  // later poll asks only for seq > since, per the /api/live/feed contract.
  // Events accumulate here because a cursor poll returns only the new ones.
  const [since, setSince] = useState(0);
  const [log, setLog] = useState<{ seq: number; type: string }[]>([]);
  const [gapNote, setGapNote] = useState<string | null>(null);
  const feed = useLiveFeed(since);
  const feedData = feed.data;
  useEffect(() => {
    if (feedData == null) return;
    if (since > 0 && feedData.oldest_seq != null && feedData.oldest_seq > since + 1) {
      setGapNote(`ring overwrote ${figure(feedData.oldest_seq - since - 1)} events between polls`);
    }
    if (feedData.events.length > 0) {
      setLog((prev) => [...prev, ...feedData.events.filter((e) => !prev.some((p) => p.seq === e.seq))].slice(-200));
    }
    if (feedData.last_seq > since) setSince(feedData.last_seq);
  }, [feedData, since]);
  const server = useServerActivityHistory(24);
  const voice = useVoiceActivityHistory(24);
  const monitoring = useMonitoringStatus();
  const health = useApiHealth();

  return (
    <Stack gap={7} style={{ paddingTop: 'var(--space-7)' }}>
      <Stack gap={2}>
        <Lbl>live · the server right now</Lbl>
        <h1 style={{ fontSize: 'var(--fs-title)', letterSpacing: 'var(--track-title)', textTransform: 'uppercase', margin: 'var(--space-3) 0 0', fontWeight: 500 }}>
          {state.data?.is_live
            ? `${state.data.current_map != null ? mapLabel(state.data.current_map) : 'unknown map'} · live`
            : 'nobody on'}
        </h1>
        {state.data && (
          <>
            <Meta>
              {state.data.is_live
                ? `${figure(state.data.roster.player_count)} playing${state.data.round_number != null ? ` · round ${figure(state.data.round_number)}` : ''}${state.data.roster.has_bots ? ' · bots present' : ''}`
                : 'the card wakes the moment the first player connects'}
            </Meta>
            {state.data.roster.roster_age_seconds != null && state.data.roster.roster_age_seconds > 60 && (
              <Meta>roster {figure(Math.round(state.data.roster.roster_age_seconds / 60))} min old — lingering through a delivery gap, dimmed, not current</Meta>
            )}
          </>
        )}
        {state.isError && <Unavailable what="live state" />}
        {state.data && <NowStrip state={state.data} beatFromDb={tonight.data?.current?.beat_seconds ?? null} />}
      </Stack>

      <TonightBoard q={tonight} liveElapsed={state.data?.round_elapsed_seconds ?? null} />

      {state.data && state.data.roster.player_count > 0 && (
        <div data-parity="live.roster">
          <Cluster gap={7} align="start" style={{ flexWrap: 'wrap' }}>
            <RosterSide side="axis" members={state.data.roster.axis} />
            <RosterSide side="allies" members={state.data.roster.allies} />
            <RosterSide side="spectating" members={state.data.roster.spectators} />
          </Cluster>
        </div>
      )}

      <div data-parity="live.feed">
        <SectionHead label="the ticker" aside={feed.data ? `seq ${figure(feed.data.last_seq)}` : undefined} />
        {feed.isPending && log.length === 0 && <Pending label="feed" />}
        {feed.isError && <Unavailable what="feed" />}
        {gapNote != null && <Meta>{gapNote}</Meta>}
        {feed.data && log.length === 0 && (
          <div style={{ marginTop: 'var(--space-2)' }}>
            <Absent reason="quiet — no renderable events since this page loaded" />
          </div>
        )}
        {log.length > 0 && (
          <Stack gap={1} className="rows" style={{ marginTop: 'var(--space-2)', maxHeight: 260, overflowY: 'auto' }}>
            {log.slice(-30).reverse().map((e) => (
              <Meta key={e.seq}>#{figure(e.seq)} · {e.type.toLowerCase().replace(/_/g, ' ')}</Meta>
            ))}
          </Stack>
        )}
      </div>

      <div data-parity="live.server-activity">
        <SectionHead label="the last 24 hours" aside={server.data ? `peak ${figure(server.data.summary.peak_players)} · uptime ${figure(server.data.summary.uptime_percent)}%` : undefined} />
        {server.isPending && <Pending label="server activity" />}
        {server.isError && <Unavailable what="server activity" />}
        {server.data && (
          <Spark label="players over 24h"
            pts={server.data.data_points.map((p) => ({ t: p.timestamp, v: p.player_count }))} />
        )}
      </div>

      <div data-parity="live.voice-activity">
        <SectionHead label="voice" aside={voice.data ? `peak ${figure(voice.data.summary.peak_members)}` : undefined} />
        {voice.isPending && <Pending label="voice activity" />}
        {voice.isError && <Unavailable what="voice activity" />}
        {voice.data && (
          <Spark label="voice members over 24h"
            pts={voice.data.data_points.map((p) => ({ t: p.timestamp, v: p.member_count }))} />
        )}
      </div>

      <div data-parity="live.monitoring">
        <SectionHead label="is anyone watching the watchers" />
        {monitoring.data && (
          <Stack gap={1} style={{ marginTop: 'var(--space-2)' }}>
            {(['server', 'voice'] as const).map((k) => {
              const m = monitoring.data![k];
              return m.is_stale ? (
                <Absent key={k} reason={`${k} sampling is STALE — last record ${m.age_seconds != null ? `${figure(Math.round(m.age_seconds / 60))} min ago` : 'unknown'} (threshold ${figure(Math.round(m.stale_threshold_seconds / 60))} min)`} />
              ) : (
                <Meta key={k}>{k} sampling fresh · {figure(m.count)} records</Meta>
              );
            })}
            {health.data && <Meta>api {health.data.status} · database {health.data.database}</Meta>}
          </Stack>
        )}
        {monitoring.isError && <Unavailable what="monitoring" />}
      </div>
    </Stack>
  );
}
