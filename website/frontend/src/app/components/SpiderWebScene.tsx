/**
 * The spider web's scene: one reconstructed moment drawn as SVG under an
 * axonometric camera (drag turns, shift-drag pans, the wheel zooms), the
 * legacy canvas's picture carried over — floors by height band, the
 * measured position-error ring per player, threads between players, and
 * under a team or player point of view the enemy regions that view was
 * entitled to draw. SVG rather than canvas so every mark takes its colour
 * from the theme tokens and a test can count the dots.
 *
 * ⛔ Draws only what the server handed over. A belief past the published
 * horizon is named in words, a label that does not fit is dropped, and an
 * edge to an unplaced player is skipped (lib/spiderWeb.ts).
 */
import { useCallback, useMemo, useRef, useState } from 'react';
import type { MapMesh, SpiderWebSnapshot } from '../lib/types';
import { stripEtColors } from '../lib/names';
import {
  DEFAULT_CAMERA, beliefRegions, boundsFromPlayers, edgeStyle, floorBands, isPlayerPov,
  isTeamPov, placeLabels, project, statusLine, viewportFor, type Camera,
} from '../lib/spiderWeb';
import { Cluster, Stack } from './layout';
import { Absent, Chip, Meta, figure } from './ui';

const W = 860; const H = 560;
// The sides' own tokens (tokens.css: --color-axis red, --color-allies blue),
// the identity the legacy canvas carried — not the accent pair.
const TEAM_COLOR: Record<string, string> = { AXIS: 'var(--color-axis)', ALLIES: 'var(--color-allies)' };
const STANCE: Record<number, string> = { 0: 'standing', 1: 'crouching', 2: 'prone' };
/** The scale bar's length in game units — a player is about 40 wide. */
const SCALE_UNITS = 512;

function clampPitch(v: number) { return Math.min(1.5, Math.max(0, v)); }

/** `mesh` is undefined while the geometry is still loading, null when the
 *  map was never exported (a named absence), and the mesh otherwise. */
