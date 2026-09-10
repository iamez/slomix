/**
 * The spider web's drawing arithmetic, ported from the legacy canvas
 * (website/js/spider-web.js, PR #803) as pure functions so the SVG scene can
 * be tested without a browser: an axonometric camera, a screen-space fit,
 * the belief regions a point of view may draw, label placement that drops
 * rather than nudges, and the thread styles.
 *
 * ⛔ Nothing here ranks anyone (spec §4.6) and nothing here invents a
 * position: a label that does not fit is not drawn, a belief past the
 * published horizon is reported in words, an edge to an unplaced player is
 * skipped.
 */

export interface Camera { yaw: number; pitch: number; zoom: number; panX: number; panY: number }

export interface View {
  cx: number; cy: number; scale: number;
  midX: number; midY: number; midZ: number;
  minZ: number; maxZ: number;
}

export interface Bounds { min: number[]; max: number[] }

/** The legacy default: turned a little and tipped well away from the plan
 *  view, whose collapsed heights are exactly the levelshot's failure. */
export const DEFAULT_CAMERA: Camera = { yaw: 0.6, pitch: 0.9, zoom: 1, panX: 0, panY: 0 };
/** Straight down: heights collapse, distances on the floor are true. */
export const PLAN_CAMERA: Camera = { yaw: 0, pitch: 0, zoom: 1, panX: 0, panY: 0 };

/**
 * World (x, y, z) to screen, as an axonometric projection.
 *
 * Yaw turns the map about its vertical axis; pitch tips it towards the
 * viewer. ⚠️ Deliberately NOT perspective: a perspective camera makes two
 * players the same distance apart look different sizes depending on where
 * they stand, and this drawing is measured against a scale bar.
 */
export function project(x: number, y: number, z: number, cam: Camera, view: { cx: number; cy: number; scale: number }) {
  const cy = Math.cos(cam.yaw); const sy = Math.sin(cam.yaw);
  const rx = x * cy - y * sy;
  const ry = x * sy + y * cy;
  const cp = Math.cos(cam.pitch); const sp = Math.sin(cam.pitch);
  return {
    x: view.cx + rx * view.scale * cam.zoom + cam.panX,
    y: view.cy + (ry * cp - z * sp) * view.scale * cam.zoom + cam.panY,
    // Depth for the painter's algorithm: further from the viewer sorts first.
    depth: ry * sp + z * cp,
  };
}

/**
 * Screen scale and centre that fit the map into the canvas AT THIS ANGLE.
 *
 * ⚠️ Fitted in SCREEN space, not world space: the projection squashes one
 * axis by cos(pitch) and shears height into it, so a scale from the world
 * extent always under-fills (measured on supply: a third of the canvas).
 * Projecting the eight corners of the bounding box and fitting THAT is the
 * arithmetic the renderer is about to do anyway, and it re-fits as the
 * camera turns.
 */
export function viewportFor(mesh: { bounds: Bounds }, canvas: { width: number; height: number }, cam: Camera): View {
  const b = mesh.bounds;
  const mid = {
    midX: (b.min[0] + b.max[0]) / 2,
    midY: (b.min[1] + b.max[1]) / 2,
    midZ: (b.min[2] + b.max[2]) / 2,
    minZ: b.min[2],
    maxZ: b.max[2],
  };
  const unit = { cx: 0, cy: 0, scale: 1 };
  const flat: Camera = { ...cam, zoom: 1, panX: 0, panY: 0 };
  let lo = { x: Infinity, y: Infinity }; let hi = { x: -Infinity, y: -Infinity };
  for (const cx of [b.min[0], b.max[0]]) {
    for (const cy of [b.min[1], b.max[1]]) {
      for (const cz of [b.min[2], b.max[2]]) {
        const p = project(cx - mid.midX, cy - mid.midY, cz - mid.midZ, flat, unit);
        lo = { x: Math.min(lo.x, p.x), y: Math.min(lo.y, p.y) };
        hi = { x: Math.max(hi.x, p.x), y: Math.max(hi.y, p.y) };
      }
    }
  }
  const pad = 0.92;
  const scale = Math.min(
    (canvas.width * pad) / Math.max(1e-6, hi.x - lo.x),
    (canvas.height * pad) / Math.max(1e-6, hi.y - lo.y),
  );
  // ⚠️ The recentring term is provably zero for a bounding box (the eight
  // corners are symmetric about the centre, `project` is linear) and kept
  // anyway: it is what keeps this correct if the corner set ever stops being
  // a box. Measured over 20,000 random maps and angles: |lo + hi| / span
  // never exceeded 1.9e-15. No test can catch its removal, so it is labelled.
  return {
    cx: canvas.width / 2 - ((lo.x + hi.x) / 2) * scale,
    cy: canvas.height / 2 - ((lo.y + hi.y) / 2) * scale,
    scale,
    ...mid,
  };
}

