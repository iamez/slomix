// Whole shipped module, recording canvas/DOM only: no browser or network.
import fs from 'node:fs';
import vm from 'node:vm';
const life = JSON.parse(fs.readFileSync(0, 'utf8'));
const strokes = [];
const fills = [];
let points = [];
const ctx = {
    beginPath() { points = []; }, moveTo(x, y) { points.push([x, y]); },
    lineTo(x, y) { points.push([x, y]); }, stroke() { strokes.push(points); },
    save() {}, restore() {}, scale() {}, clearRect() {}, setLineDash() {},
    arc() {}, fill() { fills.push(points); }, fillText() {}, closePath() {},
};
const caption = { textContent: '' };
const status = { textContent: '' };
const narrative = { textContent: '' };
const lives = { innerHTML: '', querySelectorAll: () => [] };
const strip = { innerHTML: '', classList: { add() {}, remove() {} } };
const canvas = { clientWidth: 1000, clientHeight: 1000, getContext: () => ctx };
const context = vm.createContext({ console, window: { devicePixelRatio: 1 },
    document: { getElementById(id) { return {
        'proximity-journey-canvas': canvas, 'proximity-journey-timeline': strip,
        'proximity-journey-timeline-caption': caption,
        'proximity-journey-status': status, 'proximity-journey-lives': lives,
        'proximity-journey-narrative': narrative,
    }[id] || null; } },
});
const source = fs.readFileSync('website/js/proximity.js', 'utf8');
const module = new vm.SourceTextModule(source + `
mapTransformConfig = {maps: {supply: {mapcoordsmins:[0,1000], mapcoordsmaxs:[1000,0]}}};
objectiveZonesConfig = {maps:{}};
export {drawJourneyLife, renderJourneyTimeline, renderJourney};`, { context });
await module.link(async (name) => {
    if (name === './journey-position.js') {
        return new vm.SourceTextModule(fs.readFileSync('website/js/journey-position.js', 'utf8'), { context });
    }
    const exports = name === './utils.js'
        ? ['API_BASE', 'fetchJSON', 'formatNumber', 'escapeHtml'] : ['getRouteHash'];
    return new vm.SyntheticModule(exports, function () {
        for (const key of exports) this.setExport(key, key === 'API_BASE' ? '/api' :
            key === 'fetchJSON' ? () => { throw new Error('Unexpected network'); } : String);
    }, { context });
});
await module.evaluate();
if (life.payload) {
    module.namespace.renderJourney(life.payload);
    await module.namespace.drawJourneyLife(life.payload.lives[0], 'supply');
} else {
    await module.namespace.drawJourneyLife(life, 'supply');
    module.namespace.renderJourneyTimeline(life);
}
console.log(JSON.stringify({strokes, fills, caption: caption.textContent, bands: strip.innerHTML,
    status: status.textContent, lives: lives.innerHTML, narrative: narrative.textContent}));
