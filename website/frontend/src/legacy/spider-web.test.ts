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
  THEME, alphaHex, beliefRegions, boundsFromPlayers, capabilityRows, clockBadge,
  edgeStyle, horizonOf, mixHex,
  isTeamPov, placeLabels,
  project, statusLine, viewportFor,
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

describe('edgeStyle', () => {
  it('tells opponents from teammates by colour', () => {
    expect(edgeStyle('opponent', false).color)
      .not.toBe(edgeStyle('teammate', false).color);
  });

  it('draws a contested thread solid and a quiet one dashed', () => {
    // ⚠️ Contested is emphasis, not an alarm: the tracker holds an engagement
    // open for up to 15 seconds after the last hit, so a solid thread can mean
    // "was shot at fifteen seconds ago and has stood still since".
    expect(edgeStyle('opponent', true).dash).toEqual([]);
    expect(edgeStyle('opponent', false).dash.length).toBeGreaterThan(0);
  });

  it('makes a contested thread more visible, never less', () => {
    const loud = edgeStyle('opponent', true);
    const quiet = edgeStyle('opponent', false);
    expect(loud.alpha).toBeGreaterThan(quiet.alpha);
    expect(loud.width).toBeGreaterThan(quiet.width);
  });

  it('never draws a thread fully opaque', () => {
    // The floors and the uncertainty discs have to stay readable underneath;
    // a solid mesh of lines is what made the prototype's web unreadable.
    for (const kind of ['opponent', 'teammate']) {
      for (const contested of [true, false]) {
        expect(edgeStyle(kind, contested).alpha).toBeLessThan(1);
      }
    }
  });
});

describe('isTeamPov', () => {
  it.each(['team:AXIS', 'team:allies', 'TEAM:AXIS'])('recognises %s', (pov) => {
    expect(isTeamPov(pov)).toBe(true);
  });

  it.each(['world', '', null, undefined, 'AB12CD34'])('rejects %s', (pov) => {
    // ⛔ A player GUID is not a team. Treating one as a team view would draw a
    // single player's knowledge as if it were his side's.
    expect(isTeamPov(pov)).toBe(false);
  });
});

describe('beliefRegions', () => {
  const belief = (over: Record<string, unknown> = {}) => ({
    region: { x: 10, y: 20, z: 30, radius: 400 },
    subject_guid: 'ENEMY',
    confidence: 0.6,
    source: 'contact_hit',
    ...over,
  });

  it('keeps a belief that names someone AND places them', () => {
    expect(beliefRegions({ beliefs: [belief()] }).regions).toHaveLength(1);
  });

  it('drops a belief with no subject, however well placed', () => {
    // ⛔ Gunfire names nobody (§6.3, the phantom squad). Drawing it as an enemy
    // would conjure a player out of a noise.
    expect(beliefRegions({ beliefs: [belief({ subject_guid: null })] }).regions).toEqual([]);
  });

  it('drops a belief with no region, however certain', () => {
    expect(beliefRegions({ beliefs: [belief({ region: null, confidence: 1 })] }).regions)
      .toEqual([]);
  });

  it('carries the radius the backend grew, not one of its own', () => {
    // The widening is measured server-side from real displacement; recomputing
    // or capping it here would quietly restate the uncertainty.
    expect(beliefRegions({ beliefs: [belief()] }).regions[0].radius).toBe(400);
  });

  it('is empty rather than throwing when there is no holder', () => {
    expect(beliefRegions(null).regions).toEqual([]);
    expect(beliefRegions({}).regions).toEqual([]);
  });

  describe('the published horizon', () => {
    // ⛔ Past the horizon a region is not a place. The backend already refuses
    // to derive a distance from one that wide; drawing it anyway makes the same
    // overclaim in pixels — a 2,500-unit circle on a 4,600-unit map is not
    // "somewhere here", it is the whole map.
    const holder = (radius: number) => ({
      position_claim_max_radius: 1000,
      beliefs: [belief({ region: { x: 0, y: 0, z: 0, radius } })],
    });

    it('draws a region inside the horizon', () => {
      expect(beliefRegions(holder(900)).regions).toHaveLength(1);
    });

    it('refuses to draw one past it', () => {
      expect(beliefRegions(holder(2500)).regions).toHaveLength(0);
    });

    it('still reports that subject as known, in words', () => {
      // ⭐ Not drawn is not forgotten: the team knows he exists, just not where.
      expect(beliefRegions(holder(2500)).unplacedSubjects).toEqual(['ENEMY']);
    });

    it('counts a subject as placed when ANY of his regions is fresh enough', () => {
      const both = {
        position_claim_max_radius: 1000,
        beliefs: [
          belief({ region: { x: 0, y: 0, z: 0, radius: 2500 } }),
          belief({ region: { x: 5, y: 5, z: 5, radius: 200 } }),
        ],
      };
      expect(beliefRegions(both).regions).toHaveLength(1);
      expect(beliefRegions(both).unplacedSubjects).toEqual([]);
    });

    it('draws everything when no horizon is published', () => {
      expect(horizonOf(null)).toBe(Infinity);
      expect(beliefRegions({ beliefs: [belief()] }).regions).toHaveLength(1);
    });
  });
});

