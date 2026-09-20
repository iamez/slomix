/**
 * The live mini map — the roster's last positions and the recent kills that
 * /api/live/state carries since R6 (2026-09-08), drawn as SVG over the map's
 * floor mesh when one was exported (the same /assets/maps/geometry files the
 * spider web uses; a map without one draws players on a bare stage, which is
 * the truth). Axis in the accent colour, Allies in the warm accent, a dead
 * player as a ring; a kill is a line from the killer to an × at the victim.
 * Everything is a token or a number the page derives from the data.
 */
import { Meta } from './ui';
import { svgPath } from '../lib/spark';
import { stripEtColors } from '../lib/names';
import type { LiveRosterMember, LiveState, MapMesh } from '../lib/types';

const W = 640; const H = 400; const PAD = 16; const MARGIN = 512; const MAX_TRIANGLES = 6000;

type Placed = { member: LiveRosterMember; side: 'axis' | 'allies'; x: number; y: number };

export function LiveMiniMap({ state, mesh }: { state: LiveState; mesh: MapMesh | null | undefined }) {
  const placed: Placed[] = [
    ...state.roster.axis.filter((m) => m.pos).map((m) => ({ member: m, side: 'axis' as const, x: m.pos!.x, y: m.pos!.y })),
    ...state.roster.allies.filter((m) => m.pos).map((m) => ({ member: m, side: 'allies' as const, x: m.pos!.x, y: m.pos!.y })),
  ];
  const kills = (state.recent_kills ?? []).filter((k) => k.victim_pos);
  const xs = [...placed.map((p) => p.x), ...kills.flatMap((k) => [k.victim_pos!.x, ...(k.killer_pos ? [k.killer_pos.x] : [])])];
  const ys = [...placed.map((p) => p.y), ...kills.flatMap((k) => [k.victim_pos!.y, ...(k.killer_pos ? [k.killer_pos.y] : [])])];
  if (xs.length === 0) return null;
  const minX = Math.min(...xs) - MARGIN; const maxX = Math.max(...xs) + MARGIN;
  const minY = Math.min(...ys) - MARGIN; const maxY = Math.max(...ys) + MARGIN;
  const scale = Math.min((W - 2 * PAD) / Math.max(1, maxX - minX), (H - 2 * PAD) / Math.max(1, maxY - minY));
  const px = (x: number) => PAD + (x - minX) * scale;
  const py = (y: number) => H - PAD - (y - minY) * scale;

  // The floor: only the triangles inside the view, and only up to a budget —
  // a 40k-triangle map would make the SVG heavier than the page.
  const tris: string[] = [];
  if (mesh) {
    const { vertices, indexes } = mesh;
    for (let i = 0; i + 2 < indexes.length && tris.length < MAX_TRIANGLES; i += 3) {
      const a = indexes[i] * 3; const b = indexes[i + 1] * 3; const c = indexes[i + 2] * 3;
      const ax = vertices[a]; const ay = vertices[a + 1]; const bx = vertices[b]; const by = vertices[b + 1]; const cx = vertices[c]; const cy = vertices[c + 1];
      if ((ax < minX && bx < minX && cx < minX) || (ax > maxX && bx > maxX && cx > maxX)
        || (ay < minY && by < minY && cy < minY) || (ay > maxY && by > maxY && cy > maxY)) continue;
      tris.push(`${svgPath([{ x: px(ax), y: py(ay) }, { x: px(bx), y: py(by) }, { x: px(cx), y: py(cy) }])} Z`);
    }
  }
  const colour = (side: 'axis' | 'allies') => (side === 'axis' ? 'var(--color-accent)' : 'var(--color-accent-warm)');
  return (
    <div data-parity="live.minimap">
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', maxWidth: W, border: '1px solid var(--color-rule-900)' }} role="img"
        aria-label={`${figureCount(placed.length)} placed, ${figureCount(kills.length)} recent kills`}>
        {tris.length > 0 && <path d={tris.join(' ')} fill="var(--color-text-500)" fillOpacity="0.06" stroke="none" />}
        {kills.map((k, i) => (
          <g key={`${String(k.age_seconds)}-${String(i)}`} opacity={Math.max(0.25, 1 - k.age_seconds / 20)}>
            {k.killer_pos && (
              <line x1={px(k.killer_pos.x)} y1={py(k.killer_pos.y)} x2={px(k.victim_pos!.x)} y2={py(k.victim_pos!.y)} stroke="var(--color-neg)" strokeWidth="1" strokeDasharray="2 3" />
            )}
            <text x={px(k.victim_pos!.x)} y={py(k.victim_pos!.y) + 4} textAnchor="middle" style={{ fill: 'var(--color-neg)', fontSize: 'var(--fs-small)' }}>×</text>
          </g>
        ))}
        {placed.map((p) => (
          <g key={p.member.slot}>
            {p.member.pos!.yaw != null && (
              <line x1={px(p.x)} y1={py(p.y)} x2={px(p.x) + 10 * Math.cos((p.member.pos!.yaw * Math.PI) / 180)} y2={py(p.y) - 10 * Math.sin((p.member.pos!.yaw * Math.PI) / 180)} stroke={colour(p.side)} strokeWidth="1.2" />
            )}
            <circle cx={px(p.x)} cy={py(p.y)} r={p.member.live?.alive === false ? 3.5 : 5}
              fill={p.member.live?.alive === false ? 'none' : colour(p.side)} stroke={colour(p.side)} strokeWidth="1.2" />
            <text x={px(p.x) + 8} y={py(p.y) - 6} style={{ fill: 'var(--color-text-100)', fontSize: 'var(--fs-caption)' }}>{stripEtColors(p.member.name)}</text>
          </g>
        ))}
      </svg>
      <Meta>positions under a minute old · kills of the last 20 s · {mesh ? 'floor from the exported mesh' : 'no floor mesh exported for this map'}</Meta>
    </div>
  );
}

function figureCount(n: number): string {
  return n.toLocaleString('en-US');
}
