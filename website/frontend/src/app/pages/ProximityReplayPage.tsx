/**
 * Phase 5 — the round replay (route proximity-replay,
 * /proximity/round/:roundId). Parity target is the old React tree, whose
 * page was timeline-centric: a density strip over the round, the event
 * list in four shapes, summary numbers, and tracks used for stats only —
 * it never drew a playback canvas, and neither does this one.
 */
import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router';
import { Cluster, Stack } from '../components/layout';
import { Absent, Lbl, Meta, Pending, SectionHead, Unavailable, figure } from '../components/ui';
import { ApiError } from '../lib/api';
import { stripEtColors } from '../lib/names';
import { mapLabel } from '../lib/maps';
import { useProxRoundTimeline, useProxRoundTracks } from '../lib/queries';
import type { ReplayTimelineEvent } from '../lib/types';
import { ProxRow } from './proximityShared';

const EVENT_HUE: Record<ReplayTimelineEvent['type'], string> = {
  engagement: 'var(--color-neg)',
  spawn_timing_kill: 'var(--color-accent)',
  trade_kill: 'var(--color-pos)',
  team_push: 'var(--color-text-400)',
};

function fmtClock(ms: number): string {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

function eventLine(e: ReplayTimelineEvent): { name: string; mid?: string; val: string } {
  switch (e.type) {
    case 'engagement':
      return {
        name: `${e.victim_name ? stripEtColors(e.victim_name) : 'unknown'} ${e.outcome ?? 'engaged'}`,
        mid: `${figure(e.damage)} dmg${e.attackers > 1 ? ` · ${figure(e.attackers)} attackers` : ''}`,
        val: fmtClock(e.time),
      };
    case 'spawn_timing_kill':
      return {
        name: `${e.attacker_name ? stripEtColors(e.attacker_name) : 'unknown'} timed ${e.victim_name ? stripEtColors(e.victim_name) : 'unknown'}`,
        mid: `spawn score ${figure(e.score)}`,
        val: fmtClock(e.time),
      };
    case 'trade_kill':
      return {
        name: `${e.trader_name ? stripEtColors(e.trader_name) : 'unknown'} avenged ${e.avenged_name ? stripEtColors(e.avenged_name) : 'unknown'}`,
        mid: `${figure(Math.round(e.delta_ms / 100) / 10)} s later`,
        val: fmtClock(e.time),
      };
    case 'team_push':
      return {
        name: `${(e.team ?? 'unknown').toLowerCase()} push · ${figure(e.participants)} players`,
        mid: `quality ${figure(e.quality)} · alignment ${figure(e.alignment)}`,
        val: fmtClock(e.time),
      };
  }
}

const TYPE_LABELS: { key: ReplayTimelineEvent['type'] | 'all'; label: string }[] = [
  { key: 'all', label: 'all' },
  { key: 'engagement', label: 'engagements' },
  { key: 'team_push', label: 'pushes' },
  { key: 'spawn_timing_kill', label: 'spawn kills' },
  { key: 'trade_kill', label: 'trades' },
];

export function ProximityReplayPage() {
  const params = useParams();
  const roundId = params.roundId != null && /^\d+$/.test(params.roundId) ? Number(params.roundId) : null;
  const timeline = useProxRoundTimeline(roundId);
  const tracks = useProxRoundTracks(roundId);
  const [typeFilter, setTypeFilter] = useState<ReplayTimelineEvent['type'] | 'all'>('all');

  const roundEndMs = timeline.data?.duration_ms ?? 0;
  const trackStats = useMemo(() => {
    const rows = tracks.data?.tracks;
    if (!rows || rows.length === 0) return null;
    const byTeam = new Map<string, { lives: number; alive_ms: number }>();
    for (const t of rows) {
      const key = (t.team ?? 'unknown').toLowerCase();
      const cur = byTeam.get(key) ?? { lives: 0, alive_ms: 0 };
      cur.lives += 1;
      // death_time 0 is the wire's survivor sentinel (the emitter coerces a
      // missing death to 0) -- a survivor's life runs to the round end, it
      // is not zero seconds long (review on #879).
      const end = t.death_time > t.spawn_time ? t.death_time : roundEndMs;
      if (end > t.spawn_time) cur.alive_ms += end - t.spawn_time;
      byTeam.set(key, cur);
    }
    return { total: rows.length, byTeam: [...byTeam.entries()] };
  }, [tracks.data, roundEndMs]);

  if (roundId == null) {
    return <Absent block reason="no round named — open a replay from a round's engagement panel" />;
  }
  if (timeline.isPending) return <Pending label="round timeline" />;
  if (timeline.isError || !timeline.data) {
    // A nonexistent id is a 404 here — absence, not failure (#840's lesson).
    return timeline.error instanceof ApiError && timeline.error.status === 404
      ? <Absent block reason={`no round has id ${roundId}`} />
      : <Unavailable what="round timeline" />;
  }
  const d = timeline.data;
  const shown = typeFilter === 'all' ? d.events : d.events.filter((e) => e.type === typeFilter);

  return (
    <Stack gap={7} style={{ paddingTop: 'var(--space-7)' }}>
      <Stack gap={2}>
        <Lbl>proximity · round replay</Lbl>
        <h1 style={{ fontSize: 'var(--fs-title)', letterSpacing: 'var(--track-title)', textTransform: 'uppercase', margin: 'var(--space-3) 0 0', fontWeight: 500 }}>
          {mapLabel(d.map_name)} r{d.round_number}
        </h1>
        <Meta>{d.round_date} · {fmtClock(d.duration_ms)} played · round #{figure(d.round_id)}</Meta>
      </Stack>

      {d.events.length === 0 ? (
        <Absent block reason="no proximity capture for this round — the tracker only covers sessions where it ran" />
      ) : (
        <>
          <div data-parity="proximity-replay.timeline">
            <SectionHead label="the round, in moments" aside={<span className="lbl">{figure(d.events.length)} events</span>} />
            <svg viewBox="0 0 640 46" style={{ width: '100%', marginTop: 'var(--space-3)' }} role="img" aria-label="round timeline">
              <line x1="8" y1="30" x2="632" y2="30" stroke="var(--color-rule-900)" strokeWidth="1" />
              {d.events.map((e, i) => {
                const x = d.duration_ms > 0 ? 8 + (Math.min(e.time, d.duration_ms) / d.duration_ms) * 624 : 8;
                return <line key={i} x1={x} y1={e.type === 'team_push' ? 22 : 12} x2={x} y2={30} stroke={EVENT_HUE[e.type]} strokeWidth="1" opacity="0.8" />;
              })}
              <text x="8" y="43" style={{ fill: 'var(--color-text-400)', fontSize: 'var(--fs-micro)' }}>0:00</text>
              <text x="632" y="43" textAnchor="end" style={{ fill: 'var(--color-text-400)', fontSize: 'var(--fs-micro)' }}>{fmtClock(d.duration_ms)}</text>
            </svg>
          </div>

          <div data-parity="proximity-replay.events">
            <SectionHead label="events" aside={
              <Cluster gap={3}>
                {TYPE_LABELS.map((t) => (
                  <button key={t.key} type="button" onClick={() => setTypeFilter(t.key)} aria-pressed={typeFilter === t.key}
                    style={{ all: 'unset', cursor: 'pointer', fontSize: 'var(--fs-caption)', letterSpacing: '0.06em', textTransform: 'uppercase', color: typeFilter === t.key ? 'var(--color-text-100)' : 'var(--color-text-400)' }}>
                    {t.label}
                  </button>
                ))}
              </Cluster>
            } />
            <div style={{ maxHeight: 420, overflowY: 'auto', marginTop: 'var(--space-3)' }}>
              <Stack gap={1} className="rows">
                {shown.map((e, i) => {
                  const line = eventLine(e);
                  return <ProxRow key={`${e.type}:${e.time}:${i}`} name={line.name} mid={line.mid} val={line.val} />;
                })}
              </Stack>
            </div>
          </div>

          <div data-parity="proximity-replay.tracks">
            <SectionHead label="lives" aside={<span className="lbl">from the movement tracker</span>} />
            {tracks.isPending && <Pending label="tracks" />}
            {tracks.isError && (
              tracks.error instanceof ApiError && tracks.error.status === 404
                ? <Absent reason="no movement tracks for this round" />
                : <Unavailable what="tracks" />
            )}
            {trackStats && (
              <Stack gap={1} className="rows" style={{ marginTop: 'var(--space-3)', maxWidth: 480 }}>
                <ProxRow name="lives tracked" val={figure(trackStats.total)} />
                {trackStats.byTeam.map(([team, v]) => (
                  <ProxRow key={team} name={team}
                    mid={`${figure(Math.round(v.alive_ms / 1000 / 60))} min alive total`}
                    val={`${figure(v.lives)} lives`} />
                ))}
              </Stack>
            )}
          </div>

          <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
            the parity target used tracks for summary numbers only — this page
            does the same; a playback canvas is future work, not a missing
            piece of parity
          </Lbl>
        </>
      )}
      {d.events.length > 0 && (
        <Meta>
          <Link to={`/spider-web/round/${d.round_id}`} style={{ color: 'var(--color-accent)', textDecoration: 'none', marginRight: 'var(--space-4)' }}>
            spider web →
          </Link>
          <Link to={`/proximity/round/${d.round_id}/teams`} style={{ color: 'var(--color-accent)', textDecoration: 'none' }}>
            team comparison for this round →
          </Link>
        </Meta>
      )}
    </Stack>
  );
}
