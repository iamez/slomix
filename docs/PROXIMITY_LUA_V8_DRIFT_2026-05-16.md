# Proximity Lua — Live vs Repo Drift Report (Phase 5.0)

**Date:** 2026-05-16 · **Branch:** `feat/proximity-redesign`
**Pull:** read-only `cat` over SSH (`et@91.185.207.163:48101`, key `~/.ssh/etlegacy_bot`), zero server writes.
**Live source:** `/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/proximity_tracker.lua`
**Snapshot:** `docs/reference/live_sync_backups/20260516_105508/proximity_tracker.lua`

## Verdict: NO DRIFT — live == repo `v6.01`, byte-for-byte

| | Live (server) | Repo (`proximity/lua/proximity_tracker.lua`) |
|---|---|---|
| `local version` | `"6.01"` (line 46) | `"6.01"` (line 46) |
| Line count | 4308 | 4308 |
| SHA-256 | `6a49269732bc6aba50678aac68eb424267851ae6f3866f06d306533d916835cf` | `6a49269732bc6aba50678aac68eb424267851ae6f3866f06d306533d916835cf` |
| `diff` (whitespace-normalized) | **0 lines** | — |

The repo Lua **is** the production Lua. The earlier `proximity_server_desync`
memory (server "v8+", recorded 2026-04-17) is **stale/resolved** — whatever
transient state prompted it no longer holds. That memory has been corrected.

## Anchors confirmed in the live file (for Phase 5.1 design)

- `et_WeaponFire(clientNum, weapon)` — **line 4026** (matches plan; currently shot-count only, no origin/angles).
- `safe_gentity_get(clientnum, "ps.origin")` — **line 589** (origin-capture precedent for the v9 per-shot origin).
- `viewangles` / `ps.viewangles` — **absent everywhere** in the live Lua (grep clean). Its exact ETL 2.83.1 field binding is therefore *still unproven from static code* and MUST be runtime-validated on the server during 5.1 design (no precedent live or in repo).
- `SHOT_FIRED` — absent (the v9 emission line does not exist yet; purely additive).

## Gate decision

The hard gate's purpose — *don't design v9 against the wrong base* — is **satisfied**: there is no drift, so the Phase 5.1 `et_WeaponFire` enhancement can be designed directly against the repo file with confidence it mirrors production.

Per the master plan and the owner's standing instruction, **design (5.1/5.2) does not auto-proceed**: this drift doc is the deliverable of 5.0 and Phase 5 now **stops for owner review**. 5.1 (Lua design) begins only on explicit go-ahead; 5.3 (server deploy + prod migration) remains a separate independent HARD STOP.

## Recommended next step (for owner)

Phase 5.1/5.2 are local-only and low-risk to *design* (no server writes): add a config-gated `SHOT_FIRED` emission to `et_WeaponFire` (origin via the `ps.origin` precedent; `ps.viewangles` flagged for runtime validation), plus parser `ShotFired` + `proximity_shot_fired` table + idempotent migration, then a 5th `mode=aim` on `/proximity/player-heatmap`. Say the word to proceed with the 5.1 design pass.
