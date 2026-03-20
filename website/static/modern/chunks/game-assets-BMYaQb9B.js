const n = "/assets/game", o = {
  knife: "knife",
  luger: "luger",
  colt: "colt",
  mp40: "mp40",
  thompson: "thompson",
  sten: "sten",
  fg42: "fg42",
  mg42: "mg42",
  browning: "browning",
  kar98: "kar98",
  k43: "kar98",
  garand: "m1_garand",
  m1garand: "m1_garand",
  mauser: "mauser",
  panzerfaust: "panzerfaust",
  flamethrower: "flamethrower",
  mortar: "mortar",
  grenade: "grenade",
  pineapple: "pineapple",
  dynamite: "dynamite",
  landmine: "landmine",
  satchel: "satchel",
  smokegrenade: "smoke_grenade",
  smoke: "smoke_grenade",
  syringe: "syringe",
  ammopack: "ammo_pack",
  medpack: "med_pack",
  pliers: "pliers",
  binoculars: "binoculars",
  radio: "field_radio",
  airstrike: "field_radio",
  artillery: "binoculars",
  silencedpistol: "silenced_pistol",
  poisonsyringe: "poison_syringe",
  riflegrenade: "kar98_rifle_grenade"
};
function s(e) {
  return (e || "").toLowerCase().replace(/^ws[_\s]+/, "").replace(/[_\s-]+/g, "").trim();
}
function t(e) {
  const a = s(e), r = o[a];
  return r ? `${n}/weapons/${r}.png` : null;
}
function l(e) {
  const a = (e || "").replace(/^maps[\\/]/, "").replace(/\.(bsp|pk3|arena)$/i, "").trim();
  return `${n}/levelshots/${a}.png`;
}
function m(e) {
  const a = s(e), i = {
    accuracy: "medal_accuracy",
    battlesense: "medal_battle_sense",
    engineer: "medal_engineer",
    explosives: "medal_explosives",
    firstaid: "medal_first_aid",
    lightweapons: "medal_light_weapons",
    signals: "medal_signals"
  }[a] ?? `medal_${a}`;
  return `${n}/medals/${i}.png`;
}
function p(e) {
  const a = Math.max(2, Math.min(11, e));
  return `${n}/ranks/rank_${String(a).padStart(2, "0")}.png`;
}
export {
  m as a,
  l as m,
  p as r,
  t as w
};
