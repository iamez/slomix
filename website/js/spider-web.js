/**
 * Spider Web — one moment of a round, drawn as the place it happened in.
 *
 * The proximity overlay draws players on a levelshot, which is a photograph
 * with no height in it: two players thirty metres apart vertically land on the
 * same pixel. This draws the exported floor geometry instead, in an
 * axonometric projection you can turn, so height is something you can see.
 *
 * ⭐ IT DRAWS UNCERTAINTY, NOT JUST POSITION. Every replay viewer in this genre
 * — DEMO24, RoundIQ, Memorin — draws confident dots. Ours cannot honestly do
 * that: a position is a floor sample up to some age old, and `position_error`
 * carries the MEASURED p90 for that age (about 12 units when fresh and
 * uncontested, about 875 when the reconstruction cannot tell which life a
 * player was on). So a player is a disc the size of what we actually know,
 * and a contested one is visibly a smear rather than a point.
 *
 * ⛔ A player with no state is NAMED, never omitted. `gaps` says why each one
 * is missing, and a silent absence would read as "nobody was there".
 *
 * Canvas 2D on purpose. The whole scene is at most ~17,000 triangles and ten
 * players, so WebGL would solve a problem we do not have, and the look this
 * wants — thin linework, labels, readouts — is something 2D draws more
 * sharply and without shaders.
 *
 * @module spider-web
 */

import { API_BASE, fetchJSON } from './utils.js';

/** Safe DOM element factory. Strings become text nodes; nullish children skipped. */
function _el(tag, className, ...children) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    for (const c of children) {
        if (c == null) continue;
        el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    }
    return el;
}

function stripEtColors(text) {
    return String(text || '').replace(/\^[0-9A-Za-z]/g, '');
}

const GEOMETRY_BASE = '/assets/maps/geometry';

/**
 * Every colour this page draws with, in one place.
 *
 * ⭐ ONE OBJECT, INJECTED, NOT SCATTERED. `replay.js` spread its palette across
 * a dozen call sites and the React rewrite had to hunt each one; the migration
 * spec asks for a single configuration object so the rewrite can read it
 * instead of re-deriving it. Values are the chosen dark-instrument tokens, not
 * eyeballed neighbours of them.
 *
 * ⚠️ A colour that appears nowhere in here is a colour the rewrite will miss.
 * If a new element needs one, it belongs in this object first.
 */
export const THEME = {
    // In use today.
    background: '#0b0b0a',
    text: '#eae7e1',
    allies: '#8bb0d6',
    axis: '#d1857c',
    negative: '#b0847c',
    neutral: '#807c75',

    // ⚠️ Declared and NOT yet drawn with. The clock and snapshot-integrity
    // panels are still to be built, and the hex scan below forbids inventing a
    // colour for them at the call site — so the palette they must draw from is
    // named here first.
    //
    // ⛔ This is deliberately NOT the same call as the parity keys, where only
    // the panels that exist are tagged. A parity key asserts to a harness that
    // a panel is present, and a false one makes its first run a false pass. A
    // token asserts nothing about the page; it declares what the page is
    // allowed to use. Reserving one costs nothing, reserving the other lies.
    hairline: '#171715',
    textDim: '#8d8981',
    positive: '#8fae8a',

    // ⚠️ The floor ramp, as its two endpoints. It used to be three hard-coded
    // RGB components interpolated inline, which meant the ENTIRE canvas floor
    // palette sat outside this object while the module advertised itself as
    // the single palette — and the hex scan below could not see it, because it
    // only matched `#rrggbb` literals. A rewrite reading THEME would have been
    // unable to reproduce the ramp (Codex, review of #803).
    floorLow: '#6084b0',
    floorHigh: '#c8e4ff',

    // ⚠️ `label` and `neutral` carry the same value on purpose: the rewrite
    // maps them to one token today. They are kept apart because their ROLES
    // differ — a player with no team, and the colour of an axis label — and if
    // they ever diverge it should happen here rather than at a call site
    // (Fable, review of #803).
    label: '#807c75',
};

/** Team colours, read off the theme so there is one source and not two. */
const TEAM_COLOR = {
    AXIS: THEME.axis,
    ALLIES: THEME.allies,
};
const NEUTRAL = THEME.neutral;

let loadId = 0;

const state = {
    roundId: null,
    pov: 'world',
    teams: [],
    tMs: 0,
    durationMs: 0,
    mesh: null,          // { vertices:[x,y,z,...], indexes:[i,i,i,...], bounds }
    meshMapName: null,
    snapshot: null,      // /replay/round/{id}/web payload
    camera: { yaw: 0.6, pitch: 0.9, zoom: 1, panX: 0, panY: 0 },
    drag: null,
};

// ── Projection ────────────────────────────────────────────────────────────────

/**
 * World (x, y, z) to screen, as an axonometric projection.
 *
 * Yaw turns the map about its vertical axis; pitch tips it towards the viewer.
 * At pitch = 0 this is a plan view and heights collapse — which is exactly the
 * levelshot's failure, so the default is tipped well away from it.
 *
 * ⚠️ Deliberately NOT perspective. A perspective camera makes two players the
 * same distance apart look different sizes depending on where they stand, and
 * this drawing is measured against a scale bar.
 */
export function project(x, y, z, cam, view) {
    const cy = Math.cos(cam.yaw), sy = Math.sin(cam.yaw);
    const rx = x * cy - y * sy;
    const ry = x * sy + y * cy;
    const cp = Math.cos(cam.pitch), sp = Math.sin(cam.pitch);
    return {
        x: view.cx + (rx * view.scale * cam.zoom) + cam.panX,
        y: view.cy + ((ry * cp - z * sp) * view.scale * cam.zoom) + cam.panY,
        // Depth for the painter's algorithm: further from the viewer sorts first.
        depth: ry * sp + z * cp,
    };
}

/**
 * Screen scale and centre that fit the map into the canvas AT THIS ANGLE.
 *
 * ⚠️ Fitted in SCREEN space, not world space. The projection squashes one axis
 * by cos(pitch) and shears height into it, so a scale derived from the world
 * extent always under-fills — measured at the default angle, supply covered
 * about a third of the canvas and the rest was margin. Projecting the eight
 * corners of the map's bounding box and fitting THAT is the same arithmetic
 * the renderer is about to do anyway, and it re-fits when the camera turns.
 */
