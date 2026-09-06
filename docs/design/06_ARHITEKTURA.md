# Arhitektura nove strani

**Za:** agenta, ki bo gradil · **Sledi iz:** [05_ODLOCITEV_SKLADA](05_ODLOCITEV_SKLADA.md)
**Naprej:** [07_PARITETNI_POPIS](07_PARITETNI_POPIS.md) · [08_GRADBENI_NACRT](08_GRADBENI_NACRT.md)

---

## 1. Oblika: samostojna aplikacija, ne vgnezdena

**Odločitev: nova stran je samostojna SPA z lastnim `index.html`, lastnim routerjem in
lastno CSS.** Ne mounta se v legacy lupino.

Razlog je izmerjen, ne estetski. Danes je React zgrajen v Vite **library** načinu
(`website/frontend/vite.config.ts`, entry `src/route-host.tsx`, izvoz `mountRoute`) in ga
`website/js/modern-route-host.js` vstavi v legacy `index.html`. Posledica:

| | zahtevkov | JS | CSS |
|---|---|---|---|
| legacy route (`#/sessions`) | 69 | 53 dat. / 1.082 KB | 335 KB |
| **React route (`#/skill-rating`)** | — | **73 dat. / 1.348 KB** | **441 KB (dva sheeta)** |

React route je danes **dražji** od legacy route, ker plača oboje. Tega se ne da odstraniti s
code-splittingom: `website/index.html` (320 KB, 29 `id="view-*"` sekcij, `.glass-card`
definiran inline na `:77`) in `website/css/tailwind.css` (342 KB) sta trda pogoja vsake
React route.

Dve nadaljnji posledici vgnezdenosti, obe vidni v kodi:

- `website/js/app.js:169` zahteva, da `document.getElementById('view-' + viewId)` obstaja,
  preden se React sploh lahko mounta. React route je torej izrazljiva samo, če legacy lupina
  ročno nosi prazen `div` z ustreznim id-jem.
- `Records.tsx` in `HallOfFame.tsx` sta nedosegljiva iz **dveh** neodvisnih razlogov:
  `records`, `record-book` in `hall-of-fame` so vsi `VIEW_MODE.LEGACY` (`mountRoute` se
  nikoli ne pokliče), **in** vsi trije se zložijo na `viewId: 'record-book'`, za katerega
  `route-host.tsx` nima ključa. Oboje izgine, ko ima React svoj router.

Za primerjavo, kaj samostojna aplikacija dejansko stane (izmerjeno na obstoječem buildu):
cela React aplikacija **1,01 MB surovo / 214 KB gzip**; jedro 442 KB / **98 KB gzip**;
posamezen route chunk 12–19 KB gzip. Legacy danes: `js/*.js` 349 KB gzip + `index.html`
48 KB gzip + `tailwind.css` 39 KB gzip, **na vsaki route**.

### Razporeditev na disku

En npm paket, dva build cilja. `website/frontend/` in obstoječi `vite.config.ts` (library)
ostaneta **nedotaknjena** — produkcija gradi `static/modern/` iz deployane oznake
(`scripts/deploy_release.sh:512`), zato premikanje `main` produkcije ne zadene, dokler ni
narejena nova oznaka.

Dodaj:

- `website/frontend/vite.app.config.ts` — app način, `build.outDir: '../static/app'`,
  `build.manifest: true`, `base: process.env.APP_BASE ?? '/app/'`, entry
  `website/frontend/app.html`
- `website/frontend/src/app/` — vsa nova koda

**Pravilo odvisnosti:** novo sme uvažati iz starega (`src/api/client.ts`, `src/lib/format.ts`,
`src/lib/navigation.ts`); staro ne sme nikoli uvažati iz `src/app/`. Uveljavi z vitest testom,
ki grepa importe, ne z lint pluginom.

En paket in ne dva, ker je obstoječih 26 strani + `client.ts` + `hooks.ts` surovina za prenos
in je nabor odvisnosti identičen.

---

## 2. Kako FastAPI na dev streže obe strani hkrati

