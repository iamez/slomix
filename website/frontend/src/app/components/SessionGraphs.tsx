/**
 * The graphs of an evening — GET /api/stats/session/{gsid}/graphs: the
 * eight playstyle axes as a table and as a radar for one chosen player, the
 * advanced metrics, and the per-round DPM series with the chosen player's
 * line in the accent colour and everyone else's in grey. The old React drew
 * the radar and the timeline (`src/pages/SessionDetail.tsx:1020-1043`) from
 * the DATE-keyed endpoint, which merges the sessions of a day; this one is
 * keyed by gaming session and says which round gate it stands on.
 *
 * ⛔ `advanced_metrics.frag_potential` is served and not drawn: the owner's
 * standing decision keeps it off every visitor-facing surface.
 */
import { useState } from 'react';

import { DataTable, type DataColumn } from './DataTable';
import { Cluster, Stack } from './layout';
import { Panel } from './Panel';
import { Lbl, Meta, figure } from './ui';
import { useSessionGraphs } from '../lib/queries';
import { svgPath } from '../lib/spark';
import type { SessionGraphPlayer, SessionGraphs as SessionGraphsData } from '../lib/types';

const AXES: { key: keyof SessionGraphPlayer['playstyle']; label: string }[] = [
  { key: 'aggression', label: 'aggression' }, { key: 'precision', label: 'precision' },
  { key: 'survivability', label: 'survivability' }, { key: 'support', label: 'support' },
  { key: 'lethality', label: 'lethality' }, { key: 'brutality', label: 'brutality' },
  { key: 'consistency', label: 'consistency' }, { key: 'efficiency', label: 'efficiency' },
];

const PLAYSTYLE_COLUMNS: DataColumn<SessionGraphPlayer>[] = [
  { key: 'name', label: 'player', sortValue: (p) => p.name },
  ...AXES.map((a): DataColumn<SessionGraphPlayer> => ({
    key: a.key, label: a.label, align: 'right', title: `${a.label}, 0–100 relative to the evening`,
    format: (p) => figure(Math.round(p.playstyle[a.key])), sortValue: (p) => p.playstyle[a.key],
  })),
];

const ADVANCED_COLUMNS: DataColumn<SessionGraphPlayer>[] = [
  { key: 'name', label: 'player', sortValue: (p) => p.name },
  { key: 'dpm', label: 'dpm', align: 'right', format: (p) => figure(p.combat_offense.dpm), sortValue: (p) => p.combat_offense.dpm },
  { key: 'kd', label: 'k/d', align: 'right', format: (p) => figure(p.combat_offense.kd), sortValue: (p) => p.combat_offense.kd },
  { key: 'damage_efficiency', label: 'dmg eff', align: 'right', title: 'damage given over damage taken', format: (p) => figure(p.advanced_metrics.damage_efficiency), sortValue: (p) => p.advanced_metrics.damage_efficiency },
  { key: 'survival_rate', label: 'alive %', align: 'right', title: 'share of played time alive (engine alive % when the round carried it)', format: (p) => figure(p.advanced_metrics.survival_rate), sortValue: (p) => p.advanced_metrics.survival_rate },
  { key: 'time_denied', label: 'denied/min', align: 'right', title: 'seconds of opponent playtime denied, per minute played', format: (p) => figure(p.advanced_metrics.time_denied), sortValue: (p) => p.advanced_metrics.time_denied },
  { key: 'useful_kills_per_round', label: 'uk/round', align: 'right', title: 'useful kills per round', format: (p) => figure(p.advanced_metrics.useful_kills_per_round), sortValue: (p) => p.advanced_metrics.useful_kills_per_round },
  { key: 'deaths_per_round', label: 'd/round', align: 'right', format: (p) => figure(p.advanced_metrics.deaths_per_round), sortValue: (p) => p.advanced_metrics.deaths_per_round },
  { key: 'dead_time_share', label: 'dead %', align: 'right', title: 'share of played time dead', format: (p) => figure(p.advanced_metrics.dead_time_share), sortValue: (p) => p.advanced_metrics.dead_time_share },
  { key: 'aggression_score', label: 'aggression', align: 'right', title: 'percentile of the evening', format: (p) => figure(p.advanced_metrics.aggression_score), sortValue: (p) => p.advanced_metrics.aggression_score },
  { key: 'pressure_score', label: 'pressure', align: 'right', title: 'percentile of the evening', format: (p) => figure(p.advanced_metrics.pressure_score), sortValue: (p) => p.advanced_metrics.pressure_score },
  { key: 'risk_load', label: 'risk', align: 'right', title: 'percentile of the evening', format: (p) => figure(p.advanced_metrics.risk_load), sortValue: (p) => p.advanced_metrics.risk_load },
  { key: 'empty_death_burden', label: 'empty deaths', align: 'right', title: 'percentile of the evening', format: (p) => figure(p.advanced_metrics.empty_death_burden), sortValue: (p) => p.advanced_metrics.empty_death_burden },
  { key: 'discipline_score', label: 'discipline', align: 'right', title: 'percentile of the evening', format: (p) => figure(p.advanced_metrics.discipline_score), sortValue: (p) => p.advanced_metrics.discipline_score },
  { key: 'rounds_played', label: 'rounds', align: 'right', sortValue: (p) => p.advanced_metrics.rounds_played },
];