export function viewportFor(mesh, canvas, cam) {
    const b = mesh.bounds;
    const mid = {
        midX: (b.min[0] + b.max[0]) / 2,
        midY: (b.min[1] + b.max[1]) / 2,
        midZ: (b.min[2] + b.max[2]) / 2,
        minZ: b.min[2],
        maxZ: b.max[2],
    };
    const unit = { cx: 0, cy: 0, scale: 1, ...mid };
    const flat = { ...cam, zoom: 1, panX: 0, panY: 0 };
    let lo = { x: Infinity, y: Infinity }, hi = { x: -Infinity, y: -Infinity };
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
    // ⚠️ The recentring term is provably ZERO for the input this is given, and
    // it is kept anyway. An axis-aligned box's eight corners are symmetric
    // about its centre, `project` is linear, and the centre is subtracted
    // before projecting — so the projected cloud is symmetric about the origin
    // and `lo + hi` cancels. Measured over 20,000 random maps and camera
    // angles: |lo + hi| / span never exceeded 1.9e-15.
    //
    // No test can catch its removal, so it is labelled rather than left for
    // the next reader to hunt a test for. It stays because it is what makes
    // this correct if the corner set ever stops being a box — fitting to the
    // real geometry extent instead of the bounding box would do exactly that.
    return {
        cx: canvas.width / 2 - ((lo.x + hi.x) / 2) * scale,
        cy: canvas.height / 2 - ((lo.y + hi.y) / 2) * scale,
        scale,
        ...mid,
    };
}

/**
 * Bounds taken from the players themselves, for a map with no exported floors.
 *
 * ⛔ Twelve of the twenty maps in the corpus ship no geometry: the eight most
 * played were published and the rest carry one to four rounds each. Without
 * this the renderer drew NOTHING on them — not the floors it does not have,
 * and not the players it does. The positions are known and the space is not,
 * and a black rectangle says neither of those things.
 *
 * Returns null when nobody can be placed, rather than a point at the world
 * origin: a zero span would scale the whole canvas onto one pixel.
 */
export function boundsFromPlayers(players, margin = 512) {
    const placed = (players || []).filter(
        (p) => p && p.x != null && p.y != null && p.z != null);
    if (!placed.length) return null;
    const axis = (k) => placed.map((p) => p[k]);
    const [xs, ys, zs] = [axis('x'), axis('y'), axis('z')];
    return {
        min: [Math.min(...xs) - margin, Math.min(...ys) - margin, Math.min(...zs) - margin],
        max: [Math.max(...xs) + margin, Math.max(...ys) + margin, Math.max(...zs) + margin],
    };
}

/**
 * The enemy regions a point of view is entitled to draw.
 *
 * ⭐ Under a team view an enemy is NOT a dot. The holder never knew a point —
 * they knew a place, from a contact or a crosshair or a noise, and that place
 * has been widening ever since. So the region is what gets drawn, at the size
 * the backend already grew it to, and its opacity is the belief's confidence.
 *
 * ⛔ Only beliefs that name a subject AND carry a region. A gunfire belief
 * names nobody (§6.3, the phantom squad) and a roster belief has no place;
 * drawing either as an enemy position would invent one.
 */
export function beliefRegions(holder) {
    if (!holder || !Array.isArray(holder.beliefs)) return { regions: [], unplacedSubjects: [] };
    // ⛔ Past the published horizon a region is NOT drawn. The backend already
    // refuses to derive a distance from one that wide, and drawing it anyway
    // makes the same overclaim in pixels: a 2,500-unit circle on a 4,600-unit
    // map is not "he is somewhere here", it is the whole map. Those subjects
    // are still KNOWN — they are reported as "position unknown" in words,
    // which is what the holder actually had.
    const horizon = typeof holder.position_claim_max_radius === 'number'
        ? holder.position_claim_max_radius : Infinity;
    const drawable = [];
    const unplaced = new Set();
    for (const b of holder.beliefs) {
        if (!b || !b.subject_guid) continue;
        if (!b.region) continue;
        if (b.region.radius > horizon) {
            unplaced.add(b.subject_guid);
            continue;
        }
        drawable.push({
            x: b.region.x, y: b.region.y, z: b.region.z,
            radius: b.region.radius,
            confidence: typeof b.confidence === 'number' ? b.confidence : 0,
            subject: b.subject_guid,
            source: b.source,
        });
    }
    // A subject with one fresh region and one stale one is placed, not unplaced.
    for (const d of drawable) unplaced.delete(d.subject);
    // ⚠️ An object, not an array with a property bolted on: the second answer
    // is as much part of the result as the first, and hiding it on the array
    // made it invisible to any caller that treated the return as a list.
    return { regions: drawable, unplacedSubjects: [...unplaced] };
}

/** The published horizon, or Infinity when a view does not carry one. */
export function horizonOf(holder) {
    return holder && typeof holder.position_claim_max_radius === 'number'
        ? holder.position_claim_max_radius : Infinity;
}

/** Whether this view is one team's picture rather than the oracle's. */
export function isTeamPov(pov) {
    return typeof pov === 'string' && pov.toLowerCase().startsWith('team:');
}

// ── Drawing ───────────────────────────────────────────────────────────────────

function drawFloors(ctx, mesh, cam, view) {
    const { vertices, indexes } = mesh;
    const zSpan = Math.max(1, view.maxZ - view.minZ);
    const faces = [];

    for (let i = 0; i + 2 < indexes.length; i += 3) {
        const pts = [];
        let depth = 0;
        let zSum = 0;
        for (let k = 0; k < 3; k++) {
            const v = indexes[i + k] * 3;
            const p = project(vertices[v] - view.midX, vertices[v + 1] - view.midY,
                              vertices[v + 2] - view.midZ, cam, view);
            pts.push(p);
            depth += p.depth;
            zSum += vertices[v + 2];
        }
        faces.push({ pts, depth: depth / 3, z: zSum / 3 });
    }

    // Painter's algorithm. With floors only — no walls, no overhangs to
    // interpenetrate — sorting whole triangles is enough, and it costs one
    // sort of ~10,000 items rather than a depth buffer.
    faces.sort((a, b) => a.depth - b.depth);

    for (const face of faces) {
        // Height reads as brightness. Without it a plan-ish view of a
        // multi-level map is an unreadable tangle of identical outlines.
        const t = (face.z - view.minZ) / zSpan;
        // Height reads as brightness AND opacity together. One alone is not
        // enough separation on a map like te_escape2, whose floors span 2,100
        // units: colour alone washes out, opacity alone loses the low ground.
        const shade = 0.34 + 0.46 * t;
        ctx.fillStyle = mixHex(THEME.floorLow, THEME.floorHigh, t) + alphaHex(shade);
        ctx.beginPath();
        ctx.moveTo(face.pts[0].x, face.pts[0].y);
        ctx.lineTo(face.pts[1].x, face.pts[1].y);
        ctx.lineTo(face.pts[2].x, face.pts[2].y);
        ctx.closePath();
        ctx.fill();
    }
}

