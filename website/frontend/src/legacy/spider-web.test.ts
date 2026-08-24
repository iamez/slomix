/**
 * The Spider Web renderer's arithmetic, pinned.
 *
 * ⚠️ This file exists because 441 lines of `website/js/spider-web.js` shipped
 * with no test of any kind. The repository has no harness for the legacy
 * bundle, so the page was verified by looking at screenshots — which catches a
 * blank canvas and nothing subtler. A projection that is wrong by a sign
 * produces a picture that looks entirely plausible and is upside down.
 *
 * ⭐ Vitest reaches the legacy module directly: `utils.js` has no imports of
 * its own, so there is no dependency chain to stand up, and jsdom is already
 * the configured environment.
 *
 * Everything here pins a PROPERTY rather than a pixel. The numbers a
 * projection produces depend on canvas size, camera and map, none of which is
 * a contract; what the drawing promises is that height goes up, that turning
 * is a rotation, and that the map fits on the screen.
 */

import { describe, expect, it } from 'vitest';

import type { Camera } from '../../../js/spider-web.js';

import {
  boundsFromPlayers, placeLabels, project, statusLine, viewportFor,
} from '../../../js/spider-web.js';

const VIEW = { cx: 500, cy: 300, scale: 0.1, midX: 0, midY: 0, midZ: 0 };
const CAM = { yaw: 0.6, pitch: 0.9, zoom: 1, panX: 0, panY: 0 };

function distance(a: { x: number; y: number }, b: { x: number; y: number }) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

describe('project', () => {
  it('puts the centre of the map at the centre of the canvas', () => {
    const p = project(0, 0, 0, CAM, VIEW);
    expect(p.x).toBeCloseTo(VIEW.cx, 6);
    expect(p.y).toBeCloseTo(VIEW.cy, 6);
  });

  it('draws greater height HIGHER on the screen', () => {
    // ⛔ The sign that a screenshot cannot check. Canvas y grows downward, so
    // a naive projection puts the top of a building below its foundation and
    // the result still looks like a plausible map.
    const ground = project(100, 100, 0, CAM, VIEW);
    const roof = project(100, 100, 500, CAM, VIEW);
    expect(roof.y).toBeLessThan(ground.y);
  });

  it('turning the camera is a rotation, so it preserves distances', () => {
    const a = { x: 400, y: -250, z: 0 };
    const b = { x: -100, y: 320, z: 0 };
    // Flat on, so the pitch squash cannot mask a broken rotation.
    const flat = { ...CAM, pitch: 0 };
    const before = distance(project(a.x, a.y, a.z, flat, VIEW),
                            project(b.x, b.y, b.z, flat, VIEW));
    for (const yaw of [0, 0.4, 1.1, 2.7, -1.9]) {
      const turned = { ...flat, yaw };
      const after = distance(project(a.x, a.y, a.z, turned, VIEW),
                             project(b.x, b.y, b.z, turned, VIEW));
      expect(after).toBeCloseTo(before, 6);
    }
  });

  it('sorts nearer things later, which is what the painter relies on', () => {
    const far = project(0, -800, 0, CAM, VIEW);
    const near = project(0, 800, 0, CAM, VIEW);
    expect(near.depth).toBeGreaterThan(far.depth);
  });

  it('zoom scales distance from the centre, and pan does not', () => {
    const one = project(300, 300, 0, CAM, VIEW);
    const two = project(300, 300, 0, { ...CAM, zoom: 2 }, VIEW);
    expect(distance(two, { x: VIEW.cx, y: VIEW.cy }))
      .toBeCloseTo(2 * distance(one, { x: VIEW.cx, y: VIEW.cy }), 6);

    const panned = project(300, 300, 0, { ...CAM, panX: 40, panY: -25 }, VIEW);
    expect(panned.x - one.x).toBeCloseTo(40, 6);
    expect(panned.y - one.y).toBeCloseTo(-25, 6);
  });
});

describe('viewportFor', () => {
  const mesh = { bounds: { min: [-2000, -1500, -300], max: [2600, 1900, 700] } };
  const canvas = { width: 1200, height: 640 };

  function projectedCorners(cam: Camera) {
    const view = viewportFor(mesh, canvas, cam);
    const pts = [];
    for (const x of [mesh.bounds.min[0], mesh.bounds.max[0]]) {
      for (const y of [mesh.bounds.min[1], mesh.bounds.max[1]]) {
        for (const z of [mesh.bounds.min[2], mesh.bounds.max[2]]) {
          pts.push(project(x - view.midX, y - view.midY, z - view.midZ, cam, view));
        }
      }
    }
    return pts;
  }

  it.each([
    [0, 0.15], [0.6, 0.9], [1.7, 1.45], [-2.4, 0.5], [3.1, 1.2],
  ])('fits the whole map on the canvas at yaw %s pitch %s', (yaw, pitch) => {
    // ⭐ The bug this replaces was exactly here: fitting on the WORLD extent
    // ignores that the projection squashes one axis by cos(pitch) and shears
    // height into it, so supply covered about a third of the canvas and the
    // rest was margin. Checked at several angles because a fit that only
    // holds at the default is not a fit.
    const pts = projectedCorners({ yaw, pitch, zoom: 1, panX: 0, panY: 0 });
    for (const p of pts) {
      expect(p.x).toBeGreaterThanOrEqual(-1);
      expect(p.x).toBeLessThanOrEqual(canvas.width + 1);
      expect(p.y).toBeGreaterThanOrEqual(-1);
      expect(p.y).toBeLessThanOrEqual(canvas.height + 1);
    }
  });

  it('uses the canvas, rather than leaving most of it empty', () => {
    const pts = projectedCorners(CAM);
    const w = Math.max(...pts.map((p) => p.x)) - Math.min(...pts.map((p) => p.x));
    const h = Math.max(...pts.map((p) => p.y)) - Math.min(...pts.map((p) => p.y));
    // One axis has to come close to filling, or the scale is too small — the
    // symptom of the world-space fit, which passed "fits on canvas" easily.
    const fill = Math.max(w / canvas.width, h / canvas.height);
    expect(fill).toBeGreaterThan(0.85);
  });

  // ⚠️ This passes with the recentring term removed, and that is not a hole in
  // the test: the term is provably zero for a bounding box (measured over
  // 20,000 random maps and angles, |lo+hi|/span < 2e-15). The property below
  // is still worth pinning — it is what the page needs — but it cannot
  // distinguish the two implementations, and saying so is cheaper than the
  // next reader rediscovering it.
  it('centres the map rather than pinning it to a corner', () => {
    const pts = projectedCorners(CAM);
    const midX = (Math.max(...pts.map((p) => p.x)) + Math.min(...pts.map((p) => p.x))) / 2;
    const midY = (Math.max(...pts.map((p) => p.y)) + Math.min(...pts.map((p) => p.y))) / 2;
    expect(midX).toBeCloseTo(canvas.width / 2, 3);
    expect(midY).toBeCloseTo(canvas.height / 2, 3);
  });
});