`website/static/app/` leži znotraj `StaticFiles(directory="website")` na `/`
(`website/backend/main.py:465`), zato je **že dosegljiv** na `/static/app/index.html` brez
sprememb backenda. To je zasilna varianta za prvi dan.

Za pravo predpono z globokimi povezavami registriraj **pred** vrstico 465, ob bloku
`greatshot_spa_entry` (`main.py:408-416`):

```python
APP_DIST = os.path.join(project_root, "website", "static", "app")
if os.path.isdir(APP_DIST):                       # prod checkout nima builda → route se ne registrira
    app.mount("/app/assets", StaticFiles(directory=os.path.join(APP_DIST, "assets")), name="app-assets")

    @app.get("/app", include_in_schema=False)
    @app.get("/app/{full_path:path}", include_in_schema=False)
    async def app_spa_entry(full_path: str = ""):
        return FileResponse(os.path.join(APP_DIST, "index.html"))
```

Trije detajli, ki se jih ne sme zgrešiti:

1. **Vrstni red registracije**: mount `/app/assets` mora biti pred lovilcem `{full_path:path}`.
2. `/app` in `/app/index.html` dodaj v `_ENTRYPOINT_NO_CACHE_PATHS` (`main.py:249-262`),
   in dodaj vejo `elif path.startswith("/app/assets/")` z `immutable`, ob obstoječi
   `/static/modern/chunks/`.
3. **Varovalo `if os.path.isdir(APP_DIST)`** je tisto, kar naredi to spremembo varno za
   merge na `main`, medtem ko produkcija teče vanilla: brez builda se route sploh ne rodi.

Obe strani sta potem živi hkrati na `192.168.64.116:8000`: stara na `/`, nova na `/app/`.
Isti origin, isti sejni cookie, brez CORS, brez dela z avtentikacijo.

**HMR:** `vite dev` na :5173 s `server.proxy` za `/api`, `/auth`, `/assets`, `/static` →
`127.0.0.1:8000`. Cookie ne loči vrat, zato je sejni cookie deljen; **ampak** Discord OAuth
`redirect_uri` se z :5173 ne ujema, zato za zaslone za prijavo bodisi dodaj callback bodisi
uporabi kovanje cookieja iz `scripts/audit_website_browser.mjs`.

### CSP je pri tem na boljšem

Nova `index.html` nosi svojo politiko. Vite oddaja zunanje module (ni potrebe po
`'unsafe-inline'` za skripte), `lucide-react` je bundlan (ni unpkg), in če Chart.js postane
npm odvisnost namesto neSRI-jevega jsdelivr taga (`website/index.html:1256`), tudi jsdelivr
odpade. To odstrani dva tuja izvora skript in eno nepripeto dobavno verigo.

**Chart.js zamenjaj v fazi 0**, v `components/Chart.tsx` — danes sega po `window.Chart`
(`Chart.tsx:11-14`), kar deluje samo zato, ker ga je naložila legacy lupina.

---

## 3. Rutanje: prave poti + odjemalski hash shim

**Odločitev: prave poti prek History API, z odjemalskim shimom za stare hash naslove.**

To je sprememba glede na prvo različico načrta, ki je predlagala ohranitev hash naslovov.
Obe strani, ker je bila razlika resnična:

- **Za hash:** bot objavlja hash povezave, in `route-registry.js:487` že nosi alias iz
  prejšnjega preimenovanja (`#/tonight` → `live`) s komentarjem, da morajo zaznamki in
  Discord povezave delati naprej.
- **Za prave poti (prevlada):** hash sili vsak naslov skozi en dokument — kar je natanko
  sklopitev, ki jo odstranjujemo — in ne dovoli cache glav na route. Ugovor glede bota pa se
  razreši sam: **strežnik fragmenta nikoli ne vidi**, zato mora biti shim tako ali tako
  odjemalski. ~30 vrstic v `main.tsx`: preberi `location.hash`, poženi prenešeni
  `parseHashRoute()`, `history.replaceState` na pot.

Ta en shim pokrije **vse producente hash naslovov**. Preverjeno jih je **osem**:

| Kje | Vrstica | Povezava |
|---|---|---|
| `bot/services/session_digest_service.py` | 96 | `/#/session-detail/date/{date}` |
| ″ | 166 | `/#/session-detail/{gsid}` |
| ″ | 184 | `/#/story` |
| ″ | 185 | `/#/leaderboards` |
| ″ | 233 | `/#/availability` |
| ″ | 306 | `/#/profile/{guid8}` |
| `bot/cogs/last_session_cog.py` | 183 | `/#/session-detail/date/{date}` |
| `website/backend/main.py` | 419-428 | `/share/{id}` → 302 na `/#/uploads/{id}` |

Plus alias `#/tonight` (`route-registry.js:487`) in `#/records` / `#/hall-of-fame`
(`:127`, `:279`). **Shim ostane za vedno** — Discord sporočila so trajna.

### Prenos registra

`website/js/route-registry.js` se prenese v `src/app/routes.ts` kot **edini vir resnice o
rutanju**. Vsak vnos: `{ path, key, label, nav, element, legacyHash(params), parseLegacyHash?(hash) }`.

Trije konkretni učinki prenosa:

1. **Dvojnost ključ↔`viewId` umre.** `records` in `hall-of-fame` postaneta zavihka ene
   Record Book route (`/record-book?tab=records`), `Records.tsx` in `HallOfFame.tsx` pa
   komponenti zavihka namesto rout. En identifikator: `path`.
2. **`catalog.ts` se izbriše.** Njegova edina odjemalca sta `preview-main.tsx` (dev
   predogled — nadomesti ga aplikacija sama) in tip `ModernRouteContext`, ki ga uvaža
   `route-host.tsx`; tip inlinaj (2 vrstici). Z njim gresta `preview-main.tsx` in
   `styles/route-host.css`.
3. `website/js/route-registry.js` **ostane nedotaknjen do preklopa** — uvažata ga `app.js:47`
   in `proximity.js:7`.

**Router: react-router v7.** Gnezdene postavitve, parametri, lene route, obnovitev scrolla —
ročno pisanje tega čez 33 rout stane teden, ki se ne povrne. To je edina nova runtime
odvisnost.

Dodaj vitest, ki prebere `route-registry.js` in trdi, da se vsak route key razreši v pot v
`routes.ts` in da je `hashToPath('#/x')` za vsakega neprazen. Izpuščena route postane rdeč
test, ne odkritje.

---

## 4. Tipi in klient za 91 endpointov

⚠️ **`/openapi.json` sam po sebi ne da tipov odgovorov.** Preverjeno na živi instanci:
247 poti / **259 operacij**, `components.schemas` jih ima **10**, in **samo 5 operacij ima
tipizirano 200 shemo**. Vzrok: v `website/backend/routers/*.py` je **259 dekoratorjev in
0 `response_model=`**. `openapi-typescript` bo torej zgeneriral `paths` mapo, v kateri je
vsak odgovor `unknown`.

Zato trije koraki, ne eden:

### (a) Zamrznjen posnetek specifikacije
`scripts/dump_openapi.py` uvozi aplikacijo v podprocesu **natanko tako, kot to že dela**
`tests/integration/test_route_contract.py:42-77` (minimalno okolje, nikoli dev `.env`) in
zapiše `docs/api/openapi.json`. Pytest ga regenerira in diffa. ~40 vrstic, ker podprocesni
pas že obstaja. To je hkrati changelog API-ja in hrbtenica paritetnega pasu.

### (b) `openapi-typescript` čez posnetek
→ `src/api/generated/openapi.d.ts`, nato tanek `apiGet<P extends keyof paths>(path, params)`.
Prevajalnik s tem preveri **poti in imena/tipe/privzetke query parametrov** — in prav tam
živijo pravi hrošči (`days` proti `range_days`, pravilo XOR `session_date` /
`gaming_session_id`, ki je že komentirano v `client.ts:124`).

