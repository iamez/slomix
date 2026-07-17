# Dual-frontend reachability analiza (A2)

**Datum:** 2026-07-13 · **Tip:** read-only poročilo (NE brisanje) · **Odloči:** owner
**Owner že odločil (§6.8, 2026-07-13):** NE arhiviraj — *"React stran bomo enkrat do konca
zgradili in zamenjali JS, ampak to bo čez par let; za zdaj imamo JS."* To poročilo torej
**dokumentira**, ne priporoča brisanja.

## Metoda

Dosegljivost SPA rout določa `website/js/route-registry.js` → `loadRoute(viewId,…)`:
React se mounta **samo** ko `definition.mode === VIEW_MODE.MODERN` (kliče
`runtime.modern.mountRoute`). Vse ostalo teče prek `definition.load({legacy})` = legacy JS.
`website/frontend/src/route-host.tsx` sicer mapira **vseh 25** strani (lazy import), a to je
le zmožnost renderiranja — dejansko dosegljive so le MODERN route iz registryja.

## Rezultat: 4 LIVE (React) · 21 STAGED (legacy JS je kanon)

### ✅ LIVE — React-mounted (4)
| .tsx stran | viewId | Od kod dosegljiva |
|------------|--------|-------------------|
| `ProximityPlayer.tsx` | `proximity-player` | registry MODERN → route-host.tsx; hash `#/proximity/player/{guid}` (link iz proximity.js) |
| `ProximityReplay.tsx` | `proximity-replay` | registry MODERN; hash `#/proximity/round/{id}` |
| `ProximityTeams.tsx` | `proximity-teams` | registry MODERN; hash `#/proximity/round/{id}/teams` |
| `SkillRating.tsx` | `skill-rating` | registry MODERN; nav link "ET Rating" `#/skill-rating` |

### 🟡 STAGED — .tsx obstaja, a registry mode = LEGACY → renderira legacy JS (21)
| .tsx stran | viewId | Live renderer | Zbildan chunk? |
|------------|--------|---------------|----------------|
| `Home.tsx` | home | legacy app.js | da (dead output) |
| `Records.tsx` | records/record-book | legacy | da |
| `Leaderboards.tsx` | leaderboards | legacy | da |
| `Maps.tsx` | maps | legacy | da |
| `Sessions2.tsx` | sessions2 | legacy | da |
| `SessionDetail.tsx` | session-detail | legacy | da |
| `Story.tsx` | story | legacy | da |
| `Weapons.tsx` | weapons | legacy | da |
| `Replay.tsx` | replay | legacy | da |
| `Proximity.tsx` | proximity | legacy | da |
| `HallOfFame.tsx` | hall-of-fame→record-book | legacy | ne |
| `Awards.tsx` | awards | legacy | ne |
| `Profile.tsx` | profile | legacy | ne |
| `RetroViz.tsx` | retro-viz | legacy | ne |
| `Rivalries.tsx` | rivalries | legacy | ne |
| `Uploads.tsx` | uploads | legacy | ne |
| `UploadDetail.tsx` | upload-detail | legacy | ne |
| `Greatshot.tsx` | greatshot | legacy | ne |
| `GreatshotDemo.tsx` | greatshot-demo | legacy | ne |
| `Availability.tsx` | availability | legacy | ne |
| `Admin.tsx` | admin | legacy | ne |

("Zbildan chunk" = **generiran ob deployu** v `website/static/modern/chunks/`, NE committan —
`.gitignore` izključuje `website/static/modern/`, `scripts/deploy_release.sh` (korak 3c) pa
direktorij zgradi in atomično zamenja ob vsakem deployu. Ker viewId ni MODERN, se ta lazy chunk
nikoli ne mounta = mrtev build **artefakt**, ne mrtva koda.)

## Priporočilo

- **NE arhiviraj** (owner odločil): 21 staged strani je namerno prihodnje delo (večletni React
  cutover). Niso mrtva koda — so vmesni cilj.
- **Maintenance opomba:** ker `route-host.tsx` lazy-importa vseh 25, mora modern build
  prevesti tudi teh 21 → morajo ostati **TS-valid / build-clean**, sicer prihodnji poln React
  cutover pade. To je edina cena hranjenja.
- **Kozmetika (opcijsko, nizka prio):** neaktivni chunki (Home/Records/… ki niso MODERN) so
  zgolj deploy-generiran build output, ne committani — čist Vite build jih tako ali tako regenerira
  vse (lazy-importi). **NE briši ročno `website/static/modern/`** na živem: 4 žive modern route
  (proximity-player/replay/teams, skill-rating) strežejo iz tega direktorija in bi šle offline.
- **Za promocijo strani v LIVE React:** flipni njen `mode` v `route-registry.js` na `MODERN` +
  poskrbi da chunk je zbildan. **Opozorilo za aliasirane route:** Records in Hall of Fame se v
  `route-registry.js` razrešita na `viewId: 'record-book'`, medtem ko `route-host.tsx` izpostavlja
  ključa `records` in `hall-of-fame` — flip aliasovega `mode` je zaobiden (`parseHash` vrne
  `record-book`), flip same `record-book` definicije pa poskuša mountati neobstoječo modern route.
  Ti dve strani zato rabita **spremembo route-key mappinga**, ne le enovrstičnega mode flipa.
