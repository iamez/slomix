import { useMemo, useState } from 'react';
import { useRecentRounds, useRoundViz } from '../lib/queries';
import type { RoundViz, VizPlayer } from '../lib/types';
import { mapLabel } from '../lib/maps';
import { ChartCanvas } from '../../components/Chart';
import { Lbl, Pending, SectionHead, Unavailable, rowStyle } from '../components/ui';

/**
 * Retro-viz (docs/design/12 row 23) — legacy retro-viz.js carried over:
 * a round picker (R0 Match Summary rows filtered out) and six panels over
 * /api/rounds/{id}/viz. Charts render through ChartCanvas (chart.js is an
 * npm dependency since #805, and the component owns the destroy lifecycle
 * the legacy _rvCharts registry managed by hand). The lightbox is not
 * carried — panels are full-width here.
 *
 * In THIS endpoint's convention winner_team 1 = Axis, 2 = Allies — the
 * number never leaves this page (other families disagree on it).
 */

const RADAR_COLORS = ['rgba(96,165,250,0.6)', 'rgba(251,113,133,0.6)', 'rgba(52,211,153,0.6)', 'rgba(251,191,36,0.6)', 'rgba(167,139,250,0.6)'];

function winnerLabel(team: number | null): { text: string; color: string } {
  if (team === 1) return { text: 'Axis', color: 'var(--color-accent-warm)' };
  if (team === 2) return { text: 'Allies', color: 'var(--color-accent)' };
  // 0/null are server-restart artifacts, not a draw — the endpoint has no
  // draw signal at all (test_website_session_helpers defines non-team
  // values as unknown).
  return { text: 'Unknown', color: 'var(--color-text-400)' };
}

function fmtDuration(s: number | null): string {
  // A round without a measurement has NO duration — null, and ALSO the
  // stored sentinel 0 (test_round_duration_truth defines zero as missing).
  if (s == null || s <= 0) return 'unknown';
  return `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`;
}