/**
 * How a thread between two players is drawn.
 *
 * ⚠️ `recently_contested` does NOT mean "fighting right now". The tracker holds
 * an engagement open for up to 15 seconds after the last hit and closes it only
 * on `escape_time_ms` plus 300 units of movement, so a contested edge can mean
 * "was shot at fifteen seconds ago and has been standing still since". Drawn
 * distinctly, but never as an alarm.
 *
 * ⛔ An edge is geometric separation, not tactical support. Two teammates joined
 * by a short line may have a wall between them; line-of-sight is deliberately
 * not a channel here (§6.1).
 */
export function edgeStyle(kind, contested) {
    const opponent = kind === 'opponent';
    return {
        color: opponent ? THEME.negative : THEME.allies,
        width: contested ? 1.8 : 0.8,
        dash: contested ? [] : [3, 4],
        alpha: contested ? 0.75 : 0.28,
    };
}

function drawEdges(ctx, edges, players, cam, view) {
    const at = new Map();
    for (const p of players) {
        if (p.x == null || p.y == null || p.z == null) continue;
        at.set(p.guid, project(p.x - view.midX, p.y - view.midY, p.z - view.midZ,
                               cam, view));
    }
    // Contested last, so the threads that carry the most meaning are not
    // buried under the ones that carry the least.
    const ordered = [...edges].sort(
        (x, y) => Number(!!x.recently_contested) - Number(!!y.recently_contested));

    for (const e of ordered) {
        const a = at.get(e.a);
        const b = at.get(e.b);
        // ⛔ Both ends or nothing. An edge drawn to a player we could not place
        // would be a line to a position nobody occupied.
        if (!a || !b) continue;
        const st = edgeStyle(e.kind, !!e.recently_contested);
        ctx.save();
        ctx.globalAlpha = st.alpha;
        ctx.strokeStyle = st.color;
        ctx.lineWidth = st.width;
        ctx.setLineDash(st.dash);
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
        ctx.restore();
    }
}

/** Blend two THEME colours, so a ramp is expressed in the palette it belongs to. */
export function mixHex(from, to, t) {
    const clamp = Math.max(0, Math.min(1, Number(t) || 0));
    const part = (hex, i) => parseInt(hex.slice(1 + i * 2, 3 + i * 2), 16);
    const out = [0, 1, 2].map(
        (i) => Math.round(part(from, i) + (part(to, i) - part(from, i)) * clamp));
    return '#' + out.map((v) => v.toString(16).padStart(2, '0')).join('');
}

/** Two hex digits for an alpha in 0..1, so a colour keeps its THEME value. */
export function alphaHex(a) {
    const clamped = Math.max(0, Math.min(1, Number(a) || 0));
    return Math.round(clamped * 255).toString(16).padStart(2, '0');
}

function drawBeliefRegions(ctx, regions, cam, view) {
    for (const r of regions) {
        const c = project(r.x - view.midX, r.y - view.midY, r.z - view.midZ,
                          cam, view);
        const px = Math.max(3, r.radius * view.scale * cam.zoom);
        // Confidence is the opacity, floored so a fading belief stays visible
        // as a fading belief rather than disappearing into the background.
        const a = Math.max(0.08, Math.min(0.5, r.confidence));
        ctx.save();
        ctx.beginPath();
        ctx.arc(c.x, c.y, px, 0, Math.PI * 2);
        // Hex + alpha suffix rather than a second rgba() literal, so the value
        // still comes from THEME and cannot drift away from it.
        ctx.fillStyle = THEME.negative + alphaHex(a * 0.25);
        ctx.fill();
        ctx.strokeStyle = THEME.negative + alphaHex(a);
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 4]);
        ctx.stroke();
        ctx.restore();
    }
}

function drawPlayers(ctx, players, cam, view) {
    const drawn = [];
    for (const p of players) {
        if (p.x == null || p.y == null || p.z == null) continue;
        const s = project(p.x - view.midX, p.y - view.midY, p.z - view.midZ, cam, view);
        drawn.push({ p, s });
    }
    drawn.sort((a, b) => a.s.depth - b.s.depth);
    const labels = [];

    for (const { p, s } of drawn) {
        const color = TEAM_COLOR[String(p.team || '').toUpperCase()] || NEUTRAL;

        // ⭐ The measured error, drawn at map scale. `position_error.p90` is
        // what the reconstruction was shown to be worth for a sample this old
        // in this life state — so a contested player is a wide, faint disc and
        // a fresh one is nearly a point. This is the whole reason the accuracy
        // work exists, and hiding it would put the prototype's flaw back.
        const p90 = p.position_error && p.position_error.p90;
        if (p90) {
            const r = Math.max(2, p90 * view.scale * cam.zoom);
            ctx.beginPath();
            ctx.arc(s.x, s.y, r, 0, Math.PI * 2);
            ctx.fillStyle = `${color}1a`;
            ctx.fill();
            ctx.strokeStyle = `${color}55`;
            ctx.lineWidth = 1;
            ctx.setLineDash(p.overlap_conflict ? [4, 3] : []);
            ctx.stroke();
            ctx.setLineDash([]);
        }

        ctx.beginPath();
        ctx.arc(s.x, s.y, 4, 0, Math.PI * 2);
        // A dead player is a ring, not a disc: transparent fill rather than a
        // colour, so it reads as absence instead of a fourth team.
        ctx.fillStyle = p.alive === false ? 'transparent' : color;
        ctx.fill();
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;
        ctx.stroke();

        labels.push({ x: s.x + 8, y: s.y + 3, text: stripEtColors(p.name) });
    }

    // ⚠️ Labels last, and only where one fits. At a spawn eight players stand
    // within a few units of each other and their names print on top of one
    // another into an unreadable smear. Nudging them apart would draw people
    // where they were not, so a name that has no room is simply not drawn —
    // the disc still shows the player is there.
    ctx.fillStyle = THEME.text;
    ctx.font = '11px ui-monospace, monospace';
    for (const l of placeLabels(labels)) {
        ctx.fillText(l.text, l.x, l.y);
    }
}

/**
 * Which labels get drawn when several land on top of each other.
 *
 * ⛔ Drops, never nudges. At a spawn eight players stand within a few units of
 * one another; moving their names apart would put a name beside a position
 * nobody occupied, and this page's whole argument is that it does not draw
 * things that were not there. The disc still shows the player.
 */
export function placeLabels(labels, minX = 70, minY = 13) {
    const placed = [];
    for (const l of labels) {
        if (placed.some((q) => Math.abs(q.x - l.x) < minX
                            && Math.abs(q.y - l.y) < minY)) {
            continue;
        }
        placed.push(l);
    }
    return placed;
}

