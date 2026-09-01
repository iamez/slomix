/**
 * Phase 5, slice 5 — the round scope and its canvases (07 §B.2): the wave
 * ledger, the push-death heatmap and the player journey. Their endpoints
 * REQUIRE the scope (a 422 is the wire demanding it), so every hook is
 * enabled only once the picker has the pieces — and the round identity is
 * (round_number, round_start_unix), never number alone: the same map is
 * played more than once on one date (Codex on #867, P1).
 *
 * The journey and heatmap draw in ENGINE COORDINATES normalised to their
 * own extent — no map underlay, and the captions say so: the projection
 * machinery is the spider-web work (#800), and faking an underlay would
 * claim a precision these panels do not have. Kill and death markers are
 * DERIVED from the nearest path point by timestamp, because the wire
 * carries times and names, not coordinates — the first version guessed
 * x/y fields and its own finite-filter silently skipped every marker
 * (both reviewers read the fixture and said so).
 */
import { useState } from 'react';
import { Cluster, Stack } from '../components/layout';
import { Absent, Lbl, Meta, Pending, SectionHead, Unavailable, figure } from '../components/ui';
import { mapLabel } from '../lib/maps';
import { stripEtColors } from '../lib/names';
import { isFailureStatus } from '../lib/responseStatus';
import {
  usePlayerJourney, useProxPlayers, usePushHeatmap, useWaveCycles,
} from '../lib/queries';
import type { JourneyLife, WaveClockValidation } from '../lib/types';
import { ProxPanel, ProxRow } from './proximityShared';

/** The five clock states, each its own tone — FAILED is not a weaker
 * UNVALIDATED: landings exist and they REFUTE the clock (17 §4). */
