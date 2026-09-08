/**
 * Phase 5 — the spider web, slice 1 (route spider-web,
 * /spider-web/round/:roundId): the layer-1 reconstruction at one moment,
 * drawn top-down. ⛔ The point of view is a SERVER parameter — this page
 * never fetches the world view and filters locally (#800's contract), and
 * WITHHELD branches before any clock-quality switch. What slice 1 leaves
 * out is named at the bottom: the 3D camera, belief regions and label
 * placement of the legacy canvas are a follow-up, not missing parity.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'react-router';
import { Cluster, Stack } from '../components/layout';
import { Absent, Chip, Lbl, Meta, Pending, SectionHead, Unavailable, figure } from '../components/ui';
import { ApiError } from '../lib/api';
import { stripEtColors } from '../lib/names';
import { mapLabel } from '../lib/maps';
import { useMapMesh, useSpiderWebMoment } from '../lib/queries';
import { DataTable, type DataColumn } from '../components/DataTable';
import { mmss } from '../components/RoundsTable';
import type { SpiderBelief, SpiderClock, SpiderPlayer, SpiderWebSnapshot } from '../lib/types';
import { isClockOwnHud, isClockWithheld } from '../lib/types';

const POVS = [
  { key: 'world', label: 'world' },
  { key: 'team:AXIS', label: 'axis pov' },
  { key: 'team:ALLIES', label: 'allies pov' },
];

const TEAM_HUE: Record<string, string> = {
  AXIS: '#b45f5f',
  ALLIES: '#5f87b4',
};

function ClockBadge({ team, clock }: { team: string; clock: SpiderClock }) {
  // ⛔ WITHHELD first — it is a second axis, not a sixth quality state.
  if (isClockWithheld(clock)) {
    return (
      <Stack gap={1} style={{ minWidth: 220 }}>
        <Lbl>{team.toLowerCase()} clock · withheld</Lbl>
        <Meta>{clock.reason}</Meta>
        <Meta>public interval {figure(Math.round(clock.interval_ms / 1000))} s</Meta>
      </Stack>
    );
  }
  if (isClockOwnHud(clock)) {
    return (
      <Stack gap={1} style={{ minWidth: 220 }}>
        <Lbl>{team.toLowerCase()} clock · own hud</Lbl>
        <Meta>
          wave every {figure(Math.round(clock.interval_ms / 1000))} s · next in{' '}
          {figure(Math.round(clock.time_to_next_wave_ms / 1000))} s
        </Meta>
        <Meta>{clock.reason}</Meta>
      </Stack>
    );
  }
  return (
    <Stack gap={1} style={{ minWidth: 220 }} className="rows">
      <Lbl>{team.toLowerCase()} clock · {clock.status.replace(/_/g, ' ')}</Lbl>
      <Meta>
        wave every {figure(Math.round(clock.interval_ms / 1000))} s · next in{' '}
        {figure(Math.round(clock.time_to_next_wave_ms / 1000))} s
      </Meta>
      <Meta>
        {figure(clock.passing_landing_clusters)}/{figure(clock.landing_clusters)} landing
        clusters pass ({figure(Math.round(clock.pass_ratio * 100))}%) ·{' '}
        {figure(clock.timing_observations)} observations
      </Meta>
    </Stack>
  );
}

function drawMoment(
  canvas: HTMLCanvasElement,
  snap: SpiderWebSnapshot,
  mesh: { vertices: number[]; indexes: number[] } | null,
) {
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  const W = canvas.width; const H = canvas.height;
  ctx.clearRect(0, 0, W, H);

  // Bounds from the players (legacy boundsFromPlayers margin), mesh as backdrop.
  const xs = snap.players.map((p) => p.x); const ys = snap.players.map((p) => p.y);
  if (xs.length === 0) return;
  const margin = 512;
  const minX = Math.min(...xs) - margin; const maxX = Math.max(...xs) + margin;
  const minY = Math.min(...ys) - margin; const maxY = Math.max(...ys) + margin;
  const spanX = Math.max(1, maxX - minX); const spanY = Math.max(1, maxY - minY);
  const scale = Math.min((W - 24) / spanX, (H - 24) / spanY);
  const px = (x: number) => 12 + (x - minX) * scale;
  const py = (y: number) => H - 12 - (y - minY) * scale;

  if (mesh) {
    ctx.fillStyle = 'rgba(120,120,130,0.05)';
    const { vertices, indexes } = mesh;
    for (let i = 0; i + 2 < indexes.length; i += 3) {
      const a = indexes[i] * 3; const b = indexes[i + 1] * 3; const c = indexes[i + 2] * 3;
      // Skip triangles fully outside the viewport on either axis (the mesh
      // covers the map, the moment covers the fight).
      if ((vertices[a] < minX && vertices[b] < minX && vertices[c] < minX)
        || (vertices[a] > maxX && vertices[b] > maxX && vertices[c] > maxX)
        || (vertices[a + 1] < minY && vertices[b + 1] < minY && vertices[c + 1] < minY)
        || (vertices[a + 1] > maxY && vertices[b + 1] > maxY && vertices[c + 1] > maxY)) continue;
      ctx.beginPath();
      ctx.moveTo(px(vertices[a]), py(vertices[a + 1]));
      ctx.lineTo(px(vertices[b]), py(vertices[b + 1]));
      ctx.lineTo(px(vertices[c]), py(vertices[c + 1]));
      ctx.closePath();
      ctx.fill();
    }
  }

  const byGuid = new Map(snap.players.map((p) => [p.guid, p]));
  for (const e of snap.edges) {
    const a = byGuid.get(e.a); const b = byGuid.get(e.b);
    if (!a || !b) continue;
    const opponent = e.kind === 'opponent';
    ctx.strokeStyle = opponent ? 'rgba(196,92,92,ALPHA)'.replace('ALPHA', e.recently_contested ? '0.75' : '0.28')
      : 'rgba(95,135,180,ALPHA)'.replace('ALPHA', e.recently_contested ? '0.75' : '0.28');
    ctx.lineWidth = e.recently_contested ? 1.8 : 0.8;
    ctx.setLineDash(e.recently_contested ? [] : [3, 4]);
    ctx.beginPath();
    ctx.moveTo(px(a.x), py(a.y));
    ctx.lineTo(px(b.x), py(b.y));
    ctx.stroke();
  }
  ctx.setLineDash([]);

  for (const p of snap.players) {
    const cx = px(p.x); const cy = py(p.y);
    // The honesty ring: the measured p90 position error at this staleness.
    if (p.alive && p.position_error && p.position_error.p90 > 0) {
      ctx.strokeStyle = 'rgba(160,160,170,0.18)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(cx, cy, Math.max(3, p.position_error.p90 * scale), 0, Math.PI * 2);
      ctx.stroke();
    }
    const hue = TEAM_HUE[p.team] ?? '#999999';
    ctx.beginPath();
    ctx.arc(cx, cy, p.alive ? 5 : 3.5, 0, Math.PI * 2);
    if (p.alive) { ctx.fillStyle = hue; ctx.fill(); }
    else { ctx.strokeStyle = hue; ctx.lineWidth = 1.2; ctx.stroke(); }
    ctx.fillStyle = 'rgba(200,200,210,0.85)';
    ctx.font = '10px ui-monospace, monospace';
    ctx.fillText(p.name ? stripEtColors(p.name) : p.guid.slice(0, 8), cx + 8, cy - 6);
  }
}

const STANCE_WORD: Record<number, string> = { 0: 'standing', 1: 'crouching', 2: 'prone' };

/** A distance the server publishes as an interval, printed as one. */
function span(d: { min: number; max: number }): string {
  return d.min === d.max ? figure(Math.round(d.max)) : `${figure(Math.round(d.min))}–${figure(Math.round(d.max))}`;
}

