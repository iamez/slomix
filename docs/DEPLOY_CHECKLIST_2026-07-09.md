# Deploy Checklist — canonical-key + internal-api-secret + KIS freshness (2026-07-09)

Prod (slomix_vm) je na v1.24.0. Od takrat je na `main` pristalo:
**#484** (composite Form Index + canonical round-key bundle + KIS `formula_version`,
migr 060), **#486** (KIS loaders/shadow canonical `map_name` + `round_ctx_key` helper),
**#487** (internal-api-secret: bot→website write-through auth), **#489** (freshness-aware
KIS cache-check). Vsi koraki spodaj so **owner-run**. Zaporedje: P0 → SECRET → A1 → A2 → A3 → verify.

> **Kontekst ukazov:** A-koraki tečejo NA PROD VM (`ssh slomix-vm`), v `/opt/slomix`, s
> tamkajšnjimi venvi (`venv-web` za website). `deploy_release.sh` se požene z dev/deploy stroja.

## P0 — Pred-priprava
1. Mergaj **release-please PR** (nova verzija) → nastane tag.
2. `gh pr list --state open` — potrdi, da so #484/#486/#487/#489 mergani (so).
3. Prod `.env` CRLF sanity: `ssh slomix-vm "file /opt/slomix/.env"` → če CRLF, `sed -i 's/\r$//' .env`.

## SECRET — INTERNAL_API_SECRET setup (NOVO, OBVEZNO PRED DEPLOYEM!)
Po #487 ima website **fail-fast**: `main.py` NE bo startal brez `INTERNAL_API_SECRET`
(prazen ali placeholder → `raise ValueError`). Bot brez njega **skipne** warm/persist hooke
(`_warm_kis_cache`, `_persist_s_effort`) → KIS se neha osveževati.

```
# Generiraj EN skupni secret:
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
# Dodaj ISTI string v prod okolje, ki ga bereta OBA (web fail-fast + bot hooki):
ssh slomix-vm
#   v /opt/slomix/.env dodaj:  INTERNAL_API_SECRET=<generirani-string>
#   (če bot bere ločen env/enoto, dodaj tam isti string)
grep INTERNAL_API_SECRET /opt/slomix/.env   # verify prisoten in ne-prazen
```
> Bot in web MORATA imeti **isti** string (shared secret, `secrets.compare_digest`).

## A1 — Backup (vedno prvi)
```
ssh slomix-vm "cd /opt/slomix && ./scripts/db_backup.sh"   # pg_dump → backups/etlegacy_<ts>.sql.gz
```

## A2 — Deploy
```
# migr 060 (formula_version) je website-scoped — PREVERI ali je na produ PRED deployem:
ssh slomix-vm 'cd /opt/slomix && set -a && . .env && set +a && \
  psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DATABASE -tAc \
  "SELECT 1 FROM information_schema.columns WHERE table_name='"'"'storytelling_kill_impact'"'"' AND column_name='"'"'formula_version'"'"'"'
# če prazno → migr 060 NI aplicirana → dodaj migracijski korak (ne --skip-migrations),
# ali aplicaj migrations/060_add_kis_formula_version.sql ročno pred A2.

SUDO_PASS='<sudo geslo>' ./scripts/deploy_release.sh <TAG> --skip-migrations --skip-flags
BASE_URL=https://www.slomix.fyi ./scripts/verify_post_deploy.sh
```
Opombe: root `migrations/` NIMA novih; edini schema-touch je website-scoped migr 060 (glej zgoraj).

## A3 — KIS staleness (ŽE UREJENO — samo verify)
Enkratni recompute je bil **izveden 2026-07-09** (dev 29/29, prod 27/27 → **0 stale**).
Backup tabela `storytelling_kill_impact_bak_kis_20260709` (22372 vrstic) obstaja na produ.
Po #489 (freshness cache-check) se staleness ne more več nabrati. Samo verify:
```
ssh slomix-vm
cd /opt/slomix && set -a && . .env && set +a
# read-only staleness probe (kopiraj scratchpad/kis_py_staleness_prod.py na VM):
venv-web/bin/python /tmp/kis_probe.py   # pričakovano: STALE 0/N
```

## Verify
```
curl -s "https://www.slomix.fyi/api/skill/leaderboard" | head -c 200
# s-effort je zdaj internal-only (401 brez headerja — pravilno):
curl -s -o /dev/null -w "%{http_code}\n" "https://www.slomix.fyi/api/skill/s-effort?session_date=<seja>"   # 401
curl -s -H "X-Internal-Token: <SECRET>" "https://www.slomix.fyi/api/skill/s-effort?session_date=<seja>"      # 200
# public storytelling ostane read-only (compute=read_only brez headerja):
curl -s "https://www.slomix.fyi/api/storytelling/kill-impact?session_date=<seja>&limit=3" | head -c 200
sudo systemctl status slomix-web slomix-bot
# po PRVI seji po deployu preveri, da warm hook DELA (ne skipne):
sudo journalctl -u slomix-bot --since "-1h" | grep -iE "KIS cache warmed|warm skipped|s.effort persisted|persist skipped"
#   pričakovano: "warmed"/"persisted" (NE "skipped") — sicer INTERNAL_API_SECRET manjka/napačen
```

## Rollback
- Web/deploy: `deploy_release.sh <prejšnji TAG>` (atomic, service-recovery trap).
- DB: `gunzip -c backups/etlegacy_<ts>.sql.gz | psql ... -v ON_ERROR_STOP=1`.
- KIS (če recompute kdaj pokvari): `TRUNCATE storytelling_kill_impact;
  INSERT INTO storytelling_kill_impact SELECT * FROM storytelling_kill_impact_bak_kis_20260709;`
- INTERNAL_API_SECRET: odstranitev iz `.env` → web NE bo startal (fail-fast); ne odstranjuj brez rollbacka #487.

## Po-deploy housekeeping (owner, ni nujno)
- Ko je vse potrjeno stabilno: `DROP TABLE storytelling_kill_impact_bak_kis_20260709;`
