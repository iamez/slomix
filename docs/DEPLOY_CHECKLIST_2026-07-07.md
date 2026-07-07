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

## A1 — Backup (vedno prvi)
```
./scripts/db_backup.sh        # pg_dump → backups/etlegacy_<ts>.sql.gz
```
Shrani pot — restore točka za A3/A4.

## A2 — Deploy
```
# Nova release tag NIMA scripts/release_configs/<TAG>.sh — brez obeh skip
# flagov se deploy ustavi pred checkoutom (per-release-config guard):
./scripts/deploy_release.sh <TAG> --skip-migrations --skip-flags
BASE_URL=https://www.slomix.fyi ./scripts/verify_post_deploy.sh
```
Opombe:
- Root `migrations/` NIMA novih datotek od zadnjega deploya, novih env flagov
  tudi ne — zato sta skip flaga pravilna izbira (alternativa: ustvari prazen
  `scripts/release_configs/<TAG>.sh`). `apply_migrations.py` ima NOVO
  semantiko (#457): failed vrstice se retryjajo in status jih šteje ločeno;
  populated-DB-brez-trackinga zdaj ODKLONI apply (na prod tracking obstaja,
  torej brez spremembe).

## A2b — ET Rating refresh (OBVEZNO PRED s.effort backfillom!)
s.effort bere lifetime rating iz `player_skill_ratings`; prvi refresh po
deployu prečisti OMNIBOT vnose in preračuna percentile brez botov (ratingi
±0.13, populacija ~40→~26 ljudi — pričakovano, C7). Backfill MORA teči nad
prečiščenimi ratingi, sicer persistira s.effort proti starim vrednostim:
```
# POZOR: ta klic PIŠE v DB (auto-refresh ob stale >1h) — to je namen koraka
curl -s "https://www.slomix.fyi/api/skill/leaderboard" >/dev/null
# preveri: nič OMNIBOT vnosov
psql ... -c "SELECT COUNT(*) FROM player_skill_ratings WHERE player_guid LIKE 'OMNIBOT%'"
```

## A3 — Prod backfilli (owner-gated, po A1 backupu IN A2b refreshu)
Predpogoj za orphan skripto: PostgreSQL driver `psycopg2`/`psycopg` ni pinned
v requirements — preveri `python3 -c "import psycopg2"` (sicer
`pip install psycopg2-binary` v venv).
```
# 1) s.effort session history (v0.2; idempotenten, formula_version stamped)
python3 scripts/backfill_s_effort_history.py                  # dry-run najprej
python3 scripts/backfill_s_effort_history.py --apply --i-have-a-backup
# dev referenca: 819 vrstic / 29 igralcev / 118 sej

# 2) orphan R2 označevanje (C4 — ~42 rund na prod)
python3 scripts/backfill_orphan_r2.py                         # dry-run najprej
python3 scripts/backfill_orphan_r2.py --apply
```

## A4 — Verifikacija (read-only: leaderboard je bil osvežen že v A2b)
```
curl -s "https://www.slomix.fyi/api/skill/leaderboard" | head -c 200   # brez OMNIBOT
curl -s "https://www.slomix.fyi/api/skill/s-effort?session_date=<zadnja seja>"
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
