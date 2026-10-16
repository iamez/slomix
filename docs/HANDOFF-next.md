# HANDOFF — 2026-09-06 (Fable 5.1 → naslednji agent)

> **Current routing — 2026-10-04.** Read the latest checkpoint in `docs/PLAN.md`
> first, including its local-only runtime continuation path. All dated blocks
> below are historical evidence, not current approval or deployment instructions.
>
> **Historical consolidation checkpoint — 2026-09-20.** Authority is docs/PLAN.md;
> retain both historical handoff tracks below, not their old queue as current.
> #1076 merged; #1057/#962 are conditionally approved. Runtime resumes at #1077
> completion delivery/sealing after consolidation, then new-site audit and an
> owner-approved reversible DEV transition. No deployment follows from merge.
>
> **Historical handoff override — 2026-09-07, Astra.** The "Astra execution
> ledger" in `docs/PLAN.md` recorded that day's work; the sections below are a historical
> snapshot, not the current queue. #955 and #912 are merged at `4f653c01`;
> #961 merged as `28662f04`; its Claude handoff evidence is now included.
> Merge, build, active service and runtime proof are separate states.
> Astra did not execute the old review `cut --push`. AGENTS.md records a
> narrow written exception for scripts/review_slices.sh and only the historical
> review-base/NN-* and review/NN-* vehicles. This record neither revokes that
> exception nor authorizes a new run or extends it to work branches. Consult
> current owner instructions before changing any NEVER MERGE review vehicles.
> Do NOT treat old server/browser commands as permission to start them.
> Watchdog exists; delivery/retry proof is still required. Keep its 5-minute
> cadence/two-failure policy unless explicitly changed, not a <=2-minute SLA.
> Raw Codex hook input logging must be removed, not validated by logging
> more real commands. Private Claude memory stays private.
> Runtime starts with `round_stats_imported` in the canonical PG transaction,
> NOT `round_ended` in the Discord mixin. Stability before development;
> 1–2 week observation before activation, not before development.

> **10. 9. 2026: novejša predaja je `docs/HANDOFF-fable-2026-09-10.md`** (9. 9. je posnetek tistega večera)
>
> **9. 9. 2026: `docs/HANDOFF-fable-2026-09-09.md`** (owner odsoten ~3 mesece; spider web
> zaključen, merilnik podatkovnih točk 583 → 238, bot brez reakcij na Supove slike). Začni tam; ta datoteka ostaja
> kot posnetek stanja 6. 9. in pravil.

Vstopna točka za avtonomnega agenta. Vir resnice za načrt je `docs/PLAN.md`,
pozicije in odprte stvari so v `docs/BACKLOG.md`; ta datoteka pove, KJE smo,
KAJ je naslednje in KAKO se dela (pravila + dokazi). Dizajn nove strani je v
`docs/design/` (lokalno; beri `README.md` → 16 → 05 → 06 → 08 → 07 → 09 → 11+12).


## 2026-10-16 — Persistent Lua VM supports both stopwatch halves

Four #1094 findings corrected before activation. Each fresh InitGame invalidates
old leases, receiver, ticket and consumed write attempt; only a newly validated
binding clears the write fence. Each active bootstrap receives a fresh one-shot
completion sender, so a persistent map_restart Lua VM can write R2 after R1.
Real active-start ET counter values are1 for R1 and0 for R2; both observation and
writer validation now encode2-counter. Tests no longer conceal this by inventing
half-1 counter values. An unchanged sender/lease still cannot replay a write.

Listener has separate bounded initial_readiness_wait1800 and between-half
bootstrap_wait1800 (each max3600), distinct from completion and IPC exchange.
Timeout preserves writer claims and terminally fences reuse. The game supervisor
must pass the new argument from this parent; its existing global60-minute unit
lifetime remains a stricter overall cap and may abort incomplete captures.

424 selected regressions passed, then6 final claim/deadline tests passed. Five
negative controls produced2+2+2+16+1 failures; every source restored with cmp.
Lua5.1 and5.4 same-VM proof performs warmup/R1/shutdown/warmup/R2 with two actual
closed files, independent hashes/sizes and two distinct completion messages.
ET API and channel are synthetic, not a real engine/server or deploy proof.
Ruff/diff-check pass. New exact-head CI and review replies are next. No services,
units, application rows, live Lua or production changed. Preserve all prior plan.

## 2026-10-16 — Game startup redaction, loader audit and metrics outputs

