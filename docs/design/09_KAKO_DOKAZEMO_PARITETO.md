# Kako dokažemo pariteto

**Za:** agenta, ki bo gradil · **Podlaga:** [07_PARITETNI_POPIS](07_PARITETNI_POPIS.md)

Pariteta je ownerjev pogoj (P3). Pogoj, ki se ga ne da izmeriti, ni pogoj — je želja.
Ta dokument opisuje štiri artefakte, ki iz »pokaži vse« naredijo številko v gitu.

> **Pravilo hiše:** zeleni testi niso dokaz. Rabimo funkcionalni + runtime dokaz.
> Ta dokument je zato mešanica CI testov (poceni, statični) in dev sweepov (dragi, resnični).

---

## Kar že obstaja — ne piši novega orodja

`scripts/audit_website_browser.mjs` (458 vrstic) že zna:

- skovati ownerjev Starlette sejni cookie prek `itsdangerous` (ista tehnika kot
  `tests/security/test_real_stack_security.py`)
- prečesati **29 rout × 4 viewporte × anonimno/prijavljeno**
- zabeležiti vsak URL zahtevka, konzolne napake, 4xx/5xx in posnetek zaslona
- zapisati `results.json` + JPEG-e v izhodno mapo

**To je 80 % paritetnega pasu.** Razširi ga, ne piši drugega.

---

## H1 — ratchet endpointov (statičen, gre v CI)

Razširi `tests/integration/test_route_contract.py`. Ta že lušči API poti iz
`website/js/*.js` prek `_FE_PATH_RE` / `_FE_LITERAL_API_RE` in jih prefiksno primerja z
živo aplikacijo, uvoženo v podprocesu (`:42-77`).

Dodaj:

1. tretji luščilnik čez `website/frontend/src/**/*.ts{,x}` (ista oblika predloge za
   `API_BASE` konstanto)
2. test `test_new_frontend_covers_every_legacy_endpoint`, ki trdi:

```
legacy_paths - new_paths == set(open('tests/data/endpoint_gap.txt'))
```

`tests/data/endpoint_gap.txt` je **datoteka v gitu, zasejana z 91 potmi** iz
[07 §C](07_PARITETNI_POPIS.md). Vsaka faza iz nje briše vrstice. Test pade, če se katera
vrne, in pade, če se katera pojavi, ki je ni na seznamu.

**S tem »91 manjkajočih endpointov« postane številka v gitu, ki mora priti na nič.**

---

## H2 — zamrznjen popis panelov in stolpcev

Dodaj `--manifest` v `scripts/audit_website_browser.mjs`: en `page.evaluate`, ki na vsaki
routi pobere

```js
{ apiPaths, panelTitles, tableColumns: { id: [th text] }, canvasCount, tabs }
```

→ `docs/parity/inventory.json`, **generiran enkrat iz legacyja in zamrznjen**.
`scripts/parity_diff.mjs old new` izpiše dodane/odvzete panele in stolpce na routo.

To je tisto, kar odgovori »ali ima novi session-detail vseh 22 stolpcev«, ne da bi jih kdo
štel na roko.

⚠️ **Poštena omejitev:** legacy paneli so `glass-card` divi brez stabilnih idjev, zato
pobiralnik ključa po besedilu naslova — besedilo naslovov pa se z redizajnom namenoma
spreminja. Rešitev: nove komponente nosijo

```html
data-parity="session-detail.players-table"
```

z istimi ključi kot zamrznjen popis. En atribut na panel (~120 jih je, pol dneva) naredi diff
natančen in preživi vizualni prepis.

---

## H3 — Playwright na vsako routo

Razširi `website/frontend/e2e/smoke.spec.ts` s 6 rout na podatkovno vodeno zanko, ki uvozi
`src/app/routes.ts` **neposredno** — to je povračilo za prenos registra v TS.