function render(canvas) {
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = THEME.background;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const players = (state.snapshot && state.snapshot.players) || [];
    // A map without floors still has people in it. Falling back to the extent
    // of the players keeps them on screen, and the banner above the canvas is
    // what says the space is missing.
    const bounds = state.mesh ? state.mesh.bounds : boundsFromPlayers(players);
    if (!bounds) return;

    const view = viewportFor({ bounds }, canvas, state.camera);
    if (state.mesh) drawFloors(ctx, state.mesh, state.camera, view);

    // Enemy beliefs beneath everything else: they are the least certain thing
    // on the canvas and must not sit on top of what is known.
    if (isTeamPov(state.pov)) {
        const info = (state.snapshot && state.snapshot.information_state) || {};
        const holder = Object.values(info.holders || {})[0];
        drawBeliefRegions(ctx, beliefRegions(holder).regions, state.camera, view);
    }

    // Threads under the players: a dot must never be hidden by a line.
    const edges = (state.snapshot && state.snapshot.edges) || [];
    if (Array.isArray(edges)) drawEdges(ctx, edges, players, state.camera, view);
    if (Array.isArray(players)) drawPlayers(ctx, players, state.camera, view);
}

/**
 * What the clock panel may say about a team's reinforcement wave.
 *
 * ⭐ IT REPORTS THE BACKEND'S VERDICT. An earlier version forced UNVALIDATED
 * for every team on the belief that `validated` meant "internally consistent
 * only". It does not. §5.3 and acceptance criterion B1 define `validated` as
 * having passed against **independent** `player_track` spawn landings —
 * explicitly not the `time_to_next_spawn` values that produced the candidate
 * offset, precisely so the check is not circular — with a frozen residual
 * tolerance and a minimum support count. `validate_clock` implements exactly
 * that, and only promotes a clock that was already
 * `internally_consistent_unvalidated`.
 *
 * ⚠️ So overriding the verdict was itself the overclaim, in the other
 * direction: it called a clock unproven that had passed the gate the spec
 * defines. C2 is a future DIRECT seed capture — a stronger confirmation still
 * to come — not the only independent validation that exists (Codex, #804).
 *
 * ⛔ `UNAVAILABLE` stays distinct from `UNVALIDATED`: one means the round had
 * nothing to reconstruct from, the other that a reconstruction exists and did
 * not pass.
 */
export function clockBadge(team) {
    const reason = (t) => (typeof t === 'string' && t ? t : undefined);
    if (!team || team.status === 'unavailable') {
        return { badge: 'UNAVAILABLE', reason: reason(team && team.reason) };
    }
    // ⛔ A TEAM VIEW DOES NOT GET THE OTHER SIDE'S CLOCK, and this is not the
    // same as "we could not establish one". §5.6 and §6.3 make the enemy
    // reinforcement phase an oracle diagnostic: without an observed cue this
    // team had no way to know it. The backend strips the phase; the badge has
    // to say WHY, or a reader takes the blank for a measurement failure.
    // ⭐ The holder's OWN entry under a non-oracle view: the reinforcement
    // countdown they saw on screen, without the grade of our reconstruction.
    // That grade is a FULL-ROUND verdict — publishing it early told a holder
    // how often their side would still spawn (Codex, #807) — so it stays in
    // `pov=world`. Without this branch the badge fell through to UNVALIDATED
    // and called a working HUD unverified.
    if (team.status === 'own_hud') {
        return {
            badge: 'OWN HUD',
            reason: reason(team.reason)
                || 'the reinforcement countdown this side saw; the grade of '
                   + 'the reconstruction behind it is an oracle diagnostic',
        };
    }
    if (team.status === 'unknown_to_this_pov') {
        return {
            badge: 'WITHHELD',
            reason: reason(team.reason)
                || 'the enemy reinforcement phase is oracle truth; this team '
                   + 'had no observed cue to infer it from (§5.6, §6.3)',
        };
    }
    if (team.status === 'validated') {
        return {
            badge: 'VALIDATED',
            reason: reason(team.reason)
                || 'passed against independent spawn landings (§5.3); direct '
                   + 'seed capture (C2) is a stronger confirmation still pending',
        };
    }
    if (team.status === 'inconsistent') {
        return {
            badge: 'INCONSISTENT',
            reason: reason(team.reason)
                // ⚠️ EITHER cause. `infer_clock` rejects multiple intervals as
                // well as multiple offsets, and observations can disagree on
                // the interval while producing the same modular offset. Naming
                // only the offsets states a cause the payload may contradict —
                // and such a payload carries `interval_ms: null`, so the panel
                // printed the wrong explanation beside an empty value
                // (Codex, #804).
                || 'eligible observations disagree on the interval or the '
                   + 'offset; published as null, never averaged into one',
        };
    }
    // ⛔ "We could not check" and "we checked and it failed" are different
    // facts and must not share a word. `validate_clock` assigns
    // `validation_failed` only when at least MIN_VALIDATION_LANDINGS clusters
    // EXIST and fewer than MIN_VALIDATION_PASS_RATIO of them fall inside the
    // frozen residual tolerance — evidence that CONTRADICTS the inferred
    // clock, not evidence that is missing. Reporting the 126 measured failure
    // groups as merely unsupported would hide the strongest thing we know
    // about them (Codex, #804).
    if (team.status === 'validation_failed') {
        return {
            badge: 'FAILED',
            reason: reason(team.reason)
                || 'independent spawn landings exist and CONTRADICT this offset; '
                   + 'too few residuals inside the frozen tolerance (§5.3)',
        };
    }
    // ⛔ `insufficient` comes from a DIFFERENT stage. `infer_clock` assigns it
    // when there are fewer than MIN_INTERNAL_OBSERVATIONS eligible timing
    // observations — before independent validation is ever attempted, and
    // before there is an offset to validate. Describing it as missing landing
    // clusters points at the wrong stage, and hinting at internal consistency
    // asserts something that was never established: with one or two
    // observations at differing intervals `interval_ms` is null (Codex, #804).
    if (team.status === 'insufficient') {
        return {
            badge: 'UNVALIDATED',
            reason: reason(team.reason)
                || 'too few eligible timing observations to infer an offset at '
                   + 'all; nothing was validated because nothing was inferred',
        };
    }
    return {
        badge: 'UNVALIDATED',
        reason: reason(team.reason)
            || 'offset inferred, but too few independent landing clusters to '
               + 'check it; internally consistent at most',
    };
}

/**
 * The capture policy, as three states per capability — never two.
 *
 * ⛔ `unknown` IS NOT `disabled`. For every round captured before the tracker
 * began declaring its flags, an absent section is equally consistent with the
 * capture being off and with it being on and having nothing to report. A panel
 * that renders the two the same way turns "we do not know" into "it was off",
 * which is the single claim the manifest exists to prevent.
 */
export function capabilityRows(policy) {
    const caps = (policy && policy.capabilities) || {};
    const names = Object.keys(caps).sort();
    return names.map((name) => {
        const state = caps[name];
        return {
            name,
            state: state === 'enabled' || state === 'disabled' ? state : 'unknown',
            known: state === 'enabled' || state === 'disabled',
        };
    });
}