Three new #1095 review findings corrected: both rendered unit and effective
containment gate require LD_AUDIT removal; missing deferred dependencies now
produce structured redacted ImportError JSON before launch, including an actual
isolated CLI child proof; cancellation/SystemExit remain unmasked. MetricsLogger
from_config routes reports and default SQLite metrics DB to BOT_LOG_DIR/metrics,
retains explicit separate metrics DB paths and the existing PostgreSQL protection
against using the legacy application DB as metrics. UltimateBot uses this factory.

Supervisor explicitly passes initial_readiness_wait1800 and bootstrap_wait1800
from the new #1094 listener, plus completion_wait1500. Global RuntimeMaxSec60min
remains the stricter overall resource cap; an early/incomplete capture is failure.
New supervisor code must not run with the older listener API.

143 selected tests passed with the new parent listener temporarily checked in
place; source was then restored with cmp pending the normal dependency merge.
Without that new dependency142 passed and the new caller test was deselected.
Five mutations actually failed (audit2, import3, metrics4, render6, readiness1),
each restored with cmp. Metrics proof writes real SQLite rows and JSON exports;
SSH/game/Discord are synthetic or absent. Ruff and configured Bandit pass; two
legacy test SLF001 findings are unchanged. Exact-head combined CI is next.
No live ET, services, installation, application writes or production changes.
All prior plan and owner-specific merge/activation gates remain in force.

## 2026-10-16 — Preserve proximity replay fences and warning recovery

Review of #1093 found that the previous explicit-reset change deleted proximity
receipts while retaining additive proximity aggregates. Corrected before merge
or deployment: retain those receipts, hashes, aggregate-applied/admission flags
and all aggregates; release only linked_round_id during explicit canonical reset.
The native fixture compares retained rows through rollback and successful reset.

Bound replay restores WARN markers from the immutable validation_passed=false
journal value after a missing/failed marker write, retains original warning text
where available and leaves complete markers unchanged on subsequent replay.
Legacy date repair locks its selected rounds and refuses runtime mappings or
strict proximity links before any DELETE. Bound date repair remains a separate
explicit source-admission/reconciliation task, not silently downgraded legacy
reimport. The legacy test mocks reimport and proves only deletion/admission.

Centralized the usable team-identity index predicate: the legacy schema setup
must accept migration036's standalone unique index just like the team worker.
No constraint promotion or duplicate-name DDL is needed on that valid shape.

133 selected tests passed locally; 20 native PostgreSQL cases skipped because
the private cluster is offline. Disabling warning preservation produced six
observed failures; restoration compared byte-identical and all 12 replay cases
passed. Root-manager Ruff remains its existing 12 diagnostics, with no added
code/message; other changed Python paths pass. PG14/PG17 acceptance is pending
on this new head. Earlier c71a13c1 CI passed9218/9222 tests, but does not prove
these newer changes. No application data, services or production were changed.

Next: exact-head CI, review replies and normal dependency refresh1094–1096.
All original runtime, handover, D5, proximity/gametime and UI plans remain open
where previously recorded. Per-number owner permission still gates each merge.

## 2026-10-16 — Forward-only map alphabet and explicit rebuild dependencies

Two later #1093 review findings: restrictive round-mapping FKs blocked explicit
fresh rebuild; binding/SQL map validation was narrower than the sealed transport.
The explicit wipe now clears known optional runtime/proximity/gametime children,
receipts, mappings and journal in dependency order before canonical rounds,
deleting R2 mappings before R1. Config tables remain excluded. Ordinary round
deletes still retain journal history; no live wipe or repair was performed.
Native fixture adds an omitted-mapping negative control, late-failure rollback,
full row preservation comparisons, final zero counts by two paths and retained
user-permission config.

New migration104_runtime_round_mapping_map_alphabet.sql relaxes only the map
check to the existing [A-Za-z0-9_.+-] transport alphabet. Migration099 bytes and
its checksum remain unchanged, even though its PR is still open. Both schema
snapshots append the effective104 alteration; release configuration includes104
(after103 in full source, after099 in this earlier consolidated branch).
Do not apply it to an application DB without the owner migration procedure.

106 selected local tests passed; eight native cases skipped while the private
cluster is offline. Added four native cases: period/plus upgraded-schema import
and replay, mixed-case map acceptance, and transactional explicit wipe. CI on
PG14/PG17 must prove them before closing these two new review threads. Earlier
968712a8 passed9210/9214 tests with all eight previous native additions executed;
that is separate from the newer104 head. Original migration099 compared equal
through both current-file and committed-file paths. New evidence stays local.

Next: publish, run exact-head native acceptance, refresh dependent1094–1096 and
resolve review. Keep owner merge permissions per PR, source admission/exclusive
handover, D5 and every original proximity/gametime/API/live/Spiderweb/UI item.
Full original PLAN bytes remain preserved in the primary checkout. Production,
services, installed units, application rows and old candidate packages untouched.

