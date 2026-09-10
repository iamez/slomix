/**
 * Map naming and levelshots — the legacy helpers PROMOTED to a shared
 * module. In the legacy tree normalizeMapKey/mapLabel/mapImageFor lived
 * only in sessions2.js (duplicated variants in sessions.js,
 * session-detail.js, proximity.js), and the maps page — of all pages — used
 * none of them: it rendered raw keys with no levelshots. One module, every
 * page (docs/design batch-3 port decision).
 *
 * The alias table is sessions2.js:9-49 verbatim; the fuzzy fallback in
 * mapImageFor is the legacy algorithm unchanged (it exists because server
 * map names drift across versions — etl_/sw_/et_ prefixes, _a3/_b4
 * suffixes).
 */

const MAP_IMAGE_MAP: Record<string, string> = {
  battery: 'assets/maps/levelshots/battery.png',
  fueldump: 'assets/maps/levelshots/fueldump.png',
  goldrush: 'assets/maps/levelshots/goldrush.png',
  oasis: 'assets/maps/levelshots/oasis.png',
  radar: 'assets/maps/levelshots/radar.png',
  railgun: 'assets/maps/levelshots/railgun.png',
  supply: 'assets/maps/levelshots/supply.png',
  etl_supply: 'assets/maps/levelshots/supply.png',
  adlernest: 'assets/maps/levelshots/adlernest.png',
  etl_adlernest: 'assets/maps/levelshots/etl_adlernest.png',
  etl_adlernest_a3: 'assets/maps/levelshots/etl_adlernest.png',
  etl_sp_delivery: 'assets/maps/levelshots/etl_sp_delivery.png',
  sp_delivery_te: 'assets/maps/levelshots/etl_sp_delivery.png',
  etl_delivery: 'assets/maps/levelshots/etl_sp_delivery.png',
  etl_battery: 'assets/maps/levelshots/sw_battery.png',
  sw_battery: 'assets/maps/levelshots/sw_battery.png',
  etl_oasis: 'assets/maps/levelshots/sw_oasis_b3.png',
  sw_oasis_b3: 'assets/maps/levelshots/sw_oasis_b3.png',
  etl_frostbite: 'assets/maps/levelshots/frostbite.png',
  frostbite: 'assets/maps/levelshots/frostbite.png',
  etl_goldrush: 'assets/maps/levelshots/sw_goldrush_te.png',
  sw_goldrush_te: 'assets/maps/levelshots/sw_goldrush_te.png',
  etl_brewdog: 'assets/maps/levelshots/et_brewdog.png',
  et_brewdog: 'assets/maps/levelshots/et_brewdog.png',
  etl_erdenberg: 'assets/maps/levelshots/erdenberg_t2.png',
  erdenberg_t2: 'assets/maps/levelshots/erdenberg_t2.png',
  etl_bradendorf: 'assets/maps/levelshots/etl_braundorf.png',
  etl_braundorf: 'assets/maps/levelshots/etl_braundorf.png',
  braundorf_b4: 'assets/maps/levelshots/braundorf_b4.png',
  etl_escape2: 'assets/maps/levelshots/te_escape2.png',
  te_escape2: 'assets/maps/levelshots/te_escape2.png',
  etl_beach: 'assets/maps/levelshots/etl_beach.png',
  et_beach: 'assets/maps/levelshots/etl_beach.png',
  etl_base: 'assets/maps/levelshots/etl_base.png',
  etl_ice: 'assets/maps/levelshots/etl_ice.png',
  bremen_b3: 'assets/maps/levelshots/bremen_b3.png',
  decay_sw: 'assets/maps/levelshots/decay_sw.png',
  missile_b3: 'assets/maps/levelshots/missile_b3.png',
  missile_b4: 'assets/maps/levelshots/missile_b4.png',
};

export function normalizeMapKey(mapName: string | null | undefined): string {
  const raw = (mapName ?? '').toString().trim().toLowerCase();
  if (!raw) return '';
  return raw
    .replace(/^maps[\\/]/, '')
    .replace(/\.(bsp|pk3|arena)$/i, '')
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '');
}

export function mapLabel(mapName: string | null | undefined): string {
  return (mapName || 'Unknown')
    .toString()
    .replace(/^maps[\\/]/, '')
    .replace(/\.(bsp|pk3|arena)$/i, '')
    .replace(/_/g, ' ');
}

/** Levelshot path (absolute from the site root — the app lives at /app/). */
export function mapImageFor(mapName: string | null | undefined): string {
  const key = normalizeMapKey(mapName);
  if (MAP_IMAGE_MAP[key]) return `/${MAP_IMAGE_MAP[key]}`;

  const trimmed = key.replace(/^etl_/, '').replace(/^sw_/, '').replace(/^et_/, '');
  for (const candidate of [trimmed, `etl_${trimmed}`, `sw_${trimmed}`, `et_${trimmed}`, key]) {
    if (MAP_IMAGE_MAP[candidate]) return `/${MAP_IMAGE_MAP[candidate]}`;
  }

  const keyCompact = key.replace(/_/g, '');
  for (const [mapKey, mapPath] of Object.entries(MAP_IMAGE_MAP)) {
    const mapCompact = mapKey.replace(/_/g, '');
    if (key.includes(mapKey) || mapKey.includes(key) || keyCompact.includes(mapCompact) || mapCompact.includes(keyCompact)) {
      return `/${mapPath}`;
    }
  }
  return '/assets/maps/map_generic.svg';
}
