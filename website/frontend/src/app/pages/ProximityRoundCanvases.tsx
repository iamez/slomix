/**
 * Phase 5, slice 5 — the round scope and its canvases (07 §B.2): the wave
 * ledger, the push-death heatmap and the player journey. These three are
 * the reason the scope row grows map and round chips: their endpoints
 * REQUIRE the scope (a 422 is the wire demanding it), so every hook here
 * is enabled only once the picker has the pieces.
 *
 * The journey and heatmap draw in ENGINE COORDINATES normalised to their
 * own extent — no map underlay. That is deliberate and labelled: the
 * projection machinery (map bounds, imagery) is the spider-web work
 * (#800's exported project.ts), and faking an underlay here would claim
 * a precision the panel does not have.
 */
import { useState } from 'react';
import { Cluster, Stack } from '../components/layout';
import { Lbl, Meta, Pending, SectionHead, Unavailable, figure } from '../components/ui';
import { mapLabel } from '../lib/maps';
import { stripEtColors } from '../lib/names';
import {
  usePlayerJourney, useProxPlayers, usePushHeatmap, useWaveCycles,
} from '../lib/queries';
import type { JourneyLife, WaveClockValidation } from '../lib/types';
import { ProxPanel, ProxRow } from './proximityShared';

/** The five clock states, each its own tone — FAILED is not a weaker
 * UNVALIDATED: landings exist and they REFUTE the clock (17 §4). */
const CLOCK_TONE: Record<string, string> = {
  validated: 'var(--color-pos)',
  unvalidated: 'var(--color-text-400)',
  failed: 'var(--color-neg)',
  inconsistent: 'var(--color-accent-warm)',
  unavailable: 'var(--color-text-500)',
};

function ClockBadge({ team, v }: { team: string; v: WaveClockValidation }) {
  return (
    <Meta>
      <span style={{ color: CLOCK_TONE[v.status] ?? 'var(--color-text-400)' }}>{team.toLowerCase()} clock {v.status}</span>
      {v.interval_ms != null && <> · {figure(v.interval_ms / 1000)} s wave</>}
      {/* The ratio never travels alone — its denominators say how little
        * it stands on (17 §4: pass_ratio always with counts). */}
      {v.pass_ratio != null && (
        <> · {(v.pass_ratio * 100).toFixed(0)}% ({v.passing_landing_clusters}/{v.landing_clusters} clusters, {v.timing_observations} obs)</>
      )}
    </Meta>
  );
}

function WaveLedger({ sessionDate, mapName, roundNumber }: { sessionDate: string; mapName: string; roundNumber: number }) {
  const q = useWaveCycles(sessionDate, mapName, roundNumber);
  return (
    <div data-parity="proximity.wave-ledger">
      <ProxPanel label="wave ledger" aside="reinforcement cycles, who won each" q={q} empty="no wave cycle could be built for this round — the ledger needs kills linked to a validated reinforcement clock" isEmpty={(d) => d.cycles.length === 0}>
        {(d) => (
          <Stack gap={2}>
            <Cluster gap={4} style={{ flexWrap: 'wrap' }}>
              {Object.entries(d.clock_validation).map(([team, v]) => (
                <ClockBadge key={team} team={team} v={v} />
              ))}
            </Cluster>
            {d.summary.cycles != null && (
              <Meta>
                {figure(d.summary.cycles)} cycles · allies {figure(d.summary.allies_won ?? 0)} · axis {figure(d.summary.axis_won ?? 0)} · contested {figure(d.summary.contested ?? 0)}
                {(d.excluded_unlinked_kills > 0 || d.excluded_ineligible_linked_kills > 0) && (
                  <> · {figure(d.excluded_unlinked_kills + d.excluded_ineligible_linked_kills)} kills excluded (unlinked/ineligible)</>
                )}
              </Meta>
            )}
            <Stack gap={1} className="rows">
              {d.cycles.map((c, i) => (
                <ProxRow
                  key={`${c.start_ms}:${i}`}
                  name={`${(c.start_ms / 1000).toFixed(0)}–${(c.end_ms / 1000).toFixed(0)} s`}
                  mid={`axis ${figure(c.kills_axis)}k · allies ${figure(c.kills_allies)}k${c.first_blood ? ` · first blood ${c.first_blood.toLowerCase()}` : ''}`}
                  val={c.winner ? c.winner.toLowerCase() : 'contested'}
                />
              ))}
            </Stack>
          </Stack>
        )}
      </ProxPanel>
    </div>
  );
}