## 2026-10-16 — Closed supervisor bootstrap and enforced resource contract

PR #1093 968712a8 is fully green: 9210/9214 passed on Python3.11/PG14 and
Python3.13/PG17, 179/175 skipped, eleven subtests each. Independent passed-node
counts match both summaries; all eight new native cases actually passed in both
logs. Three import review threads answered/resolved. No PR merge was performed.

#1095 supervisor now refuses a non-isolated CLI before importing anything beyond
builtin sys, reporting isolated_python_required. In -I mode all project imports
wait until exact HEAD, clean tracked/index state, no hidden index flags and a
closed untracked/ignored inventory are verified. Use a dedicated clean source
checkout with external interpreter/state; generated/ignored inputs are refused.
-I -B and runtime bytecode disabling preserve that closed tree. Native library
callers still own their source/lifecycle admission. No hostile same-UID/venv or
physical-engine authentication claim is added.

The effective systemd policy now checks MemoryMax, TasksMax, LimitFSIZE,
LimitCORE, NoNewPrivileges and UMask as well as lifetime/cgroup policy. Prepared
user units clear PYTHONPATH/PYTHONHOME/LD_PRELOAD/LD_LIBRARY_PATH; the reader
requires that complete scrub independently of ordering. Existing proof units
remain stopped and are not silently adopted as the new policy.

Final game/service suite: 86 passed. Untracked root/nested/ignored/bytecode
shadows, hidden Git flags, missing resource properties and early module-load
sentinels are covered. Removing unknown-file admission and MemoryMax was seen
failing five cases; restored source cmp matched and ten guards passed. Raw
systemd property formats were observed read-only on this host. This is source,
protocol/offline configuration proof, not a newly running contained ET service.
Ruff and script Bandit medium/high gate passed. Current CI/review must still
measure this newer head. Evidence stays in /tmp/slomix-game-review* and review2*.
Next: refresh #1096 dependency, finish application delivery review and exact-head
checks; retain D5 and every original activation/roadmap gate.

## 2026-10-16 — Import-consumer review follow-up before parent merge

PR #1093 received three additional Codex findings after its earlier green CI.
Do not treat the old zero-thread snapshot as current approval. Default bound R1
replay now repeats the legacy team assignment after canonical commit/marker
recovery; deferred mode remains untouched. Mapping verifies the actual boolean
validation value recorded by the importer, preserving save-with-warning on both
halves and replay rather than converting warnings to rollback.

Migration 036 creates session_teams_identity_unique as a standalone unique index,
whereas the schema snapshot defines a constraint. Consumer readiness now checks
the actual valid, ready, immediate, nonpartial unique index and exact three keys;
team assignment and TeamManager infer that same key tuple for ON CONFLICT.
No merged migration is edited and no application database is changed.

141 selected tests passed, 11 native tests skipped because the isolated proof
cluster is offline. Added eight native cases: cancellation after commit with
default/deferred team policy, warning pair persistence/replay, and five index
layouts (constraint, standalone, wrong keys, nonunique, partial). CI must prove
these against PG14/PG17 before claiming native acceptance or merge readiness.
Three local mutations target mapping warnings, replay team effect and index
inference; logs/restoration evidence remain local. Ruff selected paths pass;
the standalone manager has twelve preexisting diagnostics, independently
compared baseline/current with no new diagnostic codes/messages.

#1095/#1096 continue as dependent delivery PRs (37/30 paths at their prior heads).
They must receive this parent correction through normal dependency merges and
repeat exact-head checks. First #1095 full-run documentation failure was fixed;
its c933793d Python legs passed 10289/10293 tests, distinct from later heads.
Actual DEV remains bot b46f675c and web da69e923; health/database OK on read-only
inspection. No service/game/database operation, deployment or PR merge occurred.
Retain D5, source admission/exclusive writer handover, proximity/gametime/storage,
API/live/Spiderweb/UI work and all original roadmap items. The full original
plan remains byte-preserved in the primary development checkout.

## 2026-10-16 — Immutable game delivery and supervised proof import

Next cohesive branch: feat/runtime-game-delivery-20261016, based on PR #1094
b83fbfc8. PR #1093 and #1094 remain unmerged; no number-specific permission.
Consolidated committed-source Lua/native bundle, closed private workspace,
optional pinned Supply bot fixture, startup recipe, offline user-unit renderer,
contained supervisor and explicit disposable-PG import adapter. Configuration
loader consumers (bot, migration runner, audit) and bounded migration connection
budgets travel together, including native/isolated fixture dependencies.
No unit installed/started, game launched, migration run or application deployed.

