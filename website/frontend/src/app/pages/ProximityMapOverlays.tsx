/**
 * Phase 5 — the map overlays: the last seven paths of the proximity
 * inventory. All scatter/line panels share ONE extent normalisation with
 * the zero-span-center rule (a lone observation belongs in the middle of
 * a purely relative canvas, not its corner — #867 r2). No map underlay;
 * the projection machinery is the spider-web work.
 */
import { useState } from 'react';
import { WEAPON_NAMES } from '../lib/weapons';
import { Cluster, Stack } from '../components/layout';
import { Lbl, Meta, figure, decimals } from '../components/ui';
import { mapLabel } from '../lib/maps';
import { utcStamp } from '../lib/utcStamp';
import { stripEtColors } from '../lib/names';
import {
  useProxCombatHeatmap, useProxDangerZones, useProxHotzones, useProxKillLines,
  useProxMovers, useProxPlayerAim, useProxPlayerHeatmap, useProxPlayers,
} from '../lib/queries';
import { ProxPanel, ProxRow } from './proximityShared';

const NO_ROWS = 'no rows in this scope — proximity capture only covers sessions where the tracker ran';
const W = 420; const H = 300;

function extent(pts: { x: number; y: number }[]) {
  const xs = pts.map((p) => p.x); const ys = pts.map((p) => p.y);
  const minX = Math.min(...xs); const spanX = Math.max(...xs) - minX;
  const minY = Math.min(...ys); const spanY = Math.max(...ys) - minY;
  const nx = (x: number) => (spanX === 0 ? 0.5 : (x - minX) / spanX);
  const ny = (y: number) => (spanY === 0 ? 0.5 : (y - minY) / spanY);
  return {
    px: (x: number) => nx(x) * (W - 20) + 10,
    py: (y: number) => H - (ny(y) * (H - 20) + 10),
  };
}

function DotCanvas({ pts, tone, label }: {
  pts: { x: number; y: number; count: number }[];
  tone: string;
  label: string;
}) {
  const { px, py } = extent(pts);
  const maxC = Math.max(1, ...pts.map((p) => p.count));
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', maxWidth: W, border: '1px solid var(--color-rule-900)' }} role="img" aria-label={label}>
      {pts.map((z, i) => (
        <circle key={i} cx={px(z.x)} cy={py(z.y)} r={3 + (z.count / maxC) * 9}
          fill={tone} opacity={0.25 + (z.count / maxC) * 0.55} />
      ))}
    </svg>
  );
}

const HEATMAP_MODES = ['kills_from', 'victims_die', 'player_dies', 'presence', 'aim'] as const;