/** Two decimals kept — `figure()` would fold 0.031 and 0.025 into 0.0. */
function hundredths(v: number): string {
  return (Math.round(v * 100) / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/** Every placed player at this moment with the track fields the canvas
 *  cannot show: how stale the sample is, which track it came from, whether
 *  it collided with another, the velocity and why it may be missing, and
 *  the geometric distance to the nearest teammate. */
function PlacedPlayers({ snap }: { snap: SpiderWebSnapshot }) {
  const sep = snap.nearest_teammate_separation ?? {};
  const columns: DataColumn<SpiderPlayer>[] = [
    { key: 'name', label: 'player', width: 140, align: 'left', format: (p) => p.name ?? p.guid.slice(0, 8), sortValue: (p) => p.name ?? p.guid },
    { key: 'team', label: 'team', sortValue: (p) => p.team },
    { key: 'class', label: 'class', format: (p) => p.class ?? <Meta>—</Meta>, sortValue: (p) => p.class },
    { key: 'alive', label: 'state', format: (p) => (p.alive ? 'alive' : 'down'), sortValue: (p) => (p.alive ? 1 : 0) },
    { key: 'health', label: 'hp', align: 'right', sortValue: (p) => p.health },
    { key: 'stance', label: 'stance', format: (p) => (p.stance == null ? <Meta>—</Meta> : STANCE_WORD[p.stance] ?? `stance ${String(p.stance)}`), sortValue: (p) => p.stance },
    { key: 'speed', label: 'speed', align: 'right', title: 'game units per second', format: (p) => (p.speed == null ? <Meta>—</Meta> : figure(Math.round(p.speed))), sortValue: (p) => p.speed },
    { key: 'vz', label: 'vz', align: 'right', title: 'vertical velocity — null when no second sample within the window', format: (p) => (p.vz == null ? <Meta>—</Meta> : figure(Math.round(p.vz))), sortValue: (p) => p.vz },
    { key: 'velocity_reason', label: 'velocity', title: 'why the velocity is what it is (the server names it)', format: (p) => p.velocity_reason ?? <Meta>—</Meta>, sortValue: (p) => p.velocity_reason },
    { key: 'velocity_stale_ms', label: 'v pair', align: 'right', title: 'ms between the two samples the velocity was derived from (the causal pair) — not the sample age, which is the stale column', format: (p) => (p.velocity_stale_ms == null ? <Meta>—</Meta> : figure(p.velocity_stale_ms)), sortValue: (p) => p.velocity_stale_ms },
    { key: 'stale_ms', label: 'stale', align: 'right', title: 'ms since the position sample', sortValue: (p) => p.stale_ms },
    { key: 'track_id', label: 'track', align: 'right', sortValue: (p) => p.track_id },
    { key: 'overlap_conflict', label: 'overlap', title: 'two tracks claimed this player at once', format: (p) => (p.overlap_conflict ? 'conflict' : <Meta>—</Meta>), sortValue: (p) => (p.overlap_conflict ? 1 : 0) },
    { key: 'nearest', label: 'nearest mate', align: 'right', title: 'geometric distance to the nearest teammate — not tactical support distance', format: (p) => (sep[p.guid] == null ? <Meta>—</Meta> : figure(Math.round(sep[p.guid]))), sortValue: (p) => sep[p.guid] ?? null },
  ];
  return (
    <div data-parity="spider-web.players">
      <SectionHead label="placed players" aside={<span className="lbl">{figure(snap.players.length)} at {mmss(snap.t_ms / 1000)}</span>} />
      <div style={{ marginTop: 'var(--space-3)' }}>
        <DataTable<SpiderPlayer> parity="spider-web.players.table" label="placed players" columns={columns} rows={snap.players} rowKey={(p) => p.guid} defaultSort={{ key: 'team', dir: 'asc' }} minWidth={1100} />
      </div>
    </div>
  );
}

/** Layer 3 — what each player knows: the beliefs the server grants a holder
 *  (a LOWER BOUND, per its own notes), one row per belief, and the gaps: every
 *  player without a state and why. */
function Beliefs({ snap }: { snap: SpiderWebSnapshot }) {
  // A team pov's holder is the synthetic `team:AXIS` union, not a guid: keep
  // its whole name; shorten only what is actually a guid.
  const nameOf = (guid: string | null) => (guid == null ? '—'
    : guid.startsWith('team:') ? `${guid.slice(5)} (team union)`
      : (snap.players.find((p) => p.guid === guid)?.name ?? guid.slice(0, 8)));
  const holders = Object.values(snap.information_state?.holders ?? {});
  type Row = SpiderBelief & { holder: string; id: string };
  const rows: Row[] = holders.flatMap((h) => h.beliefs.map((b, i) => ({ ...b, holder: nameOf(h.holder_guid), id: `${h.holder_guid}-${String(i)}` })));
  const columns: DataColumn<Row>[] = [
    { key: 'holder', label: 'who knows', width: 120, align: 'left', sortValue: (r) => r.holder },
    { key: 'kind', label: 'belief', format: (r) => r.kind.replace(/_/g, ' '), sortValue: (r) => r.kind },
    { key: 'subject', label: 'about', format: (r) => nameOf(r.subject_guid), sortValue: (r) => nameOf(r.subject_guid) },
    { key: 'roster_state', label: 'state', format: (r) => r.roster_state?.replace(/_/g, ' ') ?? <Meta>—</Meta>, sortValue: (r) => r.roster_state },
    { key: 'source', label: 'from', format: (r) => r.source?.replace(/_/g, ' ') ?? <Meta>—</Meta>, sortValue: (r) => r.source },
    { key: 't_observed', label: 'seen at', align: 'right', format: (r) => (r.t_observed == null ? <Meta>—</Meta> : mmss(r.t_observed / 1000)), sortValue: (r) => r.t_observed },
    { key: 'confidence', label: 'conf', align: 'right', title: '0–1, decays by the expiry basis', format: (r) => hundredths(r.confidence), sortValue: (r) => r.confidence },
    { key: 'counts_as_known', label: 'known', format: (r) => (r.counts_as_known ? 'yes' : <Meta>no</Meta>), sortValue: (r) => (r.counts_as_known ? 1 : 0) },
    { key: 'capability', label: 'capability', format: (r) => r.capability ?? <Meta>—</Meta>, sortValue: (r) => r.capability },
    { key: 'expiry_basis', label: 'expires by', format: (r) => r.expiry_basis?.replace(/_/g, ' ') ?? <Meta>—</Meta>, sortValue: (r) => r.expiry_basis },
    { key: 'region', label: 'region', title: 'centre (x, y, z) and radius in game units, when the belief is a region', format: (r) => (r.region ? `r ${figure(Math.round(r.region.radius))} at ${figure(Math.round(r.region.x))}, ${figure(Math.round(r.region.y))}, ${figure(Math.round(r.region.z))}` : <Meta>—</Meta>), sortValue: (r) => r.region?.radius ?? null },
  ];
  const gaps = Object.entries(snap.gaps ?? {});
  return (
    <div data-parity="spider-web.beliefs">
      <SectionHead
        label="what each player knows"
        aside={<span className="lbl">{snap.information_state?.pov ?? 'world'} pov · gunfire audible within {snap.information_state?.audible_gunfire_radius == null ? '—' : figure(snap.information_state.audible_gunfire_radius)}</span>}
      />
      <Stack gap={3} style={{ marginTop: 'var(--space-3)' }}>
        <Cluster gap={5} style={{ flexWrap: 'wrap' }}>
          {holders.map((h) => (
            <Stack key={h.holder_guid} gap={1} style={{ minWidth: 200 }}>
              <span style={{ fontSize: 'var(--fs-row)' }}>{nameOf(h.holder_guid)}</span>
              <Meta>
                knows of {figure(h.known_enemy_count)} {h.known_enemy_count === 1 ? 'enemy' : 'enemies'}
                {h.nearest_known_enemy_distance != null && <> · nearest known {span(h.nearest_known_enemy_distance)}</>}
                {h.nearest_heard_activity_distance != null && <> · heard within {span(h.nearest_heard_activity_distance)}</>}
                {h.position_claim_max_radius != null && <> · claims within {figure(Math.round(h.position_claim_max_radius))}</>}
              </Meta>
              {Object.entries(h.unavailable ?? {}).map(([channel, why]) => (
                <Meta key={channel}>{channel.replace(/_/g, ' ')} unavailable: {why}</Meta>
              ))}
            </Stack>
          ))}
        </Cluster>
        {rows.length === 0
          ? (snap.information_state?.pov_unavailable
            ? <Unavailable what={`beliefs — ${snap.information_state.pov_unavailable}`} />
            : holders.length === 0
              ? <Unavailable what="beliefs — no reconstructed state for this round (no tracks)" />
              : <Absent reason="no beliefs granted at this moment — nothing has been seen, heard or reported yet" />)
          : <DataTable<Row> parity="spider-web.beliefs.table" label="beliefs" columns={columns} rows={rows} rowKey={(r) => r.id} defaultSort={{ key: 'holder', dir: 'asc' }} minWidth={1000} />}
        {gaps.length > 0 && (
          <Stack gap={1}>
            <Lbl style={{ fontSize: 'var(--fs-caption)' }}>without a state</Lbl>
            {gaps.map(([guid, why]) => <Meta key={guid}>{nameOf(guid)}: {why}</Meta>)}
          </Stack>
        )}
        {Object.entries(snap.information_state?.unavailable ?? {}).map(([channel, why]) => (
          <Meta key={`u-${channel}`}>{channel.replace(/_/g, ' ')} unavailable for this pov: {why}</Meta>
        ))}
        {holders.flatMap((h) => h.notes ?? []).filter((n, i, a) => a.indexOf(n) === i).map((n) => <Meta key={n}>{n}</Meta>)}
      </Stack>
    </div>
  );
}

export function SpiderWebPage() {
  const params = useParams();
  const roundId = params.roundId != null && /^\d+$/.test(params.roundId) ? Number(params.roundId) : null;
  const [pov, setPov] = useState('world');
  const [tCommitted, setTCommitted] = useState(60000);
  const [tLive, setTLive] = useState(60000);
  const moment = useSpiderWebMoment(roundId, tCommitted, pov);
  const mesh = useMapMesh(moment.data?.map_name ?? null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const snap = moment.data;
  useEffect(() => {
    if (canvasRef.current && snap) drawMoment(canvasRef.current, snap, mesh.data ?? null);
  }, [snap, mesh.data]);

  const durationMs = snap?.round_duration_ms ?? 0;
  const clockTeams = useMemo(() => (snap ? Object.keys(snap.clock).sort() : []), [snap]);

  if (roundId == null) {
    return <Absent block reason="no round named — the spider web opens from a round's engagement panel" />;
  }
  if (moment.isPending && !snap) return <Pending label="spider web" />;
  if (moment.isError && !snap) {
    return moment.error instanceof ApiError && moment.error.status === 404
      ? <Absent block reason={`no reconstructable round has id ${roundId}`} />
      : <Unavailable what="spider web" />;
  }
  if (!snap) return <Unavailable what="spider web" />;

  return (
    <Stack gap={6} style={{ paddingTop: 'var(--space-7)' }}>
      <Stack gap={2}>
        <Lbl>proximity · spider web · layer 1</Lbl>
        <h1 style={{ fontSize: 'var(--fs-title)', letterSpacing: 'var(--track-title)', textTransform: 'uppercase', margin: 'var(--space-3) 0 0', fontWeight: 500 }}>
          {mapLabel(snap.map_name)} · round #{figure(snap.round_id)}
        </h1>
        <Meta>
          {figure(snap.player_count)} players placed · capture {snap.capture_policy.mode}
          {snap.capture_policy.observation_interval_ms != null && <> · sampled every {figure(snap.capture_policy.observation_interval_ms)} ms</>}
          {snap.overlap_conflicts > 0 && <> · {figure(snap.overlap_conflicts)} overlap conflicts</>}
          {' '}· first position {snap.first_position_ms == null ? 'unknown (no tracks)' : `at ${mmss(snap.first_position_ms / 1000)}`}
          {' '}· velocity window {snap.velocity_max_dt_ms == null ? 'unknown (no valid manifest)' : `${figure(snap.velocity_max_dt_ms)} ms`}
          {' '}· {figure(snap.capture_policy.manifest_count)} manifest{snap.capture_policy.manifest_count === 1 ? '' : 's'}{snap.capture_policy.manifest_version != null ? ` v${snap.capture_policy.manifest_version}` : ' (versions disagree)'}
        </Meta>
      </Stack>

      <div data-parity="spider-web.controls">
        <Cluster gap={4} align="center" style={{ flexWrap: 'wrap' }}>
          {POVS.map((p) => (
            <Chip key={p.key} active={pov === p.key} label={p.label} onClick={() => setPov(p.key)} />
          ))}
          <input
            type="range" min={0} max={Math.max(durationMs, 1)} step={1000} value={tLive}
            aria-label="moment"
            onChange={(e) => setTLive(Number(e.target.value))}
            onPointerUp={() => setTCommitted(tLive)}
            onKeyUp={() => setTCommitted(tLive)}
            style={{ flex: 1, minWidth: 200, accentColor: 'var(--color-accent)' }}
          />
          <span className="m" style={{ fontSize: 'var(--fs-caption)', minWidth: 52, textAlign: 'right' }}>
            {Math.floor(tLive / 60000)}:{String(Math.floor((tLive % 60000) / 1000)).padStart(2, '0')}
          </span>
        </Cluster>
        {pov !== 'world' && snap.withheld_by_pov.length > 0 && (
          <div style={{ marginTop: 'var(--space-2)' }}>
            <Absent reason={`${snap.withheld_by_pov.length} players withheld from this point of view — the server holds them back, the page never saw them`} />
          </div>
        )}
      </div>

      <div data-parity="spider-web.canvas">
        <canvas ref={canvasRef} width={860} height={560}
          style={{ width: '100%', maxWidth: 860, border: '1px solid var(--color-rule-900)', background: 'var(--color-ink-900, transparent)' }}
          aria-label="reconstructed moment" role="img" />
        {mesh.data === null && !mesh.isPending && (
          <Meta>this map's floor mesh was never exported — players and edges draw without a stage, which is the truth, not a bug</Meta>
        )}
      </div>

      <div data-parity="spider-web.clock">
        <SectionHead label="reinforcement clocks" />
        <Cluster gap={7} style={{ flexWrap: 'wrap', marginTop: 'var(--space-3)' }}>
          {clockTeams.map((team) => <ClockBadge key={team} team={team} clock={snap.clock[team]} />)}
        </Cluster>
      </div>

      <div data-parity="spider-web.capabilities">
        <SectionHead label="capture manifest" aside={<span className="lbl">{snap.capture_policy.source}</span>} />
        <Cluster gap={3} style={{ flexWrap: 'wrap', marginTop: 'var(--space-3)', maxWidth: 720 }}>
          {Object.entries(snap.capture_policy.capabilities).sort().map(([cap, state]) => (
            <span key={cap} className="lbl" style={{ fontSize: 'var(--fs-caption)', color: state === 'enabled' ? 'var(--color-text-100)' : 'var(--color-text-400)' }}>
              {cap.replace(/_/g, ' ')}: {state}
            </span>
          ))}
        </Cluster>
        {snap.capture_policy.conflicting_flags > 0 && (
          <Meta>{figure(snap.capture_policy.conflicting_flags)} conflicting manifest flags</Meta>
        )}
      </div>

      <PlacedPlayers snap={snap} />
      <Beliefs snap={snap} />
      <div data-parity="spider-web.accuracy">
        <SectionHead label="reconstruction accuracy" aside={<span className="lbl">measured {snap.reconstruction_accuracy.measured_at}</span>} />
        <Stack gap={1} style={{ marginTop: 'var(--space-3)' }}>
          <Meta>
            {figure(snap.reconstruction_accuracy.rounds)} rounds ·
            {Object.entries(snap.reconstruction_accuracy.samples).map(([k, v]) => ` ${figure(v)} ${k} samples`).join(' ·')}
            {' '}· unit: {snap.reconstruction_accuracy.unit}
          </Meta>
          <Meta>sources: {snap.reconstruction_accuracy.sources.join(', ')} · excluded: {snap.reconstruction_accuracy.excluded} · {snap.reconstruction_accuracy.script}</Meta>
        </Stack>
      </div>

      {snap.notes.length > 0 && (
        <Stack gap={1}>
          {snap.notes.map((n) => <Meta key={n}>{n}</Meta>)}
        </Stack>
      )}

      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
        slice 1 draws the moment top-down; the legacy page's 3D camera,
        belief regions and label placement are a named follow-up — and
        line-of-sight is not drawn anywhere, because it stays unvalidated
        until W6
      </Lbl>
    </Stack>
  );
}