Initial extraction: 50 failed, 31 errors, 165 passed, 1 skipped. An existing
empty /tmp/.git makes outside-Git guards correctly reject all /tmp descendants;
use /var/tmp for offline output proof, never remove the guard or the directory.
Two configuration integrations and one migration fixture were missing from the
import-only inventory; included them, keeping the tests and assertions intact.
A subsequent collection failed on missing migration_runner fixture; preserved
and corrected by including its isolated fixture source.
Final selected suite: 386 passed, 73 skipped (DB/explicit real-engine prerequisites),
32.93s. Native PostgreSQL acceptance is still unmeasured locally.
Actual prepare + separate CLI verify retained an 18-file synthetic-ELF bundle;
Python SHA256 and sha256sum independently agree for every file. This verifies
packaging, not actual ET ABI, game startup, containment or database import.
An engine-hash guard mutation failed its regression; restored cmp matched and
regression passed. Ruff/Bandit gate pass; /tmp literal annotation is narrowly
limited to a namespace comparison, not allocation.
Review corrections: three Codex findings addressed. All existing Discord
session/digest/history link producers now use website_url with the explicit UI
mode (matching integration fixtures retained). Supervisor explicitly requests
--all systemd properties. On this host, an explicit --property already returned
empty values with and without --all, so "always refuses here" was not reproduced;
the flag makes the contract explicit and its regression checks the argv.
The corrected reader successfully inspected the existing stopped proof unit,
including empty NetworkNamespacePath and ControlGroup, without lifecycle action.
Service preparation catches malformed-workspace KeyError/TypeError and returns
redacted JSON; real CLI regressions retain input and create no output. 116 related
tests passed. Negative controls and restored evidence are retained locally.

Evidence remains local in /tmp/slomix-delivery-*.log and retained /var/tmp proof.

Next: publish/review this dependent slice, resolve exact-head CI findings, then
continue immutable application delivery, source admission/exclusive writer
handover and observation. Retain pending proximity/gametime migrations, API,
live mode, Spiderweb geometry/UI and all original roadmap items. Original plan
bytes from 0261b076 remain intact. No activation follows from preparation.

## 2026-10-13 — Spiderweb review recovery and versioned research evidence

Timeline failures now restore ordinary controls to the rendered time/POV;
only explicit retry retains the failed target.207 combined frontend tests and
typecheck pass, including four control sequences; two mutations fail/restored.
Layer4 collection/analysis validates schema, metric definition, cadence, LOS
and measured counts before reuse; old/mixed evidence and accidental append are
rejected before DB startup or output writes.115 targeted tests and four failed,
restored mutations pass; actual CLI accepts synthetic versioned rows and rejects
old/mixed inputs. Historical manifest remains unchanged and explicitly labelled;
no revised corpus median/effects are asserted. Independent reviews pass.

This remains an undeployed25-file slice. Fresh CI/review and the standard420s
cycle are required; ordered #1088 delivery must refresh main after #1087 merge.


## 2026-10-12 — Bounded Spiderweb correctness review

The review branch selects the completed Spiderweb source/tests onto current
main without importing the runtime integration history. Hearing uses event-time
listener positions; enemy metrics use the current roster. Legacy and SPA views
keep requested/accepted snapshots distinct, recover failed requests, distinguish
geometry failures, and fit authorized belief regions. Geometry verification
reports coverage only; success does not certify gameplay alignment.

Hearing reconstruction now names missing listener positions, invalid coordinates
and uncertain audible-range boundaries separately from capture capability.
Valid evidence survives partial reconstruction gaps. Actual ASGI requests with
a fixture database retain these reasons for player and team views without
claiming that modeled audibility proves hearing.

Revalidation: 302 Python cases, 176 targeted frontend cases, Node 22.23.2
TypeScript checks, Python lint and legacy JavaScript syntax checks. Existing
functional and guard-mutation evidence remains valid for its recorded scope;
no live deployment or new gameplay alignment is claimed by these checks.

Pending: broader positional validation and the separate runtime D4/D5
continuation. Preserve the complete original plan
and handoff below. No service activation, database writes, push or merge is
implied; this is a bounded review package awaiting the owner's PR decision.

## 2026-10-11 — CI-generated contracts reconciled

Full CI identified stale OpenAPI description, datapoint ledger and displaced
mandatory handoff preamble. Regenerate snapshots; explicitly retire oldest_seq
as a loss heuristic in favor of server gap evidence (unread baseline unchanged).
Keep the original handoff routing/authority preamble before all dated sections.
All20OpenAPI/datapoint/history contract cases pass locally; no test guard relaxed.