const SUPPORT_COLUMNS: DataColumn<SessionGraphPlayer>[] = [
  { key: 'name', label: 'player', sortValue: (p) => p.name },
  { key: 'revives', label: 'rev', align: 'right', title: 'revives given', sortValue: (p) => p.combat_defense.revives },
  { key: 'times_revived', label: 'revived', align: 'right', sortValue: (p) => p.combat_defense.times_revived },
  { key: 'kill_assists', label: 'assists', align: 'right', sortValue: (p) => p.combat_defense.kill_assists },
  { key: 'gibs', label: 'gibs', align: 'right', sortValue: (p) => p.combat_defense.gibs },
  { key: 'headshots', label: 'head hits', align: 'right', title: 'head HITS, not headshot kills', sortValue: (p) => p.combat_defense.headshots },
  { key: 'useful_kills', label: 'uk', align: 'right', title: 'useful kills', sortValue: (p) => p.combat_defense.useful_kills },
  { key: 'full_selfkills', label: 'full sk', align: 'right', title: 'full self kills (the tactical kind)', sortValue: (p) => p.combat_defense.full_selfkills },
  { key: 'self_kills', label: 'sk', align: 'right', title: 'self kills', sortValue: (p) => p.combat_defense.self_kills },
  { key: 'team_kills', label: 'tk', align: 'right', title: 'team kills', sortValue: (p) => p.combat_defense.team_kills },
  { key: 'kills', label: 'k', align: 'right', sortValue: (p) => p.combat_offense.kills },
  { key: 'deaths', label: 'd', align: 'right', sortValue: (p) => p.combat_offense.deaths },
  { key: 'damage_given', label: 'given', align: 'right', sortValue: (p) => p.combat_offense.damage_given },
];

const AXIS_TEXT = { fill: 'var(--color-text-500)', fontSize: 'var(--fs-caption)' } as const;

/** One player's eight axes as a closed polygon over the axis spokes. */
function Radar({ player }: { player: SessionGraphPlayer }) {
  const W = 280; const H = 280; const cx = W / 2; const cy = H / 2; const R = 100;
  const at = (i: number, r: number) => {
    const angle = (Math.PI * 2 * i) / AXES.length - Math.PI / 2;
    return { x: cx + Math.cos(angle) * r, y: cy + Math.sin(angle) * r };
  };
  const shape = `${svgPath(AXES.map((a, i) => at(i, (Math.max(0, Math.min(100, player.playstyle[a.key])) / 100) * R)))} Z`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', maxWidth: W }} role="img" aria-label={`playstyle of ${player.name}`}>
      {[0.5, 1].map((f) => (
        <path key={f} d={`${svgPath(AXES.map((_a, i) => at(i, R * f)))} Z`} fill="none" stroke="var(--color-rule-900)" strokeWidth="1" />
      ))}
      {AXES.map((a, i) => {
        const tip = at(i, R); const lab = at(i, R + 16);
        return (
          <g key={a.key}>
            <line x1={cx} y1={cy} x2={tip.x} y2={tip.y} stroke="var(--color-rule-900)" strokeWidth="1" />
            <text x={lab.x} y={lab.y + 3} textAnchor="middle" style={AXIS_TEXT}>{a.label}</text>
          </g>
        );
      })}
      <path d={shape} fill="var(--color-accent)" fillOpacity="0.15" stroke="var(--color-accent)" strokeWidth="1.2" />
    </svg>
  );
}