export function ProximityMapOverlays({ sessionDate, mapName }: { sessionDate: string | null; mapName: string | null }) {
  const danger = useProxDangerZones(sessionDate, mapName);
  const combat = useProxCombatHeatmap(sessionDate, mapName);
  const killLines = useProxKillLines(sessionDate, mapName);
  const hotzones = useProxHotzones(sessionDate, mapName);
  const movers = useProxMovers(sessionDate, mapName);
  const roster = useProxPlayers(sessionDate, mapName, null, null);
  const [pickedGuid, setPickedGuid] = useState<string | null>(null);
  const [mode, setMode] = useState<(typeof HEATMAP_MODES)[number]>('kills_from');
  const playerHeatmap = useProxPlayerHeatmap(sessionDate, mapName, pickedGuid, mode);
  const playerAim = useProxPlayerAim(sessionDate, mapName, pickedGuid);

  if (mapName == null) return null;

  return (
    <Stack gap={6} style={{ marginTop: 'var(--space-6)' }}>
      <div data-parity="proximity.danger-zones">
        <ProxPanel label="danger zones" aside="deaths per grid cell" q={danger} empty={NO_ROWS}
          isEmpty={(d) => d.zones.length === 0}>
          {(d) => (
            <Stack gap={2}>
              <DotCanvas pts={d.zones.map((z) => ({ x: z.x, y: z.y, count: z.deaths }))}
                tone="var(--color-neg)" label={`danger zones on ${mapLabel(d.map_name)}`} />
              <Meta>grid {figure(d.grid_size)} u · deadliest cell {figure(Math.max(...d.zones.map((z) => z.deaths)))} deaths</Meta>
              {/* Who dies there: the class split summed over every cell. */}
              <Meta>by class: {Object.entries(d.zones.reduce<Record<string, number>>((acc, z) => { for (const [cls, n] of Object.entries(z.classes)) acc[cls] = (acc[cls] ?? 0) + (n ?? 0); return acc; }, {}))
                .sort((a, b) => b[1] - a[1]).map(([cls, n]) => `${cls.toLowerCase()} ${figure(n)}`).join(' · ') || 'none recorded'}</Meta>
            </Stack>
          )}
        </ProxPanel>
      </div>

      <div data-parity="proximity.combat-heatmap">
        <ProxPanel label="combat heat" aside={combat.data ? `${combat.data.perspective} perspective` : undefined}
          q={combat} empty={NO_ROWS} isEmpty={(d) => d.hotzones.length === 0}>
          {(d) => <DotCanvas pts={d.hotzones} tone="var(--color-accent)" label={`combat heat on ${mapLabel(d.map_name)}`} />}
        </ProxPanel>
      </div>

      <div data-parity="proximity.kill-lines">
        <ProxPanel label="kill lines" aside="attacker → victim" q={killLines} empty={NO_ROWS}
          isEmpty={(d) => d.lines.length === 0}>
          {(d) => {
            const pts = d.lines.flatMap((l) => [{ x: l.ax, y: l.ay }, { x: l.vx, y: l.vy }]);
            const { px, py } = extent(pts);
            return (
              <Stack gap={2}>
                <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', maxWidth: W, border: '1px solid var(--color-rule-900)' }} role="img" aria-label={`kill lines on ${mapLabel(d.map_name)}`}>
                  {d.lines.slice(0, 400).map((l, i) => (
                    <line key={i} x1={px(l.ax)} y1={py(l.ay)} x2={px(l.vx)} y2={py(l.vy)}
                      stroke={l.attacker_team === 'AXIS' ? 'var(--color-neg)' : 'var(--color-accent)'}
                      strokeWidth="0.7" opacity="0.35" />
                  ))}
                </svg>
                <Meta>{figure(d.lines.length)} kills with both positions known{d.lines.length > 400 ? ' · drawing the first 400' : ''}</Meta>
                <Meta>by weapon: {Object.entries(d.lines.reduce<Record<string, number>>((acc, l) => { const w = WEAPON_NAMES[l.weapon_id] ?? `weapon ${l.weapon_id}`; acc[w] = (acc[w] ?? 0) + 1; return acc; }, {}))
                  .sort((a, b) => b[1] - a[1]).slice(0, 6).map(([w, n]) => `${w} ${figure(n)}`).join(' · ')}</Meta>
              </Stack>
            );
          }}
        </ProxPanel>
      </div>

      <div data-parity="proximity.hotzones">
        <ProxPanel label="engagement hotzones" aside={hotzones.data ? `source ${hotzones.data.source}` : undefined}
          q={hotzones} empty={NO_ROWS} isEmpty={(d) => d.hotzones.length === 0}>
          {(d) => (
            <Stack gap={2}>
              <DotCanvas pts={d.hotzones} tone="var(--color-accent-warm, var(--color-accent))" label={`hotzones on ${mapLabel(d.map_name)}`} />
              <Meta>{figure(d.hotzones.reduce((a, z) => a + z.count, 0))} engagements across {figure(d.hotzones.length)} cells · {figure(d.hotzones.reduce((a, z) => a + z.kills, 0))} kills, {figure(d.hotzones.reduce((a, z) => a + z.deaths, 0))} deaths</Meta>
            </Stack>
          )}
        </ProxPanel>
      </div>

      <div data-parity="proximity.movers">
        <ProxPanel label="movers" aside="distance · sprint · reaction · survival" q={movers} empty={NO_ROWS}
          isEmpty={(d) => d.distance.length === 0 && d.sprint.length === 0}>
          {(d) => (
            <Stack gap={2}>
              {!d.ready && d.message && <Meta>{d.message}</Meta>}
              <Cluster gap={7} align="start" style={{ flexWrap: 'wrap' }}>
                <Stack gap={1} className="rows" style={{ minWidth: 240 }}>
                  <Lbl>distance</Lbl>
                  {d.distance.slice(0, 5).map((r) => (
                    <ProxRow key={r.guid} name={r.name ? stripEtColors(r.name) : r.guid.slice(0, 8)} mid={`${figure(r.tracks)} tracks`}
                      val={`${figure(Math.round(r.total_distance / 1000))} k u`} />
                  ))}
                </Stack>
                <Stack gap={1} className="rows" style={{ minWidth: 240 }}>
                  <Lbl>sprint share</Lbl>
                  {d.sprint.slice(0, 5).map((r) => (
                    <ProxRow key={r.guid} name={r.name ? stripEtColors(r.name) : r.guid.slice(0, 8)} mid={`${figure(r.tracks)} tracks`}
                      val={`${figure(r.sprint_pct)}%`} />
                  ))}
                </Stack>
                {/* The other two boards the endpoint answers and the page never drew (ledger 2026-09-09). */}
                <Stack gap={1} className="rows" style={{ minWidth: 240 }}>
                  {/* AVG(time_to_first_move_ms): spawn → first move, not a reaction to a hit (proximity_movement.py) */}
                  <Lbl>first move after a spawn</Lbl>
                  {d.reaction.slice(0, 5).map((r) => (
                    <ProxRow key={r.guid} name={r.name ? stripEtColors(r.name) : r.guid.slice(0, 8)} mid={`${figure(r.tracks)} tracks`}
                      val={`avg ${figure(r.reaction_ms)} ms`} />
                  ))}
                </Stack>
                <Stack gap={1} className="rows" style={{ minWidth: 240 }}>
                  {/* AVG(duration_ms) over the player's tracks (proximity_movement.py), not a single longest life */}
                  <Lbl>average life</Lbl>
                  {d.survival.slice(0, 5).map((r) => (
                    <ProxRow key={r.guid} name={r.name ? stripEtColors(r.name) : r.guid.slice(0, 8)} mid={`${figure(r.tracks)} tracks`}
                      val={`avg ${figure(Math.round(r.duration_ms / 1000))} s`} />
                  ))}
                </Stack>
              </Cluster>
              {d.generated_at && <Meta>computed {utcStamp(d.generated_at)}</Meta>}
            </Stack>
          )}
        </ProxPanel>
      </div>

      <div data-parity="proximity.player-heatmap">
        <Stack gap={2}>
          <Cluster gap={3} style={{ flexWrap: 'wrap' }}>
            {(roster.data?.players ?? []).slice(0, 12).map((p) => (
              <button key={p.guid} type="button"
                onClick={() => setPickedGuid(pickedGuid === p.guid ? null : p.guid)}
                aria-pressed={pickedGuid === p.guid}
                style={{ all: 'unset', cursor: 'pointer', fontSize: 'var(--fs-caption)', letterSpacing: '0.06em', color: pickedGuid === p.guid ? 'var(--color-text-100)' : 'var(--color-text-400)' }}>
                {p.name ? stripEtColors(p.name) : p.guid.slice(0, 8)}
              </button>
            ))}
          </Cluster>
          {pickedGuid == null ? (
            <Meta>pick a player above for their personal heatmap and aim profile</Meta>
          ) : (
            <>
              <Cluster gap={3}>
                {HEATMAP_MODES.map((m) => (
                  <button key={m} type="button" onClick={() => setMode(m)} aria-pressed={mode === m}
                    style={{ all: 'unset', cursor: 'pointer', fontSize: 'var(--fs-caption)', letterSpacing: '0.06em', textTransform: 'uppercase', color: mode === m ? 'var(--color-text-100)' : 'var(--color-text-400)' }}>
                    {m.replace('_', ' ')}
                  </button>
                ))}
              </Cluster>
              <ProxPanel label="player heatmap" aside={playerHeatmap.data?.sampled ? 'sampled' : undefined}
                q={playerHeatmap} empty="no samples for this player in this mode"
                isEmpty={(d) => d.hotzones.length === 0}>
                {(d) => (
                  <Stack gap={2}>
                    <DotCanvas pts={d.hotzones} tone="var(--color-pos)" label={`${d.mode} heatmap`} />
                    <Meta>{figure(d.total)} samples · mode {d.mode}</Meta>
                  </Stack>
                )}
              </ProxPanel>
              <div data-parity="proximity.player-aim">
                <ProxPanel label="aim profile" aside="pitch distribution" q={playerAim}
                  empty="no aim samples for this player" isEmpty={(d) => d.pitch_hist.counts.every((c) => c === 0)}>
                  {(d) => {
                    const maxC = Math.max(1, ...d.pitch_hist.counts);
                    return (
                      <Stack gap={2}>
                        <svg viewBox="0 0 420 120" style={{ width: '100%', maxWidth: 420 }} role="img" aria-label="pitch histogram">
                          {d.pitch_hist.counts.map((c, i) => {
                            const bw = 420 / d.pitch_hist.counts.length;
                            const bh = (c / maxC) * 100;
                            return <rect key={i} x={i * bw + 1} y={110 - bh} width={bw - 2} height={bh} fill="var(--color-accent)" opacity="0.7" />;
                          })}
                        </svg>
                        <Meta>
                          pitch from {figure(d.pitch_hist.edges[0])}° to {figure(d.pitch_hist.edges[d.pitch_hist.edges.length - 1])}°
                          {' · '}{figure(d.total)} samples · yaw in {figure(d.yaw_buckets)} buckets of {figure(d.yaw_bucket_width_deg)}°
                        </Meta>
                        {/* The circular statistics the legacy page drew (proximity.js:4175):
                          * Rayleigh p < 0.05 = the shots have a preferred direction;
                          * r near 0 = aimed everywhere. */}
                        {d.circular && (
                          <Meta>
                            direction: mean yaw {figure(Math.round(d.circular.mean_yaw_deg))}° · r {decimals(d.circular.resultant_length)} · circular std ±{figure(Math.round(d.circular.circular_std_deg))}°
                            {' · '}{d.circular.rayleigh_p < 0.05 ? `a preferred direction (Rayleigh p ${d.circular.rayleigh_p < 0.001 ? '< 0.001' : decimals(d.circular.rayleigh_p, 3)})` : `no preferred direction (Rayleigh p ${decimals(d.circular.rayleigh_p)})`}
                            {' · '}pitch {d.circular.pitch_mean_deg >= 0 ? '+' : ''}{figure(Math.round(d.circular.pitch_mean_deg))}° ± {figure(Math.round(d.circular.pitch_std_deg))}° over {figure(d.circular.n)} shots
                          </Meta>
                        )}
                        {d.hotzones.some((h) => h.rose) && (() => {
                          const top = [...d.hotzones].sort((a, b) => b.count - a.count)[0];
                          const rose = top.rose ?? [];
                          const peak = rose.indexOf(Math.max(...rose));
                          return (
                            <Meta>
                              busiest zone ({figure(top.count)} shots): mean yaw {top.mean_yaw == null ? '—' : `${figure(Math.round(top.mean_yaw))}°`}, r {top.r == null ? '—' : decimals(top.r)}
                              {rose.length > 0 ? ` · rose peak bucket ${figure(peak + 1)} of ${figure(rose.length)} (${figure(Math.max(...rose))} shots)` : ''}
                            </Meta>
                          );
                        })()}
                        {d.narrative && d.narrative.length > 0 && <Meta>{d.narrative.join(' · ')}</Meta>}
                      </Stack>
                    );
                  }}
                </ProxPanel>
              </div>
            </>
          )}
        </Stack>
      </div>
    </Stack>
  );
}
