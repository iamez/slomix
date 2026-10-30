// Execute the WHOLE shipped module, exposing existing closures only for the test.
// Canvas/network are recording stubs: not a real browser or deployed UI proof.
import fs from 'node:fs';
import vm from 'node:vm';

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const context = vm.createContext({ console });
const source = fs.readFileSync('website/js/replay.js', 'utf8');
const module = new vm.SourceTextModule(source +
    '\nexport { drawTracks, _findPlayerPos, replayState, CANVAS_W, CANVAS_H };', { context });
await module.link(async (specifier) => {
    if (specifier === './utils.js') {
        return new vm.SyntheticModule(['API_BASE', 'fetchJSON'], function () {
            this.setExport('API_BASE', '/api');
            this.setExport('fetchJSON', () => { throw new Error('unexpected network call'); });
        }, { context });
    }
    if (specifier === './route-registry.js?v=20260720-ssd-gsid') {
        return new vm.SyntheticModule(['getRouteHash'], function () {
            this.setExport('getRouteHash', () => { throw new Error('unexpected routing call'); });
        }, { context });
    }
    throw new Error(`unexpected import: ${specifier}`);
});
await module.evaluate();
const { drawTracks, _findPlayerPos, replayState, CANVAS_W, CANVAS_H } = module.namespace;
const track = { guid: 'G1', name: 'Synthetic', team: 'AXIS', class: 'MEDIC',
    spawn_time: 0, death_time: 20000, path: input.path };
const strokes = [], dots = [];
let points = [];
const ctx = {
    beginPath() { points = []; },
    moveTo(x, y) { points.push([x, y]); },
    lineTo(x, y) { points.push([x, y]); },
    stroke() { if (points.length) strokes.push(points); },
    arc(x, y) { dots.push([x, y]); },
    fill() {}, fillRect() {}, fillText() {},
};
drawTracks(ctx, [track], input.time, { mapcoordsmins: [0, CANVAS_H], mapcoordsmaxs: [CANVAS_W, 0] });
replayState.tracks = { tracks: [track] };
const position = _findPlayerPos('Synthetic', input.time);
console.log(JSON.stringify({ strokes, dots, position }));