function SummaryPanel({ viz }: { viz: RoundViz }) {
  const winner = winnerLabel(viz.winner_team);
  const cells = [
    ['map', mapLabel(viz.map_name)],
    ['round', viz.round_label],
    ['date', viz.round_date ?? 'unknown'],
    ['duration', fmtDuration(viz.duration_seconds)],
    ['players', String(viz.player_count)],
  ];
  const highlights = [
    viz.highlights.mvp && { k: 'mvp', name: viz.highlights.mvp.name, v: `${viz.highlights.mvp.dpm.toFixed(1)} dpm` },
    viz.highlights.most_kills && { k: 'most kills', name: viz.highlights.most_kills.name, v: `${viz.highlights.most_kills.kills} kills` },
    viz.highlights.most_damage && { k: 'most damage', name: viz.highlights.most_damage.name, v: `${viz.highlights.most_damage.damage_given.toLocaleString('en-US')} dmg` },
  ].filter((h) => h != null);
  return (
    <div data-parity="retro-viz.summary" style={{ border: '1px solid var(--color-rule-700)', background: 'var(--color-ink-800)', padding: 14 }}>
      <div className="home-cols3" style={{ gap: 'var(--space-2)' }}>
        {cells.map(([k, v]) => (
          <div key={k}>
            <Lbl style={{ fontSize: 'var(--fs-caption)' }}>{k}</Lbl>
            <div className="m" style={{ fontSize: 'var(--fs-body)', marginTop: 'var(--space-1)' }}>{v}</div>
          </div>
        ))}
        <div>
          <Lbl style={{ fontSize: 'var(--fs-caption)' }}>winner</Lbl>
          <div className="m" style={{ fontSize: 'var(--fs-body)', marginTop: 'var(--space-1)', color: winner.color }}>{winner.text}</div>
        </div>
      </div>
      {highlights.length > 0 && (
        <div data-parity="retro-viz.highlights" className="home-cols3" style={{ gap: 'var(--space-2)', marginTop: 'var(--space-3)', borderTop: '1px solid var(--color-rule-900)', paddingTop: 'var(--space-2)' }}>
          {highlights.map((h) => (
            <div key={h.k}>
              <Lbl style={{ fontSize: 'var(--fs-caption)' }}>{h.k}</Lbl>
              <div className="m" style={{ fontSize: 'var(--fs-value)', marginTop: 'var(--space-1)' }}>{h.name}</div>
              <div className="m" style={{ fontSize: 'var(--fs-label)', color: 'var(--color-text-400)' }}>{h.v}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** Radar: top 5 by DPM, axes normalized 0-100 against the group max;
 * deaths INVERTED (fewer deaths = larger axis) — legacy math verbatim. */
function radarData(players: VizPlayer[]) {
  const top = [...players].sort((a, b) => b.dpm - a.dpm).slice(0, 5);
  const max = {
    kills: Math.max(...top.map((p) => p.kills), 1),
    deaths: Math.max(...top.map((p) => p.deaths), 1),
    dpm: Math.max(...top.map((p) => p.dpm), 1),
    damage: Math.max(...top.map((p) => p.damage_given), 1),
    gibs: Math.max(...top.map((p) => p.gibs), 1),
  };
  return {
    labels: ['Kills', 'Deaths (inv)', 'DPM', 'Damage', 'Efficiency', 'Gibs'],
    datasets: top.map((p, i) => ({
      label: p.name,
      data: [
        (p.kills / max.kills) * 100,
        (1 - p.deaths / max.deaths) * 100,
        (p.dpm / max.dpm) * 100,
        (p.damage_given / max.damage) * 100,
        p.efficiency,
        (p.gibs / max.gibs) * 100,
      ],
      backgroundColor: 'transparent',
      borderColor: RADAR_COLORS[i % RADAR_COLORS.length],
      pointRadius: 2,
    })),
  };
}

function DamageTable({ players }: { players: VizPlayer[] }) {
  const rows = [...players].sort((a, b) => b.damage_given - a.damage_given);
  const colMax = {
    given: Math.max(...rows.map((p) => p.damage_given), 1),
    received: Math.max(...rows.map((p) => p.damage_received), 1),
    tk: Math.max(...rows.map((p) => p.team_damage_given), 1),
    tkr: Math.max(...rows.map((p) => p.team_damage_received), 1),
  };
  const heat = (v: number, max: number, rgb: string) => ({
    background: `rgba(${rgb}, ${((Math.min(v / max, 1)) * 0.5 + 0.05).toFixed(2)})`,
  });
  return (
    <div data-parity="retro-viz.damage" style={{ overflowX: 'auto' }}>
      <div style={{ ...rowStyle, display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto auto auto auto', gap: 'var(--space-2)', padding: 'var(--space-2) 0' }}>
        <Lbl style={{ fontSize: 'var(--fs-caption)' }}>player</Lbl>
        <Lbl style={{ fontSize: 'var(--fs-caption)', textAlign: 'right' }}>dmg given</Lbl>
        <Lbl style={{ fontSize: 'var(--fs-caption)', textAlign: 'right' }}>dmg recv</Lbl>
        <Lbl style={{ fontSize: 'var(--fs-caption)', textAlign: 'right' }}>tk dmg</Lbl>
        <Lbl style={{ fontSize: 'var(--fs-caption)', textAlign: 'right' }}>tk recv</Lbl>
      </div>
      {rows.map((p) => (
        <div key={p.guid} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto auto auto auto', gap: 'var(--space-2)', alignItems: 'baseline', padding: 'var(--space-1) 0' }}>
          <span className="m" style={{ fontSize: 'var(--fs-small)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.name}</span>
          <span className="m" style={{ fontSize: 'var(--fs-micro)', textAlign: 'right', padding: '1px 6px', ...heat(p.damage_given, colMax.given, '96,165,250') }}>{p.damage_given.toLocaleString('en-US')}</span>
          <span className="m" style={{ fontSize: 'var(--fs-micro)', textAlign: 'right', padding: '1px 6px', ...heat(p.damage_received, colMax.received, '251,113,133') }}>{p.damage_received.toLocaleString('en-US')}</span>
          <span className="m" style={{ fontSize: 'var(--fs-micro)', textAlign: 'right', padding: '1px 6px', ...heat(p.team_damage_given, colMax.tk, '251,191,36') }}>{p.team_damage_given}</span>
          <span className="m" style={{ fontSize: 'var(--fs-micro)', textAlign: 'right', padding: '1px 6px', ...heat(p.team_damage_received, colMax.tkr, '167,139,250') }}>{p.team_damage_received}</span>
        </div>
      ))}
    </div>
  );
}

const BAR_OPTS = {
  indexAxis: 'y' as const,
  plugins: { legend: { labels: { color: '#a8a29a', font: { size: 10 } } } },
  scales: {
    x: { ticks: { color: '#807c75', font: { size: 10 } }, grid: { color: '#171715' } },
    y: { ticks: { color: '#a8a29a', font: { size: 10 } }, grid: { display: false } },
  },
};

export function RetroViz() {
  const rounds = useRecentRounds();
  const [picked, setPicked] = useState<number | null>(null);
  // R0 rows are the legacy Match Summary aggregate, not a playable round —
  // and neither is a row whose round_number is NULL, which this endpoint can
  // return (#830 typed it nullable). `!== 0` alone let those through, and a
  // null round is one this page has nothing to plot for.
  const selectable = (rounds.data ?? []).filter(
    (r) => r.round_number != null && r.round_number !== 0,
  );
  // .at(0), not [0]: without noUncheckedIndexedAccess the index read is typed
  // as always-present, which erases the null branch the empty list needs.
  const roundId = picked ?? selectable.at(0)?.id ?? null;
  const viz = useRoundViz(roundId);
  const v = viz.isError ? undefined : viz.data;
  const players = useMemo(() => v?.players ?? [], [v]);
  const fraggers = useMemo(() => [...players].sort((a, b) => a.kills - b.kills), [players]);
  const chartHeight = Math.max(200, players.length * 32);
  return (
    <div style={{ paddingTop: 'var(--space-7)', paddingBottom: 'var(--space-7)', maxWidth: 980 }}>
      <Lbl>retro viz · one round, six instruments</Lbl>
      <h1 style={{ fontSize: 'var(--fs-title)', letterSpacing: '0.03em', textTransform: 'uppercase', margin: 'var(--space-3) 0 0', fontWeight: 500 }}>
        The round, replotted.
      </h1>
      <div data-parity="retro-viz.picker" style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--space-4)', marginTop: 'var(--space-4)', flexWrap: 'wrap' }}>
        <Lbl style={{ fontSize: 'var(--fs-caption)' }}>round</Lbl>
        <select
          value={roundId ?? ''}
          onChange={(e) => { setPicked(Number(e.target.value)); }}
          aria-label="Round"
          className="m"
          style={{ background: 'var(--color-ink-800)', color: 'var(--color-text-100)', border: '1px solid var(--color-rule-700)', fontSize: 'var(--fs-value)', padding: 'var(--space-2) var(--space-2)', maxWidth: 420 }}
        >
          {selectable.map((r) => (
            <option key={r.id} value={r.id}>
              {r.map_name ? mapLabel(r.map_name) : 'unknown map'} {r.round_label} — {r.round_date ?? 'date unknown'} ({r.player_count} players)
            </option>
          ))}
        </select>
        {rounds.isPending && <Pending label="rounds" />}
        {rounds.isError && <Unavailable what="rounds" />}
        {rounds.isSuccess && selectable.length === 0 && (
          <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>no rounds available</span>
        )}
      </div>

      {viz.isPending && roundId != null && <div style={{ marginTop: 'var(--space-4)' }}><Pending label="round data" /></div>}
      {viz.isError && <div style={{ marginTop: 'var(--space-4)' }}><Unavailable what="round data" /></div>}
      {v && players.length === 0 && (
        <div className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)', marginTop: 'var(--space-4)' }}>no player data for this round</div>
      )}
      {v && players.length > 0 && (
        <div style={{ marginTop: 'var(--space-4)', display: 'grid', gap: 'var(--space-4)' }}>
          <SummaryPanel viz={v} />
          <div className="landing-split" style={{ gap: 'var(--space-4)' }}>
            <div data-parity="retro-viz.radar" style={{ border: '1px solid var(--color-rule-700)', background: 'var(--color-ink-800)', padding: 14 }}>
              <SectionHead label="combat overview · top 5 by dpm, normalized" />
              <ChartCanvas
                type="radar"
                data={radarData(players)}
                options={{
                  plugins: { legend: { labels: { color: '#a8a29a', font: { size: 10 } } } },
                  scales: { r: { min: 0, max: 100, ticks: { display: false }, grid: { color: '#26251f' }, angleLines: { color: '#26251f' }, pointLabels: { color: '#807c75', font: { size: 10 } } } },
                }}
                height={300}
              />
            </div>
            <div data-parity="retro-viz.fraggers" style={{ border: '1px solid var(--color-rule-700)', background: 'var(--color-ink-800)', padding: 14 }}>
              <SectionHead label="top fraggers" />
              <ChartCanvas
                type="bar"
                data={{
                  labels: fraggers.map((p) => p.name),
                  datasets: [{ label: 'kills', data: fraggers.map((p) => p.kills), backgroundColor: 'rgba(139,176,214,0.7)' }],
                }}
                options={BAR_OPTS}
                height={chartHeight}
              />
            </div>
          </div>
          <div className="landing-split" style={{ gap: 'var(--space-4)' }}>
            <div style={{ border: '1px solid var(--color-rule-700)', background: 'var(--color-ink-800)', padding: 14 }}>
              <SectionHead label="damage breakdown" />
              <div style={{ marginTop: 'var(--space-2)' }}><DamageTable players={players} /></div>
            </div>
            <div data-parity="retro-viz.support" style={{ border: '1px solid var(--color-rule-700)', background: 'var(--color-ink-800)', padding: 14 }}>
              <SectionHead label="support · revives, denied playtime, dead time" />
              <ChartCanvas
                type="bar"
                data={{
                  labels: [...players].sort((a, b) => a.revives_given - b.revives_given).map((p) => p.name),
                  datasets: [
                    { label: 'revives', data: [...players].sort((a, b) => a.revives_given - b.revives_given).map((p) => p.revives_given), backgroundColor: 'rgba(143,174,138,0.7)' },
                    { label: 'denied (s)', data: [...players].sort((a, b) => a.revives_given - b.revives_given).map((p) => p.denied_playtime), backgroundColor: 'rgba(201,168,107,0.7)' },
                    { label: 'dead (min)', data: [...players].sort((a, b) => a.revives_given - b.revives_given).map((p) => Math.round(p.time_dead_seconds / 60)), backgroundColor: 'rgba(176,132,124,0.7)' },
                  ],
                }}
                options={BAR_OPTS}
                height={Math.max(200, players.length * 36)}
              />
            </div>
          </div>
          <div data-parity="retro-viz.time" style={{ border: '1px solid var(--color-rule-700)', background: 'var(--color-ink-800)', padding: 14 }}>
            <SectionHead label="time distribution · alive vs dead, minutes" />
            <ChartCanvas
              type="bar"
              data={{
                labels: players.map((p) => p.name),
                datasets: [
                  // max(0, …) guards inconsistent rows — legacy math kept.
                  { label: 'alive', data: players.map((p) => Math.max(0, Math.round(p.time_played_seconds / 60) - Math.round(p.time_dead_seconds / 60))), backgroundColor: 'rgba(139,176,214,0.7)' },
                  { label: 'dead', data: players.map((p) => Math.round(p.time_dead_seconds / 60)), backgroundColor: 'rgba(209,133,124,0.7)' },
                ],
              }}
              options={{ ...BAR_OPTS, scales: { x: { ...BAR_OPTS.scales.x, stacked: true }, y: { ...BAR_OPTS.scales.y, stacked: true } } }}
              height={chartHeight}
            />
          </div>
        </div>
      )}
    </div>
  );
}
