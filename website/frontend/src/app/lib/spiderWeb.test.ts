/**
 * The legacy canvas's own tests (src/legacy/spider-web.test.ts), carried to
 * the ported module: the projection's signs, the screen-space fit, label
 * dropping, the belief horizon, the thread styles.
 */
import { describe, expect, it } from 'vitest';
import {
  beliefRegions, boundsFromPlayers, edgeStyle, floorBands, horizonOf, isPlayerPov, isTeamPov,
  placeLabels, project, statusLine, viewportFor, type Camera,
} from './spiderWeb';

const VIEW = { cx: 500, cy: 300, scale: 0.1, midX: 0, midY: 0, midZ: 0, minZ: 0, maxZ: 1 };
const CAM: Camera = { yaw: 0.6, pitch: 0.9, zoom: 1, panX: 0, panY: 0 };
const distance = (a: { x: number; y: number }, b: { x: number; y: number }) => Math.hypot(a.x - b.x, a.y - b.y);

describe('project', () => {
  it('puts the centre of the map at the centre of the canvas', () => {
    const p = project(0, 0, 0, CAM, VIEW);
    expect(p.x).toBeCloseTo(VIEW.cx, 6);
    expect(p.y).toBeCloseTo(VIEW.cy, 6);
  });

  it('draws greater height HIGHER on the screen', () => {
    // ⛔ The sign a screenshot cannot check: screen y grows downward, so a
    // naive projection puts a roof below its foundation and still looks
    // like a plausible map.
    expect(project(100, 100, 500, CAM, VIEW).y).toBeLessThan(project(100, 100, 0, CAM, VIEW).y);
  });

  it('turning the camera is a rotation, so it preserves distances', () => {
    const a = { x: 400, y: -250, z: 0 }; const b = { x: -100, y: 320, z: 0 };
    const flat = { ...CAM, pitch: 0 };
    const before = distance(project(a.x, a.y, a.z, flat, VIEW), project(b.x, b.y, b.z, flat, VIEW));
    for (const yaw of [0, 0.4, 1.1, 2.7, -1.9]) {
      const turned = { ...flat, yaw };
      expect(distance(project(a.x, a.y, a.z, turned, VIEW), project(b.x, b.y, b.z, turned, VIEW))).toBeCloseTo(before, 6);
    }
  });

  it('sorts nearer things later, which is what the painter relies on', () => {
    expect(project(0, 800, 0, CAM, VIEW).depth).toBeGreaterThan(project(0, -800, 0, CAM, VIEW).depth);
  });

  it('zoom scales distance from the centre, and pan does not', () => {
    const one = project(300, 300, 0, CAM, VIEW);
    const two = project(300, 300, 0, { ...CAM, zoom: 2 }, VIEW);
    expect(distance(two, { x: VIEW.cx, y: VIEW.cy })).toBeCloseTo(2 * distance(one, { x: VIEW.cx, y: VIEW.cy }), 6);
    const panned = project(300, 300, 0, { ...CAM, panX: 40, panY: -25 }, VIEW);
    expect(panned.x - one.x).toBeCloseTo(40, 6);
    expect(panned.y - one.y).toBeCloseTo(-25, 6);
  });
});

describe('viewportFor', () => {
  const mesh = { bounds: { min: [-2000, -1500, -300], max: [2600, 1900, 700] } };
  const canvas = { width: 1200, height: 640 };
  function corners(cam: Camera) {
    const view = viewportFor(mesh, canvas, cam);
    const pts = [];
    for (const x of [mesh.bounds.min[0], mesh.bounds.max[0]]) for (const y of [mesh.bounds.min[1], mesh.bounds.max[1]]) for (const z of [mesh.bounds.min[2], mesh.bounds.max[2]]) {
      pts.push(project(x - view.midX, y - view.midY, z - view.midZ, cam, view));
    }
    return pts;
  }

  it.each([[0, 0.15], [0.6, 0.9], [1.7, 1.45], [-2.4, 0.5], [3.1, 1.2]])('fits the whole map on the canvas at yaw %s pitch %s', (yaw, pitch) => {
    // ⭐ The bug this replaces: fitting on the WORLD extent ignores the
    // pitch squash and the height shear, so supply covered a third of the
    // canvas. Checked at several angles — a fit that only holds at the
    // default is not a fit.
    for (const p of corners({ yaw, pitch, zoom: 1, panX: 0, panY: 0 })) {
      expect(p.x).toBeGreaterThanOrEqual(-1); expect(p.x).toBeLessThanOrEqual(canvas.width + 1);
      expect(p.y).toBeGreaterThanOrEqual(-1); expect(p.y).toBeLessThanOrEqual(canvas.height + 1);
    }
  });

  it('uses the canvas, rather than leaving most of it empty', () => {
    const pts = corners(CAM);
    const w = Math.max(...pts.map((p) => p.x)) - Math.min(...pts.map((p) => p.x));
    const h = Math.max(...pts.map((p) => p.y)) - Math.min(...pts.map((p) => p.y));
    expect(Math.max(w / canvas.width, h / canvas.height)).toBeGreaterThan(0.85);
  });

  it('centres the map rather than pinning it to a corner', () => {
    const pts = corners(CAM);
    const midX = (Math.max(...pts.map((p) => p.x)) + Math.min(...pts.map((p) => p.x))) / 2;
    const midY = (Math.max(...pts.map((p) => p.y)) + Math.min(...pts.map((p) => p.y))) / 2;
    expect(midX).toBeCloseTo(canvas.width / 2, 3);
    expect(midY).toBeCloseTo(canvas.height / 2, 3);
  });
});