// ── Data ──────────────────────────────────────────────────────────────────────

async function loadMesh(mapName) {
    if (state.meshMapName === mapName && state.mesh) return state.mesh;
    try {
        const mesh = await fetchJSON(`${GEOMETRY_BASE}/${encodeURIComponent(mapName)}.json`);
        state.mesh = mesh;
        state.meshMapName = mapName;
    } catch {
        // ⛔ Named, not silent. `etl_supply` has no BSP in etmain and a handful
        // of maps were never exported; drawing an empty stage would read as an
        // empty round.
        state.mesh = null;
        state.meshMapName = mapName;
    }
    return state.mesh;
}

async function loadMoment(roundId, tMs, pov) {
    // ⛔ The point of view is a QUERY PARAMETER, so the withholding happens on
    // the server and each view is its own cache entry. Fetching the oracle once
    // and filtering locally would be faster and would quietly undo the whole
    // guarantee.
    const params = new URLSearchParams({ t: String(Math.round(tMs)) });
    if (pov && pov !== 'world') params.set('pov', pov);
    // ⛔ Returns without touching shared state. It used to assign
    // `state.snapshot` here, before the caller's staleness guard ran — so a
    // superseded request still overwrote the current moment. Scrubbing fast,
    // the request for an earlier `t` can settle after the one for a later `t`:
    // the slider and readout then show the later moment while the snapshot
    // holds the earlier one, and the next camera drag redraws the earlier
    // moment under the later label. The winner commits (CodeRabbit, #800).
    return fetchJSON(
        `${API_BASE}/replay/round/${encodeURIComponent(roundId)}/web?${params}`
    );
}

// ── View ──────────────────────────────────────────────────────────────────────

export function statusLine(snapshot) {
    if (!snapshot) return '';
    const players = snapshot.players || [];
    const positioned = players.filter((p) => p.x != null).length;
    const stale = players.reduce((m, p) => Math.max(m, p.stale_ms || 0), 0);
    const gaps = Object.keys(snapshot.gaps || {}).length;
    return `${positioned}/${players.length} razrešenih · `
        + `${snapshot.overlap_conflicts || 0} spornih življenj · `
        + `najstarejši vzorec ${stale} ms`
        + (gaps ? ` · ${gaps} brez stanja` : '');
}

function bindCamera(canvas, redraw) {
    canvas.addEventListener('mousedown', (e) => {
        state.drag = { x: e.clientX, y: e.clientY, ...state.camera };
    });
    window.addEventListener('mouseup', () => { state.drag = null; });
    window.addEventListener('mousemove', (e) => {
        if (!state.drag) return;
        state.camera.yaw = state.drag.yaw + (e.clientX - state.drag.x) * 0.006;
        // Clamped short of a plan view: at pitch 0 every height collapses onto
        // one line, which is the levelshot's failure this page exists to undo.
        state.camera.pitch = Math.min(1.45, Math.max(0.15,
            state.drag.pitch - (e.clientY - state.drag.y) * 0.005));
        redraw();
    });
    canvas.addEventListener('wheel', (e) => {
        e.preventDefault();
        state.camera.zoom = Math.min(8, Math.max(0.4,
            state.camera.zoom * (e.deltaY < 0 ? 1.1 : 1 / 1.1)));
        redraw();
    }, { passive: false });
}