export function SpiderWebScene({ snap, mesh, pov }: { snap: SpiderWebSnapshot; mesh: MapMesh | null | undefined; pov: string }) {
  const [cam, setCam] = useState<Camera>(DEFAULT_CAMERA);
  const drag = useRef<{ x: number; y: number; pan: boolean } | null>(null);

  // The wheel must not scroll the page while it zooms the scene, and React's
  // onWheel is passive — so the listener is attached by hand, through a
  // callback ref: the svg may appear only after a first render without
  // bounds (a `?t=0` link while the geometry loads), and an effect with an
  // empty dependency list would never see it (Codex on #1005).
  const wheelCleanup = useRef<(() => void) | null>(null);
  const svgRef = useCallback((el: SVGSVGElement | null) => {
    wheelCleanup.current?.();
    wheelCleanup.current = null;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      setCam((c) => ({ ...c, zoom: Math.min(6, Math.max(0.4, c.zoom * (e.deltaY < 0 ? 1.15 : 1 / 1.15))) }));
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    wheelCleanup.current = () => el.removeEventListener('wheel', onWheel);
  }, []);

  const bounds = mesh?.bounds ?? boundsFromPlayers(snap.players);
  const scene = useMemo(() => {
    if (!bounds) return null;
    const view = viewportFor({ bounds }, { width: W, height: H }, cam);
    const P = (x: number, y: number, z: number) => project(x - view.midX, y - view.midY, z - view.midZ, cam, view);
    const floors = mesh && mesh.vertices.length > 0 ? floorBands(mesh, cam, view) : [];
    const at = new Map(snap.players.map((p) => [p.guid, P(p.x, p.y, p.z)]));
    const edges = [...snap.edges]
      .sort((a, b) => Number(a.recently_contested) - Number(b.recently_contested))
      .flatMap((e) => {
        const a = at.get(e.a); const b = at.get(e.b);
        // ⛔ Both ends or nothing: a thread to an unplaced player would be a line to a position nobody occupied.
        return a && b ? [{ e, a, b, style: edgeStyle(e.kind, e.recently_contested) }] : [];
      });
    const players = snap.players.map((p) => ({ p, s: at.get(p.guid)! })).sort((a, b) => a.s.depth - b.s.depth);
    const labels = placeLabels(players.map(({ p, s }) => ({ x: s.x + 8, y: s.y + 3, text: p.name ? stripEtColors(p.name) : p.guid.slice(0, 8) })));
    // Enemy beliefs are drawn only for a view that has them: the world view is
    // the oracle and already shows every true position.
    const holder = isTeamPov(pov) || isPlayerPov(pov) ? Object.values(snap.information_state?.holders ?? {})[0] : undefined;
    const beliefs = beliefRegions(holder);
    const regions = beliefs.regions.map((r) => ({ r, s: P(r.x, r.y, r.z), px: Math.max(3, r.radius * view.scale * cam.zoom) }));
    return { view, floors, edges, players, labels, regions, unplaced: beliefs.unplacedSubjects, scalePx: SCALE_UNITS * view.scale * cam.zoom };
  }, [bounds, cam, mesh, snap, pov]);

  if (!scene) return <Absent reason="nobody could be placed at this moment — no floor mesh and no positioned player to frame the scene" />;

  const nameOf = (guid: string) => { const p = snap.players.find((q) => q.guid === guid); return p?.name ? stripEtColors(p.name) : guid.slice(0, 8); };
  const isPlan = cam.pitch === 0;

  return (
    <Stack gap={2}>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label="reconstructed moment"
        data-camera-yaw={cam.yaw.toFixed(3)}
        data-camera-pitch={cam.pitch.toFixed(3)}
        style={{ width: '100%', maxWidth: W, border: '1px solid var(--color-rule-900)', background: 'var(--color-ink-900, transparent)', touchAction: 'none', cursor: drag.current ? 'grabbing' : 'grab' }}
        onPointerDown={(e) => { drag.current = { x: e.clientX, y: e.clientY, pan: e.shiftKey }; (e.currentTarget as Element).setPointerCapture?.(e.pointerId); }}
        onPointerMove={(e) => {
          const d = drag.current; if (!d) return;
          const dx = e.clientX - d.x; const dy = e.clientY - d.y; drag.current = { ...d, x: e.clientX, y: e.clientY };
          setCam((c) => (d.pan
            ? { ...c, panX: c.panX + dx, panY: c.panY + dy }
            : { ...c, yaw: c.yaw + dx * 0.008, pitch: clampPitch(c.pitch + dy * 0.008) }));
        }}
        onPointerUp={() => { drag.current = null; }}
        onPointerLeave={() => { drag.current = null; }}
      >
        {scene.floors.map((band) => (
          <path key={band.t} d={band.d} fill="var(--color-text-500)" fillOpacity={0.03 + band.t * 0.12} stroke="none" />
        ))}
        {/* Enemy beliefs beneath everything else: the least certain thing on the scene must not sit on top of what is known. */}
        {scene.regions.map(({ r, s, px }, i) => (
          <circle
            key={`${r.subject}-${String(i)}`} cx={s.x} cy={s.y} r={px}
            data-belief-subject={r.subject}
            fill="var(--color-neg)" fillOpacity={Math.max(0.08, Math.min(0.5, r.confidence)) * 0.25}
            stroke="var(--color-neg)" strokeOpacity={Math.max(0.08, Math.min(0.5, r.confidence))} strokeDasharray="5 4"
          >
            <title>{`${nameOf(r.subject)} · believed within ${figure(Math.round(r.radius))} units from ${(r.source ?? 'a cue').replace(/_/g, ' ')} · confidence ${r.confidence.toFixed(2)}`}</title>
          </circle>
        ))}
        {scene.edges.map(({ e, a, b, style }) => (
          <line
            key={`${e.a}-${e.b}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
            data-edge-kind={e.kind} data-contested={e.recently_contested ? 'yes' : 'no'}
            stroke={style.color} strokeOpacity={style.alpha} strokeWidth={style.width}
            strokeDasharray={style.dash.length > 0 ? style.dash.join(' ') : undefined}
          >
            <title>{`${nameOf(e.a)} – ${nameOf(e.b)} · ${e.kind} · ${figure(Math.round(e.distance))} units${e.recently_contested ? ' · engagement open' : ''}`}</title>
          </line>
        ))}
        {scene.players.map(({ p, s }) => {
          const color = TEAM_COLOR[p.team] ?? 'var(--color-text-400)';
          const p90 = p.alive && p.position_error ? p.position_error.p90 : 0;
          return (
            <g key={p.guid} data-player={p.guid} data-alive={p.alive ? 'yes' : 'no'}>
              {/* ⭐ The measured error, at map scale: a contested player is a wide faint disc, a fresh one nearly a point. */}
              {p90 > 0 && (
                <circle cx={s.x} cy={s.y} r={Math.max(2, p90 * scene.view.scale * cam.zoom)} data-error-ring="p90"
                  fill={color} fillOpacity={0.1} stroke={color} strokeOpacity={0.33} strokeDasharray={p.overlap_conflict ? '4 3' : undefined} />
              )}
              {/* A dead player is a ring, not a disc: absence, not a fourth team. */}
              <circle cx={s.x} cy={s.y} r={4} fill={p.alive ? color : 'transparent'} stroke={color} strokeWidth={1.5} />
              <title>{`${p.name ? stripEtColors(p.name) : p.guid.slice(0, 8)} · ${p.team.toLowerCase()} · ${p.alive ? `${figure(p.health)} hp` : 'down'}${p.stance != null ? ` · ${STANCE[p.stance] ?? ''}` : ''} · sample ${figure(p.stale_ms)} ms old`}</title>
            </g>
          );
        })}
        {scene.labels.map((l) => (
          <text key={l.text + String(l.x)} x={l.x} y={l.y} fill="var(--color-text-100)" fontSize={11} fontFamily="ui-monospace, monospace">{l.text}</text>
        ))}
        {/* The scale bar the axonometric camera is chosen for: distances stay comparable across the scene. */}
        <g data-scale-bar={SCALE_UNITS}>
          <line x1={16} y1={H - 16} x2={16 + scene.scalePx} y2={H - 16} stroke="var(--color-text-400)" strokeWidth={1} />
          <text x={16} y={H - 22} fill="var(--color-text-400)" fontSize={10} fontFamily="ui-monospace, monospace">{figure(SCALE_UNITS)} units</text>
        </g>
      </svg>
      <Cluster gap={3} align="center" style={{ flexWrap: 'wrap' }}>
        <Chip active={!isPlan} label="tilted" onClick={() => setCam((c) => ({ ...c, pitch: DEFAULT_CAMERA.pitch }))} title="the default camera: turned a little and tipped, so heights read" />
        <Chip active={isPlan} label="plan" onClick={() => setCam((c) => ({ ...c, pitch: 0 }))} title="straight down: heights collapse, floor distances are true" />
        <Chip active={false} label="reset view" onClick={() => setCam(DEFAULT_CAMERA)} />
        <Meta>drag turns · shift-drag pans · wheel zooms · zoom {cam.zoom.toFixed(2)}×{isPlan ? '' : ` · pitch ${cam.pitch.toFixed(2)}`}</Meta>
      </Cluster>
      <Meta>{statusLine(snap)}</Meta>
      {scene.unplaced.length > 0 && (
        <Meta>known but not placed (region wider than the published horizon): {scene.unplaced.map(nameOf).join(', ')} — this side knows they exist, not where they are</Meta>
      )}
      {/* "Knew of nobody" is a measured empty result; a view the server could
        * not resolve (pov_unavailable set) is not measured at all, and the
        * beliefs panel below says so — this line must not speak for it. */}
      {(isTeamPov(pov) || isPlayerPov(pov)) && !snap.information_state?.pov_unavailable && scene.regions.length === 0 && scene.unplaced.length === 0 && (
        <Meta>at this moment this view knew of no enemy position — nothing has been seen, hit or heard closely enough to place anyone</Meta>
      )}
      <Meta>
        ring = measured position uncertainty (p90 for the sample's age), dashed when two tracks claimed the player · hollow dot = down ·
        threads are geometric distance, not sight: grey between teammates, negative between opponents, solid where an engagement was open
        (the tracker holds one open up to 15 s after the last hit) · dashed discs = where this side believed an enemy was, opacity = confidence
      </Meta>
      {mesh === null && <Meta>this map's floor mesh was never exported — players and threads draw without a stage, which is the truth, not a bug</Meta>}
    </Stack>
  );
}
