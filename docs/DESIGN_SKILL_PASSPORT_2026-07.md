# Design: Skill Passport — večdimenzionalen profil igralca

**Status:** PREDLOG za ownerjevo odločitev. Nič od tega ni implementirano; brez GO se ne kodira.
**Datum:** 2026-07-25 · **Kontekst:** audit `docs/AUDIT_DATA_CORRECTNESS_2026-07-25.md` §4 (koherenca scoringa)

**Kratice:** **KIS** = Kill Impact Score (kontekstualna vrednost posameznega ubojа, `storytelling/kis.py`) · **PWC** = Player Win Contribution (delež prispevka k zmagi runde, `win_contribution.py`) · **SSR** = Situational Skill Rating (`ssr_service.py`) · **ET Rating** = obstoječi enodimenzionalni skalar (`skill_rating_service.py`)

---

## 1. Ownerjeva vizija (dobesedno, 2026-07-25)

> "Da nas projekt lahko pokaže dejanski skill igralca… koliko je igralec dober, koliko se trudi, koliko igra z ekipo in koliko sam. Skozi čas bodo številke (KIS/PWC + drugi algoritmi) nabrale ogromno podatkov in mi bi s tem lahko naredili ornk statistiko in določili skill igralcu. **Več skillov ima lahko igralec** — nekdo je dober teamplayer in premika objective in se trudi da ekipa zmaga. Takih primerov in playstilov je veliko. Jaz osebno sem lurker/teamplayer, ki rad nastavlja ekipi priložnosti s svojim sacrificem."

Iz tega sledijo štiri zahteve, ki jih noben obstoječi sistem ne izpolnjuje:

| # | Zahteva | Stanje danes |
|---|---------|--------------|
| Z1 | **Več osi, ne ena številka** — igralec ima lahko več skillov hkrati | ET Rating = 1 skalar; archetypes obstajajo, a so session-ephemeral |
| Z2 | **Evidence se nabira čez seje** — več sej = trdnejša ocena | KIS board se resetira vsako sejo; ET Rating se vsako uro preračuna iz nič |
| Z3 | **Več sej = večja teža** | Nihče: igralec s 40 sejami je obravnavan enako kot s 3 |
| Z4 | **Zgodovina mora ostati primerljiva** | Do PR #547 je bila tabela mešanica kis-v2 in v4 |

---

## 2. Predpogoji — kaj mora biti izpolnjeno, PREDEN se to sploh začne

⚠️ **Nobeden od teh treh ni izpolnjen v tej veji.** Vsi so v odprtih PR-jih; dokler ne merga(mo), Passport ni izvedljiv in ta dokument opisuje prihodnje, ne trenutno stanje.

1. **Verzijska higiena** — čaka **#547**. Danes migracija `060` vsem obstoječim vrsticam vtisne `kis-v2`, KIS servis pa prepiše samo scope, ki ga nekdo zahteva; globalnega v4 preračuna ni. Dokler #547 ne teče, seje **niso** med sabo primerljive (potrjeno: pred zagonom 26.288 v2 proti 7.217 v4).
2. **gsid atribucija** — čaka **#546**. Migracija `063` je stolpec dodala, a ga eksplicitno pustila NULL za vso zgodovino in za legacy compute pot. Brez backfilla je 87 % vrstic neatribuiranih; seja čez polnoč ali dve seji na isti datum sta neločljivi.
3. **Čisti serving layer** — čaka **#548/#549**: bot runde izločene, duplikati pobrisani, scope pošten.

**Vrstni red je obvezen:** brez 1 in 2 vsaka agregacija čez seje sešteva mešane formule in izpušča 87 % zgodovine, kar je slabše kot današnje stanje.

**Podatkovna baza (dev, 2026-07-25):** 63 igralcev, od tega **14 z ≥10 sejami**, 9 s 3–9 sejami, 40 z <3. Najbolj aktiven igralec ima 111 sej. To je majhen, a globok vzorec — natanko tak, ki *zahteva* shrinkage in *ne dopušča* naivnih percentilov.

---

## 3. Primerjava: kaj dela gibhub.gg (in kje je njihova šibka točka)

Owner: *"gibhub.gg so vse naše ideje vzeli iz prototipa in jih naredili skoraj bolj kot midva, pri njih so statsi točni."*

Preveril sem njihov javni API (`/api/players/{id}`, `/api/leaderboards`).

**Kar delajo dobro in bi morali posnemati:**

