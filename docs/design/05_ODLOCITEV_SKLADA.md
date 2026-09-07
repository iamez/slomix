# Odločitev o skladu: React, zgrajen na novo

**Datum:** 23. 8. 2026 · **Odločil:** owner · **Status:** zaprto, se ne odpira znova
**Sledi iz:** [00_PREGLED](00_PREGLED.md) · **Naprej:** [06_ARHITEKTURA](06_ARHITEKTURA.md)

---

## Odločitev

Nova stran se zgradi **v React 19 + TypeScript**, na novem dizajnu, tako da pokaže projekt
tak, kot je danes.

## Štiri pravila, ki iz tega sledijo

Ta štiri so ownerjeva, ne moja. So robni pogoji, ne predlogi.

| # | Pravilo |
|---|---|
| **P1** | **React je cilj.** Nova stran se gradi v React, ne v vanilli, ne v čem tretjem. |
| **P2** | **Gradi in testira se dolgo na dev** (`192.168.64.116`). **Produkcija (`slomix.fyi`) teče vanilla nedotaknjena**, dokler nova stran ni dokazana. |
| **P3** | **Polna pariteta pred preklopom.** Nova stran mora pokazati vse, kar živa stran kaže danes: vseh 91 manjkajočih endpointov, vse panele, vse stolpce. Popis je v [07_PARITETNI_POPIS](07_PARITETNI_POPIS.md). |
| **P4** | **Nove funkcije od zdaj samo v novo stran.** Legacy dobi le popravke napak. |

---

## Zakaj React — in zakaj številke tega same ne pokažejo

Iz same kode React izgleda kot opuščena veja. Izmerjeno:

- poganja **4 route od 31** (`website/js/route-registry.js`, `mode: VIEW_MODE.MODERN`)
- **nobene nove od 27. 3. 2026** (`git log -S"mode: VIEW_MODE.MODERN"`)
- avgusta 2026: **80 commitov v `website/js`, 8 v `website/frontend`**
- kliče **92** endpointov proti legacyjevim **172**

Ownerjev razlog to postavi drugam: **React ni stal, ker bi bil napačna izbira.** Stal je,
ker so morale ideje sproti iz glave na stran, sicer zbledijo — in edina stran, ki je takrat
tekla, je bila vanilla. Vsaka nova ideja je zato šla v legacy, in razlika je rasla hitreje,
kot jo je kdo zapiral. To je razvojna dinamika, ne tehnična sodba, in številke je ne vidijo.

Ta dinamika je zdaj naslovljena s **P4**: nove ideje gredo v novo stran. To je edina
varianta, pri kateri se razlika zapira in ne širi — in edini razlog, da ta poskus ne konča
kot prejšnji.

---

## Kaj je bilo predlagano in zavrnjeno

Zapisano zato, da čez tri mesece nihče ne odpira iste razprave. Vsak predlog ima razlog za
zavrnitev, ne samo oznako.

### Zavrnjeno: vanilla, konsolidiran

Predlog: React ven (4 route nazaj v legacy), router polenobiti, skupni `lib/`, popravek
`escapeHtml`, lastna CSS namesto Tailwinda.

Zavrnjeno, ker: 34.195 vrstic `innerHTML` nizov brez enega samega testa ni podlaga, na kateri
hočemo graditi naslednjih pet let. Ceneje bi bilo danes, dražje vsak dan potem.

### Zavrnjeno: Preact + htm brez build koraka

Predlog: pravi komponentni model, ~16 KB vendorane ESM knjižnice, brez npm na produkciji,
samodejno escapanje.

Zavrnjeno, ker: tehnično lepo, a bi bil to **tretji** sklad v istem repotu. React drevo že
obstaja (26 strani, 11.245 vrstic) in je surovina za prenos; Preact bi to zavrgel in začel
tretjič.

### Zavrnjeno: strežniško izrisan HTML (Jinja2 + htmx)

Predlog: Python namesto JS za 81 % strani (`surfaceType` v registru: 25 read-heavy, 3
write/auth-heavy, 2 mixed, 1 static), prave poti, prvi izris ~0,9 s namesto 6,7 s.

Ima resnične prednosti in nekaj jih je bilo izmerjenih:
- prijava je že podpisan HttpOnly cookie (`website/backend/main.py:225-232`) → SSR ne rabi
  ničesar novega;
- `StaticFiles` na `/` je mountan **zadnji** (`main.py:463-465`) → nove HTML route so aditivne;
- `get_db_pool()` obstaja izrecno za klic mimo HTTP (`dependencies.py:76`) → SSR handler bi
  lahko klical obstoječo funkcijo routerja brez refaktorja.

Zavrnjeno, ker: ~11.000 vrstic res interaktivnega JS (`replay.js` 1.175, proximity canvas
~1.500, resumable uploader, `availability.js` 2.418, 5 polling zank) ostane JS v vsakem
primeru. Pokril bi torej 60 % strani in pustil dva sklada. Poleg tega je SEO — glavna
prednost SSR — za zasebno skupinsko stran skoraj brez vrednosti.

### Zavrnjeno: dokončati React po obstoječi poti (route za routo na produkciji)

Zavrnjeno z **P2**: preklapljanje na produkciji pomeni mesece stanja pol-nova-pol-stara, in
to je natanko stanje, ki je prvo migracijo naredilo nevidno.

---

## Kaj to pomeni za obstoječi React

Obstoječi React se **ne nadaljuje, ampak uporabi kot surovina**. Konkretno:

- `website/frontend/src/api/hooks.ts` (748 vrstic, 83 hookov z uglašenimi `staleTime` /
  `refetchInterval`) je nosilno znanje — **ostane skoraj v celoti**.
- 26 strani v `src/pages/` so **prvi osnutki**, ne dokončane strani. So izhodišče, ne cilj.
- `website/frontend/src/runtime/catalog.ts` je **zastarel in laže** (trdi 20 »modern«) —
  se izbriše, glej [06](06_ARHITEKTURA.md).
- Vite v **library** načinu (`vite.config.ts`, entry `src/route-host.tsx`) je razlog, da je
  React danes dražji od legacyja: mountan je v legacy lupino in plačaš oba sklada
  (izmerjeno: React route 73 zahtevkov / 1,35 MB + dva Tailwinda 441 KB, legacy route
  53 / 1,00 MB + 335 KB). Nova stran je **samostojna aplikacija**.

## Popravek prejšnjega spomina

Zapis `react-migration.md` (7. 3. 2026) trdi »19/19 routes migrated (MIGRATION COMPLETE)«.
To ni res in ni bilo res: register je takrat imel in ima še danes 4 preklopljene route.
Zapis izhaja iz istega vira zmote kot `catalog.ts`. Kdor ga bere, naj ga bere kot **seznam
napisanih strani**, ne kot stanje migracije.
