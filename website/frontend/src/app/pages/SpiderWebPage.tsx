/**
 * Phase 5 — the spider web (route spider-web, /spider-web/round/:roundId):
 * the layer-1 reconstruction at one moment under the legacy page's camera
 * (SW-2: axonometric, drag/zoom, floors by height, belief regions under a
 * team or player view, labels that drop rather than nudge), the layer-2
 * clocks and the layer-3 beliefs as tables. ⛔ The point of view is a
 * SERVER parameter — this page never fetches the world view and filters
 * locally (#800's contract), and WITHHELD branches before any clock-quality
 * switch. The moment and the view live in the URL, so a scene can be shared.
 */
import { useMemo, useRef, useState } from 'react';
import { useParams, useSearchParams } from 'react-router';
import { Cluster, Stack } from '../components/layout';
import { Absent, Chip, Lbl, Meta, Pending, SectionHead, Unavailable, figure } from '../components/ui';
import { ApiError } from '../lib/api';
import { stripEtColors } from '../lib/names';
import { mapLabel } from '../lib/maps';
import { useMapMesh, useSpiderWebMoment } from '../lib/queries';
import { SpiderWebScene } from '../components/SpiderWebScene';
import { isTeamPov } from '../lib/spiderWeb';
import { WEAPON_NAMES } from '../lib/weapons';
import { DataTable, type DataColumn } from '../components/DataTable';
import { mmss } from '../components/RoundsTable';
import type { SpiderBelief, SpiderClock, SpiderPlayer, SpiderWebSnapshot } from '../lib/types';
import { isClockOwnHud, isClockWithheld } from '../lib/types';