/**
 * Bounds taken from the players themselves, for a map with no exported
 * floors. ⛔ Twelve of the twenty maps in the corpus ship no geometry; without
 * this the page drew NOTHING on them — not the floors it does not have, and
 * not the players it does. Null when nobody can be placed, rather than a
 * point at the origin: a zero span would scale the canvas onto one pixel.
 */
export function boundsFromPlayers(players: ReadonlyArray<{ x?: number | null; y?: number | null; z?: number | null }> | null | undefined, margin = 512): Bounds | null {
  const placed = (players ?? []).filter((p) => p != null && p.x != null && p.y != null && p.z != null) as { x: number; y: number; z: number }[];
  if (placed.length === 0) return null;
  const xs = placed.map((p) => p.x); const ys = placed.map((p) => p.y); const zs = placed.map((p) => p.z);
  return {
    min: [Math.min(...xs) - margin, Math.min(...ys) - margin, Math.min(...zs) - margin],
    max: [Math.max(...xs) + margin, Math.max(...ys) + margin, Math.max(...zs) + margin],
  };
}

export interface Label { x: number; y: number; text: string }

/**
 * Which labels get drawn when several land on top of each other.
 *
 * ⛔ Drops, never nudges. At a spawn eight players stand within a few units
 * of one another; moving their names apart would put a name beside a
 * position nobody occupied. The disc still shows the player.
 */
export function placeLabels<T extends Label>(labels: T[], minX = 70, minY = 13): T[] {
  const placed: T[] = [];
  for (const l of labels) {
    if (placed.some((q) => Math.abs(q.x - l.x) < minX && Math.abs(q.y - l.y) < minY)) continue;
    placed.push(l);
  }
  return placed;
}

export interface BeliefLike {
  subject_guid?: string | null;
  region?: { x: number; y: number; z: number; radius: number } | null;
  confidence?: number;
  source?: string | null;
}
export interface HolderLike { beliefs?: BeliefLike[]; position_claim_max_radius?: number | null }

export interface DrawableRegion {
  x: number; y: number; z: number; radius: number; confidence: number;
  subject: string; source: string | null;
}

/** The published horizon, or Infinity when a view does not carry one. */
export function horizonOf(holder: HolderLike | null | undefined): number {
  return holder != null && typeof holder.position_claim_max_radius === 'number' ? holder.position_claim_max_radius : Infinity;
}

/**
 * The enemy regions a point of view is entitled to draw.
 *
 * ⭐ Under a team view an enemy is NOT a dot. The holder never knew a point —
 * they knew a place, from a contact or a crosshair or a noise, and that
 * place has been widening ever since. The region is drawn at the size the
 * server grew it to, and its opacity is the belief's confidence.
 *
 * ⛔ Only beliefs that name a subject AND carry a region. A gunfire belief
 * names nobody (§6.3, the phantom squad) and a roster belief has no place;
 * drawing either as an enemy position would invent one. ⛔ Past the
 * published horizon a region is not drawn either — a 2,500-unit circle on a
 * 4,600-unit map is not "he is somewhere here", it is the whole map. Those
 * subjects stay KNOWN: they are returned as `unplacedSubjects`, in words.
 */
export function beliefRegions(holder: HolderLike | null | undefined): { regions: DrawableRegion[]; unplacedSubjects: string[] } {
  if (holder == null || !Array.isArray(holder.beliefs)) return { regions: [], unplacedSubjects: [] };
  const horizon = horizonOf(holder);
  const drawable: DrawableRegion[] = [];
  const unplaced = new Set<string>();
  for (const b of holder.beliefs) {
    if (b == null || !b.subject_guid) continue;
    if (!b.region) continue;
    if (b.region.radius > horizon) { unplaced.add(b.subject_guid); continue; }
    drawable.push({
      x: b.region.x, y: b.region.y, z: b.region.z, radius: b.region.radius,
      confidence: typeof b.confidence === 'number' ? b.confidence : 0,
      subject: b.subject_guid, source: b.source ?? null,
    });
  }
  // A subject with one fresh region and one stale one is placed, not unplaced.
  for (const d of drawable) unplaced.delete(d.subject);
  return { regions: drawable, unplacedSubjects: [...unplaced] };
}

