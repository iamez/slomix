# Kaj naše številke sploh lahko merijo

**Datum:** 19. 8. 2026 · **Povod:** sprejemni tek za KIS v6 je odkril, da ena os
(`escort`) izboljša oceno **runde** in poslabša oceno **igralca** · **Status:**
meritev, nič spremenjeno
**Skript:** `scripts/backtest_metric_foundations.py` (READ-ONLY, razdelki A–E)
**Vzorec:** 34.597 ubojev / 638 rund (KIS del) · 1.938 rund / 36 igralcev (WOWY del)

---

## 0. Tri številke, ki spremenijo, kaj smemo obljubljati

1. **Ves kontekst skupaj je vreden +2,51 o. t.** Najboljši model iz *vseh*
   kill-ravni značilk, vrednoten z navzkrižno validacijo čez runde, napove
   zmagovalca v 75,71 %; golo štetje ubojev v 73,20 %. To je celoten proračun za
   vsako kontekstno idejo, ki jo še lahko dobimo.
2. **Osi se čisto razdelijo na lastnosti igralca in lastnosti runde.**
   `stood` 0,84 · `wave` 0,81 · `clean_pick` 0,71 so stabilne pri igralcu;
   `escort` **0,00** · `crossfire` 0,00 · `objective` 0,07 · `isolation` 0,33 niso.
3. **WOWY:** ekipa zmaguje več z igralci, ki delajo **več ubojev**
   (r = **+0,918**), ne z igralci, ki imajo boljše uboje (KIS na uboj r = +0,351).

---

## 1. A — popravljen merilni instrument

Split-half je pri 15 igralcih dajal intervale kot [−3,61; 0,75]. Zamenjan z
razgradnjo variance: opažena varianca povprečij vsebuje vzorčni šum, zato je
`med-igralska = var(povprečij) − povprečje(znotraj_i / n_i)`, zanesljivost pa
delež te med-igralske v opaženi. Ostanek je odštet po celici (mapa, stran)
**in** po vlogi. Interval iz bootstrapa po **rundah** (odvisnost, ki jo je prej
požrl split-half).

| os | zanesljivost | 95 % CI | med-igralski sd | šumni sd | najmanjša zaznavna razlika |
|---|---:|---|---:|---:|---:|
| `stood` | **0,842** | [0,74; 0,91] | 0,037 | 0,016 | 0,044 |
| `wave_z` | **0,810** | [0,70; 0,90] | 0,066 | 0,032 | 0,089 |
| `clean_pick` | **0,708** | [0,62; 0,86] | 0,024 | 0,015 | 0,043 |
| `revenge` | 0,490 | [0,34; 0,82] | 0,011 | 0,011 | 0,032 |
| `gibbed` | 0,384 | [0,09; 0,83] | 0,003 | 0,004 | 0,012 |
| `isolation` | 0,334 | [0,00; 0,75] | 0,011 | 0,015 | 0,043 |
| `objective` | 0,071 | [0,00; 0,80] | 0,003 | 0,011 | 0,030 |
| `escort` / `crossfire` / `revived` | **0,000** | [0,00; 0,84] | 0,000 | 0,007–0,013 | 0,018–0,037 |

⭐ Intervali so zdaj uporabni (širina ~0,2 namesto ~4,4).
⚠️ »Najmanjša zaznavna razlika« je v enotah **te** osi na uboj — primerjaj jo z
razponom med igralci pri isti osi, nikoli med osmi.

**Popravek k prejšnji objavi:** `escort` je s split-half kazal −0,46, kar sem
zapisal kot »negativno«. Pravilna razlaga je **0,00 = ni merljivega signala o
igralcu**; negativna ocena je bila artefakt šuma pri redkem dogodku (4,6 %
ubojev). Instrument zdaj negativne ocene stisne na nič, ker drugega pomena
nimajo.

---

## 2. B — strop: koliko je s kili sploh mogoče vedeti

Vrednoteno **na ravni runde**: seštej vsaki strani značilke njenih ubojev, vzemi
razliko AXIS−ALLIES, dodaj lutke za mapo in napovej zmagovalca s k-kratno
navzkrižno validacijo čez runde (638 rund, 13 značilk).

| model | točnost |
|---|---:|
| golo štetje ubojev | 73,20 % |
| vsota KIS v5 | 73,51 % |
| `wave` + `stood` (osi igralca) | 73,67 % |
| **vse značilke skupaj (STROP)** | **75,71 %** |
| permutacijska ničla (premešani izidi) | 64,11 % (sd 0,89) |

