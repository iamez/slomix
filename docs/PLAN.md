# PLAN — edini vir resnice za tekoči načrt

> Pravilo: ta datoteka se posodobi ob VSAKEM koraku. Nič se ne »dogovori«
> samo v pogovoru. Bereta jo obe seji (in vsak prihodnji model).
> Podrobne raziskovalne zapiske drži lokalno (docs/REPO_BOUNDARY.md);
> tu je samo načrt in pozicija. Repo je javen — brez skrivnosti.

**Zadnja posodobitev:** 2026-09-02 (Fable, po v1.44.0)

## Kje smo

Nova SPA (website/frontend/src/app) — faza 5 (proximity telemetrija) je
**skoraj zaključena**. Prod ZAMRZNJEN na v1.39.0 (ownerjeva odločitev
2026-08-28); dev soaka; deploy NI naloga.

| stanje | vrednost |
|---|---|
| izdana verzija (dev) | v1.44.0 (2026-09-02) |
| endpoint gap (H1) | 57 (`tests/data/endpoint_gap.txt`) |
| proximity inventory pending | 11 (`tests/unit/test_proximity_inventory.py` PENDING_BUDGET) |
| zgrajene strani faze 5 | proximity (6 rezin + 8 outcome instrumentov, #881 mergan), player profil, team comparison, replay, spider-web SW-1 |

## Naslednji koraki (vrstni red)

1. **Faza 5, rezina »player dodatki«** (4 poti): `competitive/player-card`,
   `duos`, `trades/player-stats`, `prox-scores/formula` → ProximityPlayerPage.
   Oblike že vzorčene (2. 9.).
2. **Faza 5, rezina »map overlayi«** (7 poti): `combat-positions/{danger-zones,
   heatmap,kill-lines}`, `hotzones`, `player-heatmap`, `movers`, `player-aim`
   (⚠️ player-aim ZAHTEVA map_name — 400 brez njega).
3. **Spider-web follow-upi** (imenovani na strani): 3D kamera, belief
   regions, label placement; W6 validacija proste poti.
4. **Faza 6**: availability/bets, uploads, greatshot, live.
5. **Faza 7**: wrapped, compare, Clips, upokojitev začasne /rounds.
6. **Ultra pregled** (owner-triggered, `/code-review ultra`) → 1–2 tedna
   teka na dev → šele nato pogovor o produkciji.

## Vzporedna proga: lag na puranu

Watcher v6.12 ŽIV na puranu (deployan + dokazan 2. 9.). Naslednji večer
igre = meritev (`~/.etlegacy/legacy/proximity/frame_health.log`; zbiralnik
vleče na sambo). Delitev populacij (sestrska seja): A = round-end burst
(naš), B = med pavzo — ⚠️ »ne more biti naša« pokriva SAMO tracker
(levelTime med pavzo zamrzne); webhookov io.popen sweep teče po os.time()
tudi med pavzo in NI izključen. Razsodi meritev prek `self`. Optimizacija bursta: batch write,
šele PO enem večeru self meritev. Sestrska seja koordinira optimizacijo Lua.

## Odprte ownerjeve odločitve

- puranov cron `0 20 * * * kill etlded` (vrže igralce sredi igre) — pogojni
  kill ali prestavitev.
- `scripts/local_et_setup.sh` P1: produkcijski webhook v lokalnem strežniku.
- hosting ticket, če watcher potrdi populacijo B (host stall).
