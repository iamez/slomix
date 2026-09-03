import { existsSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { mapImageFor, mapLabel, normalizeMapKey } from './maps';

/**
 * The alias table points at files. A path that no longer exists renders a
 * broken image on every session row (stats 2.0 puts a levelshot on each
 * evening — docs/design/18 §B), so the table is measured against the disk,
 * not trusted. `website/` is the static root the backend mounts at `/`
 * (main.py: StaticFiles(static_dir, html=True)), which is why the module
 * returns absolute paths.
 */
const WEBSITE_ROOT = resolve(__dirname, '../../../..');

// Every map name that has appeared in rounds (round_number IN (1,2)),
// measured 2026-09-03 — the top 20 by round count, plus the oddities.
const NAMES_IN_PLAY = [
  'te_escape2', 'etl_adlernest', 'supply', 'etl_sp_delivery', 'sw_goldrush_te',
  'etl_frostbite', 'et_brewdog', 'erdenberg_t2', 'braundorf_b4', 'etl_ice',
  'et_beach', 'decay_sw', 'goldrush', 'sp_delivery_te', 'bremen_b3', 'adlernest',
  'radar', 'etl_supply', 'sw_oasis_b3',
];

describe('lib/maps against the disk', () => {
  it('every levelshot the table names exists under website/', () => {
    const source = readdirSync(resolve(__dirname)).length; // sanity: dir readable
    expect(source).toBeGreaterThan(0);
    const missing: string[] = [];
    for (const name of [...NAMES_IN_PLAY, 'fueldump', 'oasis', 'battery', 'railgun', 'missile_b4']) {
      const path = mapImageFor(name);
      if (!existsSync(resolve(WEBSITE_ROOT, path.replace(/^\//, '')))) missing.push(`${name} -> ${path}`);
    }
    expect(missing).toEqual([]);
  });

  it('every map that has been played resolves to a real levelshot, not the generic fallback', () => {
    const generic = NAMES_IN_PLAY.filter((n) => mapImageFor(n).endsWith('map_generic.svg'));
    expect(generic).toEqual([]);
  });

  it('a name the table has never seen gets the generic svg, which exists', () => {
    const path = mapImageFor('mp_sillyctf');
    expect(path).toBe('/assets/maps/map_generic.svg');
    expect(existsSync(resolve(WEBSITE_ROOT, path.slice(1)))).toBe(true);
  });

  it('normalises server spellings the way the legacy helper did', () => {
    expect(normalizeMapKey('maps/ETL_Adlernest.bsp')).toBe('etl_adlernest');
    expect(mapLabel('etl_sp_delivery')).toBe('etl sp delivery');
  });
});