| Njihovo | Opis | Naš status |
|---------|------|-----------|
| **Tiers per format** | `tier: "B"` ločeno za 3v3 (`size=6`) in 6v6 (`size=12`) — diskretna razvrstitev, ki jo človek razume | Nimamo; ET Rating je zvezno število brez formata |
| **Lifetime blok** | En kanoničen agregat: matches/rounds/kills/…/`utro`/`bait_score` | Razpršeno po endpointih |
| **Playstyle metrike** | `bait_score` (!), `stance_*_sec` (prone/crouch/sprint/lean/mg/carrier), `classes_played_seconds` | Delno (lurker, gravity), a session-only |
| **Relacijski podatki** | `top_killers`, `top_victims`, `best/worst_teammates`, `easiest/hardest_opponents` | Rivalries obstaja, a ni v profilu |
| **objective_breakdown** | Po tipu: planted/defused/destroyed/repaired/taken/secured/carrierkilled | Imamo surovo, ni agregirano v profil |

**Kje imajo luknjo — in to je natanko naša priložnost:**

UTRO lestvica (`?metric=utro&size=6`, 177 igralcev) vrne na 1. mestu igralca z **22 rundami** (value 1.2741), tik nad igralcem s **741 rundami** (1.2727). **Brez sample-size korekcije.** Kdor odigra dva dobra večera, prehiti nekoga s tremi leti igre. To je točno napaka, ki jo Z3 prepoveduje.

**Naša strukturna prednost:** gibhub bere strežniške loge — imajo XP, stance čase, shove, distanco. **Nimajo pa pozicijske telemetrije.** Mi imamo 200 ms vzorce pozicij, crossfire geometrijo, spawn timing, aim tracking. Osi kot *lurk*, *space creation*, *enabler*, *objective pressure* so iz logov **fizično neizračunljive**. To je edini prostor, kjer jih ne dohitevamo, ampak delamo nekaj, česar sploh ne morejo.

---

## 4. Predlog: Skill Passport

### 4.1 Pet osi (predlog — owner naj potrdi/preimenuje)

Vsaka os je 0–100, izračunana kot **evidence-weighted percentil znotraj našega bazena**, ne absolutna vrednost.

| Os | Kaj meri | Viri, ki jih ŽE imamo |
|----|----------|----------------------|
| **FRAG** | Čista ubojna moč in kvaliteta ubojev | KIS (kontekstualni impact), K/D, accuracy, headshot % |
| **TEAMPLAY** | Koliko igra z ekipo | crossfire participacija, trade responsiveness, revives, PWC crossfire+trade share, cohesion (koliko časa blizu ekipe) |
| **OBJECTIVE** | Delo za zmago, ki ga K/D spregleda | objective pressure sekunde, carrier events/returns, construction, KIS `is_objective_area` delež, useless-defense (negativno) |
| **LURK / SPACE** | Ownerjeva os: samostojno ustvarjanje prostora in priložnosti | lurker `solo_pct`, space_created (produktivne smrti), enabler (asisti), gravity (koliko pozornosti nase potegne) |
| **CLUTCH** | Vrednost pod pritiskom | solo-clutch KIS multiplierji, low-HP kills, outnumbered situacije, best-lives |

Igralec ni "78" — igralec je npr. **FRAG 61 · TEAMPLAY 84 · OBJECTIVE 72 · LURK 91 · CLUTCH 55**, kar se prevede v čitljivo značko: *"Lurker/Enabler"*. Ownerjev lastni opis (*"lurker/teamplayer, ki nastavlja priložnosti s sacrificem"*) mora iz teh številk pasti ven sam od sebe — to je sprejemni test.

### 4.2 Evidence weighting (jedro Z2/Z3)

Za vsako os in igralca:

```
raw_i        = per-session vrednost osi (že jo znamo izračunati)
n            = število sej z veljavnimi podatki za to os
pool_mean    = povprečje osi čez cel bazen (prior)

shrunk = (n * mean(raw_i) + C * pool_mean) / (n + C)        # C = 5 sej
```

- Igralec z **1 sejo** je potegnjen skoraj do sredine bazena (nima še dokaza).
- Igralec z **20+ sejami** je praktično pri svoji pravi vrednosti.
- Nihče ne "izstreli" na vrh po enem dobrem večeru — rešuje točno gibhubovo 22-rund napako.
- `C = 5` je izhodišče (SSR — Situational Skill Rating, `ssr_service.py` — že uporablja prag 5 sej); kalibriramo na obstoječih 63 igralcih.

Poleg tega vsak profil izpiše **`confidence`** (`min(1, n/15)`) in **`n_sessions`** — ne kot okrasek, ampak vidno ob vsaki osi. Ko je `n < 3`, os prikažemo kot *"premalo podatkov"*, ne kot številko.

### 4.3 Zamrznjeni posnetki (rešuje Z4 in tiho preračunavanje zgodovine)

Danes se `get_player_session_history` preračuna proti **današnji** populaciji percentilov — pretekla seja tako spremeni oceno, ne da bi se karkoli zgodilo.

**Kaj se zamrzne (popravljeno po reviewu):** shraniti samo `raw` + `formula_version` + `n_sessions` **problema ne reši** — če se percentil in `pool_mean` jemljeta iz *trenutne* populacije, vsak nov igralec ali seja spet tiho premakne zgodovinske ocene. Zato posnetek hrani **oboje**:

| Polje | Zakaj |
|-------|-------|
| `raw` | surova vrednost osi za to sejo |
| `pool_mean`, `pool_n`, `pool_sd` | populacijski kontekst **ob tistem trenutku** — brez tega shrinkage ni reproduciren |
| `percentile_at_time` | zamrznjena relativna vrednost = "kje si bil takrat med svojimi" |
| `formula_version`, `n_sessions`, `format` | verzijska in vzorčna sled |

Iz tega sledita **dve različni številki, ki ju je treba ločeno prikazati**:
- **Historični pogled** (npr. "tvoja sezona") = agregat `percentile_at_time` → se **nikoli** ne spremeni za nazaj;
- **Trenutni pogled** ("kje si danes med aktivnimi") = preračun proti današnji populaciji → se **sme** premikati, ker odgovarja na drugo vprašanje.

Verzijski bump → **novi** posnetki, stari ostanejo označeni (kot to že dela `s_effort_service`, edini sistem z dobro verzijsko higieno).

**Kdaj se posnetek zapiše (popravljeno po reviewu):** NE takoj ob koncu seje. KIS se računa leno in ima lastno svežinsko preverbo za pozne proximity/stats importe, zato bi takojšen zapis lahko trajno zamrznil delne podatke. Posnetek nastane šele, ko so izpolnjeni pogoji:

1. vse pričakovane runde seje imajo `round_correlations` popolne (ali je potekel 6-urni timeout, ki ga uporablja obstoječi orphan mehanizem), **in**
2. KIS za ta gsid je aktualne verzije in ni "stale" po obstoječi svežinski preverbi.

Do takrat je seja `pending`. Če pozni import vseeno pride po zamrznitvi, posnetek **ni** tiho prepisan — zapiše se nov z `supersedes` sklicem, tako da ostane vidno, da se je kaj spremenilo.

### 4.4 Formatna ločnica (posnemamo gibhub)

Naši večeri niso homogeni: 3v3 in 6v6 sta drugačni igri, poleg tega **owner sredi večera menja postave za balans**. Zato:

- vsaka os se hrani **per format** (velikost postave iz `rounds`/`lua_round_teams`);
- team-based osi (TEAMPLAY, OBJECTIVE) se pripisujejo **per rundo**, ne per tekmo — menjava postave sredi tekme ne sme pripisati zaslug napačni ekipi;
- Passport privzeto prikaže format, ki ga igralec igra največ, z možnostjo preklopa.

---

## 5. Implementacijski načrt (šele po GO)

| Faza | Vsebina | Ocena |
|------|---------|-------|
| **P0** | Tabela `player_skill_passport_snapshot` (gsid, guid, os, raw, `pool_mean`/`pool_n`/`pool_sd`, `percentile_at_time`, formula_version, n_sessions, format, `supersedes`) + zapis, **sprožen šele ob izpolnjenih pogojih iz §4.3**, ne ob koncu seje | 1 PR |
| **P1** | Backfill posnetkov iz obstoječe zgodovine (38 sej z viri) — vse osi so izračunljive za nazaj | 1 PR + skripta |
| **P2** | Agregacijski servis: shrinkage, confidence, percentil znotraj bazena, per-format | 1 PR |
| **P3** | Endpoint `/api/skill/passport/{guid}` + značke (playstyle label iz osi) | 1 PR |
| **P4** | Kalibracija na 14 igralcih z ≥10 sejami; ownerjev sprejemni test ("ali me sistem prepozna kot lurkerja?") | brez kode |
| **P5** | Šele po P4: leaderboard per os in "kdo je najbolj X" | 1 PR |

UI/UX se namerno ne dotikamo — Passport najprej živi kot JSON + Discord izpis.

---

## 6. Odprta vprašanja za ownerja

1. **Osi**: je 5 pravih? Manjka kaj (npr. *SUPPORT* ločen od TEAMPLAY — medic/ammo delo)? Je katera odveč?
2. **Imena**: FRAG/TEAMPLAY/OBJECTIVE/LURK/CLUTCH — ali raje ET-jezik (npr. *fragger, glue, objective, ghost, clutch*)?
3. **Prag zaupanja**: naj se os pod 3 sejami skrije, ali prikaže sivo z opozorilom?
4. **Formati**: ločiti 3v3/6v6 (kot gibhub) ali za naš community združiti, ker je vzorec majhen?
5. **Značke**: naj sistem dodeli en glavni label (npr. "Lurker") ali dva ("Lurker/Enabler")?
6. **Javnost**: je Passport viden vsem, ali samo igralcu (nekatere osi so lahko občutljive — npr. useless-defense)?
7. **Tiers**: bi želel tudi diskretno lestvico A/B/C kot gibhub, poleg zveznih osi?
