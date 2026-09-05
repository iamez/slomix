# Dots Arena 1v1 — fair duels for ET:Legacy

A server-side Lua module that makes a 1v1 on `dots_arena` actually fair, plus
the config that switches it on. Optional lifesteal, unlimited ammo, unlimited
sprint. Tested on **ET:Legacy v2.84.0**.

**Version 1.1.0** — the Lua module, this README and `dots_arena_1v1.config`
carry the same number, and a test refuses to let them drift apart.

- [English](#english) · [Français](#français) · [Slovensko](#slovensko)

> **Repo note.** In this repository the Lua module lives one level up, at
> `vps_scripts/dots_arena_1v1.lua`, so that a single copy is deployed and
> tested. The tables below describe the **shipped bundle**, not this layout.

---

## English

### What it does

On a pure-aim 1v1 map the two players never start a duel on equal terms. The
winner keeps whatever health and ammo he was left with and carries no spawn
shield; the loser goes through limbo and comes back at full health with the
engine's 3-second invulnerability. Players work around this by typing `/kill`,
but the two deaths are a second or two apart, so the shields expire at
different moments and the reset is only approximately fair.

This module does the same thing **in the same frame as the kill**, which is
the part a human cannot do:

- when someone dies, the world kills the winner too — so both respawn together;
- both spawn shields are levelled to the **earlier** expiry, so nobody gets
  more protection than the engine meant to give;
- the world keeps the score and announces it after every duel;
- the forced death is credited to the world, so it never shows up as a suicide
  in anyone's stats.

Optional on top: **lifesteal** (Diabotical Shaft Arena style, 50 % by default),
a **health pool** of 250/500/1000, **unlimited ammo**, and **unlimited sprint**.

### Files

| File | Goes to |
|---|---|
| `dots_arena.pk3` | `<gamedir>/etmain/` |
| `dots_arena_1v1.lua` | `<gamedir>/legacy/luascripts/` |
| `dots_arena_1v1.config` | `<gamedir>/etmain/configs/` |

All three can also live **inside a single pk3** — the engine reads configs and
Lua modules through its virtual filesystem, so `luascripts/…` and `configs/…`
inside the map pk3 are found normally. `sv_pure` does not change this on a
dedicated server.

### Turning it on

⛔ **Order matters.** `g_gametype` is a latched cvar, and a config vote only
does a `map_restart` — which does not re-latch anything. So voting the config
gives you the Lua module but *not* the gametype.

**On a running server:**

```
g_gametype 3          // or 2. dots_arena supports wolfmp, wolfsw and wolflms
map dots_arena
callvote config dots_arena_1v1
```

**On a dedicated arena server** (cleanest — put this in `server.cfg`):

```
set g_gametype 3
set g_customConfig "dots_arena_1v1"
map dots_arena
```

⛔ **The config's `lua_modules` line REPLACES your server's module list** —
the config format has no "append". If you already run wolfadmin or anything
else, add it to that line in `init`, or it stops working the moment this config
loads. Measured on a server with six modules: loading this config took it to one.

⭐ The line in `init` is **for your maps, not for the arena**: the arena module
is named again in the `map dots_arena` block, which overrides `init` on that one
map. So put your own modules on the `init` line and your rotation keeps them
everywhere else. (The module also gates itself on the map name — its first hook
line is `if not active then return end` — but that is belt and braces now, not
the mechanism.)

### Player commands

| Command | What it does |
|---|---|
| `/arenahp 250` | health pool: `250`, `500`, `1000`, or `0` for the engine default |
| `/vampiric` | lifesteal on/off |
| `/vampiric 250` | lifesteal on **and** set the pool, in one command |

Both take effect **at the next spawn of both players**, never mid-duel —
changing the pool in the middle of a fight would hand one player a number the
other never had.

### Server cvars

| Cvar | Default | Meaning |
|---|---|---|
| `arena_1v1` | `1` | `0` makes the module stand down without unloading it |
| `arena_1v1_map` | `dots_arena` | which map arms it (substring match) |
| `arena_hp` | `0` | pool: `0` = engine health, else `250`/`500`/`1000` |
| `arena_vamp` | `0` | lifesteal |
| `arena_vamp_steal` | `50` | percent of damage healed back |
| `arena_vamp_grace` | `90` | seconds before the leech starts decaying |
| `arena_vamp_decay` | `30` | seconds over which it decays to zero |
| `arena_ammo` | `1` | 9999/9999 at every spawn |
| `arena_nofatigue` | `1` | unlimited sprint (and unlimited jumping) |
| `arena_symmetric` | `0` | force MP40/Thompson — see the warnings |
| `arena_1v1_log` | `1` | write `<homepath>/legacy/arena_1v1.log` |
| `arena_1v1_test` | `0` | unlock the console commands used for testing |

`arena_hp` accepts only 250, 500 and 1000. Anything else snaps to the nearest
one and says so — the duel-length numbers below only speak for those points.

### How long a duel lasts (measured, ET:Legacy 2.84, two bots)

| Pool | Median duel |
|---|---|
| 250 HP | **6 s** (n=13) |
| 500 HP | 14 s (n=7) |
| 1000 HP | **one duel in 120 s** |

⛔ 300 HP was measured too (median 7 s, n=11) and is not listed: `nearest_preset` snaps it to 250, so no operator can ask for it. A row naming an unreachable setting is a lie about the interface, however true it is about the past.

With lifesteal the pool and the duel length are **not** proportional — the
fight becomes a race between two drains, so the curve bends hard. 1000 HP is
the "fights take forever" failure QuakeLive's community warns about, reached
here at 50 % leech rather than 100 %. Pick the pool for the duel length you
want, not for the number that sounds generous.

⚠️ Every one of those numbers was measured with **mixed loadouts** — Omni-bot
picks its own class and the module cannot make it stop. They are consistent
with each other, but none of them is a mirrored-SMG duel.

### What this config does to your whole server

Read this before you vote it in. The config is derived from the official
Legacy 1on1 competition config, and it brings that config's opinions with it.

- ⛔ **It becomes your server's permanent config.** `G_configSet` writes the
  name into `g_customConfig`, which is `CVAR_ARCHIVE` — so the arena ruleset
  applies to **every map**, survives map changes, and survives a restart of the
  server process. Vote another config to undo it.
- ⛔ **Only Field Ops is selectable.** `team_maxSoldiers/Medics/Engineers/
  Covertops "0"` cap those classes at zero (`-1` means unlimited, `0` means
  banned), so your players get "class is not available" for four of the five.
  On every map, per the point above. Raise the caps if you do not want that.
- ⛔ **Your map rotation stops.** `set nextmap "map_restart 0"` makes the
  server replay the current map forever. Remove that line to keep a rotation.
- ⛔ **A referee can unload the config by accident.** `\ref warmup 30` writes
  `g_warmup`, which this config locks, and the votes for friendlyfire, antilag,
  warmupdamage and balancedteams write locked cvars too. Any of them triggers
  "WAS UNLOADED DUE TO EXTERNAL MANIPULATION" on the next frame — the config is
  forgotten and the value is *not* restored.
- ⚠️ **It is ready-up match mode.** `g_doWarmup 1`, `match_minplayers 2`,
  `match_readypercent 100`: two players who join will sit in warmup until both
  type `/ready`.
- ⚠️ **`g_mapConfigs` and `g_campaignfile` are cleared**, so any per-map
  configs or campaign you had are disabled while this config is loaded.

### Things that will bite you

- ⛔ **Do not set `lua_modules` by hand while the server runs.** The engine's
  cvar-change hook calls `G_LuaShutdown()` with no matching init, so you get a
  dead Lua and no error message. Use `lua_restart`, or load a map.
- ⛔ **If `g_luaModuleList` is set on your server, `lua_modules` is ignored
  entirely.** The server says so in one line at startup and then quietly loads
  nothing. This is the first thing to check if the module does not come up.
- ⛔ **Keep `arena_hp` as `set`, never `setl`.** The engine re-checks every
  `setl` cvar once per frame and unloads the whole config the moment one of
  them changes — and `/arenahp` changes this one. You will see
  "Config WAS UNLOADED DUE TO EXTERNAL MANIPULATION".
- ✅ **Voting another config takes the arena back out cleanly.** Measured:
  arena armed -> `g_forcerespawn -1`; the vote's `lua_modules` change kills the
  module and `et_Quit` puts `g_forcerespawn` back to `0`; the `map_restart` the
  vote issues then loads that config's own modules. Worth knowing why the
  module needs `et_Quit` at all: a runtime `lua_modules` change calls
  `G_LuaShutdown` directly, which reaches `et_Quit` but never
  `et_ShutdownGame` — without it the server would keep instant respawn on every
  map afterwards.
- ⛔ **The module stays loaded after you leave the map.** `lua_modules` is
  never reverted by a later config vote, so it survives map changes until
  another config overwrites it or the server process restarts. The
  module stays loaded but inert on other maps, which is harmless; if you
  switch to a config that does not set `lua_modules`, clear it yourself.
- ⚠️ **The health pool does not protect against a hit over 190 damage.** The
  engine sets health to −176 outright in that case, regardless of the pool, so
  a panzerfaust, dynamite or satchel one-shots a 1000 HP duelist just as
  happily as a 100 HP one.
- ⚠️ **The engine bleeds surplus health at 1 HP per second.** About 3 % over a
  duel at the 500 default, 12 % at 1000. The health bar is also scaled against
  the engine's maximum, so a 500 HP duelist shows an overfull bar. Cosmetic.
- ⚠️ **`arena_symmetric` does not hold against bots.** Measured: the weapon is
  written correctly 50 times out of 50, and the bot has taken its own weapon
  back by the end of the duel in 23 of 25 cases. It also costs about 1.5× the
  normal `ClientUserinfoChanged` traffic. It should work with humans.

### If you use `lua_allowedModules`

That cvar is a SHA1 allowlist and is **empty by default**, which allows
everything. If your server uses it, add this module's digest:

```
sha1sum dots_arena_1v1.lua
```

The digest is deliberately not printed here: it changes with every edit of the
module, and a stale hash in a README is worse than no hash at all.

---

## Français

### Ce que ça fait

Sur une carte de duel pur, les deux joueurs ne commencent jamais à armes
égales. Le vainqueur garde la vie et les munitions qui lui restent et n'a
aucun bouclier de réapparition ; le perdant passe par les limbes et revient
avec toute sa vie et les 3 secondes d'invulnérabilité du moteur. Les joueurs
contournent ça en tapant `/kill`, mais les deux morts sont espacées d'une ou
deux secondes, donc les boucliers expirent à des moments différents et la
remise à zéro n'est équitable qu'approximativement.

Ce module fait la même chose **dans la même frame que le kill**, ce qu'un
humain ne peut pas faire :

- quand quelqu'un meurt, le monde tue aussi le vainqueur — les deux
  réapparaissent ensemble ;
- les deux boucliers sont alignés sur l'expiration **la plus proche**, donc
  personne n'obtient plus de protection que ce que le moteur prévoyait ;
- le monde tient le score et l'annonce après chaque duel ;
- la mort forcée est attribuée au monde, elle n'apparaît donc jamais comme un
  suicide dans les statistiques.

En option : le **vol de vie** (façon Shaft Arena de Diabotical, 50 % par
défaut), une **réserve de vie** de 250/500/1000, des **munitions illimitées**
et un **sprint illimité**.

### Fichiers

| Fichier | Destination |
|---|---|
| `dots_arena.pk3` | `<dossier du jeu>/etmain/` |
| `dots_arena_1v1.lua` | `<dossier du jeu>/legacy/luascripts/` |
| `dots_arena_1v1.config` | `<dossier du jeu>/etmain/configs/` |

Les trois peuvent aussi tenir **dans un seul pk3** — le moteur lit les configs
et les modules Lua via son système de fichiers virtuel, donc `luascripts/…` et
`configs/…` à l'intérieur du pk3 de la carte sont trouvés normalement.
`sv_pure` n'y change rien sur un serveur dédié.

### Activation

⛔ **L'ordre compte.** `g_gametype` est une cvar verrouillée (*latched*), et un
vote de config ne fait qu'un `map_restart`, qui ne reverrouille rien. Voter la
config vous donne donc le module Lua mais *pas* le type de jeu.

**Sur un serveur en cours :**

```
g_gametype 3          // ou 2. dots_arena accepte wolfmp, wolfsw et wolflms
map dots_arena
callvote config dots_arena_1v1
```

**Sur un serveur dédié à l'arène** (le plus propre — dans `server.cfg`) :

```
set g_gametype 3
set g_customConfig "dots_arena_1v1"
map dots_arena
```

⛔ **La ligne `lua_modules` de la config REMPLACE la liste des modules de
votre serveur** — le format de config ne sait pas « ajouter ». Si vous utilisez
déjà wolfadmin ou autre chose, ajoutez-le sur cette ligne dans `init`, sinon il
cessera de fonctionner dès le chargement de cette config. Mesuré sur un serveur
avec six modules : le chargement de cette config l'a ramené à un.

⭐ La ligne dans `init` est **pour vos cartes, pas pour l'arène** : le module
d'arène est nommé de nouveau dans le bloc `map dots_arena`, qui remplace `init`
sur cette seule carte. Mettez donc vos propres modules sur la ligne `init` et
votre rotation les conserve partout ailleurs. (Le module se verrouille aussi
sur le nom de la carte — sa première ligne de hook est
`if not active then return end` — mais c'est désormais une ceinture et des
bretelles, plus le mécanisme.)

### Commandes joueur

| Commande | Effet |
|---|---|
| `/arenahp 250` | réserve de vie : `250`, `500`, `1000`, ou `0` pour la valeur du moteur |
| `/vampiric` | vol de vie activé/désactivé |
| `/vampiric 250` | active le vol de vie **et** règle la réserve, en une commande |

Les deux prennent effet **à la réapparition suivante des deux joueurs**, jamais
en plein duel : changer la réserve au milieu d'un combat donnerait à l'un une
valeur que l'autre n'a jamais eue.

### Cvars serveur

| Cvar | Défaut | Signification |
|---|---|---|
| `arena_1v1` | `1` | `0` met le module en veille sans le décharger |
| `arena_1v1_map` | `dots_arena` | quelle carte l'arme (correspondance partielle) |
| `arena_hp` | `0` | réserve : `0` = vie du moteur, sinon `250`/`500`/`1000` |
| `arena_vamp` | `0` | vol de vie |
| `arena_vamp_steal` | `50` | pourcentage des dégâts rendus en vie |
| `arena_vamp_grace` | `90` | secondes avant que le vol commence à décroître |
| `arena_vamp_decay` | `30` | secondes sur lesquelles il tombe à zéro |
| `arena_ammo` | `1` | 9999/9999 à chaque réapparition |
| `arena_nofatigue` | `1` | sprint illimité (et sauts illimités) |
| `arena_symmetric` | `0` | impose MP40/Thompson — voir les avertissements |
| `arena_1v1_log` | `1` | écrit `<homepath>/legacy/arena_1v1.log` |
| `arena_1v1_test` | `0` | déverrouille les commandes console de test |

`arena_hp` n'accepte que 250, 500 et 1000. Toute autre valeur est ramenée à la
plus proche, avec un message — les durées ci-dessous ne valent que pour ces
trois points.

### Durée d'un duel (mesurée, ET:Legacy 2.84, deux bots)

| Réserve | Durée médiane |
|---|---|
| 250 HP | **6 s** (n=13) |
| 500 HP | 14 s (n=7) |
| 1000 HP | **un seul duel en 120 s** |

⛔ 300 HP a également été mesuré (médiane 7 s, n=11) et n'est pas listé : `nearest_preset` le ramène à 250, donc personne ne peut le demander. Une ligne qui nomme un réglage inatteignable ment sur l'interface, aussi vraie soit-elle sur le passé.

Avec le vol de vie, la réserve et la durée ne sont **pas** proportionnelles :
le combat devient une course entre deux fuites, et la courbe se casse. 1000 HP
est exactement l'échec « les combats n'en finissent plus » dont la communauté
QuakeLive avertit, atteint ici à 50 % de vol et non à 100 %. Choisissez la
réserve pour la durée voulue, pas pour le chiffre qui paraît généreux.

⚠️ Tous ces chiffres ont été mesurés avec des **équipements mélangés** —
Omni-bot choisit sa propre classe et le module ne peut pas l'en empêcher. Ils
sont cohérents entre eux, mais aucun n'est un duel SMG contre SMG.

### Ce que cette config fait à tout votre serveur

À lire avant de la voter. Elle est dérivée de la config officielle 1on1 de
compétition et elle en apporte les partis pris.

- ⛔ **Elle devient la config permanente du serveur.** `G_configSet` écrit son
  nom dans `g_customConfig`, qui est `CVAR_ARCHIVE` : le règlement de l'arène
  s'applique donc à **toutes les cartes**, survit aux changements de carte et
  survit à un redémarrage du processus. Votez une autre config pour l'annuler.
- ⛔ **Seul Field Ops est sélectionnable.** `team_maxSoldiers/Medics/Engineers/
  Covertops "0"` plafonnent ces classes à zéro (`-1` = illimité, `0` = interdit),
  donc vos joueurs obtiennent « classe non disponible » pour quatre des cinq.
  Sur toutes les cartes, cf. le point précédent. Relevez les plafonds si ce
  n'est pas ce que vous voulez.
- ⛔ **Votre rotation de cartes s'arrête.** `set nextmap "map_restart 0"` fait
  rejouer la carte courante indéfiniment. Retirez cette ligne pour garder une
  rotation.
- ⛔ **Un arbitre peut décharger la config sans le vouloir.** `\ref warmup 30`
  écrit `g_warmup`, que cette config verrouille ; les votes friendlyfire,
  antilag, warmupdamage et balancedteams écrivent eux aussi des cvars
  verrouillées. N'importe lequel déclenche « WAS UNLOADED DUE TO EXTERNAL
  MANIPULATION » à la frame suivante — la config est oubliée et la valeur n'est
  *pas* restaurée.
- ⚠️ **C'est un mode match avec ready.** `g_doWarmup 1`, `match_minplayers 2`,
  `match_readypercent 100` : deux joueurs qui arrivent resteront en warmup
  jusqu'à ce que les deux tapent `/ready`.
- ⚠️ **`g_mapConfigs` et `g_campaignfile` sont vidés**, donc vos configs par
  carte et votre campagne sont désactivées tant que cette config est chargée.

### Ce qui va vous poser problème

- ⛔ **Ne réglez pas `lua_modules` à la main pendant que le serveur tourne.**
  Le hook de changement de cvar appelle `G_LuaShutdown()` sans init
  correspondant : vous obtenez un Lua mort et aucun message d'erreur. Utilisez
  `lua_restart`, ou chargez une carte.
- ⛔ **Si `g_luaModuleList` est défini sur votre serveur, `lua_modules` est
  entièrement ignoré.** Le serveur le signale sur une seule ligne au démarrage,
  puis ne charge rien. C'est la première chose à vérifier si le module ne
  s'active pas.
- ⛔ **Gardez `arena_hp` en `set`, jamais en `setl`.** Le moteur revérifie
  chaque cvar `setl` à chaque frame et décharge toute la config dès que l'une
  d'elles change — et `/arenahp` change celle-ci. Vous verrez
  « Config WAS UNLOADED DUE TO EXTERNAL MANIPULATION ».
- ✅ **Voter une autre config retire l'arène proprement.** Mesuré : arène
  armée -> `g_forcerespawn -1` ; le changement de `lua_modules` du vote tue le
  module et `et_Quit` remet `g_forcerespawn` à `0` ; le `map_restart` émis par
  le vote charge ensuite les modules de cette config. Pourquoi `et_Quit` est
  nécessaire : un changement de `lua_modules` à chaud appelle directement
  `G_LuaShutdown`, qui atteint `et_Quit` mais jamais `et_ShutdownGame` — sans
  lui le serveur garderait la réapparition instantanée sur toutes les cartes.
- ⛔ **Le module reste chargé après avoir quitté la carte.** `lua_modules`
  n'est jamais remis à zéro par un vote de config ultérieur : il survit aux
  changements de carte jusqu'à ce qu'une autre config l'écrase ou que le
  processus redémarre. Le module reste chargé mais inerte sur les autres
  cartes, ce qui est sans conséquence ; si vous passez à une config qui ne
  définit pas `lua_modules`, videz-le vous-même.
- ⚠️ **La réserve de vie ne protège pas d'un coup dépassant 190 de dégâts.**
  Le moteur met alors la vie à −176 quelle que soit la réserve : un
  panzerfaust, une dynamite ou un satchel tuent un duelliste à 1000 HP aussi
  facilement qu'un à 100.
- ⚠️ **Le moteur fait fondre la vie excédentaire à raison de 1 PV par
  seconde.** Environ 3 % sur un duel à 500 par défaut, 12 % à 1000. La barre de
  vie est en plus calibrée sur le maximum du moteur, donc un duelliste à 500 HP
  affiche une barre débordante. Purement cosmétique.
- ⚠️ **`arena_symmetric` ne tient pas face aux bots.** Mesuré : l'arme est
  écrite correctement 50 fois sur 50, et le bot a repris la sienne avant la fin
  du duel dans 23 cas sur 25. Cela coûte en plus environ 1,5× le trafic
  `ClientUserinfoChanged` normal. Cela devrait fonctionner avec des humains.

### Si vous utilisez `lua_allowedModules`

Cette cvar est une liste blanche de SHA1, **vide par défaut**, ce qui autorise
tout. Si votre serveur l'utilise, ajoutez l'empreinte de ce module :

```
sha1sum dots_arena_1v1.lua
```

L'empreinte n'est volontairement pas imprimée ici : elle change à chaque
modification du module, et une empreinte périmée dans un README est pire que
pas d'empreinte du tout.

---

## Slovensko

### Kaj počne

Na čisti dvobojni mapi igralca nikoli ne začneta pod enakimi pogoji.
Zmagovalec obdrži zdravje in strelivo, ki mu je ostalo, in nima spawn ščita;
poraženec gre skozi limbo in se vrne s polnim zdravjem ter motorjevo
3-sekundno nedotakljivostjo. Igralci to zaobidejo z ukazom `/kill`, a sta smrti
sekundo ali dve narazen, zato ščita potečeta ob različnih trenutkih in je
ponastavitev poštena le približno.

Ta modul naredi isto **v istem frameu kot kill**, kar je tisti del, ki ga
človek ne zmore:

- ko nekdo umre, svet pobije tudi zmagovalca — oba spawnata skupaj;
- oba ščita se poravnata na **zgodnejšo** potečo, tako da nihče ne dobi več
  zaščite, kot mu jo je motor namenil;
- svet vodi izid in ga po vsakem dvoboju objavi;
- prisilna smrt gre na račun sveta, zato se v statistiki nikoli ne pokaže kot
  samomor.

Izbirno še: **lifesteal** (po vzoru Diabotical Shaft Arene, privzeto 50 %),
**zalogovnik zdravja** 250/500/1000, **neomejeno strelivo** in **neomejen
sprint**.

### Datoteke

| Datoteka | Kam gre |
|---|---|
| `dots_arena.pk3` | `<mapa igre>/etmain/` |
| `dots_arena_1v1.lua` | `<mapa igre>/legacy/luascripts/` |
| `dots_arena_1v1.config` | `<mapa igre>/etmain/configs/` |

Vse troje lahko živi tudi **znotraj enega samega pk3** — motor bere confige in
Lua module prek virtualnega datotečnega sistema, zato `luascripts/…` in
`configs/…` znotraj pk3 mape najde povsem normalno. `sv_pure` na dediciranem
strežniku pri tem ne spremeni ničesar.

### Vklop

⛔ **Vrstni red šteje.** `g_gametype` je zamaknjen (*latched*) cvar, glasovanje
o configu pa naredi le `map_restart`, ki ničesar ne prelatcha. Izglasovan
config ti torej prinese Lua modul, **ne pa gametypa**.

**Na strežniku, ki teče:**

```
g_gametype 3          // ali 2. dots_arena podpira wolfmp, wolfsw in wolflms
map dots_arena
callvote config dots_arena_1v1
```

**Na namenskem arena strežniku** (najčisteje — v `server.cfg`):

```
set g_gametype 3
set g_customConfig "dots_arena_1v1"
map dots_arena
```

⛔ **Vrstica `lua_modules` v configu PREPIŠE seznam modulov tvojega
strežnika** — config format ne zna »dodajati«. Če že poganjaš wolfadmin ali
karkoli drugega, ga dopiši v to vrstico v `init`, sicer neha delovati v
trenutku, ko se ta config naloži. Izmerjeno na strežniku s šestimi moduli:
nalaganje tega configa ga je spravilo na enega.

⭐ Vrstica v `init` je **za tvoje mape, ne za areno**: arena modul je znova
naveden v bloku `map dots_arena`, ki `init` prepiše samo na tej eni mapi. Na
vrstico v `init` torej daj svoje module in rotacija jih obdrži povsod drugod.
(Modul se tudi sam zapre po imenu mape — prva vrstica hooka je
`if not active then return end` — a to je zdaj varovalka, ne mehanizem.)

### Ukazi za igralce

| Ukaz | Kaj naredi |
|---|---|
| `/arenahp 250` | zalogovnik zdravja: `250`, `500`, `1000` ali `0` za motorjevo vrednost |
| `/vampiric` | lifesteal vklop/izklop |
| `/vampiric 250` | vklopi lifesteal **in** nastavi zalogovnik z enim ukazom |

Oboje velja **od naslednjega spawna obeh igralcev**, nikoli sredi dvoboja —
sprememba zalogovnika med bojem bi enemu podarila številko, ki je drugi ni imel.

### Strežniški cvari

| Cvar | Privzeto | Pomen |
|---|---|---|
| `arena_1v1` | `1` | `0` modul uspava, ne da bi ga odstranil |
| `arena_1v1_map` | `dots_arena` | katera mapa ga oboroži (ujemanje po delu imena) |
| `arena_hp` | `0` | zalogovnik: `0` = motorjevo zdravje, sicer `250`/`500`/`1000` |
| `arena_vamp` | `0` | lifesteal |
| `arena_vamp_steal` | `50` | odstotek škode, ki se vrne kot zdravje |
| `arena_vamp_grace` | `90` | sekunde, preden lifesteal začne upadati |
| `arena_vamp_decay` | `30` | sekunde, v katerih upade na nič |
| `arena_ammo` | `1` | 9999/9999 ob vsakem spawnu |
| `arena_nofatigue` | `1` | neomejen sprint (in neomejeno skakanje) |
| `arena_symmetric` | `0` | vsili MP40/Thompson — glej opozorila |
| `arena_1v1_log` | `1` | piše `<homepath>/legacy/arena_1v1.log` |
| `arena_1v1_test` | `0` | odklene konzolne ukaze za testiranje |

`arena_hp` sprejme samo 250, 500 in 1000. Karkoli drugega se prilepi na
najbližjo vrednost in to tudi pove — spodnje dolžine dvobojev govorijo le za te
tri točke.

### Kako dolgo traja dvoboj (izmerjeno, ET:Legacy 2.84, dva bota)

| Zalogovnik | Mediana dvoboja |
|---|---|
| 250 HP | **6 s** (n=13) |
| 500 HP | 14 s (n=7) |
| 1000 HP | **en sam dvoboj v 120 s** |

⛔ 300 HP je bil prav tako izmerjen (mediana 7 s, n=11) in ni naveden: `nearest_preset` ga prilepi na 250, zato ga nihče ne more nastaviti. Vrstica, ki imenuje nedosegljivo nastavitev, laže o vmesniku, pa naj bo o preteklosti še tako resnična.

Z lifestealom zalogovnik in dolžina dvoboja **nista** sorazmerna — boj postane
dirka med dvema odtokoma in krivulja se zlomi. 1000 HP je natanko tista
odpoved »dvoboji trajajo večno«, pred katero svari QuakeLive skupnost, tu
dosežena že pri 50 % in ne pri 100 %. Zalogovnik izberi glede na želeno dolžino
dvoboja, ne glede na številko, ki zveni radodarno.

⚠️ Vse te številke so izmerjene z **mešanimi orožji** — Omnibot si razred
izbere sam in modul mu tega ne more preprečiti. Med seboj so skladne, nobena pa
ni dvoboj brzostrelka proti brzostrelki.

### Kaj ta config naredi celemu tvojemu strežniku

Preberi, preden ga izglasuješ. Izpeljan je iz uradnega tekmovalnega 1on1
configa in s sabo prinese njegova stališča.

- ⛔ **Postane trajni config strežnika.** `G_configSet` njegovo ime zapiše v
  `g_customConfig`, ki je `CVAR_ARCHIVE` — arena ruleset torej velja na
  **vseh mapah**, preživi menjave map in preživi restart procesa. Odpraviš ga
  z izglasovanjem drugega configa.
- ⛔ **Izbirni razred je samo Field Ops.** `team_maxSoldiers/Medics/Engineers/
  Covertops "0"` te razrede omeji na nič (`-1` pomeni neomejeno, `0` pomeni
  prepovedano), zato igralci pri štirih od petih dobijo »razred ni na voljo«.
  Na vseh mapah, glej prejšnjo točko. Če tega nočeš, dvigni omejitve.
- ⛔ **Rotacija map se ustavi.** `set nextmap "map_restart 0"` pomeni, da
  strežnik v nedogled ponavlja isto mapo. Odstrani to vrstico, če hočeš
  rotacijo.
- ⛔ **Referee lahko config nehote odklopi.** `\ref warmup 30` piše `g_warmup`,
  ki ga ta config zaklepa; prav tako pišejo zaklenjene cvare glasovanja
  friendlyfire, antilag, warmupdamage in balancedteams. Katerokoli od njih
  sproži »WAS UNLOADED DUE TO EXTERNAL MANIPULATION« v naslednjem frameu —
  config je pozabljen, vrednost pa **ni** povrnjena.
- ⚠️ **To je tekmovalni način z ready.** `g_doWarmup 1`, `match_minplayers 2`,
  `match_readypercent 100`: dva igralca, ki se pridružita, bosta v warmupu,
  dokler oba ne natipkata `/ready`.
- ⚠️ **`g_mapConfigs` in `g_campaignfile` sta izpraznjena**, torej so tvoje
  per-map konfiguracije in kampanja onemogočene, dokler je ta config naložen.

### Kar te bo ugriznilo

- ⛔ **Ne nastavljaj `lua_modules` na roko med tekom strežnika.** Motorjev
  hook ob spremembi cvara pokliče `G_LuaShutdown()` brez ustreznega inita:
  dobiš mrtvo Lua in nobenega sporočila o napaki. Uporabi `lua_restart` ali
  naloži mapo.
- ⛔ **Če je na tvojem strežniku nastavljen `g_luaModuleList`, se
  `lua_modules` v celoti ignorira.** Strežnik to ob zagonu javi z eno samo
  vrstico in nato tiho ne naloži ničesar. To je prva stvar, ki jo preveriš, če
  se modul ne prižge.
- ⛔ **`arena_hp` naj ostane `set`, nikoli `setl`.** Motor vsak frame znova
  preveri vsak `setl` cvar in odklopi cel config, brž ko se eden od njih
  spremeni — `/arenahp` pa spremeni prav tega. Videl boš
  »Config WAS UNLOADED DUE TO EXTERNAL MANIPULATION«.
- ✅ **Glasovanje o drugem configu areno čisto odstrani.** Izmerjeno: arena
  oborožena -> `g_forcerespawn -1`; sprememba `lua_modules` ob glasovanju modul
  ubije in `et_Quit` postavi `g_forcerespawn` nazaj na `0`; `map_restart`, ki
  ga glasovanje sproži samo, nato naloži module tistega configa. Zakaj je
  `et_Quit` sploh potreben: sprememba `lua_modules` med tekom pokliče
  `G_LuaShutdown` naravnost, ta pa doseže `et_Quit`, nikoli pa
  `et_ShutdownGame` — brez njega bi strežnik obdržal instant respawn na vseh
  mapah.
- ⛔ **Modul ostane naložen tudi potem, ko zapustiš mapo.** `lua_modules` se ob
  kasnejšem glasovanju o configu nikoli ne povrne, zato preživi menjave map,
  dokler ga drug config ne prepiše ali dokler se proces ne zažene znova. Blok
  Modul ostane naložen, a na drugih mapah nedejaven, kar ni škodljivo; če
  preklopiš na config, ki `lua_modules` ne nastavlja, ga počisti sam.
- ⚠️ **Zalogovnik ne varuje pred zadetkom nad 190 škode.** Motor v tem primeru
  postavi zdravje na −176 ne glede na zalogovnik, zato panzerfaust, dinamit ali
  satchel z enim zadetkom ubijejo duelista s 1000 HP prav tako zlahka kot
  tistega s 100.
- ⚠️ **Motor odnaša presežno zdravje po 1 HP na sekundo.** Pri privzetih 500 je
  to okoli 3 % na dvoboj, pri 1000 pa 12 %. Lestvica zdravja je poleg tega
  umerjena na motorjev maksimum, zato duelist s 500 HP kaže prenapolnjeno
  lestvico. Zgolj kozmetično.
- ⚠️ **`arena_symmetric` proti botom ne drži.** Izmerjeno: orožje se pravilno
  zapiše 50-krat od 50, do konca dvoboja pa si ga je bot vzel nazaj v 23
  primerih od 25. Poleg tega stane okoli 1,5× običajnega prometa
  `ClientUserinfoChanged`. Proti ljudem bi moralo delovati.

### Če uporabljaš `lua_allowedModules`

Ta cvar je SHA1 seznam dovoljenih modulov in je **privzeto prazen**, kar
dovoljuje vse. Če ga tvoj strežnik uporablja, dodaj vsoto tega modula:

```
sha1sum dots_arena_1v1.lua
```

Vsota tu namenoma ni izpisana: spremeni se ob vsaki spremembi modula, zastarel
hash v READMEju pa je slabši kot nobeden.