Obstoječa izjema za 401/403 samo z `/auth/*` (`smoke.spec.ts:20`, `:54`) je **pravilna,
prepiši jo dobesedno.**

Dodaj dva Playwright projekta: `anon` in `owner` (`storageState` iz skovanega cookieja).
Na vsaki routi trdi:

- HTTP 200
- nič konzolnih napak, nič `pageerror`
- nič 4xx/5xx razen dovoljene avtentikacijske izjeme
- vsak `data-parity` ključ iz popisa je prisoten
- ni error boundaryja
- besedilo ne vsebuje `[object Object]` (ta preverba je v repotu že ujela pravi hrošč)

---

## H4 — korpusna regresija

Vsaka pot, ki jo novo drevo kliče, mora obstajati v posnetem korpusu
(`website/frontend/src/app/pages/__fixtures__/api_*.json` — 55 datotek na 2026-08-29; pot iz načrta `tests/fixtures/api/` ni nikoli nastala, glej [06 §4](06_ARHITEKTURA.md)) — torej je bila na dev
resnično izvedena in vemo, kakšna je oblika odgovora.

---

## Razdelitev CI ↔ dev

| | Kje teče | Zakaj |
|---|---|---|
| H1 + openapi diff | **CI** (`.github/workflows/tests.yml`) | statično + uvoz v podprocesu, brez baze |
| H2, H3, H4 | **dev**, za enim `scripts/parity_sweep.sh` | rabijo Postgres + Redis + živ backend |

⛔ **Ne** poskušaj v `react-frontend` CI job vriniti Postgresa in Redisa.
`playwright.config.ts:31-38` že razlaga, zakaj je to pravo delo zase.

Izhod dev sweepa je **dokaz faze** in se prilepi k PR-ju — kar se ujema z obstoječim
pravilom repota, da je dokaz funkcionalni + runtime, ne zeleni test
([04](04_IZVEDBENI_NACRT.md)).

---

## Posebej: canvas

Nič od zgornjega ne ujame napačne projekcije koordinat. Zato za fazo 5:

1. **vitest** za `src/app/lib/geo/project.ts` in `src/app/lib/proximity/objectives.ts`
   proti posnetim fixtureom — napisan **že v fazi 0**
2. **Playwright pixel-diff** canvasa za **tri fiksne runde na treh mapah**. To je edino
   mesto v celotni migraciji, kjer se primerjava slik splača.

---

## Merilo za dan preklopa

Vse spodnje mora držati hkrati:

| # | Pogoj |
|---|---|
| 1 | `tests/data/endpoint_gap.txt` je **prazna** |
| 2 | `parity_diff.mjs` je čist na **33 routah × 4 viewportih × anon/owner** |
| 3 | H3 zelen na vseh routah, oba projekta |
| 4 | canvas pixel-diff zelen na 3 rundah × 3 mapah |
| 5 | openapi posnetek se ujema z živo aplikacijo |
| 6 | nova stran preizkušena na dev **z realnimi podatki po pravem večeru igranja**, ne samo na zgodovini |

Točka 6 ni birokracija: polovica hroščev v tem produktu se pokaže samo na sveži seji
(nepovezane runde, prazne R1, zamenjave igralcev, warmup okna).

---

## Rollback

Preklop je ena sprememba v `main.py` (SPA fallback) plus ena v deployu. Rollback je
**revert tega commita + `systemctl restart slomix-web`**: fallback izgine,
`StaticFiles(html=True)` spet streže `website/index.html` na `/`. Brez spremembe baze, brez
brisanja datotek.

Vsebinsko hashirana imena datotek so tisto, kar naredi to varno proti 24-urnemu Cloudflare
TTL-ju za JS: rollback in ponovni roll-forward lahko sobivata v cacheu, ne da bi se
zastrupila — kar sedanja `?v=` `sed` shema ne zagotavlja.

**Legacy drevo ostane na disku še en release cikel**, dosegljivo na `/legacy/index.html`
prek ene dodatne route.