## 2026-10-11 — Live review findings addressed

PR #1085: eviction now records the last evicted sequence per admitted event
type, so hidden telemetry cannot manufacture a default-feed gap. Explicit
filters still receive gap evidence for their own lost types. Three HTTP
regressions failed first;55Python cases pass. Bump the full HTML/app/home/tonight/
ticker import chain and share one tonight URL. AST/DOM cache contract failed
before the bump;37frontend cases pass including failed replacement-worker read.
Watermark/cache mutations failed, source restored/cmp. Actual main-app ASGI:
HTML and all four JS URLs return200/source-equal; HTML/app revalidate, remaining
JS cache86400s. Same synthetic eviction returns default gap=false and explicit
movement gap=true. No listener, app lifespan, database or deployed browser proof.

## 2026-10-11 — Live empty/error polling recovery follow-up

PR #1085 self-review reproduced stale rendered status after a failed request
and stale derived scores on an empty gap response. Render every poll outcome,
age retained rows even during silence/failure, and honor gap before testing
whether a page has events. Two DOM regressions failed before the fix; all35
focused frontend cases pass afterward. Disabling row expiry was observed
failing in the real ticker's rendered JSDOM output, then restored with cmp.
No browser/server/deployment claim. Return to runtime-v2 D2 remains unchanged.

## 2026-10-11 — Live feed recovery isolated for review

A worker restart resets the in-memory sequence, previously stranding clients
behind an old cursor or mixing two workers' events. Add worker identity and
cursor-reset metadata, authoritative event envelopes and explicit gap evidence.
SPA query generations and serialized legacy polling recover retained events;
upstream failure is unavailable, and silence does not establish player absence.
This slice is based on main and contains no runtime-v2 migration/deployment work.
The complete runtime-v2 roadmap remains preserved in the local integration
branch fix/website-live-feed-recovery-20261011 at1d09f778; its D2 migration review
and owner service handover remain separate. Do not replace that plan with this
smaller public review branch. No service action or database write is part of PR.

Validation on this isolated branch:52Python/33frontend cases, typecheck and lint;
three negative controls observed failing/restored with cmp, and fresh-process
ASGI proof of old cursor50 recovering event1 with a new stream identity.
Browser/deployed acceptance, source-clock semantics, durable retry idempotency
and roster reconstruction after restart remain open follow-up work.

## 0. Kako se dela v tem repu (trda pravila)
- Feature veja + PR; **nikoli merge brez ownerjevega dovoljenja za TA PR**;
  merge prek `~/slomix-ops/cycle.sh <pr> <veja> "<naslov>" <telo.md>` (čaka CI,
  7 min pavze, zavrne vejo za mainom → prej `git merge origin/main`).
- `git add` po IMENIH (pre-push zavrne > 25 datotek čez vse commite pusha in
  `git add -A`); pred pushem `git diff --check origin/main...HEAD -- . ':(exclude)*.md'`
  (CI whitespace gate pade na prazno vrstico na koncu datoteke, brez pytest
  izpisa — Python job konča s kodo 2).
- Zeleni testi NISO dovolj: vsaka rezina rabi runtime dokaz (endpoint/stran/log)
  in vsaj eno mutacijo varovala, ki je bila VIDENA pasti (`cmp` po obnovi).
- Dev servisi tečejo iz `/home/samba/share/slomix-dev-run` (klon na mainu, od
  7. 9.), NE iz tega drevesa; deploy na dev = `scripts/dev_deploy.sh`
  (restart je NOPASSWD). Enote: `deploy/systemd/`. Watchdog timer teče iz
  istega imenika; webhook je v run-dir `.env` (`WATCHDOG_WEBHOOK_URL`).
- Nikoli restart/deploy servisov (`etlegacy-*`/`slomix-*`) brez ownerja; dev
  strežnik agenta je `nohup ./venv/bin/python -m uvicorn website.backend.main:app --host 0.0.0.0 --port 8056`
  (pid prek `ss -ltnp | grep :8056`, nikoli `pgrep -f`; zagon traja > 10 s).
  Dev `:8000` restarta owner. Puran (igralni strežnik) deploy = owner ali
  izrecna predaja; nikoli `lua_restart`.
- Lokalne datoteke, ki NISO v repu (gitignore): `docs/design/00–23`,
  `docs/OMNIBOT_PROJECT.md`, `server/omnibot/*`, `docs/archive`, `docs/research`.
  Agent v TEM checkoutu jih vidi; svež klon ne.
- Slovenščina v pogovoru z ownerjem; koda, komentarji in commiti angleško.
- Ownerju postavljaj konkretna vprašanja z opcijami, eno odločitev naenkrat.

