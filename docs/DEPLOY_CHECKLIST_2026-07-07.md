# Deploy Checklist — prod catch-up po All-Seeing Eye/s.effort/audit sprintu (2026-07-07)

Prod (slomix_vm) je na starejšem releasu; od takrat je na `main` pristalo:
scoring poenotenje na BOX kanon, Good Night Phase 0+1, composite Form Index,
**s.effort + adjusted lifetime (K-D, #455)**, **Codex audit remediacija (#457)**,
K-E backtest (#458), bot permission fixi (#460), DB-manager connect/migrate
split (#461). Vsi koraki spodaj so **owner-run**; skripte so dry-run/read-only
privzeto. Zaporedje: P0 → A1 → A2 → A3 → A4 → verify.

## P0 — Pred-priprava (enkratno)
1. Počakaj/mergaj **release-please PR** (nova verzija ~v1.23.0) → nastane tag.
2. Preveri, da so vsi nameravani PR-ji mergani (`gh pr list --state open`).
3. Prod `.env` sanity: `file .env` — če pokaže CRLF, `sed -i 's/\r$//' .env`
   (dev je imel CRLF in je `db_backup.sh` padel na sourcanju!).

> **Kontekst ukazov:** A1–A4 tečejo NA PROD VM (`ssh slomix-vm`), v
> `/opt/slomix`, s TAMKAJŠNJIMI venvi (`venv-web` za website skripte).
> Edina izjema je `deploy_release.sh`, ki se požene z dev/deploy stroja.

## A1 — Backup (vedno prvi, NA PROD VM!)
```
ssh slomix-vm "cd /opt/slomix && ./scripts/db_backup.sh"
# pg_dump → /opt/slomix/backups/etlegacy_<ts>.sql.gz (prod baza, ne dev!)
```
Shrani pot — restore točka za A3/A4.

## A2 — Deploy
```
# Nova release tag NIMA scripts/release_configs/<TAG>.sh — brez obeh skip
# flagov se deploy ustavi pred checkoutom (per-release-config guard):
# brez NOPASSWD sudoja MORA biti SUDO_PASS nastavljen, sicer se deploy
# ustavi na service stop/start koraku ("re-run with SUDO_PASS=<pass>"):
SUDO_PASS='<sudo geslo VM userja>' ./scripts/deploy_release.sh <TAG> --skip-migrations --skip-flags
BASE_URL=https://www.slomix.fyi ./scripts/verify_post_deploy.sh
```
Opombe:
- Root `migrations/` NIMA novih datotek od zadnjega deploya, novih env flagov
  tudi ne — zato sta skip flaga pravilna izbira (alternativa: ustvari prazen
  `scripts/release_configs/<TAG>.sh`). `apply_migrations.py` ima NOVO
  semantiko (#457): failed vrstice se retryjajo in status jih šteje ločeno;
  populated-DB-brez-trackinga zdaj ODKLONI apply (na prod tracking obstaja,
  torej brez spremembe).

## A2b — Orphan R2 označevanje (PRED vsakim rating preračunom!)
Orphan R2 vrstice so do označbe `is_valid=TRUE` in bi ušle v percentile ter
s.effort (codexov P1 na tem checklistu). Predpogoj: PostgreSQL driver
`psycopg2`/`psycopg` ni pinned v requirements — preveri
`venv-web/bin/python -c "import psycopg2"` (sicer `pip install psycopg2-binary` v venv-web).
```
ssh slomix-vm
cd /opt/slomix
set -a; . .env; set +a          # skripte berejo POSTGRES_* iz okolja!
venv-web/bin/python scripts/backfill_orphan_r2.py            # dry-run (~42 rund)
venv-web/bin/python scripts/backfill_orphan_r2.py --apply
```

## A2c — ET Rating refresh (OBVEZNO PRED s.effort backfillom!)
s.effort bere lifetime rating iz `player_skill_ratings`; forsiran recompute
prečisti OMNIBOT vnose in preračuna percentile brez botov in brez orphan rund
(ratingi ±0.13, populacija ~40→~26 ljudi — pričakovano, C7). Backfill MORA
teči nad prečiščenimi ratingi:
```
# curl NI dovolj: auto-refresh teče samo ob stale >1h, torej lahko po deployu
# vrne stare vrstice. Recompute FORSIRAJ direktno (piše v DB):
cd /opt/slomix && set -a && . .env && set +a && venv-web/bin/python -c "
import asyncio
from website.backend.dependencies import get_db_pool, init_db_pool
from website.backend.services.skill_rating_service import compute_and_store_ratings
async def main():
    await init_db_pool()
    n = await compute_and_store_ratings(get_db_pool())
    print(f'ratings recomputed for {n} players')
asyncio.run(main())"
# preveri: nič OMNIBOT vnosov IN svež last_rated_at
psql ... -c "SELECT COUNT(*) FILTER (WHERE player_guid LIKE 'OMNIBOT%'), MAX(last_rated_at) FROM player_skill_ratings"
```

## A3 — s.effort backfill (owner-gated; po A1 backupu, A2b orphanih in A2c refreshu)
```
ssh slomix-vm
cd /opt/slomix
set -a; . .env; set +a          # backfill bere POSTGRES_* iz okolja (P1!)
# s.effort session history (v0.2; idempotenten, formula_version stamped)
venv-web/bin/python scripts/backfill_s_effort_history.py                  # dry-run najprej
venv-web/bin/python scripts/backfill_s_effort_history.py --apply --i-have-a-backup
# dev referenca: 819 vrstic / 29 igralcev / 118 sej

```

## A4 — Verifikacija (read-only: recompute je bil forsiran že v A2c)
```
curl -s "https://www.slomix.fyi/api/skill/leaderboard" | head -c 200   # brez OMNIBOT
curl -s -H "X-Internal-Token: ${INTERNAL_API_SECRET:?set INTERNAL_API_SECRET}" "https://www.slomix.fyi/api/skill/s-effort?session_date=<zadnja seja>"
curl -s "https://www.slomix.fyi/api/skill/adjusted-lifetime" | head -c 300
sudo systemctl status slomix-web slomix-bot
sudo journalctl -u slomix-web --since "-10 min" | grep -iE "error|greatshot recovery"
```
- Greatshot: ob startu se izpiše "♻️ Greatshot recovery" če so bili obtičani
  jobi (#457 sweeper) — enkratno je pričakovano.
- `player_skill_history` scope='session' vrstice: `SELECT COUNT(*) ...
  WHERE scope='session' AND components->>'formula_version'='s.effort-v0.2'`.

## Rollback
- Web/deploy: `deploy_release.sh <prejšnji TAG>` (atomic, service-recovery trap).
- DB: `gunzip -c backups/etlegacy_<ts>.sql.gz | psql ... -v ON_ERROR_STOP=1`
  (dump je --clean --if-exists → pravi rollback).
- s.effort vrstice same (SAMO ta formula, ne vsa session zgodovina):
  `DELETE FROM player_skill_history WHERE scope='session'
   AND components->>'formula_version' = 's.effort-v0.2'`
  (backfill je idempotenten, ponovni apply jih obnovi).