describe('placeLabels', () => {
  it('drops a name that collides instead of moving it', () => {
    const labels = [
      { x: 100, y: 100, text: 'first' },
      { x: 105, y: 103, text: 'second' },
    ];
    const placed = placeLabels(labels);
    expect(placed.map((l: { text: string }) => l.text)).toEqual(['first']);
  });

  it('never changes a coordinate it keeps', () => {
    // ⛔ Nudging a label would put a name beside a position nobody occupied.
    const labels = [{ x: 12, y: 34, text: 'a' }, { x: 500, y: 400, text: 'b' }];
    expect(placeLabels(labels)).toEqual(labels);
  });

  it('keeps names that are only close on one axis', () => {
    const labels = [
      { x: 100, y: 100, text: 'a' },
      { x: 100, y: 400, text: 'b' },
      { x: 900, y: 100, text: 'c' },
    ];
    expect(placeLabels(labels)).toHaveLength(3);
  });
});

describe('statusLine', () => {
  const snapshot = (over: Record<string, unknown> = {}) => ({
    players: [
      { x: 1, y: 2, z: 3, stale_ms: 200 },
      { x: 4, y: 5, z: 6, stale_ms: 1400 },
    ],
    overlap_conflicts: 0,
    gaps: {},
    ...over,
  });

  it('reports the OLDEST sample, not the newest', () => {
    // A page that advertises its freshness by its best sample is advertising
    // nothing: the reader needs the worst one on screen.
    expect(statusLine(snapshot())).toContain('1400 ms');
  });

  it('counts only players it could place', () => {
    const s = snapshot({ players: [{ x: 1, y: 2, z: 3, stale_ms: 0 }, { stale_ms: 0 }] });
    expect(statusLine(s)).toContain('1/2');
  });

  it('says how many players have no state at all', () => {
    // ⛔ A player without a position is named, never quietly absent.
    expect(statusLine(snapshot({ gaps: { A: 'no track', B: 'dead' } })))
      .toContain('2 brez stanja');
  });

  it('says nothing about gaps when there are none', () => {
    expect(statusLine(snapshot())).not.toContain('brez stanja');
  });

  it('is empty rather than fabricated when there is no snapshot', () => {
    expect(statusLine(null)).toBe('');
  });
});

describe('boundsFromPlayers', () => {
  // ⛔ Twelve of the twenty maps in the corpus ship no geometry — the eight most
  // played were published and the rest carry 1-4 rounds each. Before this, a
  // missing mesh meant the renderer drew NOTHING: not the floors it does not
  // have, and not the players it does. The positions are known; only the space
  // is missing, and a black rectangle says neither.
  // ⭐ `boundsFromPlayers` returns `Bounds | null`, and the declaration file
  // makes the type checker insist these tests acknowledge it. They did not,
  // which is the kind of assumption a test is supposed to state rather than
  // carry silently.
  function requireBounds(players: Array<Record<string, unknown>>) {
    const b = boundsFromPlayers(players);
    expect(b).not.toBeNull();
    return b as { min: number[]; max: number[] };
  }

  it('brackets the players it was given', () => {
    const b = requireBounds([
      { x: -100, y: 50, z: 0 },
      { x: 900, y: -200, z: 320 },
    ]);
    expect(b.min[0]).toBeLessThanOrEqual(-100);
    expect(b.max[0]).toBeGreaterThanOrEqual(900);
    expect(b.min[1]).toBeLessThanOrEqual(-200);
    expect(b.max[2]).toBeGreaterThanOrEqual(320);
  });

  it('ignores players who have no position', () => {
    const b = requireBounds([{ x: 10, y: 10, z: 10 }, { name: 'gap' }]);
    expect(b.min).toEqual([10, 10, 10].map((v) => v - 512));
  });

  it('is null when nobody can be placed, rather than a point at the origin', () => {
    expect(boundsFromPlayers([])).toBeNull();
    expect(boundsFromPlayers([{ name: 'gap' }])).toBeNull();
  });

  it('never collapses to zero span, which would divide the scale by nothing', () => {
    const b = requireBounds([{ x: 5, y: 5, z: 5 }]);
    expect(b.max[0] - b.min[0]).toBeGreaterThan(0);
    expect(b.max[1] - b.min[1]).toBeGreaterThan(0);
  });
});
