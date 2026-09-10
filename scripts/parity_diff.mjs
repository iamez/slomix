// parity_diff.mjs old.json new.json — compares two inventory manifests
// (audit_website_browser.mjs --manifest) and prints added/removed panels,
// columns, tabs and api paths per route. Exit 1 when anything differs, so
// CI can gate on it once the new app claims a route.
//
// H2 of docs/design/09: the frozen legacy inventory is the yardstick;
// "does the new session-detail have all 22 columns" becomes a diff, not a
// manual count. Legacy panels key by heading text, new pages by
// data-parity keys — the diff reports both channels and lets the reader
// map them; parity is claimed key-by-key, never by silence.
import { readFileSync } from 'node:fs';

const [oldPath, newPath] = process.argv.slice(2);
if (!oldPath || !newPath) {
    process.stderr.write('usage: node scripts/parity_diff.mjs <old-inventory.json> <new-inventory.json>\n');
    process.exit(2);
}

const load = (p) => JSON.parse(readFileSync(p, 'utf8')).routes ?? {};
const a = load(oldPath);
const b = load(newPath);

const diffList = (xs = [], ys = []) => ({
    removed: xs.filter((x) => !ys.includes(x)),
    added: ys.filter((y) => !xs.includes(y)),
});

let differences = 0;
const routeNames = [...new Set([...Object.keys(a), ...Object.keys(b)])].sort();
for (const name of routeNames) {
    const ra = a[name];
    const rb = b[name];
    if (!ra || !rb) {
        differences += 1;
        process.stdout.write(`${name}: ${!ra ? 'only in NEW' : 'only in OLD'}\n`);
        continue;
    }
    const lines = [];
    for (const field of ['apiPaths', 'panelTitles', 'tabs', 'dataParityKeys']) {
        const { removed, added } = diffList(ra[field], rb[field]);
        for (const r of removed) lines.push(`  - ${field}: ${r}`);
        for (const add of added) lines.push(`  + ${field}: ${add}`);
    }
    const tables = [...new Set([
        ...Object.keys(ra.tableColumns ?? {}),
        ...Object.keys(rb.tableColumns ?? {}),
    ])];
    for (const t of tables) {
        const { removed, added } = diffList(ra.tableColumns?.[t], rb.tableColumns?.[t]);
        for (const r of removed) lines.push(`  - column[${t}]: ${r}`);
        for (const add of added) lines.push(`  + column[${t}]: ${add}`);
    }
    if ((ra.canvasCount ?? 0) !== (rb.canvasCount ?? 0)) {
        lines.push(`  ~ canvasCount: ${ra.canvasCount} -> ${rb.canvasCount}`);
    }
    if (lines.length) {
        differences += lines.length;
        process.stdout.write(`${name}:\n${lines.join('\n')}\n`);
    }
}

process.stdout.write(differences === 0
    ? 'parity_diff: identical\n'
    : `parity_diff: ${differences} difference(s)\n`);
process.exit(differences === 0 ? 0 : 1);
