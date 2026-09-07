# Predaja: Opus 5, seja 2026-09-06 → 2026-09-07

Komplementarna k `docs/HANDOFF-astra.md` (sestrina seja). Ta datoteka nosi
**moje** delo, moje odprte postavke in — najbolj uporabno za naslednjega —
pasti, ki so me danes ujele, vsako z meritvijo.

> Bralcu: če imaš pet minut, preberi §3. Tam so napake, ki jih boš sicer
> ponovil, ker so vse videti kot razumno prvo dejanje.

---

## 1. Kaj je šlo na main

| PR | kaj | dokaz |
|---|---|---|
| **#923** | SSH monitor, štiri rezine | v živo: 4 ločeni PID-i, alarm ob 3. napaki kljub 2 restartoma |
| **#948** | popravek PLAN.md | — |
| **#950** | paramiko traceback ne poplavi loga | v živo: `errors.log` 0 vrstic, `bot.log` 24 |
| **#952** | plan ne more več navajati napačnega gapa | kontrola videna pasti na `[3, 16]` proti 13 |
| **#955** | nagrade rund v SPA + botovski filter + `DISTINCT` | gap 13 → 12 |
| **#958** | `--anon-only` ne rabi ownerjeve skrivnosti | prelet steče; prej se ni zagnal |

Vse v **v1.45.0**.

### Odprto ob predaji

- **#912** (arena Lua) — tehnično čist, CI zelen. ⛔ **Pridržek:** `arena_acc_log`
  je nameščen, a **neizmerjen** (0 ACC vrstic v živo; owner je ugasnil testni
  strežnik). Offline pokrit (48/49 primerov, 32/32 mutacij). Manjka en dvoboj.
- **#962** (watchdog: disk mera) — glej §4.

---

## 2. Kaj NE delati (vsak razlog izmerjen)

