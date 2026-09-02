/**
 * Phase 6 — the live surface (route live): the server card whose roster
 * LINGERS through delivery gaps (dimmed by age, never oscillating
 * full↔empty — the backend's own contract), the event feed, 24 hours of
 * server and voice activity as sparklines, and the monitoring panel that
 * says out loud when its own data is stale.
 */
import { useState } from 'react';
import { Cluster, Stack } from '../components/layout';
import { Absent, Lbl, Meta, Pending, SectionHead, Unavailable, figure } from '../components/ui';
import { mapLabel } from '../lib/maps';
import { stripEtColors } from '../lib/names';
import {
  useApiHealth, useLiveFeed, useLiveState, useMonitoringStatus,
  useServerActivityHistory, useVoiceActivityHistory,
} from '../lib/queries';
import type { LiveRosterMember } from '../lib/types';

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

export function LivePage() {
  const state = useLiveState();
  const [since] = useState(0);
  const feed = useLiveFeed(since);
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
      </Stack>

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
        {feed.isPending && <Pending label="feed" />}
        {feed.isError && <Unavailable what="feed" />}
        {feed.data && (feed.data.events.length === 0 ? (
          <div style={{ marginTop: 'var(--space-2)' }}>
            <Absent reason="quiet — no renderable events since this page loaded" />
          </div>
        ) : (
          <Stack gap={1} className="rows" style={{ marginTop: 'var(--space-2)', maxHeight: 260, overflowY: 'auto' }}>
            {feed.data.events.slice(-30).reverse().map((e) => (
              <Meta key={e.seq}>#{figure(e.seq)} · {e.type.toLowerCase().replace(/_/g, ' ')}</Meta>
            ))}
          </Stack>
        ))}
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