describe('placeLabels', () => {
  it('drops a name that collides instead of moving it', () => {
    expect(placeLabels([{ x: 100, y: 100, text: 'first' }, { x: 105, y: 103, text: 'second' }]).map((l) => l.text)).toEqual(['first']);
  });
  it('never changes a coordinate it keeps', () => {
    // ⛔ Nudging a label would put a name beside a position nobody occupied.
    const labels = [{ x: 12, y: 34, text: 'a' }, { x: 500, y: 400, text: 'b' }];
    expect(placeLabels(labels)).toEqual(labels);
  });
  it('keeps names that are only close on one axis', () => {
    expect(placeLabels([{ x: 100, y: 100, text: 'a' }, { x: 100, y: 400, text: 'b' }, { x: 900, y: 100, text: 'c' }])).toHaveLength(3);
  });
});

describe('statusLine', () => {
  const snapshot = (over: Record<string, unknown> = {}) => ({
    players: [{ x: 1, stale_ms: 200 }, { x: 2, stale_ms: 1950 }, { x: null, stale_ms: 0 }],
    overlap_conflicts: 1, gaps: { G: 'no track' }, ...over,
  });
  it('reports the OLDEST sample, not the newest', () => { expect(statusLine(snapshot())).toContain('oldest sample 1950 ms'); });
  it('counts only players it could place', () => { expect(statusLine(snapshot())).toMatch(/^2\/3 placed/); });
  it('says how many players have no state at all', () => { expect(statusLine(snapshot())).toContain('1 without a state'); });
  it('says nothing about gaps when there are none', () => { expect(statusLine(snapshot({ gaps: {} }))).not.toContain('without a state'); });
  it('is empty rather than fabricated when there is no snapshot', () => { expect(statusLine(null)).toBe(''); });
});

describe('boundsFromPlayers', () => {
  it('brackets the players it was given', () => {
    const b = boundsFromPlayers([{ x: -100, y: 50, z: 0 }, { x: 900, y: -200, z: 320 }])!;
    expect(b.min[0]).toBeLessThanOrEqual(-100); expect(b.max[0]).toBeGreaterThanOrEqual(900);
    expect(b.min[1]).toBeLessThanOrEqual(-200); expect(b.max[2]).toBeGreaterThanOrEqual(320);
  });
  it('ignores players who have no position', () => {
    expect(boundsFromPlayers([{ x: 10, y: 10, z: 10 }, {}])!.min).toEqual([10, 10, 10].map((v) => v - 512));
  });
  it('is null when nobody can be placed, rather than a point at the origin', () => {
    expect(boundsFromPlayers([])).toBeNull();
    expect(boundsFromPlayers([{}])).toBeNull();
  });
  it('never collapses to zero span, which would divide the scale by nothing', () => {
    const b = boundsFromPlayers([{ x: 5, y: 5, z: 5 }])!;
    expect(b.max[0] - b.min[0]).toBeGreaterThan(0);
  });
});

