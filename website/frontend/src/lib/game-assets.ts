/**
 * Game asset path helpers — maps weapon keys, class names, and map names
 * to extracted PNG icons from ET:Legacy pk3 files.
 *
 * Assets live at /assets/game/{category}/{name}.png
 */

const ASSET_BASE = '/assets/game';

// Map API weapon keys/names to extracted icon filenames
const WEAPON_ICON_MAP: Record<string, string> = {
  knife: 'knife',
  luger: 'luger',
  colt: 'colt',
  mp40: 'mp40',
  thompson: 'thompson',
  sten: 'sten',
  fg42: 'fg42',
  mg42: 'mg42',
  browning: 'browning',
  kar98: 'kar98',
  k43: 'kar98',
  garand: 'm1_garand',
  m1garand: 'm1_garand',
  mauser: 'mauser',
  panzerfaust: 'panzerfaust',
  flamethrower: 'flamethrower',
  mortar: 'mortar',
  grenade: 'grenade',
  pineapple: 'pineapple',
  dynamite: 'dynamite',
  landmine: 'landmine',
  satchel: 'satchel',
  smokegrenade: 'smoke_grenade',
  smoke: 'smoke_grenade',
  syringe: 'syringe',
  ammopack: 'ammo_pack',
  medpack: 'med_pack',
  pliers: 'pliers',
  binoculars: 'binoculars',
  radio: 'field_radio',
  airstrike: 'field_radio',
  artillery: 'binoculars',
  silencedpistol: 'silenced_pistol',
  poisonsyringe: 'poison_syringe',
  riflegrenade: 'kar98_rifle_grenade',
};

const CLASS_ICON_MAP: Record<string, string> = {
  soldier: 'soldier',
  medic: 'medic',
  engineer: 'engineer',
  fieldops: 'fieldops',
  'field ops': 'fieldops',
  covertops: 'covertops',
  'covert ops': 'covertops',
};

function normalize(name: string): string {
  return (name || '')
    .toLowerCase()
    .replace(/^ws[_\s]+/, '')
    .replace(/[_\s-]+/g, '')
    .trim();
}

/** Get weapon icon URL. Returns null if no matching icon. */
export function weaponIcon(weaponKeyOrName: string): string | null {
  const key = normalize(weaponKeyOrName);
  const file = WEAPON_ICON_MAP[key];
  return file ? `${ASSET_BASE}/weapons/${file}.png` : null;
}

/** Get class icon URL. Returns null if no matching icon. */
export function classIcon(className: string): string | null {
  const key = normalize(className);
  const file = CLASS_ICON_MAP[key];
  return file ? `${ASSET_BASE}/classes/${file}.png` : null;
}

/** Get class portrait URL (Allied or Axis). */
export function classPortrait(className: string, team: 'allied' | 'axis' = 'allied'): string | null {
  const key = normalize(className);
  const file = CLASS_ICON_MAP[key];
  return file ? `${ASSET_BASE}/classes/${team}_${file}.png` : null;
}

/** Get map levelshot URL. Returns fallback placeholder path if not found. */
export function mapLevelshot(mapName: string): string {
  const clean = (mapName || '')
    .replace(/^maps[\\/]/, '')
    .replace(/\.(bsp|pk3|arena)$/i, '')
    .trim();
  return `${ASSET_BASE}/levelshots/${clean}.png`;
}

/** Get medal icon URL. */
export function medalIcon(medalName: string): string {
  const key = normalize(medalName);
  const nameMap: Record<string, string> = {
    accuracy: 'medal_accuracy',
    battlesense: 'medal_battle_sense',
    engineer: 'medal_engineer',
    explosives: 'medal_explosives',
    firstaid: 'medal_first_aid',
    lightweapons: 'medal_light_weapons',
    signals: 'medal_signals',
  };
  const file = nameMap[key] ?? `medal_${key}`;
  return `${ASSET_BASE}/medals/${file}.png`;
}

/** Get rank icon URL (rank 2-11). */
export function rankIcon(rankNum: number): string {
  const n = Math.max(2, Math.min(11, rankNum));
  return `${ASSET_BASE}/ranks/rank_${String(n).padStart(2, '0')}.png`;
}

/** Get team flag/logo URL. */
export function teamIcon(team: 'allied' | 'axis'): string {
  return `${ASSET_BASE}/teams/button_${team}.png`;
}

/** ET Logo URL. */
export function etLogo(): string {
  return `${ASSET_BASE}/teams/et_logo.png`;
}
