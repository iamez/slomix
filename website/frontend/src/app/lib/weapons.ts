/**
 * The per-round weapon table names weapons by their stats token (`WS_MP40`,
 * `WS_KNIFE_KBAR`); the profile's per-weapon table already receives labels
 * from the backend (`Mp40`, `Knife Kbar`). One label here, so a token never
 * reaches a visitor and the two tables agree on a name.
 */
const LABELS: Record<string, string> = {
  WS_KNIFE: 'Knife', WS_KNIFE_KBAR: 'Ka-Bar knife', WS_LUGER: 'Luger', WS_COLT: 'Colt',
  WS_MP40: 'MP40', WS_THOMPSON: 'Thompson', WS_STEN: 'Sten', WS_FG42: 'FG42',
  WS_PANZERFAUST: 'Panzerfaust', WS_BAZOOKA: 'Bazooka', WS_FLAMETHROWER: 'Flamethrower',
  WS_GRENADE: 'Grenade', WS_MORTAR: 'Mortar', WS_MORTAR2: 'Mortar', WS_DYNAMITE: 'Dynamite',
  WS_AIRSTRIKE: 'Airstrike', WS_ARTILLERY: 'Artillery', WS_SATCHEL: 'Satchel',
  WS_GRENADELAUNCHER: 'Grenade launcher', WS_LANDMINE: 'Landmine', WS_MG42: 'MG42',
  WS_BROWNING: 'Browning', WS_CARBINE: 'Carbine', WS_KAR98: 'Kar98', WS_GARAND: 'Garand',
  WS_K43: 'K43', WS_MP34: 'MP34', WS_SYRINGE: 'Syringe', WS_SMOKE: 'Smoke',
};

/** `WS_THOMPSON` → `Thompson`; an unknown token loses its prefix and its
 *  shouting, never its identity (`WS_NEW_THING` → `New thing`). */
export function weaponLabel(token: string): string {
  const known = LABELS[token];
  if (known) return known;
  const bare = token.replace(/^WS_/, '').replace(/_/g, ' ').toLowerCase();
  return bare.charAt(0).toUpperCase() + bare.slice(1);
}

/** The engine's weapon_t numbers → names, for fields that carry the number
 *  (proximity weapon_id, the spider web's `weapon` at a sample). One copy:
 *  it used to live in ProximityPlayerPage alone. */
export const WEAPON_NAMES: Record<number, string> = {
  3: 'Knife', 8: 'MP40', 9: 'Thompson', 10: 'Sten',
  15: 'Panzerfaust', 19: 'FG42', 23: 'Garand', 28: 'K43',
  32: 'Colt', 33: 'Luger', 35: 'Grenade', 36: 'Grenade',
  44: 'Landmine', 47: 'Mortar', 50: 'Dynamite', 57: 'MG42',
};