describe('edgeStyle', () => {
  it('tells opponents from teammates by colour', () => { expect(edgeStyle('opponent', false).color).not.toBe(edgeStyle('teammate', false).color); });
  it('draws a contested thread solid and a quiet one dashed', () => {
    expect(edgeStyle('opponent', true).dash).toEqual([]);
    expect(edgeStyle('opponent', false).dash.length).toBeGreaterThan(0);
  });
  it('makes a contested thread more visible, never less', () => {
    expect(edgeStyle('opponent', true).alpha).toBeGreaterThan(edgeStyle('opponent', false).alpha);
    expect(edgeStyle('opponent', true).width).toBeGreaterThan(edgeStyle('opponent', false).width);
  });
  it('never draws a thread fully opaque, and draws with theme tokens', () => {
    for (const kind of ['opponent', 'teammate']) for (const contested of [true, false]) {
      expect(edgeStyle(kind, contested).alpha).toBeLessThan(1);
      expect(edgeStyle(kind, contested).color).toMatch(/^var\(--color-/);
    }
  });
});

describe('isTeamPov / isPlayerPov', () => {
  it.each(['team:AXIS', 'team:allies', 'TEAM:AXIS'])('recognises %s as a team', (pov) => { expect(isTeamPov(pov)).toBe(true); expect(isPlayerPov(pov)).toBe(false); });
  it.each(['world', '', null, undefined])('rejects %s as either', (pov) => { expect(isTeamPov(pov)).toBe(false); expect(isPlayerPov(pov)).toBe(false); });
  it('a guid is a player view, not a team', () => {
    // ⛔ Treating a guid as a team would draw one player's knowledge as his side's.
    expect(isTeamPov('AB12CD34')).toBe(false);
    expect(isPlayerPov('AB12CD34')).toBe(true);
  });
});

describe('beliefRegions', () => {
  const belief = (over: Record<string, unknown> = {}) => ({ region: { x: 10, y: 20, z: 30, radius: 400 }, subject_guid: 'ENEMY', confidence: 0.6, source: 'contact_hit', ...over });
  it('keeps a belief that names someone AND places them', () => { expect(beliefRegions({ beliefs: [belief()] }).regions).toHaveLength(1); });
  it('drops a belief with no subject, however well placed', () => {
    // ⛔ Gunfire names nobody (§6.3, the phantom squad).
    expect(beliefRegions({ beliefs: [belief({ subject_guid: null })] }).regions).toEqual([]);
  });
  it('drops a belief with no region, however certain', () => { expect(beliefRegions({ beliefs: [belief({ region: null, confidence: 1 })] }).regions).toEqual([]); });
  it('carries the radius the backend grew, not one of its own', () => { expect(beliefRegions({ beliefs: [belief()] }).regions[0].radius).toBe(400); });
  it('is empty rather than throwing when there is no holder', () => {
    expect(beliefRegions(null).regions).toEqual([]);
    expect(beliefRegions({}).regions).toEqual([]);
  });
  describe('the published horizon', () => {
    const holder = (radius: number) => ({ position_claim_max_radius: 1000, beliefs: [belief({ region: { x: 0, y: 0, z: 0, radius } })] });
    it('draws a region inside the horizon', () => { expect(beliefRegions(holder(900)).regions).toHaveLength(1); });
    it('refuses to draw one past it', () => { expect(beliefRegions(holder(2500)).regions).toHaveLength(0); });
    it('still reports that subject as known, in words', () => { expect(beliefRegions(holder(2500)).unplacedSubjects).toEqual(['ENEMY']); });
    it('counts a subject as placed when ANY of his regions is fresh enough', () => {
      const both = { position_claim_max_radius: 1000, beliefs: [belief({ region: { x: 0, y: 0, z: 0, radius: 2500 } }), belief({ region: { x: 5, y: 5, z: 5, radius: 200 } })] };
      expect(beliefRegions(both).regions).toHaveLength(1);
      expect(beliefRegions(both).unplacedSubjects).toEqual([]);
    });
    it('draws everything when no horizon is published', () => {
      expect(horizonOf(null)).toBe(Infinity);
      expect(beliefRegions({ beliefs: [belief()] }).regions).toHaveLength(1);
    });
  });
});

describe('floorBands', () => {
  const view = { cx: 100, cy: 100, scale: 1, midX: 0, midY: 0, midZ: 0, minZ: 0, maxZ: 100 };
  // two triangles: one on the floor, one on a roof
  const mesh = { vertices: [0, 0, 0, 10, 0, 0, 0, 10, 0, 0, 0, 100, 10, 0, 100, 0, 10, 100], indexes: [0, 1, 2, 3, 4, 5] };
  it('puts a low and a high triangle in different bands, low first', () => {
    const bands = floorBands(mesh, CAM, view, 4);
    expect(bands).toHaveLength(2);
    expect(bands[0].t).toBeLessThan(bands[1].t);
    expect(bands[0].d).toMatch(/^M[\d.-]+ [\d.-]+L/);
  });
  it('leaves out empty bands rather than emitting empty paths', () => {
    expect(floorBands({ vertices: [], indexes: [] }, CAM, view)).toEqual([]);
  });
});
