# docs/design — nova spletna stran

Deset dokumentov, dva sklopa. **Lokalni, netrackani** — commit šele na ownerjevo besedo.

## Sklop 1 — pregled dizajnerske predaje (23. 8. 2026 dopoldne)

Predmet: `Slomix design refresh discussion2.zip` (razpakirano v
`/home/samba/share/slomix-archive/design_handoff_2026-08-22/`).

| | |
|---|---|
| [00_PREGLED](00_PREGLED.md) | kaj je v paketu, sodba, pet stvari, ki jih moraš vedeti prej |
| [01_PREVERJENE_TRDITVE](01_PREVERJENE_TRDITVE.md) | 25 trditev drži, 15 ne, 10 izmišljenih, 7 nedoslednosti, 10 najdb o naši kodi |
| [02_PO_ZASLONIH](02_PO_ZASLONIH.md) | 8 zaslonov: kaj imamo, kaj manjka, ocena, pasti |
| [03_TOKENI_IN_STIL](03_TOKENI_IN_STIL.md) | paleta, tipografija, izmerjen kontrast, cena preklopa |
| [04_IZVEDBENI_NACRT](04_IZVEDBENI_NACRT.md) | ⚠️ delno preživet — pisan za pot »dizajn v obstoječo stran« |

## Sklop 2 — gradnja nove React strani (23. 8. 2026 popoldne)

Predmet: ownerjeva odločitev, da se React zgradi na novo, na novem dizajnu.

| | |
|---|---|
| [05_ODLOCITEV_SKLADA](05_ODLOCITEV_SKLADA.md) | **beri prvi.** Zakaj React, kaj je bilo zavrnjeno in zakaj, štiri pravila |
| [06_ARHITEKTURA](06_ARHITEKTURA.md) | samostojna SPA, dve strani hkrati na dev, rutanje + hash shim, tipi za 91 endpointov |
| [07_PARITETNI_POPIS](07_PARITETNI_POPIS.md) | **hrbtenica.** 31 rout, panel za panelom, vseh 91 manjkajočih endpointov |
| [08_GRADBENI_NACRT](08_GRADBENI_NACRT.md) | 8 faz, prenos interaktivne kode, ocena 21–28 tednov, najbolj tvegana faza |
| [09_KAKO_DOKAZEMO_PARITETO](09_KAKO_DOKAZEMO_PARITETO.md) | štirje artefakti, merilo za dan preklopa, rollback |

## Sklop 3 — raziskava pred gradnjo (24. 8. 2026, Fable)

Predmet: živi claude.ai design projekt (novejši od zipa!), tehnični spiki,
API korpus, preslikava rout. Ownerjeva odločitev 24. 8.: smer = temna
instrumentna iz zipa (D3).

| | |
|---|---|
| [10_VIZUALNA_REFERENCA](10_VIZUALNA_REFERENCA.md) | živi projekt vs zip; 9 home variant, theme-variations, spiderweb; kje so kopije in posnetki |
| [11_KOMPONENTNI_POPIS](11_KOMPONENTNI_POPIS.md) | besednjak dizajna → seznam React komponent + pravila, ki jih uveljavijo |
| [12_PRESLIKAVA_ROUT](12_PRESLIKAVA_ROUT.md) | vseh 33 rout → prototip/prekritje/izpeljava, po fazah |
| [13_SPIKE_REZULTATI](13_SPIKE_REZULTATI.md) | S1–S4 dokazani (dva builda, router+shim, tokeni+fonti, openapi tipi) + 2 pasti shima + verzije paketov |
| [14_API_KORPUS](14_API_KORPUS.md) | 204×200 posnetih GET odgovorov, referenčni ID-ji, opažanja |
| [15_ODPRTE_ODLOCITVE](15_ODPRTE_ODLOCITVE.md) | padle (D1–D4) in odprte (O1–O8) odločitve |
| [16_NAVODILA_ZA_GRADBENEGA_AGENTA](16_NAVODILA_ZA_GRADBENEGA_AGENTA.md) | **vstopna točka za builderja** |
| [17_PROXIMITY_POPIS](17_PROXIMITY_POPIS.md) | vodotesen popis proximity/storytelling/replay: 91 poti, razredi A–D, 7 sirot (O9), kontrolni seznam faze 5 |

## Bralni vrstni red za agenta, ki gradi

`16` → `05` → `06` → `08` (svoja faza) → `07` (naloge te faze) → `09` (kako dokažem, da je faza končana) → `11`+`12` → `13`/`14`.

## Kar velja povsod

- Produkcija (`slomix.fyi`) teče vanilla in se je **ne dotikamo**, dokler nova stran ni dokazana.
- Nove funkcije od 23. 8. 2026 gredo **samo** v novo stran; legacy dobi le popravke.
- Nov dizajn je vizualni jezik, **ne obseg** — nova stran mora pokazati vse, kar kaže današnja.
- Dokazi: funkcionalni + runtime, ne zeleni testi.