Tip odgovora se razreši skozi **ročno pisano preslikavo**, in to je tisto, kar postane
`types.ts`: ključana po poti, tako da je neuporabljen tip napaka prevajanja, manjkajoč pa
`unknown`, ki ga moraš namerno razširiti. To je mehanizem, ki prepreči, da spet zraste čez
1.851 vrstic. **Cilj pod 400 vrstic do preklopa.**

⛔ **Ne** poganjaj `orval` / `openapi-fetch` čez celoto — dobiš 260 funkcij, ki vračajo
`unknown`, in izgubiš urejen `api` objekt.

### (c) Prave tipe odgovorov si zaslužiš po fazah
Vsaka faza doda `response_model=` endpointom, ki jih ta faza porabi. ~1 dan backend dela na
fazo. Dvojno povračilo: generirani TS tip postane resničen, **in**
`tests/integration/test_api_response_contracts.py` dobi shemo namesto ročnih seznamov ključev.

### Pospeševalnik z najvišjim vzvodom
`scripts/record_api_corpus.py` — obišči vsak GET iz posnetka na dev z ownerjevim cookiejem
in shrani `website/frontend/src/app/pages/__fixtures__/api_<slug>.json` (načrtovana pot `tests/fixtures/api/` ni bila uporabljena — posnetki živijo poleg testov, ki jih berejo). En artefakt, tri uporabe: (1) osnova za oblike
`response_model`, (2) MSW mocki, da testi strani ne rabijo baze, (3) zlati podatki za
paritetni pas. **En popoldan dela, ki spremeni vsako naslednjo fazo.**

### Kaj od obstoječega preživi

- **`client.ts` oblika preživi** — en `api` objekt z imenovanimi metodami je pravilen in je
  tisto, kar sploh omogoča statični pregled endpointov. `get<T>()` zamenja `apiGet`.
- ⛔ **Izbriši 304-retry cache (`client.ts:80-104`).** Obstaja, ker `HTTPCacheMiddleware`
  pošilja ETage in `fetch` ponovi `If-None-Match`; React Query plus `cache: 'no-store'` na
  živih endpointih to pokrije, modulski `Map`, ki nikoli ne izloča, pa je v dolgo živeči SPA
  puščanje pomnilnika.
- **`hooks.ts` preživi skoraj v celoti** — 748 vrstic uglašenih `staleTime` /
  `refetchInterval` je nosilno znanje (live-status 30 s / 60 s). Manjkajo mu `useMutation`
  ovoji; danes vsak zapis živi v `auth.js` / `uploads.js`.

---

## 5. Dizajnerski sistem

- Tokeni iz [03_TOKENI_IN_STIL](03_TOKENI_IN_STIL.md) gredo v `@theme` nove aplikacije
  (Tailwind v4). **Legacy Tailwind v3 se ne dotika** — produkcija teče iz njega.
- Brez `glass-*`, brez `font-black`, radij 0. Ker je aplikacija nova, tu ni 488 klicnih mest
  za popravljanje — samo se jih ne uvede.
- Fonta **self-hostaj** (`@fontsource/barlow-condensed`, `@fontsource/ibm-plex-mono`). Nova
  `index.html` odpravi razlog, zaradi katerega je 03 predlagal Google Fonts: lastna lupina
  pomeni lastno CSP in lasten build, `@font-face` pa Vite obdela sam.
- Popravek kontrasta iz 03: oznake `#6b6862` → `#807c75` (3,55 → 4,74).
- **Ena** navigacija in **ena** animacijska konstanta (950 ms, s `prefers-reduced-motion`) —
  prototipi imajo štiri različice navigacije in tri različne dolžine animacije.

---

## 6. Kaj se NE spreminja v tej fazi

| | Zakaj |
|---|---|
| `website/js/**`, `website/index.html` | produkcija teče iz tega |
| `website/tailwind.config.cjs`, `website/css/tailwind.css` | isto |
| `website/frontend/vite.config.ts` (library) + `route-host.tsx` | gradi živih 4 React rout |
| `scripts/deploy_release.sh` | do dneva preklopa nespremenjen |
| Botove povezave | shim jih pokrije; menjajo se zadnje, in šele ko sprejmemo, da stara Discord sporočila nehajo delati |