export async function loadSpiderWebView(params = {}) {
    const container = document.getElementById('spider-web-container');
    if (!container) return;

    const myLoad = ++loadId;
    const roundId = params.roundId || state.roundId;
    container.textContent = '';

    if (!roundId) {
        container.appendChild(_el('p', 'text-slate-400 text-sm py-12 text-center',
            'Izberi rundo: #/spider-web/round/<id>'));
        return;
    }
    // ⛔ A NEW ROUND STARTS AT ITS OWN BEGINNING. `state` is module-level and
    // survives navigation, so opening round B after round A kept A's `tMs`.
    // Two ways that goes wrong, both silent: the retained moment is past B's
    // end, or it is before anybody in B has spawned — and the empty map that
    // follows is exactly what the `first_position_ms` logic below exists to
    // prevent (Codex, PR #807). `pov` deliberately persists: it is a viewing
    // preference, not a property of the round.
    // ⛔ AND THE RESET IS LOCAL UNTIL THE LOAD WINS. Writing it to `state`
    // here was a race: two overlapping loads for different rounds, the newer
    // one zeroes the shared time, then the OLDER request resolves and writes
    // its own snapshot and `first_position_ms` back — before any `myLoad`
    // check. The newer load then sees a nonzero `state.tMs`, skips its own
    // first-position reload, and renders its round at t=0 under the previous
    // round's slider and readout (Codex, PR #807).
    //
    // Everything below works on locals; shared state is committed once, after
    // the last await, and only by the load that is still current.
    const roundChanged = String(roundId) !== String(state.roundId);
    // ⛔ AND THE POINT OF VIEW GOES BACK TO THE ORACLE ON A NEW ROUND.
    //
    // It used to persist as "a viewing preference", which broke twice over.
    // The team list is rebuilt from `snapshot.players`, so a carried
    // `team:AXIS` made the FIRST request for the new round team-filtered —
    // the rebuild then saw one side and permanently omitted the other,
    // because `goTo` updates panels without recreating the POV buttons
    // (Codex, PR #807).
    //
    // ⭐ And it got worse the moment an unresolvable team started failing
    // CLOSED: carrying `team:AXIS` into a round with no AXIS side used to
    // fall back to the oracle, and now withholds everyone — the page would
    // open empty with no way back except reloading. A point of view belongs
    // to a round's roster, so it does not outlive it.
    const pov = roundChanged ? 'world' : state.pov;
    let tMs = roundChanged ? 0 : (state.tMs || 0);

    container.appendChild(_el('p', 'text-slate-400 text-sm py-12 text-center',
        'Nalagam rundo…'));

    // ⚠️ Opening at t=0 shows an empty map: nobody has spawned yet, and the
    // page would read as "nobody was there". The payload says when the round
    // first has anybody, so the first frame is a moment that exists.
    let snapshot;
    try {
        snapshot = await loadMoment(roundId, tMs, pov);
        if (myLoad !== loadId) return;
        if (!tMs && snapshot && snapshot.first_position_ms) {
            // Clamped here too. The payload is fixed, but the endpoint answers
            // `t < 0` with a 422 and this page's only response to that is
            // "could not load" — a floor the caller can enforce for itself
            // costs one call to Math.max.
            tMs = Math.max(0, snapshot.first_position_ms);
            snapshot = await loadMoment(roundId, tMs, pov);
            if (myLoad !== loadId) return;
        }
    } catch {
        if (myLoad !== loadId) return;
        container.textContent = '';
        container.appendChild(_el('p', 'text-rose-400 text-sm py-12 text-center',
            `Runde ${roundId} ni bilo mogoče naložiti.`));
        return;
    }
    if (myLoad !== loadId) return;

    // ⭐ THE COMMIT. One place, after the last await that could be superseded,
    // reached only by the winning load.
    state.roundId = roundId;
    state.tMs = tMs;
    state.pov = pov;
    state.snapshot = snapshot;
    // ⛔ The team list belongs to the round, and is rebuilt only when empty:
    // a round whose reconstruction resolved one side left that single team
    // cached and the NEXT round permanently offered one POV button — and the
    // reverse, a two-team list surviving into a one-team round, offers a view
    // that cannot resolve (Codex, PR #807).
    if (roundChanged) state.teams = [];

    const mapName = (snapshot.players || []).length ? snapshot.map_name : snapshot.map_name;
    await loadMesh(mapName || '');
    if (myLoad !== loadId) return;

    container.textContent = '';

    // Teams are learned from the oracle load and kept: under a team view the
    // payload no longer contains the other side, so the switch would lose its
    // own options after the first click.
    if (!state.teams.length) {
        state.teams = [...new Set((snapshot.players || [])
            .map((p) => p.team).filter(Boolean))].sort();
    }

    const header = _el('div', 'mb-3');
    header.appendChild(_el('h2', 'text-lg font-semibold text-slate-100',
        `Spider Web · runda ${roundId}${mapName ? ` · ${mapName}` : ''}`));
    const status = _el('p', 'text-xs text-slate-400 font-mono', statusLine(snapshot));
    header.appendChild(status);
    container.appendChild(header);

    if (!state.mesh) {
        container.appendChild(_el('p', 'text-amber-400 text-sm mb-3',
            `Za mapo ${mapName || '?'} ni izvožene geometrije — lege so znane, prostor ni.`));
    }

    // ⭐ Point of view. §6.4 makes `world` a NAMED diagnostic, so it is spelled
    // out as one rather than being the unlabelled default.
    const povBar = _el('div', 'flex items-center gap-2 mb-2 flex-wrap');
    // ⭐ Parity keys for the React rewrite's harness, in its stable kebab-case
    // form. ⚠️ Only the panels that EXIST are marked. The spec reserves keys
    // for the clock, snapshot integrity, gaps and the rest; tagging elements
    // that are not built yet would tell the harness a panel is present and
    // make its first run a false pass.
    povBar.dataset.parity = 'spider-web.pov-toggle';
    povBar.appendChild(_el('span', 'text-[11px] uppercase tracking-wider text-slate-500',
        'točka pogleda'));
    const povButtons = [];
    for (const [value, label] of [
        ...state.teams.map((t) => [`team:${t}`, t]),
        ['world', 'WORLD (ORACLE)'],
    ]) {
        const btn = _el('button', 'px-2 py-1 text-xs rounded font-mono border', label);
        btn.dataset.pov = value;
        povButtons.push(btn);
        btn.addEventListener('click', async () => {
            if (state.pov === value) return;
            state.pov = value;
            await goTo(state.tMs);
            paintPov();
        });
        povBar.appendChild(btn);
    }
    const paintPov = () => {
        for (const b of povButtons) {
            const on = b.dataset.pov === state.pov;
            b.className = 'px-2 py-1 text-xs rounded font-mono border '
                + (on ? 'bg-slate-700 text-slate-100 border-slate-500'
                      : 'bg-slate-900 text-slate-400 border-slate-800 hover:bg-slate-800');
        }
    };
    container.appendChild(povBar);

    // What this view IS and IS NOT. Under a team view the page withholds truth
    // it holds, and §6 requires the own-team simplification to be stated rather
    // than assumed — an unstated simplification is just an error.
    const povNote = _el('p', 'text-[11px] leading-relaxed mb-2');
    const paintPovNote = () => {
        const info = (state.snapshot && state.snapshot.information_state) || {};
        const withheld = (state.snapshot && state.snapshot.withheld_by_pov) || [];
        povNote.textContent = '';
        if (info.pov_unavailable) {
            povNote.className = 'text-[11px] leading-relaxed mb-2 text-amber-400';
            povNote.textContent = info.pov_unavailable;
            return;
        }
        if (!isTeamPov(state.pov)) {
            povNote.className = 'text-[11px] leading-relaxed mb-2 text-amber-500/80';
            povNote.textContent = 'ORACLE: vidiš vse, kar se je zgodilo, ne tega, '
                + 'kar je kdo vedel. Diagnostika, ne pogled igralca.';
            return;
        }
        const holder = Object.values(info.holders || {})[0] || {};
        const known = holder.known_enemy_count || 0;
        const unplaced = beliefRegions(holder).unplacedSubjects.length;
        povNote.className = 'text-[11px] leading-relaxed mb-2 text-slate-400';
        povNote.textContent =
            `Lege ${withheld.length} nasprotnikov so ZADRŽANE na strežniku, ne skrite `
            + 'pri risanju. Nasprotnik je narisan samo kot regija, ki jo je ta ekipa '
            + 'lahko sklepala, in ta se s časom širi. '
            + (known
                ? `Trenutno pozna ${known} ${known === 1 ? 'nasprotnika' : 'nasprotnikov'}.`
                : 'V tem trenutku ta ekipa ni vedela za nobenega nasprotnika.')
            + (unplaced
                ? ` Pri ${unplaced} od njih je regija že širša od `
                  + `${Math.round(horizonOf(holder))} enot, zato ni narisana: `
                  + 'ekipa ve, da obstaja, ne pa več kje je.'
                : '')
            + ' ⚠️ Lege soigralcev so prikazane kot znane — to je poenostavitev '
            + '(glasovni kanal ni zajet), ne meritev.';
    };
    container.appendChild(povNote);

    const canvas = document.createElement('canvas');
    canvas.className = 'w-full rounded border border-slate-800 bg-slate-950 cursor-move';
    canvas.dataset.parity = 'spider-web.web-canvas';
    canvas.style.height = '640px';
    container.appendChild(canvas);

    // ⚠️ Backing store sized to the element it is actually shown at, times the
    // device pixel ratio. A fixed 1100x640 buffer stretched across a wider
    // element resamples every line, and this drawing is nothing but lines.
    const sizeCanvas = () => {
        const ratio = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        canvas.width = Math.max(320, Math.round(rect.width * ratio));
        canvas.height = Math.max(240, Math.round(640 * ratio));
    };
    sizeCanvas();

    const redraw = () => render(canvas);
    window.addEventListener('resize', () => { sizeCanvas(); redraw(); });

    // Time scrubber. The steps are the prototype's, and 200 ms is the capture
    // interval — a smaller step would ask for a moment nothing was recorded at.
    const controls = _el('div', 'flex items-center gap-2 mt-3 flex-wrap');
    controls.dataset.parity = 'spider-web.timeline';
    const slider = document.createElement('input');
    slider.type = 'range';
    slider.min = '0';
    slider.max = String(Math.max(1000, snapshot.round_duration_ms || 600000));
    slider.step = '200';
    slider.value = String(state.tMs || 0);
    slider.className = 'flex-1 min-w-[240px]';
    const readout = _el('span', 'text-xs font-mono text-slate-300 tabular-nums',
        `t = ${state.tMs || 0} ms`);

    const goTo = async (nextMs) => {
        const clamped = Math.max(0, Math.min(Number(slider.max), Math.round(nextMs)));
        state.tMs = clamped;
        slider.value = String(clamped);
        readout.textContent = `t = ${clamped} ms`;
        const mine = ++loadId;
        let fresh;
        try {
            fresh = await loadMoment(roundId, clamped, state.pov);
        } catch {
            return;
        }
        if (mine !== loadId) return;
        state.snapshot = fresh;
        status.textContent = statusLine(state.snapshot);
        paintPovNote();
        paintPanels();
        redraw();
    };

    for (const [label, delta] of [['−1 s', -1000], ['−200 ms', -200],
                                  ['+200 ms', 200], ['+1 s', 1000]]) {
        const btn = _el('button', 'px-2 py-1 text-xs rounded bg-slate-800 '
            + 'hover:bg-slate-700 text-slate-200 font-mono', label);
        btn.addEventListener('click', () => goTo(state.tMs + delta));
        controls.appendChild(btn);
    }
    controls.appendChild(slider);
    controls.appendChild(readout);
    slider.addEventListener('change', () => goTo(Number(slider.value)));
    container.appendChild(controls);

    // ── The clock, and the snapshot's own integrity ──────────────────────────
    const panels = _el('div', 'grid gap-4 mt-4 md:grid-cols-2');

    const clockPanel = _el('div', 'rounded border p-3');
    clockPanel.style.borderColor = THEME.hairline;
    clockPanel.dataset.parity = 'spider-web.clock';
    const integrityPanel = _el('div', 'rounded border p-3');
    integrityPanel.style.borderColor = THEME.hairline;
    integrityPanel.dataset.parity = 'spider-web.snapshot-integrity';
    panels.appendChild(clockPanel);
    panels.appendChild(integrityPanel);
    container.appendChild(panels);

    const paintPanels = () => {
        const snap = state.snapshot || {};
        clockPanel.textContent = '';
        integrityPanel.textContent = '';

        clockPanel.appendChild(_el('h3',
            'text-[11px] uppercase tracking-wider mb-2', 'ura — tretji nasprotnik'));
        clockPanel.lastChild.style.color = THEME.label;
        for (const [name, team] of Object.entries(snap.clock || {})) {
            const { badge, reason } = clockBadge(team);
            const row = _el('div', 'mb-2');
            const head = _el('div', 'flex items-baseline justify-between gap-2');
            const label = _el('span', 'font-mono text-sm', name);
            label.style.color = name.toUpperCase() === 'AXIS' ? THEME.axis : THEME.allies;
            const tag = _el('span', 'text-[10px] font-mono px-1 rounded', badge);
            tag.style.color = THEME.textDim;
            tag.style.border = `1px solid ${THEME.hairline}`;
            head.appendChild(label);
            head.appendChild(tag);
            row.appendChild(head);

            const detail = _el('p', 'text-[11px] font-mono');
            detail.style.color = THEME.textDim;
            // ⛔ Driven by the VERDICT, not by whether `interval_ms` happens to
            // be set. With one or two observations at the same interval,
            // `infer_clock` returns `insufficient` and still keeps
            // `interval_ms` — so a truthiness test rendered the interval,
            // skipped the badge's explanation, and made a sparse clock look
            // like an ordinarily inferred one (Codex, #804).
            // ⛔ Only a CHECKED verdict may stand on its numbers alone. An
            // internally consistent clock with zero qualifying landings still
            // carries a non-null `interval_ms` (and `pass_ratio: null`), so
            // including it here left a row showing an interval with nothing to
            // say it was never checked (Codex, #804).
            const inferred = badge === 'VALIDATED' || badge === 'FAILED';
            const numbers = team && team.interval_ms
                ? `interval ${(team.interval_ms / 1000).toFixed(0)} s`
                  + (typeof team.time_to_next_wave_ms === 'number'
                      ? ` · do naslednjega vala ${(team.time_to_next_wave_ms / 1000).toFixed(1)} s`
                      : '')
                  // ⚠️ A ratio without its denominator is not evidence: 100%
                  // from two landings and 100% from thirty are different
                  // claims, and the payload carries the counts that separate
                  // them (Codex, #804).
                  + (typeof team.pass_ratio === 'number'
                      ? ` · preverba ${(team.pass_ratio * 100).toFixed(1)} %`
                        + (typeof team.landing_clusters === 'number'
                            ? ` (${team.passing_landing_clusters ?? '?'}/`
                              + `${team.landing_clusters} pristankov`
                              + (typeof team.timing_observations === 'number'
                                  ? `, ${team.timing_observations} opazovanj)`
                                  : ')')
                            : '')
                      : '')
                : '';
            detail.textContent = inferred && numbers
                ? numbers
                : [reason, numbers && `(${numbers})`].filter(Boolean).join(' ')
                  || 'ure za to ekipo ni bilo mogoče ugotoviti';
            row.appendChild(detail);
            clockPanel.appendChild(row);
        }
        // ⚠️ Derived from the actual verdicts. An unconditional sentence here
        // claimed both teams were UNVALIDATED and internally consistent, which
        // contradicted the badges above it whenever a team was UNAVAILABLE and
        // asserted the opposite of the backend for an INCONSISTENT one
        // (Codex, #804).
        const badges = Object.values(snap.clock || {}).map((t) => clockBadge(t).badge);
        const note = _el('p', 'text-[10px] leading-relaxed mt-1',
            badges.includes('VALIDATED') && !badges.includes('FAILED')
                ? 'VALIDATED pomeni: prestala neodvisno preverbo proti spawn '
                  + 'pristankom iz player_track (§5.3), z zamrznjenim pragom — '
                  + 'ne proti vrsticam, iz katerih je odmik nastal. Neposreden '
                  + 'zajem semena (C2) je močnejša potrditev in še ni na voljo.'
                : badges.includes('FAILED')
                    ? 'FAILED pomeni, da neodvisni pristanki OBSTAJAJO in odmik '
                      + 'ovržejo — ne da jih ni. To je močnejša ugotovitev od '
                      + 'nepreverjenosti in je ni mogoče brati kot »morda drži«.'
                // ⚠️ Nothing to reconstruct from is not the same as a
                // reconstruction that failed a check, and the sentence must
                // not mention an agreement figure that does not exist for this
                // round. Caught here rather than by a fifth review round, but
                // it is the same class as the two before it.
                : badges.every((x) => x === 'UNAVAILABLE')
                    ? 'Za to rundo ni upravičenih vrstic o spawn času, zato ura '
                      + 'ni bila niti izpeljana — to ni neuspela preverba, ampak '
                      + 'odsotnost vhoda.'
                    : 'Nobena ura tu ni prestala neodvisne preverbe; kjer je '
                      + 'odstotek skladnosti prikazan, je to ujemanje z lastnim '
                      + 'izvorom, ne dokaz.');
        note.style.color = THEME.label;
        clockPanel.appendChild(note);

        integrityPanel.appendChild(_el('h3',
            'text-[11px] uppercase tracking-wider mb-2', 'integriteta posnetka'));
        integrityPanel.lastChild.style.color = THEME.label;
        const policy = snap.capture_policy || {};
        // ⚠️ The WHOLE provenance. `manifest_version`, `manifest_count` and
        // `conflicting_flags` were dropped, so a reader could not tell a normal
        // single manifest from an ambiguous multi-manifest result — which is
        // exactly what decides whether a capability state can be trusted
        // (acceptance A6; Codex, #804).
        const facts = [
            ['zajem', `${policy.mode || 'unknown'}`
                + (policy.observation_interval_ms ? ` · ${policy.observation_interval_ms} ms` : '')],
            ['vir politike', policy.source || 'unknown'],
            ['verzija manifesta', policy.manifest_version ?? 'unknown'],
            ['manifestov', String(policy.manifest_count ?? 'unknown')],
            ['nasprotujočih zastavic', String(policy.conflicting_flags ?? 'unknown')],
            // ⚠️ PLAYERS, not lives or pairs. `Snapshot.overlap_conflicts`
            // counts each player whose life was ambiguous once, however many
            // candidates they had — the field's own docstring says so, and the
            // old label gave the number the wrong unit (Codex, #804).
            ['igralci s spornim življenjem', String(snap.overlap_conflicts ?? 'unknown')],
            ['igralci brez stanja', String(Object.keys(snap.gaps || {}).length)],
        ];
        if (Array.isArray(snap.withheld_by_pov) && snap.withheld_by_pov.length) {
            facts.push(['zadržani po pogledu', String(snap.withheld_by_pov.length)]);
        }
        for (const [k, v] of facts) {
            const row = _el('div', 'flex justify-between text-[11px] font-mono');
            const a = _el('span', '', k); a.style.color = THEME.textDim;
            const b = _el('span', '', v); b.style.color = THEME.text;
            row.appendChild(a); row.appendChild(b);
            integrityPanel.appendChild(row);
        }
        const caps = capabilityRows(policy);
        if (caps.length) {
            const capHead = _el('p', 'text-[10px] uppercase tracking-wider mt-2 mb-1',
                'zmožnosti zajema');
            capHead.style.color = THEME.label;
            integrityPanel.appendChild(capHead);
            // ⚠️ A6 asks every semantic sensor to declare its schedule,
            // interval, integration rule, version and completeness. The
            // manifest records NONE of those — it carries `flag -> state` and
            // nothing else — so the panel cannot publish them without
            // inventing them. Naming the gap is the only honest option: an
            // unqualified list would imply the requirement is met
            // (Codex, #804).
            const capGap = _el('p', 'text-[10px] mb-1 leading-relaxed',
                '⚠️ Manifest beleži samo stanje zastavice. Razpored senzorja '
                + '(dogodkovni/fiksni/prilagodljivi), interval, pravilo '
                + 'integracije, verzija in popolnost NISO zajeti, zato jih tu '
                + 'ni — to je vrzel v zajemu (A6), ne v tem panelu.');
            capGap.style.color = THEME.label;
            integrityPanel.appendChild(capGap);
            for (const c of caps) {
                const row = _el('div', 'flex justify-between text-[11px] font-mono');
                const a = _el('span', '', c.name); a.style.color = THEME.textDim;
                const b = _el('span', '', c.state);
                // ⛔ `unknown` gets its own colour, never the one `disabled`
                // gets: rendering them alike turns "we do not know" into "it
                // was off", which is the claim the manifest exists to prevent.
                b.style.color = c.state === 'enabled' ? THEME.positive
                    : c.state === 'disabled' ? THEME.negative : THEME.label;
                row.appendChild(a); row.appendChild(b);
                integrityPanel.appendChild(row);
            }
        }
        const acc = snap.reconstruction_accuracy || {};
        if (acc.measured_at) {
            // ⚠️ Including what was EXCLUDED and what it was checked against.
            // Dropping `excluded` hid that the victim coordinate was left out
            // because it shares a writer with the reconstructed track — the
            // single fact that keeps the measurement from being circular — and
            // dropping `sources` hid that two separately written pipelines
            // agreed (Codex, #804).
            const samples = acc.samples && typeof acc.samples === 'object'
                ? Object.entries(acc.samples).map(([k, v]) => `${k} ${v}`).join(', ')
                : null;
            const prov = _el('p', 'text-[10px] mt-2 leading-relaxed',
                `Napaka lege izmerjena ${acc.measured_at} na ${acc.rounds} rundah `
                + `(${acc.script}). Enota: ${acc.unit}.`
                + (samples ? ` Vzorci: ${samples}.` : '')
                + (Array.isArray(acc.sources) ? ` Viri: ${acc.sources.join(', ')}.` : '')
                + (acc.excluded ? ` Izključeno: ${acc.excluded}.` : ''));
            prov.style.color = THEME.label;
            integrityPanel.appendChild(prov);
        }
    };

    const legend = _el('p', 'text-[11px] text-slate-500 mt-2 leading-relaxed',
        'Obroč okoli igralca je IZMERJENA negotovost lege (p90 za starost vzorca); '
        + 'črtkan pomeni sporno življenje, kjer rekonstrukcija ne ve, katero od '
        + 'prekrivajočih se življenj je pravo. Niti so geometrijska razdalja, '
        + 'ne vidno polje — modre med soigralci, rdeče med nasprotniki, polne '
        + 'tam, kjer je bil spopad odprt. ⚠️ Odprt spopad tracker drži do 15 s '
        + 'po zadnjem zadetku, zato polna nit ne pomeni »zdaj se streljata«. '
        + 'Vlečenje vrti, kolešček približa.');
    container.appendChild(legend);

    bindCamera(canvas, redraw);
    paintPov();
    paintPovNote();
    paintPanels();
    redraw();
}