⛔ **Prva izvedba tega razdelka je bila napačna** in je dala 50,47 %: seštevala
je log-obete po ubojih, kar skupaj z intercept/vloga/mapa členi spremeni ekipno
vsoto v število ubojev z dodatnimi koraki. Vrednotenje mora biti na ravni runde.

**Posledica:** razlika med »štej uboje« in »najboljše, kar znamo« je **2,51 o. t.**
Vsak nov multiplikator, vsaka nova os, vsaka ideja — vse skupaj se mora zmestiti
v teh 2,5 točke.

---

## 3. C — matrika: lastnost igralca ali lastnost runde

| os | stabilnost | \|coef\| | kam spada |
|---|---:|---:|---|
| `stood` | 0,842 | 0,274 | **ocena igralca (KIS)** |
| `wave_z` | 0,810 | 0,156 | **ocena igralca (KIS)** |
| `clean_pick` | 0,708 | 0,074 | ocena igralca (šibek učinek) |
| `isolation` | 0,334 | 0,180 | ocena runde (PWC) |
| `gibbed` | 0,384 | 0,103 | ocena runde |
| `objective` | 0,071 | 0,314 | **ocena runde (PWC)** |
| `escort` | **0,000** | **0,632** | **ocena runde (PWC)** — najmočnejši napovednik, nič o igralcu |
| `crossfire` | 0,000 | 0,156 | ocena runde |
| `revived` | 0,000 | 0,051 | ocena runde |
| `revenge` | 0,490 | 0,014 | ⛔ ven (ne napove ničesar) |

To je arhitekturna odločitev, izpeljana iz meritve: **KIS dobi stabilne osi,
kontekst runde gre v PWC.** Carrier družina (escort) je s tem dokončno na
strani PWC — ne iz sklepanja, ampak ker ima stabilnost 0,00 in |coef| 0,63.

---

## 4. D — WOWY: ali številka sploh kaj pove o igralcu

Ridge APM (λ = 25) na 1.938 rundah in 36 igralcih: ena vrstica na rundo, +1 za
igralce ene strani, −1 za drugo, izid = ali je zmagala prva. 14 igralcev ima
≥ 100 rund.

| korelacija z ridge APM | r |
|---|---:|
| **uboji na rundo** | **+0,918** |
| surovi delež zmag (druga pot do WOWY) | +0,778 |
| **KIS na uboj** | +0,351 |

Obe poti do WOWY se ujemata (+0,78), torej APM ni artefakt.

⚠️ n = 13 igralcev — beri predznak in vrstni red, ne tretje decimalke. In
možna je obratna vzročnost: dobra ekipa ti daje uboje. Ridge nadzoruje za
soigralce, kar je najboljše, kar vzorec dopušča.

**Sklep:** kdo pomaga ekipi zmagovati, se pozna po **količini** (uboji na rundo),
ne po kakovosti posameznega uboja. KIS je zato ocena **kakovosti uboja** in se
ne sme objavljati kot »kdo je boljši igralec«.

---

## 5. E — prag: kaj ta vzorec zmore

- **Test zmagovalca runde:** utež mora neto obrniti ~3,4 % rund, da doseže
  p < 0,05 (McNemar, ~19 % neskladnih parov pri 638 rundah).
- **Ločevanje igralcev:** glej stolpec »najmanjša zaznavna razlika« v razdelku 1;
  pod tem pragom razlike med igralcema ne smemo trditi.
- **Strop:** +2,51 o. t. je celoten proračun za ves kontekst skupaj.

⭐ Vsaka naslednja ideja za metriko se najprej primerja s temi tremi številkami.
Šest metrik je padlo 17. 8. (memory `et-metrics-what-fails-2026-08-17`); ta
tabela naredi tisto lekcijo številčno.

---

## 6. Kaj iz tega sledi za implementacijo

1. **KIS v6 brez escorta** je edina različica, ki je prestala oba vnaprej
   postavljena praga (zanesljivost 0,755, runde 69,75 % proti 66,93 %).
   Njena vrednost je **poštenost in razložljivost**, ne napovedna moč — ker te
   po razdelku 2 skoraj ni na voljo.
2. **Escort in carrier družina gresta v PWC**, ne v KIS (razdelek 3).
3. **UI mora ločiti dve vprašanji**: »kako dober je bil ta uboj« (KIS) in
   »kdo je prispeval k zmagi« (PWC/WOWY). Superboyyjevo vprašanje o MVP-ju je
   natanko ta zmešnjava.
4. Ob vsaki objavi lestvice KIS gre zraven stavek, da **KIS na uboj korelira z
   dejansko pomočjo ekipi le r = 0,35**, medtem ko uboji na rundo r = 0,92.
