import { useState } from 'react';
import { useMapSegments, useMapStats } from '../lib/queries';
import type { MapStatsRow } from '../lib/types';
import { mapImageFor, mapLabel } from '../lib/maps';
import { Chip, Lbl, lblStyle, Pending, rowStyle, SectionHead, Unavailable } from '../components/ui';

/**
 * Maps (docs/design/12 row 4) — legacy matches.js loadMapsView carried
 * over: one array from /api/stats/maps, all sorting and the four summary
 * cards computed client-side, plus the objective-records section
 * (/api/records/maps/segments, 07 §B.6 — the section legacy React never
 * had). Two deliberate departures: map names go through mapLabel() with
 * levelshots (the legacy maps page, alone, rendered raw keys), and a null
 * win rate renders a dash — the legacy default of 50 was an invented
 * middle.
 */

// avg_duration 0 = unknown (endpoint sentinel) — an unknown must never
// outrank a measured time, so 'fastest' pushes it to the end.
const knownDuration = (m: MapStatsRow) => (m.avg_duration > 0 ? m.avg_duration : Infinity);

const SORTS: { key: string; label: string; cmp: (a: MapStatsRow, b: MapStatsRow) => number }[] = [
  { key: 'most-played', label: 'Most played', cmp: (a, b) => b.matches_played - a.matches_played },
  { key: 'fastest', label: 'Fastest avg', cmp: (a, b) => knownDuration(a) - knownDuration(b) },
  { key: 'longest', label: 'Longest avg', cmp: (a, b) => b.avg_duration - a.avg_duration },
  { key: 'last-played', label: 'Last played', cmp: (a, b) => (b.last_played ?? '').localeCompare(a.last_played ?? '') },
  { key: 'grenade-spam', label: 'Nade spam', cmp: (a, b) => b.grenade_kills - a.grenade_kills },
];

function fmtSeconds(s: number): string {
  if (s <= 0) return '—';
  const m = Math.floor(s / 60);
  return `${m}:${String(Math.round(s % 60)).padStart(2, '0')}`;
}


function Summary({ maps }: { maps: MapStatsRow[] }) {
  if (maps.length === 0) return null;
  const by = (cmp: (a: MapStatsRow, b: MapStatsRow) => number) => [...maps].sort(cmp)[0];
  const cards = [
    { k: 'most played', m: by((a, b) => b.matches_played - a.matches_played), v: (m: MapStatsRow) => `${m.matches_played} matches` },
    { k: 'fastest avg', m: by((a, b) => knownDuration(a) - knownDuration(b)), v: (m: MapStatsRow) => fmtSeconds(m.avg_duration) },
    { k: 'longest avg', m: by((a, b) => b.avg_duration - a.avg_duration), v: (m: MapStatsRow) => fmtSeconds(m.avg_duration) },
    { k: 'nade spam', m: by((a, b) => b.grenade_kills - a.grenade_kills), v: (m: MapStatsRow) => `${m.grenade_kills.toLocaleString('en-US')} nades` },
  ];
  return (
    <div data-parity="maps.summary" className="landing-quad" style={{ gap: 'var(--space-2)', marginTop: 'var(--space-4)' }}>
      {cards.map((c) => (
        <div key={c.k} style={{ border: '1px solid var(--color-rule-700)', background: 'var(--color-ink-800)', padding: 12 }}>
          <Lbl style={{ fontSize: 'var(--fs-caption)' }}>{c.k}</Lbl>
          <div style={{ fontSize: 'var(--fs-body-lg)', letterSpacing: '0.04em', textTransform: 'uppercase', marginTop: 'var(--space-2)' }}>{mapLabel(c.m.name)}</div>
          <div className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-400)', marginTop: 'var(--space-1)' }}>{c.v(c.m)}</div>
        </div>
      ))}
    </div>
  );
}

