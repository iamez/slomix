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

/** Team colours. Axis warm, Allies cool — the same pairing the rest of the site uses. */
const TEAM_COLOR = {
    AXIS: '#f0a868',
    ALLIES: '#6aa9f0',
};
const NEUTRAL = '#8892a4';

let loadId = 0;

const state = {
    roundId: null,
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
function project(x, y, z, cam, view) {
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
function viewportFor(mesh, canvas, cam) {
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
    return {
        cx: canvas.width / 2 - ((lo.x + hi.x) / 2) * scale,
        cy: canvas.height / 2 - ((lo.y + hi.y) / 2) * scale,
        scale,
        ...mid,
    };
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
        ctx.fillStyle = `rgba(${Math.round(96 + 104 * t)}, ${Math.round(132 + 96 * t)}, ${Math.round(176 + 74 * t)}, ${shade})`;
        ctx.beginPath();
        ctx.moveTo(face.pts[0].x, face.pts[0].y);
        ctx.lineTo(face.pts[1].x, face.pts[1].y);
        ctx.lineTo(face.pts[2].x, face.pts[2].y);
        ctx.closePath();
        ctx.fill();
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
        ctx.fillStyle = p.alive === false ? '#00000000' : color;
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
    ctx.fillStyle = '#c8d2e0';
    ctx.font = '11px ui-monospace, monospace';
    const placed = [];
    for (const l of labels) {
        if (placed.some((q) => Math.abs(q.x - l.x) < 70 && Math.abs(q.y - l.y) < 13)) {
            continue;
        }
        placed.push(l);
        ctx.fillText(l.text, l.x, l.y);
    }
}

function render(canvas) {
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#0a0d14';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    if (!state.mesh) return;
    const view = viewportFor(state.mesh, canvas, state.camera);
    drawFloors(ctx, state.mesh, state.camera, view);
    if (state.snapshot && Array.isArray(state.snapshot.players)) {
        drawPlayers(ctx, state.snapshot.players, state.camera, view);
    }
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

async function loadMoment(roundId, tMs) {
    const snapshot = await fetchJSON(
        `${API_BASE}/replay/round/${encodeURIComponent(roundId)}/web?t=${Math.round(tMs)}`
    );
    state.snapshot = snapshot;
    return snapshot;
}

// ── View ──────────────────────────────────────────────────────────────────────

function statusLine(snapshot) {
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
    state.roundId = roundId;

    container.appendChild(_el('p', 'text-slate-400 text-sm py-12 text-center',
        'Nalagam rundo…'));

    // ⚠️ Opening at t=0 shows an empty map: nobody has spawned yet, and the
    // page would read as "nobody was there". The payload says when the round
    // first has anybody, so the first frame is a moment that exists.
    let snapshot;
    try {
        snapshot = await loadMoment(roundId, state.tMs || 0);
        if (!state.tMs && snapshot && snapshot.first_position_ms) {
            state.tMs = snapshot.first_position_ms;
            snapshot = await loadMoment(roundId, state.tMs);
        }
    } catch {
        if (myLoad !== loadId) return;
        container.textContent = '';
        container.appendChild(_el('p', 'text-rose-400 text-sm py-12 text-center',
            `Runde ${roundId} ni bilo mogoče naložiti.`));
        return;
    }
    if (myLoad !== loadId) return;

    const mapName = (snapshot.players || []).length ? snapshot.map_name : snapshot.map_name;
    await loadMesh(mapName || '');
    if (myLoad !== loadId) return;

    container.textContent = '';

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

    const canvas = document.createElement('canvas');
    canvas.className = 'w-full rounded border border-slate-800 bg-slate-950 cursor-move';
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
        try {
            await loadMoment(roundId, clamped);
        } catch {
            return;
        }
        if (mine !== loadId) return;
        status.textContent = statusLine(state.snapshot);
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

    const legend = _el('p', 'text-[11px] text-slate-500 mt-2 leading-relaxed',
        'Obroč okoli igralca je IZMERJENA negotovost lege (p90 za starost vzorca); '
        + 'črtkan pomeni sporno življenje, kjer rekonstrukcija ne ve, katero od '
        + 'prekrivajočih se življenj je pravo. Vlečenje vrti, kolešček približa.');
    container.appendChild(legend);

    bindCamera(canvas, redraw);
    redraw();
}
