/**
 * Map transform + image resolution for canvas pages.
 *
 * Two known bugs this module retires (docs/design/00 §4, 08):
 *  - the alias table for map names lived only in sessions.js:23-64 and was
 *    unreachable from the drawing code, so etl_supply / sp_delivery_te /
 *    et_beach 404'd although their images exist — the aliases live HERE now,
 *    next to the transform lookup;
 *  - prototypes hand-copied seven maps into a constant and dropped
 *    sw_goldrush_te; this module always reads map_transforms.json (21 maps)
 *    at runtime, never a hand-written table.
 */

import { stripEtColors } from '../names';

/** Re-exported ON PURPOSE, not for convenience: this module used to define
 *  its own stripEtColors with `\^.` under a comment claiming legacy parity,
 *  and a behavioral test cannot catch that copy coming back if nothing
 *  imports it — so names.test.ts asserts FUNCTION IDENTITY through this
 *  re-export (`fromGeo === stripEtColors`), which fails the moment anyone
 *  redefines a local one here. */
export { stripEtColors };

export interface MapTransformEntry {
  map_name: string;
  image: string;
  size: [number, number];
  mapcoordsmins: [number, number];
  mapcoordsmaxs: [number, number];
}

export interface MapTransformConfig {
  maps: Record<string, MapTransformEntry>;
}

export const MAP_TRANSFORM_CONFIG_URL = '/assets/maps/proximity/map_transforms.json';
export const OBJECTIVE_ZONES_CONFIG_URL = '/assets/maps/proximity/objective_zones.json';

export function normalizeMapKey(mapName: string | null | undefined): string {
  // The strip comes from lib/names — this module used to hand-roll `\^.`
  // under a comment claiming it was "the same strip as legacy stripEtColors",
  // and it was not: the canonical class everywhere else (backend
  // et_constants.py, six legacy JS files) is `\^[0-9a-zA-Z]`. Importing the
  // one copy retires both the drift and the lying comment (Codex on #842).
  return stripEtColors(mapName ?? '').trim().toLowerCase();
}

/**
 * Alias -> canonical transform/image key. Transferred from sessions.js
 * MAP_IMAGE_MAP (the pairs whose value differs from the key); extend here,
 * never inline in a page.
 */
export const MAP_KEY_ALIASES: Readonly<Record<string, string>> = Object.freeze({
  etl_supply: 'supply',
  etl_adlernest_a3: 'etl_adlernest',
  sp_delivery_te: 'etl_sp_delivery',
  etl_delivery: 'etl_sp_delivery',
  etl_battery: 'sw_battery',
  etl_oasis: 'sw_oasis_b3',
  etl_frostbite: 'frostbite',
  etl_goldrush: 'sw_goldrush_te',
  etl_brewdog: 'et_brewdog',
  etl_erdenberg: 'erdenberg_t2',
  etl_bradendorf: 'etl_braundorf',
  etl_escape2: 'te_escape2',
  et_beach: 'etl_beach',
});

export function resolveMapKey(mapName: string | null | undefined): string {
  const key = normalizeMapKey(mapName);
  return MAP_KEY_ALIASES[key] ?? key;
}

export function getMapTransformEntry(
  config: MapTransformConfig | null | undefined,
  mapName: string | null | undefined,
): MapTransformEntry | null {
  if (!config?.maps) return null;
  const key = resolveMapKey(mapName);
  return config.maps[key] ?? (mapName ? config.maps[mapName] ?? null : null);
}

type FetchLike = (url: string) => Promise<{ ok: boolean; json: () => Promise<unknown> }>;

let transformConfigPromise: Promise<MapTransformConfig | null> | null = null;

/**
 * Load (and memoise) map_transforms.json. Degrades to null on failure — the
 * caller must render "no calibration for this map", never an empty canvas.
 */
export function loadMapTransformConfig(
  fetchImpl: FetchLike = fetch,
): Promise<MapTransformConfig | null> {
  if (!transformConfigPromise) {
    transformConfigPromise = fetchImpl(MAP_TRANSFORM_CONFIG_URL)
      .then((res) => (res.ok ? (res.json() as Promise<MapTransformConfig>) : null))
      .catch(() => null);
  }
  return transformConfigPromise;
}

/** Test hook: forget the memoised config. */
export function resetMapTransformConfigCache(): void {
  transformConfigPromise = null;
}