function ObjectiveRecords() {
  const segments = useMapSegments();
  const rows = segments.data?.records ?? [];
  // The endpoint catches its own query failures and answers 200 with
  // {status: "error", records: []} — success + empty there is an OUTAGE,
  // not an empty record book (same family as the #811 waves).
  const failed = segments.isError || segments.data?.status === 'error';
  return (
    <div data-parity="maps.objective-records" style={{ marginTop: 'var(--space-6)' }}>
      <SectionHead label="fastest objective completions · full map records" />
      {segments.isPending && <div style={{ marginTop: 'var(--space-2)' }}><Pending label="records" /></div>}
      {failed && <div style={{ marginTop: 'var(--space-2)' }}><Unavailable what="objective records" /></div>}
      {segments.isSuccess && !failed && rows.length === 0 && (
        <div className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)', marginTop: 'var(--space-2)' }}>no objective records yet</div>
      )}
      {rows.length > 0 && (
        <div className="landing-split" style={{ gap: 'var(--space-5)', marginTop: 'var(--space-2)' }}>
          {[rows.slice(0, Math.ceil(rows.length / 2)), rows.slice(Math.ceil(rows.length / 2))].map((half, i) => (
            <div key={i}>
              {half.map((r) => (
                <div key={r.map_name} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto auto auto', gap: 'var(--space-3)', alignItems: 'baseline', padding: 'var(--space-2) 0' }}>
                  <span style={{ fontSize: 'var(--fs-body)', letterSpacing: '0.03em', textTransform: 'uppercase', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{mapLabel(r.map_name)}</span>
                  {/* winner_side is the SERVER's word — the numeric
                    * winner_team means different things per endpoint family,
                    * so it is never interpreted here. */}
                  <span className="m" style={{ fontSize: 'var(--fs-micro)', color: r.winner_side === 'Allies' ? 'var(--color-accent)' : 'var(--color-accent-warm)' }}>{r.winner_side.toLowerCase()}</span>
                  <span className="m" style={{ fontSize: 'var(--fs-value)' }}>{r.fastest_time}</span>
                  <span className="m" style={{ ...lblStyle, fontSize: 'var(--fs-caption)' }}>{r.played}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function MapsPage() {
  const stats = useMapStats();
  const [sort, setSort] = useState('most-played');
  const data = stats.isError ? undefined : stats.data;
  const cmp = SORTS.find((s) => s.key === sort)?.cmp ?? SORTS[0].cmp;
  const sorted = data ? [...data].sort(cmp) : [];
  return (
    <div style={{ paddingTop: 'var(--space-7)', paddingBottom: 'var(--space-7)', maxWidth: 980 }}>
      <Lbl>maps · every map we keep score on</Lbl>
      <h1 style={{ fontSize: 'var(--fs-title)', letterSpacing: '0.03em', textTransform: 'uppercase', margin: 'var(--space-3) 0 0', fontWeight: 500 }}>
        The grounds we fight over.
      </h1>
      {stats.isPending && <div style={{ marginTop: 'var(--space-4)' }}><Pending label="maps" /></div>}
      {stats.isError && <div style={{ marginTop: 'var(--space-4)' }}><Unavailable what="maps" /></div>}
      {data && <Summary maps={data} />}
      <ObjectiveRecords />
      {data && (
        <div data-parity="maps.grid" style={{ marginTop: 'var(--space-6)' }}>
          <SectionHead
            label={`${sorted.length} maps`}
            aside={
              <span style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
                {SORTS.map((s) => (
                  <Chip key={s.key} active={sort === s.key} label={s.label} onClick={() => { setSort(s.key); }} />
                ))}
              </span>
            }
          />
          {sorted.length === 0 && (
            <div className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)', marginTop: 'var(--space-2)' }}>no map statistics yet</div>
          )}
          <div className="home-cols3" style={{ gap: 'var(--space-4)', marginTop: 'var(--space-3)' }}>
            {sorted.map((m) => (
              <div key={m.name} style={{ border: '1px solid var(--color-rule-700)', background: 'var(--color-ink-800)' }}>
                <img
                  src={mapImageFor(m.name)}
                  alt={mapLabel(m.name)}
                  style={{ width: '100%', height: 96, objectFit: 'cover', display: 'block', filter: 'saturate(0.55) brightness(0.8)' }}
                  loading="lazy"
                />
                <div style={{ padding: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 'var(--space-2)' }}>
                    <span style={{ fontSize: 'var(--fs-body-lg)', letterSpacing: '0.04em', textTransform: 'uppercase', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{mapLabel(m.name)}</span>
                    <span className="m" style={{ ...lblStyle, fontSize: 'var(--fs-caption)', flex: 'none' }}>{m.matches_played} matches</span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
                    {[
                      ['avg time', fmtSeconds(m.avg_duration)],
                      ['last played', m.last_played ?? '—'],
                      ['players', String(m.unique_players)],
                      ['avg dpm', m.avg_dpm.toFixed(1)],
                    ].map(([k, v]) => (
                      <div key={k}>
                        <Lbl style={{ fontSize: 'var(--fs-caption)' }}>{k}</Lbl>
                        <div className="m" style={{ fontSize: 'var(--fs-small)', marginTop: 'var(--space-1)' }}>{v}</div>
                      </div>
                    ))}
                  </div>
                  {/* An undecided map is NOT 50/50 — but the endpoint
                    * serializes exactly that (records_maps defaults both
                    * rates to 50), so nullability can't detect it; the win
                    * COUNTS can. */}
                  {m.allies_wins + m.axis_wins > 0 && m.allies_win_rate != null && m.axis_win_rate != null ? (
                    <div style={{ marginTop: 'var(--space-2)' }}>
                      <div style={{ display: 'flex', height: 5, background: 'var(--color-rule-900)' }}>
                        <span style={{ width: `${m.allies_win_rate}%`, background: 'var(--color-accent)', display: 'block' }} />
                        <span style={{ width: `${m.axis_win_rate}%`, background: 'var(--color-accent-warm)', display: 'block' }} />
                      </div>
                      <div className="m" style={{ ...lblStyle, fontSize: 'var(--fs-caption)', marginTop: 'var(--space-1)' }}>
                        allies {m.allies_win_rate.toFixed(1)}% · axis {m.axis_win_rate.toFixed(1)}%
                      </div>
                    </div>
                  ) : (
                    <Lbl style={{ fontSize: 'var(--fs-caption)', marginTop: 'var(--space-2)' }}>win rate — no decided maps yet</Lbl>
                  )}
                  <div className="m" style={{ display: 'flex', gap: 'var(--space-2)', fontSize: 'var(--fs-label)', color: 'var(--color-text-500)', marginTop: 'var(--space-2)', flexWrap: 'wrap' }}>
                    <span>{m.total_kills.toLocaleString('en-US')} kills</span>
                    <span>{m.total_rounds} rd</span>
                    <span>{m.grenade_kills} nades</span>
                    {m.panzer_kills > 0 && <span>{m.panzer_kills} panzer</span>}
                    {m.mortar_kills > 0 && <span>{m.mortar_kills} mortar</span>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