/** Every player's per-round DPM as a line; the chosen one in the accent. */
function DpmTimeline({ players, chosen }: { players: SessionGraphPlayer[]; chosen: string }) {
  const W = 640; const H = 120; const L = 34; const B = 18;
  const n = Math.max(...players.map((p) => p.dpm_timeline.length), 0);
  if (n < 2) return <Meta>the timeline needs at least two rounds</Meta>;
  const maxDpm = Math.max(1, ...players.flatMap((p) => p.dpm_timeline.map((t) => t.dpm)));
  const x = (i: number) => L + (i / (n - 1)) * (W - L - 6);
  const y = (v: number) => 6 + (1 - v / maxDpm) * (H - B - 6);
  const labels = players.reduce((acc, p) => (p.dpm_timeline.length > acc.length ? p.dpm_timeline : acc), [] as SessionGraphPlayer['dpm_timeline']);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', maxWidth: W }} role="img" aria-label="dpm per round">
      {[0, maxDpm / 2, maxDpm].map((v) => (
        <g key={v}>
          <line x1={L} x2={W - 6} y1={y(v)} y2={y(v)} stroke="var(--color-rule-900)" strokeWidth="1" />
          <text x={L - 4} y={y(v) + 3} textAnchor="end" style={AXIS_TEXT}>{figure(Math.round(v))}</text>
        </g>
      ))}
      {labels.map((t, i) => (i % Math.ceil(n / 6) === 0 || i === n - 1) && (
        <text key={`${t.label}-${String(i)}`} x={x(i)} y={H - 4} textAnchor="middle" style={AXIS_TEXT}>{t.label}</text>
      ))}
      {players.filter((p) => p.guid !== chosen).map((p) => (
        <path key={p.guid} d={svgPath(p.dpm_timeline.map((t, i) => ({ x: x(i), y: y(t.dpm) })))} fill="none" stroke="var(--color-text-500)" strokeWidth="1" strokeOpacity="0.5" />
      ))}
      {players.filter((p) => p.guid === chosen).map((p) => (
        <path key={p.guid} d={svgPath(p.dpm_timeline.map((t, i) => ({ x: x(i), y: y(t.dpm) })))} fill="none" stroke="var(--color-accent)" strokeWidth="1.6" />
      ))}
    </svg>
  );
}

export function SessionGraphsPanel({ sessionId }: { sessionId: number }) {
  const q = useSessionGraphs(sessionId);
  const [chosen, setChosen] = useState<string | null>(null);
  return (
    <Panel<SessionGraphsData>
      parity="session.graphs"
      label="playstyle"
      aside={q.data ? `${q.data.gate === 'counts_toward_totals' ? 'counted rounds only' : q.data.gate} · ${figure(q.data.rounds_counted)} rounds` : undefined}
      q={q}
      empty="no player rows over the counted rounds"
      isEmpty={(d) => d.players.length === 0}
    >
      {(d) => {
        const pick = d.players.find((p) => p.guid === chosen) ?? d.players[0];
        return (
          <Stack gap={4}>
            <Cluster gap={2} align="baseline" style={{ flexWrap: 'wrap' }}>
              <Lbl style={{ fontSize: 'var(--fs-caption)' }}>radar for</Lbl>
              {d.players.map((p) => (
                <button
                  key={p.guid}
                  type="button"
                  aria-pressed={p.guid === pick.guid}
                  onClick={() => { setChosen(p.guid); }}
                  style={{ all: 'unset', cursor: 'pointer', fontSize: 'var(--fs-small)', color: p.guid === pick.guid ? 'var(--color-text-100)' : 'var(--color-text-500)' }}
                >
                  {p.name}
                </button>
              ))}
            </Cluster>
            <Cluster gap={6} align="start" style={{ flexWrap: 'wrap' }}>
              <Radar player={pick} />
              <Stack gap={1} style={{ flex: '1 1 320px' }}>
                <Lbl style={{ fontSize: 'var(--fs-caption)' }}>dpm per round · {pick.name} in colour</Lbl>
                <DpmTimeline players={d.players} chosen={pick.guid} />
              </Stack>
            </Cluster>
            <DataTable<SessionGraphPlayer>
              parity="session.graphs.playstyle"
              label="playstyle axes"
              columns={PLAYSTYLE_COLUMNS}
              rows={d.players}
              rowKey={(p) => p.guid}
              defaultSort={{ key: 'aggression', dir: 'desc' }}
              minWidth={760}
            />
            <DataTable<SessionGraphPlayer>
              parity="session.graphs.advanced"
              label="advanced metrics"
              columns={ADVANCED_COLUMNS}
              rows={d.players}
              rowKey={(p) => p.guid}
              defaultSort={{ key: 'dpm', dir: 'desc' }}
              minWidth={1100}
            />
            <DataTable<SessionGraphPlayer>
              parity="session.graphs.support"
              label="support and discipline"
              columns={SUPPORT_COLUMNS}
              rows={d.players}
              rowKey={(p) => p.guid}
              defaultSort={{ key: 'revives', dir: 'desc' }}
              minWidth={900}
            />
            <Meta>axes and percentile scores are relative to this evening's players, not to the whole database</Meta>
          </Stack>
        );
      }}
    </Panel>
  );
}