const POVS = [
  { key: 'world', label: 'world' },
  { key: 'team:AXIS', label: 'axis pov' },
  { key: 'team:ALLIES', label: 'allies pov' },
];

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
  const exposure: Record<string, number> = snap.line_of_sight?.exposure ?? {};
  const columns: DataColumn<SpiderPlayer>[] = [
    { key: 'name', label: 'player', width: 140, align: 'left', format: (p) => p.name ?? p.guid.slice(0, 8), sortValue: (p) => p.name ?? p.guid },
    { key: 'team', label: 'team', sortValue: (p) => p.team },
    { key: 'class', label: 'class', format: (p) => p.class ?? <Meta>—</Meta>, sortValue: (p) => p.class },
    { key: 'alive', label: 'state', format: (p) => (p.alive ? 'alive' : 'down'), sortValue: (p) => (p.alive ? 1 : 0) },
    { key: 'health', label: 'hp', align: 'right', sortValue: (p) => p.health },
    { key: 'stance', label: 'stance', format: (p) => (p.stance == null ? <Meta>—</Meta> : STANCE_WORD[p.stance] ?? `stance ${String(p.stance)}`), sortValue: (p) => p.stance },
    { key: 'speed', label: 'speed', align: 'right', title: 'game units per second', format: (p) => (p.speed == null ? <Meta>—</Meta> : figure(Math.round(p.speed))), sortValue: (p) => p.speed },
    { key: 'vx', label: 'vx', align: 'right', title: 'velocity along x, game units per second — derived from a causal same-life pair, null without one', format: (p) => (p.vx == null ? <Meta>—</Meta> : figure(Math.round(p.vx))), sortValue: (p) => p.vx },
    { key: 'vy', label: 'vy', align: 'right', title: 'velocity along y, game units per second', format: (p) => (p.vy == null ? <Meta>—</Meta> : figure(Math.round(p.vy))), sortValue: (p) => p.vy },
    { key: 'vz', label: 'vz', align: 'right', title: 'vertical velocity — null when no second sample within the window', format: (p) => (p.vz == null ? <Meta>—</Meta> : figure(Math.round(p.vz))), sortValue: (p) => p.vz },
    { key: 'weapon', label: 'weapon', title: 'the weapon held at the sample (engine weapon number, named where known)', format: (p) => (p.weapon == null ? <Meta>—</Meta> : (WEAPON_NAMES[Number(p.weapon)] ?? `#${String(p.weapon)}`)), sortValue: (p) => (p.weapon == null ? null : Number(p.weapon)) },
    { key: 'velocity_reason', label: 'velocity', title: 'why the velocity is what it is (the server names it)', format: (p) => p.velocity_reason ?? <Meta>—</Meta>, sortValue: (p) => p.velocity_reason },
    { key: 'velocity_stale_ms', label: 'v pair', align: 'right', title: 'ms between the two samples the velocity was derived from (the causal pair) — not the sample age, which is the stale column', format: (p) => (p.velocity_stale_ms == null ? <Meta>—</Meta> : figure(p.velocity_stale_ms)), sortValue: (p) => p.velocity_stale_ms },
    { key: 'stale_ms', label: 'stale', align: 'right', title: 'ms since the position sample', sortValue: (p) => p.stale_ms },
    { key: 'track_id', label: 'track', align: 'right', sortValue: (p) => p.track_id },
    { key: 'overlap_conflict', label: 'overlap', title: 'two tracks claimed this player at once', format: (p) => (p.overlap_conflict ? 'conflict' : <Meta>—</Meta>), sortValue: (p) => (p.overlap_conflict ? 1 : 0) },
    { key: 'nearest', label: 'nearest mate', align: 'right', title: 'geometric distance to the nearest teammate — not tactical support distance', format: (p) => (sep[p.guid] == null ? <Meta>—</Meta> : figure(Math.round(sep[p.guid]))), sortValue: (p) => sep[p.guid] ?? null },
    { key: 'exposed', label: 'exposed to', align: 'right', title: 'oracle diagnostic: living enemies with at least one clear ray to this player\'s body in the static geometry (W6-validated tracer) — necessary, not sufficient, for being seen; dash = not traced (a view, a down player, no geometry)', format: (p) => (exposure[p.guid] == null ? <Meta>—</Meta> : figure(exposure[p.guid])), sortValue: (p) => exposure[p.guid] ?? null },
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

/** `world` in any case is the oracle, `team:x` is a team (upper-cased to the
 *  server's spelling), anything else is a player guid as given. */
export function normalisePov(raw: string | null): string {
  const v = (raw ?? '').trim();
  if (v === '' || v.toLowerCase() === 'world') return 'world';
  if (v.toLowerCase().startsWith('team:')) return `team:${v.slice(5).toUpperCase()}`;
  return v;
}

/** The steps the nudge buttons move the moment by. */
const NUDGES: [string, number][] = [['−1 s', -1000], ['−200 ms', -200], ['+200 ms', 200], ['+1 s', 1000]];

export function SpiderWebPage() {
  const params = useParams();
  const roundId = params.roundId != null && /^\d+$/.test(params.roundId) ? Number(params.roundId) : null;
  // The moment and the point of view are URL state: `?t=<ms>&pov=<world|team:X|guid>`
  // — a scene worth discussing is a scene worth linking to.
  const [search, setSearch] = useSearchParams();
  const tFromUrl = Number(search.get('t'));
  // The server compares the pov case-insensitively and answers `?pov=World`
  // with the oracle; the page must see the same view it will draw.
  const pov = normalisePov(search.get('pov'));
  const tCommitted = Number.isFinite(tFromUrl) && search.get('t') != null && tFromUrl >= 0 ? Math.round(tFromUrl) : 60000;
  const [tLive, setTLive] = useState(tCommitted);
  const moment = useSpiderWebMoment(roundId, tCommitted, pov);
  const mesh = useMapMesh(moment.data?.map_name ?? null);

  const snap = moment.data;
  const durationMs = snap?.round_duration_ms ?? 0;
  const commit = (t: number, nextPov = pov) => {
    const clamped = Math.max(0, Math.min(durationMs || t, Math.round(t)));
    setTLive(clamped);
    setSearch((prev) => {
      const next = new URLSearchParams(prev);
      next.set('t', String(clamped));
      if (nextPov === 'world') next.delete('pov'); else next.set('pov', nextPov);
      return next;
    }, { replace: true });
  };
  const setPov = (p: string) => commit(tCommitted, p);
  const clockTeams = useMemo(() => (snap ? Object.keys(snap.clock).sort() : []), [snap]);
  // Names survive a switch to a team view, where the withheld side arrives
  // as bare guids: remembered from every snapshot this page has seen.
  const names = useRef(new Map<string, string>());
  if (snap) for (const p of snap.players) if (p.name) names.current.set(p.guid, stripEtColors(p.name));
  // Placed, withheld AND without a state (`gaps`): a player with no sample
  // at this moment is still a point of view — at t=0 that is everyone.
  const rosterGuids = snap ? [...new Set([...snap.players.map((p) => p.guid), ...snap.withheld_by_pov, ...Object.keys(snap.gaps ?? {})])] : [];

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
        <Lbl>proximity · spider web · layers 1–3</Lbl>
        <h1 style={{ fontSize: 'var(--fs-title)', letterSpacing: 'var(--track-title)', textTransform: 'uppercase', margin: 'var(--space-3) 0 0', fontWeight: 500 }}>
          {mapLabel(snap.map_name)} · round #{figure(snap.round_id)}{snap.teams.length > 0 ? ` · ${snap.teams.map((t) => t.toLowerCase()).join(' v ')}` : ''}
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
            onPointerUp={() => commit(tLive)}
            onKeyUp={() => commit(tLive)}
            style={{ flex: 1, minWidth: 200, accentColor: 'var(--color-accent)' }}
          />
          <span className="m" style={{ fontSize: 'var(--fs-caption)', minWidth: 52, textAlign: 'right' }}>
            {Math.floor(tLive / 60000)}:{String(Math.floor((tLive % 60000) / 1000)).padStart(2, '0')}
          </span>
          {NUDGES.map(([label, step]) => (
            <Chip key={label} active={false} label={label} onClick={() => commit(tCommitted + step)} title="move the moment and reload it" />
          ))}
        </Cluster>
        {/* One player's own picture: the server returns that holder's beliefs
          * alone (never the team union) and withholds the other side. */}
        <Cluster gap={2} align="center" style={{ flexWrap: 'wrap', marginTop: 'var(--space-2)' }}>
          <Lbl style={{ fontSize: 'var(--fs-caption)' }}>as seen by</Lbl>
          {rosterGuids.map((g) => (
            <Chip key={g} active={pov === g} label={names.current.get(g) ?? g.slice(0, 8)} onClick={() => setPov(g)} title="this player's own beliefs, and only their side's positions" />
          ))}
        </Cluster>
        <div style={{ marginTop: 'var(--space-2)' }}>
          {pov === 'world'
            ? <Meta>oracle: you see everything that happened, not what anyone knew — a diagnostic, not a player's view</Meta>
            : <Meta>{isTeamPov(pov) ? 'this side' : 'this player'} sees only what the server grants: an opponent is a region this view could infer, widening with time
              {snap?.information_state?.own_team_positions_are_a_simplification && <> · ⚠️ own-team positions are drawn as known — a simplification (the voice channel is not captured), not a measurement</>}
            </Meta>}
        </div>
        {pov !== 'world' && snap.withheld_by_pov.length > 0 && (
          <div style={{ marginTop: 'var(--space-2)' }}>
            <Absent reason={`${snap.withheld_by_pov.length} players withheld from this point of view — the server holds them back, the page never saw them`} />
          </div>
        )}
      </div>

      <div data-parity="spider-web.canvas">
        {/* null = the server said 404 (never exported, a named absence);
          * undefined = still loading OR the request failed — a failure is
          * said below as unavailable, not as "never exported". */}
        <SpiderWebScene snap={snap} mesh={mesh.isPending || mesh.isError ? undefined : mesh.data ?? null} pov={pov} />
        {mesh.isError && <Unavailable what="this map's floor mesh" />}
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
        the scene carries the legacy canvas whole — camera, belief regions,
        label placement — and line of sight as a labelled oracle overlay in
        the world view: a clear ray is an upper bound on what could have been
        seen (§6.1), never a belief; no metric consumes it
      </Lbl>
    </Stack>
  );
}