function Heatmap({ sessionDate, mapName }: { sessionDate: string; mapName: string }) {
  const q = usePushHeatmap(sessionDate, mapName);
  return (
    <div data-parity="proximity.push-heatmap">
      <ProxPanel label="push deaths" aside="where advances die" q={q} empty="no push died on this map in this scope — either the pushes got through, or none were tracked" isEmpty={(d) => d.hotzones.length === 0}>
        {(d) => {
          const xs = d.hotzones.map((h) => h.x);
          const ys = d.hotzones.map((h) => h.y);
          const minX = Math.min(...xs); const maxX = Math.max(...xs);
          const minY = Math.min(...ys); const maxY = Math.max(...ys);
          const spanX = Math.max(1, maxX - minX); const spanY = Math.max(1, maxY - minY);
          const maxC = Math.max(1, ...d.hotzones.map((h) => h.count));
          const w = 420; const h = 300;
          return (
            <Stack gap={2}>
              <Meta>{figure(d.push_deaths)} push deaths · {figure(d.carrier_deaths)} carrier deaths · grid {d.grid_size} u</Meta>
              <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', maxWidth: w, border: '1px solid var(--color-rule-900)' }} role="img" aria-label={`push death hotzones on ${mapLabel(d.map_name)}`}>
                {d.hotzones.map((z, i) => (
                  <circle
                    key={i}
                    cx={((z.x - minX) / spanX) * (w - 20) + 10}
                    cy={h - (((z.y - minY) / spanY) * (h - 20) + 10)}
                    r={3 + (z.count / maxC) * 9}
                    fill="var(--color-neg)"
                    opacity={0.25 + (z.count / maxC) * 0.55}
                  />
                ))}
              </svg>
              <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
                engine coordinates normalised to the hotzone extent — no map
                underlay; the projection machinery is the spider-web work
              </Lbl>
            </Stack>
          );
        }}
      </ProxPanel>
    </div>
  );
}

function LifePath({ life, extent }: { life: JourneyLife; extent: { minX: number; spanX: number; minY: number; spanY: number } }) {
  const w = 420; const h = 260;
  const px = (x: number) => ((x - extent.minX) / extent.spanX) * (w - 20) + 10;
  const py = (y: number) => h - (((y - extent.minY) / extent.spanY) * (h - 20) + 10);
  // Finite-only: measured live, some kill/death records carry no
  // coordinates and a NaN cx is ten console errors per render — a marker
  // without a place is simply not drawn (the ledger row still counts it).
  const finite = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);
  const pathPts = life.path.filter((p) => finite(p.x) && finite(p.y));
  const d = pathPts.map((p, i) => `${i === 0 ? 'M' : 'L'}${px(p.x).toFixed(1)} ${py(p.y).toFixed(1)}`).join(' ');
  const spawn = pathPts[0];
  return (
    <g>
      <path d={d} fill="none" stroke="var(--color-accent)" strokeWidth="1.2" opacity="0.8" />
      {spawn && <circle cx={px(spawn.x)} cy={py(spawn.y)} r="3.5" fill="var(--color-pos)" />}
      {life.kills.flatMap((k, i) =>
        finite(k.x) && finite(k.y)
          ? [<circle key={`k${i}`} cx={px(k.x)} cy={py(k.y)} r="3" fill="var(--color-accent-warm)" />]
          : [])}
      {life.death && finite(life.death.x) && finite(life.death.y) && (
        <circle cx={px(life.death.x)} cy={py(life.death.y)} r="3.5" fill="var(--color-neg)" />
      )}
    </g>
  );
}