// Keyed to the statuses the backend ACTUALLY emits
// (reinforcement_clock.py) — the first table guessed friendlier names and
// rendered a REFUTED clock in the neutral fallback (Codex on #867 r2).
// validation_failed is not a weaker unvalidated: landings exist and they
// refute the clock (17 §4).
const CLOCK_TONE: Record<string, string> = {
  validated: 'var(--color-pos)',
  internally_consistent_unvalidated: 'var(--color-text-400)',
  validation_failed: 'var(--color-neg)',
  inconsistent: 'var(--color-accent-warm)',
  insufficient: 'var(--color-text-500)',
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

function WaveLedger({ sessionDate, mapName, roundNumber, roundStartUnix }: { sessionDate: string; mapName: string; roundNumber: number; roundStartUnix: number | null }) {
  const q = useWaveCycles(sessionDate, mapName, roundNumber, roundStartUnix);
  // Hand-rolled states instead of ProxPanel, deliberately: a failed or
  // unvalidated clock answers empty cycles WITH a detailed
  // clock_validation payload — the frame's failure branch would hide
  // exactly the diagnosis worth showing (Codex on #867).
  const clocks = q.data?.clock_validation ?? {};
  const hasClocks = Object.keys(clocks).length > 0;
  return (
    <div data-parity="proximity.wave-ledger">
      <Stack gap={2}>
        <SectionHead label="wave ledger" aside={<span className="lbl">reinforcement cycles, who won each</span>} />
        {q.isPending && <Pending label="wave ledger" />}
        {q.isError && <Unavailable what="wave ledger" />}
        {q.data && (
          <Stack gap={2}>
            {hasClocks && (
              <Cluster gap={4} style={{ flexWrap: 'wrap' }}>
                {Object.entries(clocks).map(([team, v]) => <ClockBadge key={team} team={team} v={v} />)}
              </Cluster>
            )}
            {isFailureStatus(q.data.status) ? (
              <Unavailable what="wave cycles" />
            ) : q.data.cycles.length === 0 ? (
              <Absent reason="no wave cycle could be built for this round — the ledger needs kills linked to a validated reinforcement clock, and the clock verdicts above say why" />
            ) : (
              <>
                {q.data.summary.cycles != null && (
                  <Meta>
                    {figure(q.data.summary.cycles)} cycles · allies {figure(q.data.summary.allies_won ?? 0)} · axis {figure(q.data.summary.axis_won ?? 0)} · contested {figure(q.data.summary.contested ?? 0)}
                    {(q.data.excluded_unlinked_kills > 0 || q.data.excluded_ineligible_linked_kills > 0) && (
                      <> · {figure(q.data.excluded_unlinked_kills + q.data.excluded_ineligible_linked_kills)} kills excluded (unlinked/ineligible)</>
                    )}
                  </Meta>
                )}
                <Stack gap={1} className="rows">
                  {q.data.cycles.map((c, i) => (
                    <ProxRow
                      key={`${c.start_ms}:${i}`}
                      name={`${(c.start_ms / 1000).toFixed(0)}–${(c.end_ms / 1000).toFixed(0)} s`}
                      // Denials ride along: they are the TIE-BREAK when kills
                      // are level, and a row showing a winner without them
                      // looked arbitrary on the fixture's first cycle
                      // (1k–1k, allies by denial) (Codex on #867).
                      mid={`axis ${figure(c.kills_axis)}k/${c.denied_axis_s.toFixed(1)}s denied · allies ${figure(c.kills_allies)}k/${c.denied_allies_s.toFixed(1)}s${c.first_blood ? ` · fb ${c.first_blood.toLowerCase()}` : ''}`}
                      val={c.winner ? c.winner.toLowerCase() : 'contested'}
                    />
                  ))}
                </Stack>
              </>
            )}
          </Stack>
        )}
      </Stack>
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
          // A zero-width axis maps to the CENTER, not the border: with one
          // hotzone (or all sharing a coordinate) span=1 left the numerator
          // at zero and drew the sole observation in a corner of a canvas
          // that is otherwise purely relative (Codex on #867 r2).
          const spanX = maxX - minX; const spanY = maxY - minY;
          const maxC = Math.max(1, ...d.hotzones.map((h) => h.count));
          const w = 420; const h = 300;
          const nx = (x: number) => (spanX === 0 ? 0.5 : (x - minX) / spanX);
          const ny = (y: number) => (spanY === 0 ? 0.5 : (y - minY) / spanY);
          return (
            <Stack gap={2}>
              <Meta>{figure(d.push_deaths)} push deaths · {figure(d.carrier_deaths)} carrier deaths · grid {d.grid_size} u</Meta>
              <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', maxWidth: w, border: '1px solid var(--color-rule-900)' }} role="img" aria-label={`push death hotzones on ${mapLabel(d.map_name)}`}>
                {d.hotzones.map((z, i) => (
                  <circle
                    key={i}
                    cx={nx(z.x) * (w - 20) + 10}
                    cy={h - (ny(z.y) * (h - 20) + 10)}
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

/** The path point nearest to a timestamp — kill/death records carry times,
 * not coordinates, so a marker's place is the track's own answer to
 * "where were they then". */
function nearestPoint(life: JourneyLife, t: number) {
  let best = null as { x: number; y: number } | null;
  let bestD = Infinity;
  for (const p of life.path) {
    if (!Number.isFinite(p.x) || !Number.isFinite(p.y)) continue;
    const d = Math.abs(p.t - t);
    if (d < bestD) { bestD = d; best = { x: p.x, y: p.y }; }
  }
  return best;
}

function LifePath({ life, extent }: { life: JourneyLife; extent: { minX: number; spanX: number; minY: number; spanY: number } }) {
  const w = 420; const h = 260;
  const px = (x: number) => ((x - extent.minX) / extent.spanX) * (w - 20) + 10;
  const py = (y: number) => h - (((y - extent.minY) / extent.spanY) * (h - 20) + 10);
  const pathPts = life.path.filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));
  const d = pathPts.map((p, i) => `${i === 0 ? 'M' : 'L'}${px(p.x).toFixed(1)} ${py(p.y).toFixed(1)}`).join(' ');
  const spawn = pathPts[0];
  return (
    <g>
      <path d={d} fill="none" stroke="var(--color-accent)" strokeWidth="1.2" opacity="0.8" />
      {spawn && <circle cx={px(spawn.x)} cy={py(spawn.y)} r="3.5" fill="var(--color-pos)" />}
      {life.kills.flatMap((k, i) => {
        const at = nearestPoint(life, k.time);
        return at ? [<circle key={`k${i}`} cx={px(at.x)} cy={py(at.y)} r="3" fill="var(--color-accent-warm)" />] : [];
      })}
      {life.death && (() => {
        const at = nearestPoint(life, life.death.time);
        return at ? <circle cx={px(at.x)} cy={py(at.y)} r="3.5" fill="var(--color-neg)" /> : null;
      })()}
    </g>
  );
}

function Journey({ sessionDate, mapName, roundNumber, roundStartUnix }: { sessionDate: string; mapName: string; roundNumber: number; roundStartUnix: number | null }) {
  // Round-scoped roster: the date-only list includes players with no track
  // in THIS round (substitutions, partial evenings), and the first of them
  // as the default rendered "no tracks" while valid journeys existed one
  // chip over (Codex on #867 r2).
  const roster = useProxPlayers(sessionDate, mapName, roundNumber, roundStartUnix);
  const [picked, setPicked] = useState<string | null>(null);
  // Re-validated against the CURRENT roster: a guid kept from another
  // scope would beat the new roster's first player and render "no tracks"
  // while every visible chip looks unselected — the RoundsPage lesson,
  // relearned here by review (Codex on #867).
  const players = roster.data?.players ?? [];
  const known = picked != null && players.some((p) => p.guid === picked);
  const effectiveGuid = (known ? picked : players[0]?.guid) ?? null;
  const q = usePlayerJourney(sessionDate, mapName, roundNumber, roundStartUnix, effectiveGuid);
  return (
    <div data-parity="proximity.journey">
      <Stack gap={2}>
        <SectionHead
          label="player journey"
          aside={
            players.length > 0 ? (
              <Cluster gap={2} style={{ flexWrap: 'wrap' }}>
                {players.map((p) => (
                  <button
                    key={p.guid}
                    type="button"
                    onClick={() => setPicked(p.guid)}
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
        {/* A DISABLED query is pending forever in React Query v5 (the
          * RoundsPage comment, quoted): with an empty roster the journey
          * query never runs, so the roster's own answer must speak first. */}
        {roster.isPending ? (
          <Pending label="journey roster" />
        ) : roster.isError ? (
          <Unavailable what="journey roster" />
        ) : players.length === 0 ? (
          <Absent reason="the tracker recorded no players for this date, so there is no journey to draw" />
        ) : q.isPending ? (
          <Pending label="journey" />
        ) : q.isError ? (
          <Unavailable what="journey" />
        ) : q.data && (q.data.lives.length === 0 ? (
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
                green spawn · amber kills · red death, each placed at the
                track point nearest its timestamp — engine coordinates
                normalised to this player's own extent, no map underlay
              </Lbl>
            </Stack>
          );
        })())}
      </Stack>
    </div>
  );
}

export function ProximityRoundCanvases({ sessionDate, mapName, roundNumber, roundStartUnix }: {
  sessionDate: string;
  mapName: string | null;
  roundNumber: number | null;
  roundStartUnix: number | null;
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
          <WaveLedger sessionDate={sessionDate} mapName={mapName} roundNumber={roundNumber} roundStartUnix={roundStartUnix} />
          <Journey sessionDate={sessionDate} mapName={mapName} roundNumber={roundNumber} roundStartUnix={roundStartUnix} />
        </>
      )}
    </Stack>
  );
}