/** Whether this view is one team's picture rather than the oracle's. */
export function isTeamPov(pov: unknown): boolean {
  return typeof pov === 'string' && pov.toLowerCase().startsWith('team:');
}

/** A player's own picture: a guid, not `world` and not a team. */
export function isPlayerPov(pov: unknown): boolean {
  return typeof pov === 'string' && pov !== '' && pov.toLowerCase() !== 'world' && !isTeamPov(pov);
}

export interface EdgeStyle { color: string; alpha: number; width: number; dash: number[] }

/**
 * How a thread is drawn. Contested is emphasis, not an alarm: the tracker
 * holds an engagement open for up to 15 s after the last hit. Never fully
 * opaque — the floors and the uncertainty discs stay readable underneath.
 * Colours are theme tokens, so the scene follows the page's palette.
 */
export function edgeStyle(kind: string, contested: boolean): EdgeStyle {
  // Opponent threads carry the negative token; teammate threads stay neutral
  // so they never compete with the team colour of the dots they join.
  const color = kind === 'opponent' ? 'var(--color-neg)' : 'var(--color-text-400)';
  return contested
    ? { color, alpha: 0.75, width: 1.8, dash: [] }
    : { color, alpha: 0.28, width: 0.8, dash: [3, 4] };
}

/** One line under the scene: how much of the moment could be placed. */
export function statusLine(snapshot: { players?: { x?: number | null; stale_ms?: number | null }[]; overlap_conflicts?: number; gaps?: Record<string, string> } | null | undefined): string {
  if (!snapshot) return '';
  const players = snapshot.players ?? [];
  const positioned = players.filter((p) => p.x != null).length;
  const stale = players.reduce((m, p) => Math.max(m, p.stale_ms ?? 0), 0);
  const gaps = Object.keys(snapshot.gaps ?? {}).length;
  return `${positioned}/${players.length} placed · ${snapshot.overlap_conflicts ?? 0} overlap conflicts · oldest sample ${stale} ms`
    + (gaps ? ` · ${gaps} without a state` : '');
}

/**
 * The floor mesh as a few height bands, each one SVG path — 9,000 triangles
 * as separate elements would be the slow part of every camera move, and a
 * band per 1/8 of the height range is the same ramp the legacy canvas drew
 * per triangle. Triangles are sorted by depth inside a band so the painter
 * still holds where bands overlap.
 */
export function floorBands(mesh: { vertices: number[]; indexes: number[] }, cam: Camera, view: View, bands = 8): { d: string; t: number }[] {
  const { vertices, indexes } = mesh;
  const zSpan = Math.max(1, view.maxZ - view.minZ);
  const perBand: { d: string[]; depth: number }[][] = Array.from({ length: bands }, () => []);
  for (let i = 0; i + 2 < indexes.length; i += 3) {
    const pts: string[] = [];
    let depth = 0; let zSum = 0;
    for (let k = 0; k < 3; k++) {
      const v = indexes[i + k] * 3;
      const p = project(vertices[v] - view.midX, vertices[v + 1] - view.midY, vertices[v + 2] - view.midZ, cam, view);
      pts.push(`${p.x.toFixed(1)} ${p.y.toFixed(1)}`);
      depth += p.depth; zSum += vertices[v + 2];
    }
    const t = (zSum / 3 - view.minZ) / zSpan;
    const band = Math.min(bands - 1, Math.max(0, Math.floor(t * bands)));
    perBand[band].push({ d: pts, depth });
  }
  return perBand.map((tris, b) => ({
    t: (b + 0.5) / bands,
    d: tris.sort((p, q) => p.depth - q.depth).map((tri) => `M${tri.d[0]}L${tri.d[1]}L${tri.d[2]}Z`).join(''),
  })).filter((band) => band.d !== '');
}
