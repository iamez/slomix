# Slomix — dom naše scene (vizija 2026 → ciljno stanje 2027)

> Produktno-strateška vizija, zapisana 2026-06-11; opisuje ciljno stanje
> platforme do konca 2027. Sinteza: lastnikova filozofija
> ([domain brief](research/VISION_2026_DOMAIN_BRIEF.md)) + 4 research reporti:
> [R1 engagement](research/VISION_2026_R1_ENGAGEMENT.md) ·
> [R2 UX](research/VISION_2026_R2_UX.md) ·
> [R3 ET ekosistem](research/VISION_2026_R3_ET_ECOSYSTEM.md) ·
> [R4 male skupnosti](research/VISION_2026_R4_SMALL_COMMUNITIES.md).
> Vsaka trditev ima vir ali eksplicitno oznako negotovosti — dopustni
> obliki sta [hipoteza] (naša domneva) in [inferenca]/[naša izpeljava]
> (sklep iz virov, ki ga vir neposredno ne potrjuje).

## Severnica

**Večer je produkt; website je njegov spomin.** (R4, zapoved #1)

Slomix ni "stats viewer". Je operacijski sistem naše 20-letne skupine:
pripravi naslednji igralni večer, ga v živo spremlja, ga zjutraj pove kot
zgodbo in ga za vedno shrani. Discord ostane reka (pogovor, sprožilci),
website postane knjižnica (spomin, identiteta, globina) — in vsaka stvar na
strani je en deep-link stran od Discorda (R4 §2).

**Pozicioniranje** (R3 positioning mapa): vsi vrstniki sedijo v enem kotu —
trackerji imajo doseg brez globine, Oksii ima match reporte brez weba in
identitete, greatshot ima deme brez igralcev, crossfire.nu je imel skupnost
in je mrtev. Slomix je sam na desnem robu analitične globine (pozicije
@200ms, spawn-wave, KIS, aim — tega nima nihče); odprt prostor je navpično:
**micro-crossfire + deep analytics za eno skupnost**. Oksii se približuje
(etl-match-reports, etl-player-chemistry, jun 2026) — a Discord-image-first;
naš moat je interaktivni web + telemetrija, ki je ne zajema.

## Pet stebrov

### 1. JUTRO — push spomina, ne parkiranje (prvi po ROI)
Arhiv, na katerega nihče ni opomnjen, je mrtev arhiv (R4 §3, Facebook
"On This Day": 60-90M dnevnih uporabnikov). Najmočnejši dokazani vzorec
celotne raziskave:
- **Jutranji digest v Discord** po vsaki seji: zmagovalec, score, MVP, en
  narativ, "novi rekordi" — vsak element deep-link na stran (Tracker.gg
  "session report"; R1 §4.2). Druga seansa engagementa na večer, off-peak.
- **Session detail z verdiktom najprej**: per-igralec "ocena večera" na
  distribuciji skupnosti, potem dokazi (Leetify vzorec, R2 §1.1); vsaka
  številka z baseline delto ("23 fragov — 6 nad tvojim povprečjem"; Whoop
  pravilo, R2 §6.4 — implementirano enkrat kot helper).
- **Five-beat zgodba** (AP recap skelet, R2 §6.1): lede → mehanizem → momenti
  → standouts → posledice (rekordi/streaki). Naš storytelling že ima 80 %
  sestavin.
- **Share kartica** (1080×1920 canvas → "copy image" → Discord; R2 §5.4).
- **Home = tri kartice**: naslednja seja / včerajšnji recap / movers
  (HLTV vzorec, R2 §4.1-4.2; `player_skill_history` že obstaja).

### 2. VEČER — ritual in live
- **Session lobby**: potrjeni/standby/sub nivoji ("7/12 za nocoj"), en klik
  "rabimo šestega" ping. Sub-sistem je po raziskavi make-or-break za PUG
  skupine (R1 §1.3); naša availability infrastruktura je temelj.
- **Captain draft na strani**: kapetana izmenično izbirata iz potrjenih
  (FACEIT hub ritual, R1 §1.1); ET Rating predlaga balansirane ekipe z
  ročnim overridom (R1 §1.4).
- **Tonight live hub**: score + map-chip strip + živ momentum graf (naš
  session-team-momentum, hranjen iz Lua webhooka), 5-10 s polling — dovolj
  po industrijskih konvencijah (Sofascore Attack Momentum lekcija: EN graf,
  ne 20 stolpcev; R2 §3.1, §3.3). Kasneje: hold-probability krivulja iz
  spawn/stagger podatkov [naša izpeljava, R2 §3.2 analogija].
- **Challenge tedna**: en tematski izziv ("največ knife killov"), zmagovalec
  imenovan v digestu (R1 §5.3) — quest brez grinda.

### 3. IDENTITETA — kariera, ne tabela
- **Account stran**: Discord OAuth → poveži GUID, aliasi, display ime (most
  do vseh interaktivnih funkcij; obstoječi link-cog backend).
- **Profil IA prenova** (R2 §2): identity header (avatar, ET Rating + tier,
  **arhetip** "Objective Anchor / Entry / Lurker" — socialna valuta, R2 §2.2)
  + zavihki + privzeti scope "zadnjih 10 sej" (forma > lifetime) + per-map
  mini tabela + karierna časovnica z awardi.
- **Focus line**: en stavek iz najšibkejšega percentila ("trade-kill rate
  34. percentil — 50. bi obrnil 2 rundi"; Mobalytics "ena stvar", R2 §1.4).
- **Duo synergy**: "s SuperBoyyem zmagaš 71 %, brez 44 %" (Leetify recap
  vzorec, R2 §6.3) — gorivo za draft banter.

### 4. TEKMOVANJE — sezone in stave, ne globalna lestvica
- **Mesečna/kvartalna sezona** s soft resetom ob ohranjenem all-time
  (layered timescales, R1 §2.3): re-entry hook za odsotne, "slab mesec te ne
  pokoplje". `season_manager` že obstaja.
- **Sezonski awardi, vgravirani za vedno**: MVP (peer-voted!, R1 §1.4),
  Oracle, Iron Man (prisotnost — Strava "Local Legend", R1 §4.3), Most
  Improved, + konsenzualna lesena žlica (fantasy-league retention dokaz,
  R1 §5.2). Status za veterane = anti-evaporative-cooling (R4 §5.3).
- **Parimutuel predikcije** (Twitch Channel Points model, R1 §3.1): brezvredne
  točke, pool-split, prop-beti iz naših metrik ("X nocoj 5+ first bloodov").
  Vključi klop in neigralce — populacijo, ki jo majhna skupnost prva izgubi.
- **Per-map rekordi kot "segmenti"** (Strava, R1 §4.3): najhitrejši doc-run
  na supply, najboljši hold — vsaka mapa svoja record tabla (timing podatki
  obstajajo).

### 5. SPOMIN — biti "estate"
20 let zgodovine je edina stvar, ki je Discord strukturno ne more držati
(R4 §3, zapoved #4: Xfire/GameBattles žalovanje).
- **"Na današnji dan"** push v Discord (#1 feature po dokazih, R4).
- **Record book** (fantasy-league model): all-time rekordi, head-to-head
  kariere (rivalries razširitev), prvenstva po sezonah.
- **Slomix Wrapped** ob koncu sezone: 6-8 kartic/igralca (signature mapa,
  orožje, arhetip, nemesis, najboljši soigralec, rekord) — optimal
  distinctiveness (R1 §4.5, R2 §6.2).
- **LAN/meetup stran**: countdown prej, foto-arhiv potem (najdlje živeči
  artefakti skupnosti, R4 §6). Eventa NE digitaliziramo (R4).
- **SupaStats 2024 import** in podobni zgodovinski viri → globlji arhiv.

### Posebna stava: demo↔stats fuzija (R3 #1 unique bet)
Nihče v ET ekosistemu nikoli ni povezal kill vrstice z demo timestampom /
renderiranim klipom. Mi imamo greatshot pipeline IN momente (KIS spike, PB
runi). Auto-queue greatshot render iz "momentov" seje → klip v digestu.
ET:Legacy 2.84 demo UI + UDT_converter ETTV arhiv sta veter v hrbet.

## Anti-cilji (kaj NE gradimo — enako pomembno)
- ❌ **Globalna all-time K/D lestvica kot prva stvar** — pri realnem skill
  razponu spodnji polovici trajno pove, da je spodnja polovica (R1 §5.1,
  R4 zapoved #7). Rank proti sebi in proti nocojšnjemu večeru; teamplay
  podiumi (naš Invisible Value je pravilna protiutež — R4 sinteza).
- ❌ Web chat/komentarji — reka ostane v Discordu (R4 §2).
- ❌ Growth machinery, SEO, onboarding za tujce — "warren" je moat; rast je
  threat model, ne cilj (R4 §5.3).
- ❌ Daily streaki, login XP, generične badge mreže, points shop — votlo za
  odrasle; napačna kadenca za 2-3 večere/teden (R1 §4.4, §5.1).
- ❌ Funkcije, ki rabijo dnevno človeško hranjenje — postanejo vidna trupla
  (R4 §5.6). Vse avtomatizirano ali nič.
- ❌ Rcon/admin web panel — bot ostane ops interface (lastnikova odločitev).
- ⚠️ **Obrezovanje, ne samo dodajanje**: 25+ strani za 20 uporabnikov tvega
  "ghost town" signal — vsaka nova stran naj nadomesti/združi staro [R4
  inferenca, sprejeto kot pravilo].

## Win conditions (kako vemo, da deluje)
1. Jutranji telefon-check po seji postane navada (digest CTR v Discordu).
2. Torek se zgodi brez organizatorja: poll → "game on" → ekipe → digest brez
   ročnega koraka (organizer ranljivost = glavni org. risk, R4 sinteza #3).
3. Spodnja polovica skill razpona ima kaj osvojiti (Oracle, Iron Man,
   teamplay podiumi) in voli/stavi vsak teden.
4. Estate test: DB export + arhiv preživita katerokoli platformo.
