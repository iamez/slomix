# PLAN — edini vir resnice za tekoči načrt

> Pravilo: ta datoteka se posodobi ob VSAKEM koraku. Nič se ne »dogovori«
> samo v pogovoru. Bereta jo obe seji (in vsak prihodnji model).
> Podrobne raziskovalne zapiske drži lokalno (docs/REPO_BOUNDARY.md);
> tu je samo načrt in pozicija. Repo je javen — brez skrivnosti.
>
> **Sočasnost (več agentov, plan mode):**
> - Plan-mode datoteke (`~/.claude/plans/*.md`) so ZAČASNE in si jih seje
>   DELIJO po slugih — ista datoteka je bila prepisana 3× v dveh dneh
>   (tri različne seje, trije nepovezani načrti). Nikoli niso vir resnice:
>   trajni izid se ob ExitPlanMode PREPIŠE SEM.
> - Ta datoteka se ureja SAMO prek veje+PR (kot vse) — sočasni prepis se
>   pokaže kot git konflikt, ne kot tiha izguba; vsaka verzija je commit.
> - Vsaka delovna proga ima SVOJ razdelek in ureja samo svojega +
>   skupno glavo; razdelki različnih prog se v gitu zlijejo brez konflikta.
> - Vsak razdelek nosi vrstico »Zadnja posodobitev: datum (kdo)«.

**Zadnja posodobitev:** 2026-09-02 popoldne (Fable, po #884 — faza 5 endpoint-kompletna)

## Proga: nova stran (Fable)

### Kje smo

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

1. **Faza 6 — availability rezina 1** (v delu, veja feat/phase6-availability):
   dostopne stopnje (401/403/200), tedenski grid + moj status (POST),
   planning today, market/wallet, promo povzetki. Rezina 2: linked formi
   (settings/subscriptions/link-token/preview/campaigns), betting UI.
2. **Faza 6 — uploads, greatshot, live** strani.
3. **Spider-web follow-upi** (3D kamera, belief regions, label placement;
   W6) — premaknjeno ZA paritetno fazo 6: polish ne prehiteva paritete
   (razlog zapisan 2. 9.).
4. **Faza 7**: wrapped, compare, Clips, upokojitev začasne /rounds.
5. **Ultra pregled** (owner-triggered) → 1–2 tedna teka na dev → pogovor o
   produkciji.

| ratchet | stanje |
|---|---|
| endpoint gap | 41 po tej rezini (74 ob začetku 1. 9.) |
| proximity inventory pending | **0** (#884) |

## Proga: lag na puranu + Lua optimizacija (sestrska seja)

**Zadnja posodobitev:** 2026-09-02 (Fable — predaja koordinacije)

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