function Journey({ sessionDate, mapName, roundNumber }: { sessionDate: string; mapName: string; roundNumber: number }) {
  const roster = useProxPlayers(sessionDate);
  const [guid, setGuid] = useState<string | null>(null);
  const effectiveGuid = guid ?? roster.data?.players[0]?.guid ?? null;
  const q = usePlayerJourney(sessionDate, mapName, roundNumber, effectiveGuid);
  return (
    <div data-parity="proximity.journey">
      <Stack gap={2}>
        <SectionHead
          label="player journey"
          aside={
            roster.data ? (
              <Cluster gap={2} style={{ flexWrap: 'wrap' }}>
                {roster.data.players.map((p) => (
                  <button
                    key={p.guid}
                    type="button"
                    onClick={() => setGuid(p.guid)}
                    aria-pressed={effectiveGuid === p.guid}
                    style={{ all: 'unset', cursor: 'pointer', fontSize: 'var(--fs-caption)', letterSpacing: '0.06em', color: effectiveGuid === p.guid ? 'var(--color-text-100)' : 'var(--color-text-400)' }}
                  >
                    {p.name ? stripEtColors(p.name) : p.guid.slice(0, 8)}
                  </button>
                ))}
              </Cluster>
            ) : undefined
          }
        />
        {(roster.isPending || q.isPending) && <Pending label="journey" />}
        {(roster.isError || q.isError) && <Unavailable what="journey" />}
        {q.data && (q.data.lives.length === 0 ? (
          <Meta>{q.data.message ?? 'no tracks for this player in this round'}</Meta>
        ) : (() => {
          const pts = q.data.lives.flatMap((l) => l.path)
            .filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));
          const xs = pts.map((p) => p.x); const ys = pts.map((p) => p.y);
          const extent = {
            minX: Math.min(...xs), spanX: Math.max(1, Math.max(...xs) - Math.min(...xs)),
            minY: Math.min(...ys), spanY: Math.max(1, Math.max(...ys) - Math.min(...ys)),
          };
          return (
            <Stack gap={2}>
              <svg viewBox="0 0 420 260" style={{ width: '100%', maxWidth: 420, border: '1px solid var(--color-rule-900)' }} role="img" aria-label="paths of every life this round">
                {q.data.lives.map((l) => <LifePath key={l.life_index} life={l} extent={extent} />)}
              </svg>
              <Stack gap={1} className="rows">
                {q.data.lives.map((l) => (
                  <ProxRow
                    key={l.life_index}
                    name={`life ${l.life_index} · ${l.player_class.toLowerCase()}`}
                    mid={l.narrative}
                    val={`${figure(Math.round(l.duration_ms / 1000))} s · ${figure(l.kills.length)}k`}
                  />
                ))}
              </Stack>
              <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
                green spawn · amber kills · red death — engine coordinates
                normalised to this player's own extent, no map underlay
              </Lbl>
            </Stack>
          );
        })())}
      </Stack>
    </div>
  );
}

export function ProximityRoundCanvases({ sessionDate, mapName, roundNumber }: {
  sessionDate: string;
  mapName: string | null;
  roundNumber: number | null;
}) {
  if (mapName == null) {
    return (
      <Meta>pick a map above to open the heatmap, and a round for the wave ledger and journeys</Meta>
    );
  }
  return (
    <Stack gap={6} style={{ marginTop: 'var(--space-6)' }}>
      <Heatmap sessionDate={sessionDate} mapName={mapName} />
      {roundNumber == null ? (
        <Meta>pick a round above for the wave ledger and player journeys</Meta>
      ) : (
        <>
          <WaveLedger sessionDate={sessionDate} mapName={mapName} roundNumber={roundNumber} />
          <Journey sessionDate={sessionDate} mapName={mapName} roundNumber={roundNumber} />
        </>
      )}
    </Stack>
  );
}