## 1. Kje smo (verificirano 6. 9.)

### Nova spletna stran (SPA `website/frontend/src/app`, servirana na `/app`)
| kaj | stanje |
|---|---|
| faze 0–6 | zgrajene (32 rut v `routes.data.json`, vse `built`) |
| dolg r. 1 (#919, mergan) | keymap 7 rut resničen + guard (zgrajena ruta ne sme imeti `phase-N`), `/replay` → `/proximity`, `/api/diagnostics` admin panel na `/admin`; **vrzel endpointov 3** (`/api/bets`, `/api/bets/market` = ownerjeva odločitev; `/api/stats/sessions` = z upokojitvijo legacy JS) |
| faza 7 r. 1 (#920, mergan) | `compare` (`/compare/:a?/:b?`) in `wrapped` (`/profile/:id/wrapped`) kot ruti; **O1 zaprta: Clips strani NI** |
| faza 6 r. 3 + faza 7 r. 2 (#915, **mergan 6. 9. 14:40**) | availability admin market (open/settle/void); greatshot sekcije highlights/clips/renders (ruta je `:section?` nosila od faze 6, stran ga je ignorirala — brez novega endpointa); profil: rating trendi (`skill/…/form` + `/history`), serije po metriki (podatek je bil ŽE na strani, le nihče ga ni risal), memory card; `PlayerDrilldown` 6. instrument = dueli seje. ⚠️ `compare`/`wrapped` iz te veje ODSTRANJENA — #920 ju je mergal medtem |
| ⛔⛔ vrzel endpointov | **3 → 13, in to je KOREKCIJA, ne novo delo.** Legacy ekstraktor se je ustavil pri prvi `${`, zato je odrezan prefiks (`/api/players`) veljal za pokritega, brž ko nova stran kliče karkoli globljega — 29 legacy klicev nosi interpolacijo s segmentom za njo. Popravljeno v `test_route_contract._FE_FULL_PATH_RE`; vsaka vrstica v `tests/data/endpoint_gap.txt` ima zdaj zapisan razlog. #915 je od 15 zaprl dve (`bets/market`, `skill/…/form`+`/history`) in nato še tri (memory-card, player vs-stats) |
| končni paritetni prelet | veja `docs/phase7-sweep`: `scripts/audit_website_browser.mjs --app` čez 32 rut × 4 viewporti × anon/owner (256 preverb). Prava napaka: **»proximity →« s seje je nosil 8-znakovni guid → vsak skok na »ni zajema«** (popravljeno + e2e dokaz v tej veji); popravljeni audit/e2e vzorci (`:id/:a?/:b?/:guid`) in SPA-zavedna zaznava praznih pogledov; `admin` networkidle timeout kot owner = stran polla (artefakt merilnika); greatshot anon 401 = načrtovano stanje. Drugi tek z vsemi popravki: izid v `docs/PLAN.md`. |
| prod | **zamrznjen v1.39.0**; SPA na prod NI; preklop = `build:app` v `scripts/deploy_release.sh` (ownerjev dan); pred tem ultra pregled + 1–2 tedna soaka |

### Raziskovalne proge (vse mergane)
- Doc 22 dvojčki: r. 1 #913 (osebnost poti = časovna utež), r. 2 #914
  (camp-profile, peta plošča vlog), r. 3 #918 (generator
  `scripts/build_bot_twin_profiles.py` → `server/omnibot/twins/`, poročilo
  `docs/design/23`; kontrola s premešanimi sejami preživi ≈ 21 % — pragi iz
  kontrole). **Rezina 4 (harness bot proti človeku) rabi ownerjev deploy
  dvojčkov na puran + bot test.**
- Moments r. 2 #916: Lua v6.14 **deployan na puran** 5. 9.; migracija 082 na
  dev DA, na prod ob naslednjem release deployu; odprto: en večer
  `frame_health.log` brez novega `self` stroška; popravek korpusa
  `destroyed_count` (fantomska +1 na goldrush rundah pred v6.14) — owner.
- Doc 19 (per-user pogled): plan mode odprt in prekinjen, nič napisanega.
- Lokalni ET test strežnik (2.85, :27961): deploy Lua prek `sudo -n -u et tmux
  -S /home/et/.et-console-285.sock run-shell "cp /tmp/x.lua …"`, map load,
  `lua_status` SHA1 = `sha1sum`; po testu `scripts/local_et.sh -v 2.85.0 stop`.

## 2. Naslednji koraki (vrstni red, owner 6. 9.: ultra rezine → Astra)
1. ~~`docs/phase7-sweep`~~ = #921 mergan; ~~#915~~ mergan; #911 zaprt (dvojnik
   #919; razlike v BACKLOG); #912 ostane sestri; #882 (release 1.45.0) owner
   merga zadnjega → tag v1.45.0 = glava pregledov.
2. **Ultra pregled = 20 rezin, ne en PR.** Ultra sprejme ≤ 8 000 spremenjenih
   vrstic in ≤ 500 datotek na pregled (dokumentirano); koda od proda
   (v1.39.0) je 93 k vrstic. `scripts/review_slices.sh measure|cut --push|prs`
   seka veje `review-base/NN-<območje>` (= main z območjem vrnjenim na
   v1.39.0) in `review/NN-<območje>` (drevo = main, starš = baza; GitHub
   zavrne PR, katerega glava je prednik baze) in odpre draft PR-je (telesa v
   `docs/review/SLICES.md`, vodnik `docs/REVIEW_GUIDE.md`); **nikoli
   mergati**. ⛔ Ob vsakem premiku maina (#882!) `cut --push` znova. Owner
   požene `/code-review ultra <PR#>` (7. 9. opoldne) po vrsti: **#924** (01
   proximity+spiderweb+Lua) → **#925** (02 backend routerji) → **#926** (03 SPA
   lib); ostali #927–#943 po dnevih (odprti 6. 9. kot draft). ⛔ Stara baza `19c61847` je bila hash iz PRE-prepisne zgodovine
   (pravi #802 merge = `87a7063d`); veja izbrisana.
3. **Astra (Codex CLI, od 7. 9.)**: **predaja celotnega projekta = `docs/HANDOFF-astra.md` (§C delovni paket, §D ne delaj) + `docs/HANDOFF-astra-inventory.md`** (7. 9.); vstop = `AGENTS.md` (Codex ga naloži sam;
   preveri s `codex debug prompt-input "ping"`), kickoff
   `docs/prompts/astra_kickoff.md`, zanka `docs/process/MANDELBROT_RCA.md`,
   dnevnik `docs/AGENT_LOG.md`. Vrstni red (owner): triaža najdb ultra →
   odprte rezine (§2.5, §4) → watchdog r. 2 (r. 1 = `scripts/slomix_watchdog.py`
   + `deploy/systemd/etlegacy-watchdog.timer`, 6. 9.; r. 2 = SSH sonde na
   puran, `watchdog` ključ v `/api/diagnostics`, vrstica na About) → runtime
   v2 r. 1 (doc 21 §8) šele na ownerjev DA. Štiri proge 6. 9. popoldne: guid
   prefiks #945, diagnostics stanja #946, register datasetov #947, watchdog —
   podrobnosti v `docs/PLAN.md` »Proga: štiri točke do Astre«. Zunaj repa: `~/.codex/config.toml`, `~/.codex/AGENTS.md`,
   `~/.codex/rules/slomix-guard.rules`, `~/.codex/hooks.json` + hooka
   (`slomix-guard.py`: port `block-git-sweep`; surov stdin v
   `~/.codex/hooks/last_input.json` — obliko preveri po prvi seji).
4. Popravki iz pregleda → 1–2 tedna soaka na dev → pogovor o produkciji
   (preklop `build:app` v deploy skripti; migracija 082 na prod).
5. Vzporedno po ownerjevi izbiri: dvojčki r. 4 (rabi puran bot test), doc 19
   r. 1 (register datasetov + tipiziran `GET /api/datasets`), popravek korpusa
   `destroyed_count`, ~~proximity endpointi s sprejemom 8-znakovnega guida~~ = narejeno 6. 9. (resolver v `proximity_helpers.resolve_player_guid`, 17 handlerjev + AST varovalo). ~~availability r. 3~~ = narejena v #915.
6. **Preostalih 13 vrzeli, po izmerjenem trudu** (raziskave 6. 9.; podrobnosti
   in pasti so v komentarjih `tests/data/endpoint_gap.txt`):
   - `players/{}/card` (M) — arhetip + 90-dnevni form; ⚠️ njegovi percentili
     NISO percentili ET komponent (drug bazen, drugo okno — izmerjeno);
     dobesedni port FUT kartice bi trčil ob tipografski dizajn.
   - `rounds/{}/player/{}/details` (M) — objectives in sprees niso nikjer;
     ⚠️ `matches.js:970` bere polji, ki ju handler NE vrne (`combat.useful_kills`,
     `w.weapon_name`) — legacy modal že izpisuje `undefined`, ne prenesi napake.
   - `rounds/{}/awards` (S, blokirano na odločitvi o mestu — površine za
     posamezno rundo še ni; surov `value`, `session_awards_service` zna lepše).
   - `greatshot/{}/crossref` (S) — GET, auth+lastništvo, 23 analiziranih demotov.
   - `stats/player/{}/form` (S–M) — DPM/KD serija je že narisana iz
     `skill/…/form`; ta endpoint ima le datume, rounds/sejo, `avg_dpm`, `trend`.
   - `sessions/{}/graphs` (**L**) — osem osi `playstyle` + `dpm_timeline` ne
     obstajata nikjer; ni grafičnega primitiva (edini precedens `RetroViz.tsx`);
     ⚠️ šteje `round_number IN (1,2)`, Stats 2.0 pa `counts_toward_totals` —
     številke se NE bodo ujemale, panel mora povedati, katera vrata je uporabil.
   - ⛔⛔ `rounds/{}/vs-stats` — **NE migriraj**: handler nima `GROUP BY` in
     zavrže `subject_guid` (18 vrstic za 6 igralcev na rundi 11425). Popravi
     handler ali izbriši vrstico ob upokojitvi `matches.js`.
   - ⛔⛔ `greatshot/{}/highlights/render` — POST; renderer na tem stroju NI
     konfiguriran (ni ffmpeg, ni `GREATSHOT_RENDER_COMMAND`); `greatshot_renders`
     ima ENO vrstico ever, `failed`, ob 622 highlightih. Gumb bi vedno dal
     `queued → failed` — ownerjeva odločitev, ne samoumevna gradnja.
   - `uploads/{}/download` — **funkcionalno že pokrit** prek `download_url`
     (`UploadsPage.tsx:325`); vrstica ostane, ker literala v `src/app` ni.
     Res manjkata: gumb za prenos na kartici seznama in inline predvajalnik.
   - `/api/bets`, `/api/stats/sessions` — zapre ju šele upokojitev legacy JS.

## 3. Kako preveriti stanje (agent to lahko požene sam)
```bash
# ratcheti in guardi (Python), frontend testi, lint
venv/bin/python -m pytest tests/unit/test_parity_keymap.py tests/integration/test_endpoint_gap.py tests/integration/test_route_contract.py -q
(cd website/frontend && npm run typecheck && npx vitest run)
bash scripts/lint-js.sh
# živ dev strežnik + e2e (owner projekt NI admin — rig nima admin nivoja)
(cd website/frontend && npm run build:app)
nohup ./venv/bin/python -m uvicorn website.backend.main:app --host 0.0.0.0 --port 8056 > /tmp/uvicorn8056.log 2>&1 &
(cd website/frontend && SMOKE_BASE_URL=http://127.0.0.1:8056 npx playwright test --project=anon && SMOKE_BASE_URL=http://127.0.0.1:8056 npx playwright test --project=owner)
# paritetni prelet (manifest ~2 min, celoten ~25 min); rezultat <out>/results.json
AUDIT_BASE_URL=http://127.0.0.1:8056 node scripts/audit_website_browser.mjs --app --manifest --out /tmp/audit
AUDIT_BASE_URL=http://127.0.0.1:8056 node scripts/audit_website_browser.mjs --app --out /tmp/audit_full
```
Branje preleta: `deadState` = prazen pogled; `consoleErrors` s 401/404 preveri
proti namenu strani (greatshot anon 401 je stanje, ne napaka); `navigation
failed … Timeout` na `admin` je networkidle proti pollingu. Absent panel je
VELJAVEN render — prelet »renders without errors« ne ujame strani, ki vedno
pravi »ni podatkov« (zato je vzorčni guid v preletu polni, 32-znakovni).

## 4. Odprte ownerjeve odločitve
- ~~`docs/design` za ultra~~: podmnožica 00/05/06/09/12/17 + README commitana 6. 9.
- Po uvajanju Astre (O-3): rotacija DB gesla (194 vrstic v `~/.codex/rules/default.rules` ga nosi), čiščenje `default.rules` (`ssh`, `systemctl restart`), ali `.codex/rules`+`hooks.json` v javni repo.
- Watchdog oblika (O-2): samostojna skripta + systemd timer (priporočeno) ali oživitev `HealthMonitor`.
- Popravek korpusa `destroyed_count` — da/ne.
- Dvojčki: deploy `server/omnibot/twins/*` na puran + bot test (r. 4).
- Availability r. 3 (admin kontrole trga) — kdaj. Doc 19 — kdaj.

## 5. Sestrska seja
Dela v ločenem worktreeju `/home/samba/share/slomix-arena` (1v1 arena Lua,
veja `feat/lua-dots-arena`, pavzirana). Nikoli ne deli delovnega drevesa z
drugo sejo (worktree).