describe('THEME', () => {
  // The chosen dark-instrument tokens. Pinned here because the React rewrite
  // will READ this object rather than re-derive the palette, so a value that
  // drifts to an eyeballed neighbour silently desynchronises the two surfaces
  // — and nothing else in the suite would notice.
  it.each([
    ['background', '#0b0b0a'],
    ['allies', '#8bb0d6'],
    ['axis', '#d1857c'],
    ['positive', '#8fae8a'],
    ['negative', '#b0847c'],
    ['floorLow', '#6084b0'],
    ['floorHigh', '#c8e4ff'],
  ])('%s is the chosen token', (key, value) => {
    expect(THEME[key as keyof typeof THEME]).toBe(value);
  });

  it('has no colour literal left outside it', async () => {
    // ⭐ The structural half. Pinning the values catches a changed token; this
    // catches a NEW colour introduced somewhere else, which is how a palette
    // scatters in the first place (the `replay.js` lesson the spec cites).
    const fs = await import('node:fs/promises');
    const path = await import('node:path');
    // ⚠️ From the vitest root (website/frontend), not `import.meta.url` — under
    // vitest that is not a file: URL and readFile rejects it.
    const source = await fs.readFile(
      path.resolve(process.cwd(), '../js/spider-web.js'), 'utf8');
    const themeBlock = source.slice(
      source.indexOf('export const THEME'), source.indexOf('};', source.indexOf('export const THEME')));
    const outside = source.replace(themeBlock, '');
    // ⚠️ Hex literals AND colours built from raw components. The first version
    // matched only `#rrggbb`, and the whole canvas floor ramp — three RGB
    // numbers interpolated inline — slipped past it while the module advertised
    // itself as the single palette (Codex, review of #803). A guard that only
    // catches one spelling of the mistake invites the other.
    const strays = [
      ...[...outside.matchAll(/#[0-9a-fA-F]{6}\b/g)].map((m) => m[0]),
      ...[...outside.matchAll(/rgba?\(\s*[\d$][^)]*\)/g)].map((m) => m[0]),
    ];
    expect(strays).toEqual([]);
  });
});

describe('alphaHex', () => {
  it('turns an opacity into two hex digits', () => {
    expect(alphaHex(1)).toBe('ff');
    expect(alphaHex(0)).toBe('00');
    expect(alphaHex(0.5)).toBe('80');
  });

  it('is always two digits, so a colour never becomes malformed', () => {
    // ⛔ `(3).toString(16)` is "3", and `#b0847c3` is not a colour — the
    // canvas would silently drop the style and draw in whatever came before.
    for (const a of [0.001, 0.01, 0.02, 0.05]) {
      expect(alphaHex(a)).toHaveLength(2);
    }
  });

  it('clamps rather than producing nonsense for out-of-range input', () => {
    expect(alphaHex(5)).toBe('ff');
    expect(alphaHex(-1)).toBe('00');
    expect(alphaHex(NaN)).toBe('00');
  });
});

describe('mixHex', () => {
  it('returns the endpoints unchanged', () => {
    expect(mixHex('#6084b0', '#c8e4ff', 0)).toBe('#6084b0');
    expect(mixHex('#6084b0', '#c8e4ff', 1)).toBe('#c8e4ff');
  });

  it('lands between them in the middle', () => {
    expect(mixHex('#000000', '#ffffff', 0.5)).toBe('#808080');
  });

  it('always returns six digits, so a colour never becomes malformed', () => {
    // ⛔ Same trap as alphaHex: an unpadded component makes `#8084b` and the
    // canvas silently drops the style.
    for (const t of [0, 0.02, 0.5, 0.97, 1]) {
      expect(mixHex('#010203', '#040506', t)).toMatch(/^#[0-9a-f]{6}$/);
    }
  });

  it('clamps rather than extrapolating past an endpoint', () => {
    expect(mixHex('#000000', '#ffffff', 5)).toBe('#ffffff');
    expect(mixHex('#000000', '#ffffff', -2)).toBe('#000000');
  });
});

describe('clockBadge', () => {
  it('reports the backend verdict rather than overriding it', () => {
    // ⭐ An earlier version forced UNVALIDATED everywhere, believing
    // `validated` meant "internally consistent only". It does not: §5.3 and
    // acceptance B1 define it as having passed against INDEPENDENT
    // `player_track` spawn landings — explicitly not the rows that produced
    // the offset — with a frozen residual tolerance. Overriding it was itself
    // an overclaim, in the other direction: it called a clock unproven that
    // had passed the gate the spec defines.
    expect(clockBadge({ status: 'validated', interval_ms: 30000 }).badge)
      .toBe('VALIDATED');
  });

  it('separates "could not check" from "checked and contradicted"', () => {
    // ⛔ `validate_clock` assigns `validation_failed` only when the landing
    // clusters EXIST and too few residuals fall inside the frozen tolerance —
    // evidence against the offset, not missing evidence. Sharing a word with
    // "unvalidated" would hide the strongest thing known about those groups.
    const failed = clockBadge({ status: 'validation_failed' });
    const unchecked = clockBadge({ status: 'internally_consistent_unvalidated' });
    expect(failed.badge).toBe('FAILED');
    expect(unchecked.badge).toBe('UNVALIDATED');
    expect(failed.badge).not.toBe(unchecked.badge);
    expect(failed.reason).toMatch(/CONTRADICT/);
    expect(unchecked.reason).toMatch(/too few/);
  });

  it('keeps the three verdicts apart', () => {
    // ⛔ `inconsistent` is not a weaker `unvalidated`: the candidates disagree
    // and the value is published as null, never averaged into one.
    expect(clockBadge({ status: 'internally_consistent_unvalidated' }).badge)
      .toBe('UNVALIDATED');
    expect(clockBadge({ status: 'insufficient' }).badge).toBe('UNVALIDATED');
    expect(clockBadge({ status: 'inconsistent' }).badge).toBe('INCONSISTENT');
  });

  it('says C2 is a stronger confirmation still pending, not the only one', () => {
    expect(clockBadge({ status: 'validated' }).reason).toMatch(/C2/);
    expect(clockBadge({ status: 'validated' }).reason).toMatch(/§5\.3/);
  });

  it('never returns a non-string reason, whatever the payload holds', () => {
    // ⛔ The type promises `string | undefined`. `team && team.reason` handed
    // back `null` for the explicitly supported `clockBadge(null)` call, and a
    // consumer narrowing on `!== undefined` would then treat null as a string
    // (Codex, #804).
    for (const team of [null, undefined, { status: 'unavailable' },
                        { status: 'unavailable', reason: null },
                        { status: 'unavailable', reason: 42 }]) {
      const { reason } = clockBadge(team as never);
      expect(reason === undefined || typeof reason === 'string').toBe(true);
    }
  });

  it('distinguishes "no clock at all" from "not independently confirmed"', () => {
    // These are different facts and a reader needs them apart: one means the
    // round had nothing to reconstruct from, the other that the reconstruction
    // exists and has not been checked from outside.
    expect(clockBadge({ status: 'unavailable', reason: 'no rows' }).badge)
      .toBe('UNAVAILABLE');
    expect(clockBadge(null).badge).toBe('UNAVAILABLE');
  });

  it('says why, so the badge is never bare', () => {
    for (const status of ['validated', 'insufficient', 'inconsistent']) {
      expect(clockBadge({ status }).reason).toBeTruthy();
    }
  });
});

describe('capabilityRows', () => {
  it('keeps three states and never folds unknown into disabled', () => {
    // ⛔ For every round captured before the tracker declared its flags, an
    // absent section is equally consistent with the capture being off and with
    // it being on and having nothing to report. Rendering them alike turns "we
    // do not know" into "it was off".
    const rows = capabilityRows({ capabilities: {
      shot_fired: 'enabled', aim_lock: 'disabled', comm_events: 'unknown',
    } });
    // Sorted by name, so the order is aim_lock, comm_events, shot_fired —
    // stable output matters more than input order for a panel a human reads.
    expect(rows.map((r) => `${r.name}=${r.state}`)).toEqual([
      'aim_lock=disabled', 'comm_events=unknown', 'shot_fired=enabled',
    ]);
  });

  it('treats an unrecognised value as unknown rather than guessing', () => {
    const rows = capabilityRows({ capabilities: { odd: 'maybe', missing: '' } });
    expect(rows.every((r) => r.state === 'unknown' && r.known === false)).toBe(true);
  });

  it('marks only enabled and disabled as known', () => {
    const rows = capabilityRows({ capabilities: { a: 'enabled', b: 'unknown' } });
    expect(rows.map((r) => r.known)).toEqual([true, false]);
  });

  it('is empty rather than throwing when there is no policy', () => {
    expect(capabilityRows(null)).toEqual([]);
    expect(capabilityRows({})).toEqual([]);
  });
});