1. ⛔⛔ **Ne gradi connection poola za SSH.** `paramiko.SSHClient.connect()` ni
   thread-safe ([#1904](https://github.com/paramiko/paramiko/issues/1904)), naše
   operacije tečejo v `run_in_executor`. To je bila moja prvotna postavka v
   #923; iskanje jo je **obrnilo**. Pomaga razmik (Full Jitter), ne pool.
2. ⛔ **Ne dodajaj retryja na `download_file`** — nima zunanjega `wait_for`
   (listing ga ima, 30 s), zato bi držal nit dlje od intervala zanke.
3. ⛔ **Ne "popravljaj" 25 handlerjev s HTTP 200 + `{"status":"error"}`** —
   ownerjeva odločitev (2026-08-30), pripeta s testom.
4. ⛔ **Ne gradi UI za mrtve poti:** `/api/bets` (0 vrstic), `/api/players/{}/awards`
   (2 vrstici), `/api/greatshot/{}/highlights/render` (1 render, februar).
5. ⛔ **Ne briši vrstic iz `tests/data/endpoint_gap.txt`,** da bi bila številka
   manjša — test set preračuna in pade.
6. ⛔ **Ne združuj 282 skupin podvojenih nagrad** (`docs/KNOWN_ISSUES.md`).
   `DISTINCT` odstrani 929 **identičnih**; preostalih 282 je dveh uvozov z
   **različnimi** odgovori — to je neskladje podatkov, ne prikaza.
7. ⛔ **Ne kopiraj `/api/sessions/{}/graphs` kot je.** Pot nosi DATUM; 2 od 3
   legacy klicev ne pošljeta `gaming_session_id`, in **13 od 176 dni (7,4 %)**
   ima več sej — takrat gola klica zlijeta seje v en graf.
8. ⛔ **Ne poganjaj `npx tsc` / `npx vitest`** namesto `npm run` — `openapi.d.ts`
   je generirana in gitignorana; `npm run` jo prek `pre*` kljuk regenerira,
   `npx` NE. Najhujša ni manjkajoča, ampak **zastarela**.

---

## 3. Pasti, ki so me danes ujele

Vse so bile videti kot razumno prvo dejanje. Vsako številko sem izmeril
dvakrat, ker prva ni držala.

### 3.1 ⛔⛔ Artefakt ni commit

Drevo je lahko na pravem commitu, medtem ko je bundle 13 ur star. `/api/build`
bere **kodo**, zato bi kazal prav. Izmerjeno 2026-09-07: `static/app` zgrajen
`09-06 11:03`, SPA vir spremenjen `09-07 00:23`. Guard je zdaj v
`scripts/dev_deploy.sh`.

### 3.2 ⛔⛔ Hladen cache spremeni, koliko klicev merilnik SPLOH VIDI

Ne samo časa. Ista stran, isto okno: **hladno 2 klica, toplo 40**. Dvakrat sem
skoraj poročal lažno degradacijo. Vsaka številka mora povedati hladno/toplo.

### 3.3 ⛔⛔ `ls -la <mapa>` pove mtime IMENIKA, ne vsebine

Na tem sem zgradil pripombo, da je legacy bundle 5 dni zastarel, in jo moral
**preklicati** — bil je 6 ur novejši. Pravo orodje: `find <dir> -type f -printf '%T@'`.

### 3.4 ⛔⛔ Squash merge naredi, da veja NI prednik maina

`git merge-base --is-ancestor origin/<veja> origin/main` je zato javil "ni
mergana" za **7 vej, katerih PR-ji so vsi MERGED** (#885, #892, #893, #900…).
Pravi test je stanje PR-ja, ne prednikovanje.

### 3.5 ⛔ Merilnik, ki meri prehitro, poroča prazno stran, ki ni prazna

`/record-book` mi je javil 350 znakov; stran je polna rekordov. Uradni prelet
čaka `networkidle` + 2 500 ms, moj je čakal `load` + 1 200 ms.

### 3.6 ⛔ Štej nosilce, ne datotek

»7 proximity strani brez testa« je bilo napačno: `Proximity.test.tsx`
(403 vrstic, 14 testov) jih pokriva prek starša.

### 3.7 ⛔ Štetje napak po VRSTICAH ni primerljivo čez #950

`scripts/health_check.sh:585` ima prag 20/24 h, šteto po vrsticah. Isti dan:
**751 → 38**. Prag ni bil prenizek — bil je **neuporaben** (vedno čez).
Če dodajaš »error rate« preverbo, štej **dogodke**.

### 3.8 ⛔ `git stash pop` brez `git stash list`

`git stash -q` na čistem drevesu ne shrani ničesar, `pop` pa potegne **tuj**
stash. Naredil sem si konflikte v čistem drevesu. Na tem stroju stoji
`stash@{0}: WIP on deploy-script-and-docs` — **ni moj**, nedotaknjen.

### 3.9 ⛔ `grep -c chrom` šteje sebe

Trikrat danes je ta razred (grep/pkill ujame lastno ukazno vrstico) dal
napačen odgovor; enkrat sem si s `pkill -f` ubil lastno lupino.

---

## 4. Predlagani popravki, ki jih nisem izvedel

Vsi rabijo ownerjeve roke (sudo) ali njegovo odločitev.

| kaj | ukaz | zakaj |
|---|---|---|
| **journald raste brez meje** | `sudo journalctl --vacuum-size=200M` + `SystemMaxUse=200M` v `/etc/systemd/journald.conf` | drži **442 MB** na 32 GB SSD; brez trajne meje spet zraste |
| **`/tmp` se ne čisti sam** | `sudo systemctl enable --now systemd-tmpfiles-clean.timer` | timer je `static`; zato so tam sedele **avgustovske** datoteke |
| **#962: watchdog disk mera** | merge | watchdog je kazal 84,9 %, `df` 90 % — prag 85 % se sproži šele pri `df` ~89,6 % |
| **restart dev bota** | ownerjeva domena | vsakič, ko gre nova koda na main |
| 🔑 **geslo v `ps`** | rotacija + `PGPASSWORD`/`.pgpass` | MCP DSN je v argv, `ps -eo args` ga pokaže vsem |

### Kaj sem 2026-09-07 sprostil na SSD (nič izbrisano)

`/` je šel z **90 % → 80 %** (3,2 G → 6,2 G prosto):

- `share/_from_ssd_tmp_2026-09-07/` ← stari venvi, playwright, etlegacy-source
  in **2 719** map testnih logov (**1,7 G**)
- `share/slomix-archive/cleanup-2026-08-26/` ← git backupi pred prepisom
  zgodovine #817 (**630 M**)
- 9 git worktreejev odstranjenih prek `git worktree remove` (ne `rm -rf`);
  preverjeno, da nobeden ni držal nepotisnjenega dela

---

## 5. Stanje ob predaji

- **endpoint gap: 12** — merilo je `grep -vcE '^\s*(#|$)' tests/data/endpoint_gap.txt`,
  ne spomin. Vrstni red preostalih 12 (po podatkih in **živosti**, ne po
  velikosti) je v komentarjih te datoteke.
- **Prelet faze 7: delen.** Manifest (32 rut) + skrajšani prelet (20 rut, vse
  200, 0 konzolnih napak). Celoten (4 viewporti × anon/owner) ni tekel — RAM.
- ⛔ **Bundle ni zgrajen**: nobena SPA sprememba od `09-06 11:03` ni vidna na
  `:8000`. Pred preletom ali oceno frontenda: `npm run build:app` +
  `scripts/dev_deploy.sh` (ta restarta servise → **ownerjev DA**).
- Dev servisi tečejo iz `/home/samba/share/slomix-dev-run` (ne več iz
  agentovega drevesa). Watchdog: 11 preverb, vse `ok`, vključno z
  `bot_streaks`, ki bere datoteko iz #923.

---

## 6. Kje so podrobnosti

- `docs/KNOWN_ISSUES.md` — podvojene nagrade (1472/929/282), sprememba štetja
  vrstic v `errors.log`
- `tests/data/endpoint_gap.txt` — triaža 12 poti z razlogi in datumi živosti
- `docs/PLAN.md` — proga SSH monitorja, štiri rezine
- `docs/HANDOFF-astra.md` — sestrin del predaje (§H je moj odgovor Astri)
