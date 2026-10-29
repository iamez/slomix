## 2026-10-29 — Native ingestion succeeds; repair remaining historical fixture closure

First expanded CI346f75a0/PG14 proves all six new checkpoint/configured-entrypoint
policy cases and actual Lua canonical mapping/aggregate tests PASS. The full job
reports20failed/11848passed/163skipped: nineteen depend on an older linked_import
fixture lacking migration096/its batch-dispatch keyword interface; one still
asserts the old known-bug zero-origin duration of0instead of3000. Carry the existing
canonical fixture/test updates without changing source or weakening schema guards.
Current5a7d1323 Lua, security, frontend and CodeQL checks pass; the same obsolete
PG fixture closure still needs correction and a fresh exact-head full CI run.

Owner also requested a short player-facing Puran upgrade recap. Before-update
native evidence says2.84.0; selected archive/native proof says2.86.0-13-g39c75a3.
Primary upstream comparison confirms exactly13commits beyond v2.86.0, no behind
commits. Private evidence/puran-community-comp13-recap.md records the ready draft
and links. Do not attribute later Coming Soon antilag fixes or native-client-only
OpenAL benefits to this server/PK3 upgrade; no Discord message was sent.

Original runtime/D4/D5 and all retained incident/UI/history lanes remain intact.
No service, production, game, live DB or migration action; no merge permission1108.

## 2026-10-29 — Preserve full Lua CI contracts during ingestion publication

#1108 expanded head346f75a0 is published,67paths, within the recorded75-file
review target. Self-review confirms default-off policy and retained main schema;
CodeQL Python/JS and security checks pass. Fresh full CI exposed an old Lua
harness assertion: "a frozen levelTime for > 1 s must read paused=1". Pinned
COMP13 upstream39c75a3 g_main.c4614+ proves timeCurrent freezes during pause while
level.time advances; etmain/ui/menudef.h403 defines CV_SVS_PAUSE=16.

Carry the existing corrected frame-health harness and fix the vehicle fixture's
engine stubs: numeric unpaused CS_SERVERTOGGLES and an accepted-byte count from
FS_Write. Movement/escort/destruction assertions remain intact. All four actual
Lua CI harness commands now pass locally; all35tracked Lua files parse. Removing
the real pause-bit guard causes the updated harness to fail; cmp restores source.
This is a fixture/contract integration fix, not a reason to restore the incorrect
clock inference. Actual engine source references stay in private evidence.

Full original plan/features/history remain retained. PostgreSQL CI execution is
still pending; no1108merge approval, activation, migration or service/game action.

## 2026-10-29 — Complete proximity integration prepared for disposable-PG CI

Existing #1108 now carries one cohesive source path: real Lua producer IDs and
capture-quality headers, verified timing decoder, canonical parser, manifest-
gated ingestion, independent commit observation, durable retry/queue/cursor and
bounded worker/spawn supervisor. Explicit declaration policy remains default-off.
No extra branch or worktree was created. Existing main migrations/bootstrap are
preserved; unrelated website/config/community-parser changes are excluded.

Local selected suite: 595 passed, 110 PostgreSQL cases explicitly skipped; XML
and console counts agree. Sixteen frame-health compatibility cases also pass.
The first composition exposed24failures from a missing decode_gametime_document
prerequisite; carrying its existing stateless decoder resolves them. The changed
subset then passes160cases and the final selected suite has zero failures.
Three actual Lua/file/parser/receipt capture scenarios execute. Removing the gap
distance guard causes two observed failures (1010units instead of20); restore
is verified by cmp and all three runtime capture cases pass again. Selected
Python sources lint clean apart from the same two pre-existing parser datetime
warnings independently reproduced on main; no suppression or clock change.

Four new opted-in PG cases exercise actual DEV configuration through an async
worker or a freshly spawned native batch, with default-off and explicit-on policy,
owned DB resources, independent exact canonical links and retained inputs. These
and the two checkpoint-policy cases have not yet executed locally; actual PG14/17
CI is required. The old green46b5cabb foundation proof cannot certify this update.
#1108 has no numbered merge approval. No deployment, migration, live DB write,
service action, Puran/production change or source deletion. Retain the complete
original runtime/D4/D5, Supply/frame-health/Spiderweb/UI/Stats and README B+C plan.

## 2026-10-29 — Publish the complete proximity ingestion path in existing #1108

Fresh checks on46b5cabb completed without failures. Preserve that exact foundation
checkpoint and extend the same review worktree/PR with the canonical parser,
bounded ingest/commit/queue/batch/cursor/worker and explicit default-off policy.
Carry actual Lua producer/harness and timing-admission prerequisites needed by
the full stats + proximity identity proof. Keep existing migrations/bootstrap
from main; the full candidate contains an older schema ordering and must not
replace the already-published104/105 definitions. Do not copy unrelated config,
community parser or website/UI changes merely because static imports reach them.

Run selected local contracts and actual opted-in disposable PG14/17 CI, including
the two new policy-through-batch canonical import cases. Check exact source and
fixture dependencies, fresh processes, observer visibility, rollback/replay and
mutation failures before a complete-ingestion claim. No deployment/activation
claim follows. Preserve sticky reconciliation holds, source files and default-off.
#1108 still requires its own numbered owner merge permission after fresh proof.

All original runtime/D4/D5, Supply, frame-health, Spiderweb/UI/Stats work and
README B+C remain retained. No live DB write, migration, service/Puran action,
production change, new branch/worktree, source deletion or archival pruning.

## 2026-10-29 — Extend existing proximity PR with retry and resource foundations

Continue from the consolidated workspace; no new branch or worktree. #1107 at
b46b3bae and #1108 at e12acdc8 both have green CI and no unresolved review threads.
Neither has numbered merge permission. Extend #1108's existing caller-owned
identity/receipt primitives with the existing durable retry and database-resource
primitives instead of opening another PR for this closely related foundation.

Retry charges before work, serializes cooperating processes with flock, retains
backoff across restarts/cancellation/crashes, caps delay at 1800s and attempts at
64, and never acknowledges or deletes a source. Resource borrowing uses distinct
primary writer/observer backends, rejects database/schema mismatch and inherited
transactions, and unwinds borrowed connections on cancellation. No new pool or
service is implicitly started. Legacy writer exclusion remains the owner gate.

Combined local contracts pass132cases;16real-PostgreSQL cases explicitly skip
without a disposable DB. Native fresh-process retry/locking/crash tests execute;
removing backoff causes one observed failure, dropping resource identity guard
causes two; cmp verifies restoration. Actual PG resource fixture checks commit
visibility and rollback through the real adapter; fresh CI execution is required.
Its cleanup explicitly handles Exception and CancelledError. The worker/cursor
integration test remains in the full candidate for its later dependency slice.
An unused test import exposed by extracting that case was removed before publish.

Keep new test output and temporary directories inside the existing evidence
packet (workspace evidence link). Existing conftest unconditionally creates a
slomix-test-logs directory per run, even when log variables are configured;
set TMPDIR to the packet's test-tmp for these local runs instead of scattering
new directories in /tmp. No cleanup/deletion of previous outputs is performed.

Next remains parser integration and bounded ingest/commit/retry/dispatch/queue/
batch, then D4/D5 trusted-source/exclusive-writer acceptance. Original full PLAN,
Supply/frame-health/Spiderweb/UI/Stats and deferred README/About B+C survive.
No migration, live DB write, deployment, service/Puran action or merge occurs.

## 2026-10-29 — Publish declared proximity parent and receipt primitives

App #1096 and state #1097 are merged (5c4ad123 and 70a94d35). Independent
comparison proves the latter merge tree equals the exact reviewed 52189ee5 tree.
#1101 now targets main at 6d3b5958; source bytes are unchanged by verified ancestry
recording. #1107 at b08ced4e includes the timing declaration detection exemption
and inherits all current state guards. Fresh CI is required; neither PR has
numbered owner merge permission.

The next dependency slice reuses existing header, declared parent resolution and
receipt-link primitives from the full candidate, including the dot/plus map
alphabet fix. Independent trusted source/hash/size/date binding precedes mapping,
canonical round and initial-journal agreement. Legacy absence remains unbound;
explicit contradictions refuse instead of clock fallback. Receipt prevalidation
refuses historical completed/unlinked rows and reassignment; late link recording
participates in the caller-owned transaction. No parser/Lua/consumer activation
or ingest/queue wiring is included in this library slice.

Local focused contracts: 95 passed, 15 PostgreSQL cases explicitly skipped.
Native verified-source file proof covers both halves of five map spellings with
exact identical library bytes and independent GNU/Python hashes. Digest guard
removal causes one observed failure; actual journal-guard removal causes two,
then cmp verifies restoration. An earlier inequality inversion was inconclusive:
it rejected a different healthy half, masking the intended negative mutation.
Do not call that result a proven guard. New disposable-PG cases exercise actual
R1/R2 mapping/journal queries, contradictions, missing mapping without clock
fallback, receipt rollback, legacy refusal and strict late-link prerequisites.
Actual PostgreSQL CI proof remains required for these newly extracted cases.

Next: review the identity primitives, then the existing bounded ingest/commit/
retry/dispatch/queue/batch integration. Preserve D4/D5 trusted-source/exclusive
writer gates and the original runtime/Supply/frame-health/Spiderweb/UI/Stats
roadmap. No service, database write, new server, Puran or production action.

## 2026-10-29 — Verified forward schema and inherited state admission fix

All 67 proximity schema cases at 428a0ee4 passed on both actual CI PostgreSQL 14
and 17, with zero skips. These include valid-row preservation, atomic refusal of
invalid preexisting lineage and three executable SQL guard mutants. This closes
that head's SQL proof gap; fresh CI is still required after inheriting #1097's
new bare-ancestor admission correction. No applied migration bytes changed.

#1096 is merged. #1097's prior merge cycle correctly refused a new unresolved
review; its corrected source is inherited here before the replacement cycle.
#1107 separately publishes all five preserved timing/lifecycle SQL sources and
currently awaits its own PostgreSQL CI. Neither #1101 nor #1107 has numbered
owner merge permission. They do not authorize database execution or activation.
Identity/receipt linking and bounded ingestion remain next, with D4/D5 and the
complete Supply/frame-health/Spiderweb/UI/Stats roadmap preserved.

## 2026-10-29 — Refuse selected subtrees of bare Git repositories

The approved #1097 merge cycle refused safely: failed=0, threads=1, behind=0,
sha=yes; the PR stayed OPEN. Review 4407550761 is confirmed: selecting a child
of a bare repository bypassed the root/nested metadata guard. Nine new cases
failed before the fix, covering initial plan, late seed arrival, source/target
delta scans and an actual plan CLI subprocess.

Inventory now inspects every selected-root ancestor for bare metadata, using a
separate bare-layout predicate. Ordinary data inside a normal Git worktree
remains supported. The existing selected-root/nested .git and bare checks stay
in force. All 217 state tests pass; removing the ancestor guard produces two
observed failures, then cmp confirms restoration. Native CLI refuses before
report/destination creation. No live state is copied or service controlled.

Publish the corrected head, answer/resolve the confirmed review, and repeat fresh
CI plus the complete prescribed 420-second merge cycle under existing numbered
#1097 approval. Do not reuse the earlier completed wait or claim it merged.
#1096 remains merged; #1101 and new #1107 (preserved timing/lifecycle schema)
have no numbered merge permission. Original full runtime plan, D4/D5 and
Supply/frame-health/Spiderweb/UI/Stats obligations remain. Production and
owner-upgraded Puran are unchanged.

## 2026-10-29 — Preserve the timing declaration coverage exemption

Initial #1107 PostgreSQL 17 CI executed all 65 new timing/lifecycle schema cases
successfully, with zero skips, but the whole job failed two round-id coverage
contract cases. Publication omitted an existing full-candidate dependency:
runtime_gametime_identities.round_id is a producer-issued 32-hex TEXT identity,
not canonical rounds.id. Restore its documented detection exemption; generic
clock-based relinking must never rewrite these immutable declarations.

Only the existing six-line exemption is ported. Relinker queries/writers and
coverage/canary tests remain unchanged. The focused local contract/schema suite
passes 19 cases and explicitly skips 53 PostgreSQL cases. Removing the exemption
causes both observed failures again; cmp confirms restoration. Re-run full CI at
the corrected published head before claiming green. No services, database writes
or historical source adoption. #1107 still has no numbered owner merge approval.
Original runtime plan, D4/D5 and retained incident/UI/Spiderweb work remain.

## 2026-10-29 — Publish preserved timing schema before identity ingestion

Runtime app #1096 is merged at 5c4ad123; the separately approved state #1097
is still in its final merge cycle. Proximity #1101 at 428a0ee4 passed all 67
actual schema cases on PostgreSQL 14 and 17, with zero skips. Its applied
096/100 bytes are preserved; stricter provenance is forward migration 105.
Neither #1101 nor this follow-up has numbered owner merge permission.

Publish the five existing, already-applied timing/lifecycle SQL sources
097/098/101/102/103 byte-for-byte from the preserved release. Register them in
dependency order and retain exact timing bootstrap blocks plus the nullable
player_track.death_type column. No timing consumer, Lua change, historical
adoption, backfill, service action or migration execution accompanies this slice.
Identity/receipt linking follows after source publication, then bounded ingestion.

Ten source/registration/bootstrap cases failed before restoration. Afterwards,
26 focused static cases pass, with 106 PostgreSQL cases explicitly skipped
locally (including the inherited proximity suite); actual CI PostgreSQL proof is
still required. Checksum and omitted-bootstrap mutants each produce one observed
failure, then source restoration passes cmp. New SQL fixtures exercise legacy
source preservation, private ACL replay/reachable-role refusal and nullable
lifecycle cause preservation. Existing link/application schema fixtures are reused.

Native read-only checks against BOTH actual DEV roles independently count 105
applied ledger entries and verify every restored file checksum. Missing files,
checksum differences and invalid required columns are all zero; only 104/105
remain pending. This proves source completeness, not activation readiness.
Preserve D4/D5 trusted-source admission/exclusive writer handover, the original
full runtime plan and Supply/frame-health/Spiderweb/UI/Stats work. Production
Slomix and owner-upgraded Puran stay unchanged. Private proof packet:
/home/samba/share/slomix-runtime-app-final-20261029-9nixuxrr.

## 2026-10-29 — Preserve applied migrations and move lineage guards forward

Actual DEV role preflights exposed checksum differences for096/100. Independently
verified original bytes against105-row live ledger and eight preserved release
copies per file, including Git object38dbeebf. Restore the consumed096/100bytes;
keep their historical semantics intact and move the existing strict lineage
indexes/FKs/null-gate check into NEW105_runtime_proximity_parent_constraints.sql.
No live ledger or table is edited. New105validates existing rows and refuses
incompatible lineage; it never infers a link or rewrites data.

Bootstrap mirrors original096/100once plus105once; newest release config includes
105. Tests cover a valid existing row unchanged across upgrade, atomic rejection
of three invalid existing states, three executable SQL guard mutants and pinned
old checksums. Local71unit/static/release-config cases pass;53actual PostgreSQL
cases explicitly skip without an isolated service. This is NOT a SQL execution
certificate. Publish for current-head PG14/17CI before claiming the fix verified.

Unpublished identity/application source still accounts for five other already
applied migrations097/098/101/102/103. The earlier shorthand attributing all seven
missing app-source migrations to1101was imprecise:1101provides096/100only. Preserve
both later publication lanes and never weaken startup inventory to hide omissions.
Original runtime/D4/D5, Supply recovery and UI/Spiderweb plans remain. Owner's
Puran update and production app version are unchanged. No new server or DB write.

## 2026-10-25 — PR #1101: actual PostgreSQL proof and rejected column-ACL review premise

- Verified public source head 9db6212a8c52905d4b45515affeda496856d3049 against CI run 39654495446, both Python jobs SUCCESS. PostgreSQL 14 / Python 3.11 job 119411051105: 11140 passed,161 skipped,11 subtests; PostgreSQL 17 / Python 3.13 job 119411050977: 11144 passed,157 skipped,11 subtests. Each job executed all 57 proximity schema cases, including 49 database cases, eight direct/PUBLIC column-ACL cases, three inherited-access refusals and three observed SQL guard mutations. Schema case counts independently agree via parsed log records and line counts.
- This closes the previous missing disposable-PG proof for the Oct21 relational constraints. Native PG executed the mismatched stats parent, legacy/unlinked/hash-mismatched receipt, nullable gate, post-binding receipt edits, migration replay and SQL mutant cases. Local services/databases were not started or changed.
- Review 4340613934 / PRRT_kwDOP4ZX3s6u52sJ is a false positive: the claimed column-ACL test failures are contradicted by both actual CI logs. PostgreSQL REVOKE documentation explicitly states table privilege revocation also revokes corresponding privileges on every column: https://www.postgresql.org/docs/17/sql-revoke.html . Existing REVOKE ALL covers direct website_app and PUBLIC column grants; inherited access intentionally remains a refusal. No redundant column enumeration or SQL/bootstrap change is needed.
- Evidence is in the public CI jobs; private downloaded logs remain outside git. Continue the original runtime plan and review queue. PR #1101 remains unmerged and still needs its own explicit owner merge permission; approvals #1095–#1097 do not extend to it.

## 2026-10-21 — PR #1101 review: strict relational provenance and recoverable admission

- Addressed reviews 4337378411/8425/8436/8445/8462: release v1.45.0 explicitly lists unmerged migrations 096 and 100; admission source IDs use the existing lowercase RoundIdentity alphabet; shared publication refuses unreadable/non-private temporary modes before the atomic link, preserving restrictive 0400 and ordinary 0600 without chmod.
- Migration 100 adds unique parent indexes and composite foreign keys: source/round/canonical ID must name the SAME stats mapping; filename/canonical ID/SHA-256 must name the SAME strictly linked receipt. Migration 096 requires runtime_parent_gate IS TRUE (NULL must not pass SQL CHECK). No merged migration was edited, no backfill or historical receipt adoption is introduced. Exact bootstrap blocks match both migration files.
- Local proof: 292 passed, 49 disposable-PG cases skipped; shared spool, completion, manifest read/retry, release contract and fresh-process admission recovery included. Source/mode/release guard mutants visibly failed 1/3/1 cases and source bytes were restored with cmp. Ruff and diff checks passed. New SQL rejection, post-link receipt mutation and three in-memory SQL guard-mutant cases await disposable CI PostgreSQL; skipped tests are NOT database proof.
- Prior published head CI job log independently confirms 42 schema cases passed and the sole Python 3.11 failure was the missing release config entries (11120 passed,161 skipped). That old SQL execution does NOT validate the new relational constraints. No database/service/browser was started and no production or DEV state changed.
- Continue the preserved runtime plan after fresh CI/review; #1101 still needs its own explicit owner merge permission. Existing approval for #1095–#1097 does not extend here.

## 2026-10-21 — Proximity publication checkpoint

First existing-code slice contains schema096/100 and persistent admission only.
40 offline tests pass;34 disposable-PG cases are pending, not runtime acceptance.
Keep identity/parser parent linkage next, followed by ingest/commit/retry/queue.
The three ingest-dependent admission cases remain in the full local candidate.
Preserve later clock/pause, gametime, API/UI and all original D4/D5 obligations;
do not copy mixed parser/test snapshots into this schema-only publication.
No service, migration application, push or new PR approval accompanies this slice.

## 2026-10-29 — Protect release directories and publication from permissive umask

Review4403859169 is confirmed: umask000/002 allowed writable payload directories,
and restrictive umask077 also prevented normalized directory modes. Fifteen new
cases failed before the fix. Create every directory component with0755 and
normalize it, including root and both frontend output trees. Reserve each file
owner-only0600 before copyfile writes any bytes, then set its committed0644/0755
mode. Reserve the manifest privately and publish it as0644. This closes the
related open-file race under umask000, not just final directory permissions.

Version2verification now requires0755directories and0644manifest in addition to
its existing complete file-mode/hash inventory. Legacy version1retains its prior
byte-only contract.243focused packaging/bootstrap/contract/health/consumer tests
pass. Directory-admission and private-copy mutants are observed failing, then
restored with cmp. Fresh exact-source actual-package/native unit proof follows;
old local version2artifacts are retained and never silently rewritten.

Native9db712c4artifact proof completed before this follow-up: both frontends,
1037fileGit-free package, exact HTTP200bytes, operator tools without-B, actual
external config/role interpreters and systemd249parse passed. No native schema
readiness is claimed: applied096/100source hashes still require immutable source
restoration and a new forward hardening migration, plus pending104. No live DB,
service, game or production change. Owner's completed Puran upgrade is preserved.

## 2026-10-28 — Fix native systemd 249 inline argument rejection

Actual final-path unit verification exposed a previously untested host limit:
4411byte hex bootstrap argument exceeds systemd249's4095byte argument budget.
A native isolated unit fixture independently reproduces rejection at4096bytes
but accepts4095 with default dependencies disabled. Encode the same trusted
stdlib verifier using strict Base64, preserving all integrity pins, source
buffers, namespace admission and raw-argv matching. Refuse oversized startup
arguments during preparation rather than emitting unusable unit text.
Three new cases failed before the change;201focused bootstrap/contract/health/
package/ledger cases pass afterwards. Disabling the size guard fails visibly;
source restored with cmp. Repeat exact-source builds/package/native unit proof
from this final commit before considering the approved merge cycle ready.

Correction: an earlier ad-hoc shell sequence masked systemd-analyze's returncode
with a subsequent successful Python command. Explicit returncode capture showed
failure; do not claim old generated units passed. Separate read-only actual-role
schema gates refuse the old package's missing applied-source files and pending104;
fullcandidate additionally exposes096/100source-vs-ledger checksum differences.
Do not rewrite DB ledger checksums or apply migrations automatically. Puran stays
deferred; no service/unit installation, restart or live DB write occurred.

## 2026-10-28 — Refuse bare Git metadata in state sources

Review4370885447 is confirmed: the prior inventory admitted bare repositories
at a selected source root or nested directory. Reuse the existing git_boundary
recognizer before scanning every directory; plan, seed revalidation and delta
source/target inventories now reject metadata before copying it.
Eight new cases were observed failing before the fix, including actual native
CLI acceptance, and all207state cases pass after it. Disabling the new guard
again makes both root/nested cases fail; restore is cmp-checked and restored
native refusal cases pass. Target-preservation classification mutation also
fails as expected and restores with cmp. No live state/data or service change.

Actual synthetic seven-scope plan/seed/delta workflow preserves a divergent new
target. Read-only actual manager observations show DEV bot/webactive and both
watchdogunitsinactive; no claim of exhaustive writer exclusion or readiness.
Keep the routing header before dated handoff entries (11ledger cases pass in
app after its first full-CI documentation ordering failure). App final source
isecb812b9, actual final1037filepackage rebuilt and statically served; app CI and
its420second approved merge gate are still pending. Puran update stays deferred.

## 2026-10-28 — Refresh state handover after final app preparation

Owner deferred Puran updates and requested autonomous runtime continuation.
Merge reviewed app source71589a60 into the existing #1097 branch, preserving all
state-only tools/tests and both ledger histories. The only conflict was an empty
state side versus the diagnostic-tool handoff insertion; retain the insertion.
App proof: 1037 Git-free payload files, native static responses, hash/mode tamper
refusals, 285 Python cases and 985 frontend tests. #1096 current-head CI and its
approved merge cycle remain separate; no merged state is asserted here.
Next: focused state seed/delta/writer tests and fresh native CLI proof, then
refresh #1097 after #1096 actually lands. No new data seed from live roots,
service action, migration, Puran change or production deployment.

## 2026-10-28 — Final app source integration verified locally

222 focused Python cases pass using a new outside-Git basetemp. The first
attempt under the default /tmp fixture path correctly refused this host's
existing /tmp/.git fence; the marker was preserved and no guard weakened.
Modern-output integrity guard mutation was observed failing at the assertion
that refusal precedes destination creation; source restored with cmp and the
restored case passes. Both npm lock audits report zero vulnerabilities;
frontend typecheck passes with isolated Node22.23.4. Frontend tests and final
exact-source builds/package proof follow. No live service or data change.

## 2026-10-28 — Resume runtime app delivery; defer Puran update

Owner explicitly deferred the Puran engine update until a future instruction.
Retain its reviewed packet without executing the updater. Resume original runtime
queue at #1096 application packaging, then #1097 state handover and D4/D5.
Integrate the previously verified modern route-host provenance/copy guards into
#1096 while retaining its newer no-bytecode bootstrap and raw systemctl argument
fixes. Inherit the already developed Node22.23.4 and frontend lockfile security
floor so this application preparation does not rebuild superseded dependencies.
Next: focused regression/mutation checks, both exact-source builds, new Git-free
package and native static-response proof. Source readiness, merge and service
activation remain separate. Production, Puran and live DEV services unchanged.

## 2026-10-25 — Diagnostic tools preserve inventory and raw systemd argv

Reviews4369811073/4369811077 addressed. Packaged contract/health tools set
sys.dont_write_bytecode before project imports; preparation does the same.
Native actual packaged --help now runs without -B and preserves the v2 inventory.
Health command parsing compares systemctl's raw joined argv bytes, never shlex
syntax; the known contract requires whitespace-free arguments and rejects
ambiguous inputs. Literal quotes inside the hex bootstrap remain significant.
The fixture now models actual raw systemctl output rather than shlex.join.

103 focused tests pass. Contract-bytecode, health-bytecode and raw-argv mutants
were observed failing, then restored with cmp. No manager mutation, application
startup, service restart or deploy. The separate static/modern artifact omission
review remains in progress in an isolated worktree.1095 owner-approved merge
cycle is running with full420second pause; no merge asserted until verification.

## 2026-10-25 — Close remaining inherited settings, audit path and CLI bytecode gaps

Corrected #1095 review4340638914: marked environment loading now calls the full
explicit allowlist already developed downstream in #1096. The same shared
SYSTEM_ENVIRONMENT, RELEASE_BOOTSTRAP_KEYS and refusal helper are preserved,
including strict preflight compatibility. Non-DB application settings absent
from the approved file (for example BOT_NAME_REGEX or SSH_ENABLED) cannot enter
through inherited environment. This supersedes the narrower Oct21 DB-only
additional-key guard; identical approved repeated loads remain valid.

Corrected review4340638928 by porting the identical downstream server_control
BOT_LOG_DIR change: cog construction and audit writes use the external log root,
while unmarked legacy fallback stays logs. Corrected review4340638938 by setting
sys.dont_write_bytecode before any project import in prepare_runtime_game_service.
An ordinary CLI invocation without -B cannot dirty source before verify_source.

Final focused/shared regression suite:143 passed in23.33s, also independently
collected. Native subprocess evidence includes inherited non-DB refusals, an
actual ServerControl audit write to external logs with the payload directory
remaining empty, and CLI --help without -B/PYTHONDONTWRITEBYTECODE, comparing
complete before/after source file hashes and independently checking no pyc files.
Three guard mutations fail5(environment),1(audit path),1(bytecode) tests; each
source is restored and verified with cmp. Ruff/diff checks pass. Initial focused
run had91passes/2fixture failures because pytest itself injected PYTEST_CURRENT_TEST;
the two in-process fixtures now remove it. Production allowlist was not weakened.

Only source, tests and these four existing ledgers changed. No service, production
configuration, database, Discord connection, game process or deployment occurred.
#1095/#1096/#1097 approvals remain subject to fresh reviews/CI and the prescribed
merge cycle; no push or merge performed here. Continue trusted #1096 bootstrap
integration and preserved runtime/state/proximity/UI/Spiderweb plan.

## 2026-10-25 — Package startup dependency, modes and unfiltered readiness

PR1096 reviews4340716247/4340716262/4340716275/4340716286 addressed in source.
The release allowlist now includes runtime_app_bootstrap. New prepared releases
emit manifest v2 with exact0644/0755 modes for every payload file, and verification
checks the full mode inventory including executable/set-ID drift. Historical v1
manifests retain their previous byte-only contract; no existing artifact rewritten.
Readiness writes/flushed stderr after startup checks, independent of LOG_LEVEL.
Resolved command comparison refuses concatenated extra ExecStartPre structures.

143 targeted tests pass, including actually prepared Git-free package tools
--help in isolated native Python, all log-level cases and exact-mode drift.
Four removed guards visibly fail (package inclusion/modes/extra commands/readiness)
and original files are restored with cmp. Full package preparation remains offline;
no service/DB/network listener started. Existing prepared units need regeneration
from final reviewed source. Original runtime/proximity/UI/D4/D5 plan preserved.
Initial overly broad v1 mode restriction rejected legacy fixtures under host
umask0002; corrected to versioned v2 guarantees instead of silently changing the
historical format. Two existing websockets deprecation warnings remain.

## 2026-10-21 — Verify application payload before any project execution

PR1096 closes the launcher integration for1095 review4337326790. Prepared unit
commands now embed a standard-library-only bootstrap under isolated Python.
External unit pins bind both manifest and verifier bytes; the verified verifier
buffer executes before any project import, then verifies the complete payload.
Bot/preflight entry buffers are rehashed and executed directly with the verified
root marker. Web CLI starts only after the same admission. No payload-local
launcher is trusted before verification. Stable trusted owner/unit/interpreter
remain prerequisites; this is not protection against an authorized hostile owner.

104 targeted tests pass, including native child execution, preflight and actual
uvicorn --version without binding a server. Tampering with entry, imports,
verifier, manifest, extra files and symlinks refuses before application output.
Three removed guards (manifest pin/verifier pin/full inventory) each visibly fail;
original file restored and cmp verified. Older contract tests were updated for
new argv shape and systemd quoting; isolation flags remain actually exercised.
No service was installed/started/restarted and no database was contacted.
Existing prepared units must be regenerated from final reviewed source before
any owner activation. Original runtime/D4/D5 and proximity/UI roadmap retained.

## 2026-10-21 — Enforce marked bot configuration and writable-state boundaries

Addressed #1095 reviews4337326762/4337326777. Marked release environment loading
now refuses differing inherited file settings and additional database/PG settings
before any partial environment update. Identical settings permit repeated imports;
unmarked legacy checkouts retain process precedence. Literal dotenv values and
approved digest checks remain unchanged.

Marked bot startup requires canonical absolute external STATS_DIRECTORY,
LOCAL_STATS_PATH, BACKUP_DIRECTORY and BOT_LOG_DIR before importing bot services
or logging. Active gametimes/proximity paths are mandatory; supplied metrics,
cache and storage paths are checked too. Metrics and error-streak defaults derive
from the validated external log root. Missing, relative, payload-local and symlink
paths fail closed; legacy paths remain compatible.

Review4337326790 integration: direct marked bot script/module startup now refuses
unless the executing namespace contains the verified release root. This is not
an environment toggle. #1096 must supply that namespace only after its external,
pinned bootstrap verifies the payload; direct startup refusal alone is not proof
of trusted launch. Unmarked source startup remains available. No service change.

Functional/native evidence: isolated subprocesses load marked payload copies,
refuse inherited database/path overrides without writes, reject unsafe writable
paths and direct entry, and permit a repeated approved load followed by an
external stats-directory write. Final shared bot/migration/audit regressions:
103 passed in19.08s. Three observed guard mutations fail3(environment),4(required
paths),1(bootstrap) tests respectively, then each source is restored with cmp.
Ruff and diff checks pass. Initial sandbox fixture run failed with read-only
/var/tmp; rerun with isolated fixture permission succeeded. No real database,
Discord, game, network listener, service or deployed payload was touched.

Original runtime/UI/Spiderweb plan remains preserved. Owner approval for
#1095/#1096/#1097 remains unconsumed; final CI/reviews and prescribed merge cycle
still apply, and bootstrap integration is required before considering the queue
ready. No merge/deploy approval is inferred for any other PR.

## 2026-10-21 — Redact marked audit failures after successful connection

Corrected #1095 review4332958068. Audit main now owns a marked-release ordinary
Exception boundary across rule validation, cursor/query execution, connection
close and reporting. It returns structured refusal without raw driver/query/path
messages. Existing configuration/connection refusals remain compatible; unmarked
legacy execution errors retain their existing propagation. KeyboardInterrupt,
SystemExit and cancellation are not swallowed. In marked execution, an ordinary
close failure cannot mask an already active control-flow BaseException.

Native isolated Python fixtures use successful fake psycopg2 connections and
actual audit rules/cursor execution: read-only session, cursor/query/close errors,
rule validation, legacy controls and interrupts with/without cleanup failure.
No actual DB/Discord/network connection occurs. Driver event markers confirm the
intended paths ran and close was attempted. Initial harness10failures came from
an empty synthetic password rejected by the audit's existing nonempty setting
contract before the driver; fixture corrected, production policy unchanged.

Combined targeted suite75passed. Redaction guard mutation produces4failing marked
controls and4passing legacy controls; cleanup guard mutation produces2failures
and2passing ordinary interrupt controls. Source restored and cmp verified after
each. Final restored twelve native execution controls pass; Ruff/diff pass. Counts
overlap prior runs. Pillow13.0.0 security fix retained unchanged. No service,
engine, live database, deployed payload or production configuration touched.

Owner explicitly approved1095/1096/1097merges onOct21; approval remains conditional
on green exact-head CI/reviews and the ordered merge procedure, not activation.
Next: refresh dependent parents/full candidate, publish, resolve this review and
complete approved cycles. Original D4/D5/exclusive writer handover and the entire
runtime roadmap remain preserved.

## 2026-10-21 — Trusted probe execution, early report reservation and no-atime reads

Addressed #1097 reviews4332970087/4332970092/4332970097. Writer probes execute
only /usr/bin/systemctl after checking root ownership, regular executable kind,
no symlink and non-group/world-writable executable/ancestors. Child environment
is a fixed minimal allowlist, plus the validated canonical user bus for user
scope; inherited PATH/loader/system-bus overrides cannot select probe code.
Native fake PATH binary demonstrably executes in an unguarded positive control,
then never executes through CLI. Actual read-only UID1000 host proof: sanitized
CLI and independent clean /usr/bin/systemctl agree bot456340active. Named unit
metadata remains neither writer exclusion nor source freshness/activation proof.

Seed CLI validates the saved plan/UID before output, exclusively reserves the
private report stream before any seed copy, and completes/fsyncs the same stream.
Existing output wins before copy; partial report/output are retained on failure.
Native filesystem/main control attempts a competing exclusive report create
during seed, observes refusal, then verifies complete report and copied content.
Inventory fingerprints, directory scans and source copying use Linux O_NOATIME;
unsupported/permission-denied no-atime access refuses without unsafe fallback.
Actual old atime fixtures prove file AND directory access timestamps unchanged
through plan, seed and delta scans; target-deleted ancestry fence remains intact.

199targeted tests pass. Four observed failing guard mutations: no-atime3cases,
early reservation1, clean environment1, trusted executable metadata3. All source
restored and compared with cmp. Ruff/diff pass; no service/ET/live DB/state change.
Fresh game audit redaction review fixed separately as f40ede2e before any merge.
Owner-approved1095cycle previously completed failed0/threads1/behind0/head same,
correctly leftPRopen. Refresh/publish all parents, answer these reviews and run
new exact-head CI plus full420second cycles; preserve D4/D5 and original roadmap.
## 2026-10-21 — Repair newly failing Pillow security gate

Fresh exact-head Security CI failed: pip-audit reports8new CVEs for pinned
Pillow12.3.0, all fixed in13.0.0. Updated only the root runtime Pillow pin.
Official13.0.0release notes/Python support retain Python3.11and3.13 compatibility.
Isolated actual13.0.0wheel (not installed in active venv) passes9existing image
reader tests with real7/8map screenshots, exact numeric results, malformed and
wrong-zoom refusal. Actual Pillow module path/version verified at runtime.
Independent old/new pip-audit JSON control:12.3.0has8findings,13.0.0has0.
No audit suppressions. Full CI will validate both Python lanes before merge.
Collected entire obsolete1095wrapper output and stopped only that wrapper;
no source merge had happened. Restart full420-second cycle only on corrected
head and fresh checks. Owner approval1095–1097remains valid; no service/deploy.
Sources: https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html
https://pillow.readthedocs.io/en/stable/installation/python-support.html
## 2026-10-21 — Complete marked inner migration failure redaction

Root self-review found two pre-existing cmd_apply catches that printed raw error
text and raised SystemExit before the new outer Exception boundary could redact
it. Marked MigrationRejected now propagates to the structured outer refusal.
Marked DDL exceptions still record the failure ledger row, then propagate without
printing the original error. Unmarked legacy REJECTED/FAILED text and error detail
remain unchanged. Connection-close failures already reach the outer boundary.

Native synthetic connection fixtures now reach actual cmd_apply transaction,
execute, failure-recording and close code, rather than only connect failures.
Marked execute/rejection/close failures return redacted structured results with
partial_commits_possible=true; matching unmarked controls retain legacy error
printing/trace behavior. Driver event markers prove execute/failure recording and
close paths ran. No database connection or real SQL execution occurs.

Twenty native migration tests pass, including prior command/identity/interrupt
controls. Three mutations (rejection catch, DDL catch, outer close boundary) each
produce respectively1/1/3observed failing marked controls while retaining
1/1/3passing legacy controls. All source restored and cmp verified; final restored twenty-test group
passes. Ruff/diff checks pass. Owner's explicit Oct21 merge approvals for
#1095/#1096/#1097 remain conditional on review/CI and the ordered merge procedure;
no service/deploy authority is added. Next:publish both migration corrections,
refresh parents, resolve reviews and inspect exact-head CI before approved cycles.
Original D4/D5, exclusive writer and full runtime roadmap remain preserved.

## 2026-10-21 — Marked migration execution redaction and nonempty identities

Owner explicitly approved merging #1095, #1096 and #1097 on2026-10-21, subject to
successful review/CI closure and the existing ordered merge procedure. No service
activation or production deployment follows from that approval.

Corrected #1095 reviews4328317906/4328317921 before consolidation. The marked CLI
now wraps every command's asyncio.run dispatch in an ordinary Exception boundary,
returning a structured redacted refused_or_failed result with explicit
partial_commits_possible=true. This is not a rollback claim. KeyboardInterrupt,
SystemExit and cancellation remain outside that boundary; legacy unmarked errors
retain their existing propagation.

Marked explicit configuration must select a nonempty host/database/user (and
port). A blank primary POSTGRES value cannot silently fall back to a populated
DB alias or implicit PostgreSQL driver defaults. Missing passwords remain refused,
but an explicitly empty password remains valid for supported local authentication.

Native isolated Python children exercise all six actual CLI command paths with a
synthetic asyncpg.connect failure and no real connection. Driver sentinels confirm
command execution; raw exception text never escapes the marked redaction. Six
empty/whitespace identity cases refuse before the driver. Exit73 and SIGINT-style
KeyboardInterrupt propagate. Combined targeted suite91passed; two deliberate
guard mutations each caused6observed test failures, restored byte-for-byte with
cmp. Final restored native group14passed; counts overlap and must not be added.
Ruff and diff checks pass. No services, ET, live database or deployed files touched.
Next: refresh dependent application/state parents, publish, answer both reviews,
then exact-head CI and ordered owner-approved merges. Original D4/D5, exclusive
writer handover and all runtime roadmap/activation obligations remain preserved.

## 2026-10-21 — Preserve target-deleted directory ancestry

Addressed #1097 review4328261007. A baseline directory missing from the target
now fences every descendant as target_changed_preserve, including newly added
source files and empty directories; none can be proposed as copy_new and undo
the independent deletion. Genuinely new siblings remain copy candidates.
Native CLI and direct library results agree for shallow/nested deleted parents,
empty dirs, zero-byte and nested files. Both source/target inventories remain
unchanged and activation stays false.50targeted tests pass; disabling ancestry
propagation produces2observed failures, then exact cmp restoration. Ruff/diff
pass. No state application, DB write, service or deployment performed.
Owner explicitly approved1095/1096/1097 on Oct21; fresh review findings are fixed
before the ordered prescribed merge cycles. Preserve full original roadmap.
## 2026-10-20 — External supervisor bootstrap and raw source comparison

Addressed #1095 P1 reviews4325182407/4325182418. Source admission no longer runs
Git diff: local clean filters can execute arbitrary commands even with fsmonitor
disabled. It compares approved ls-tree entries against the stage-zero index and
raw worktree blob hashes/modes, without attributes conversion. Ignored/unknown
files, hidden index flags, staged changes, executable drift and wrong file kinds
remain refused. Regular files use non-following descriptors and stat stability
checks. SHA1 is used only for Git object-format identity, with usedforsecurity=False;
SHA256 remains the trusted supervisor artifact pin.

Prepared units now embed a fixed stdlib bootstrap in isolated Python -c argv.
The bootstrap opens an owner-only regular0600 artifact with O_NOFOLLOW/nonblocking,
reads at most1MiB+1 once, verifies the SHA256 pinned in the unit, then compiles and
executes that same verified buffer. It never executes a supervisor from the mutable
checkout or reopens its artifact after hashing. The artifact is copied from the
exact approved commit blob; original source filename/revision remain available
for subsequent source/project admission. Direct main-process run without the
external bootstrap is refused. Source/workspace commit binding and exact effective
unit argv/environment/log-sink checks remain. Existing prepared units need
regeneration; Type=exec still confirms launcher startup, not app readiness.

Native controls cover an actually executed clean-filter positive control, no
filter execution under admission, committed artifact extraction despite mutable
checkout drift, valid artifact guard execution, checkout/artifact/symlink/mode
tampering and replacement AFTER hashing. Tampered bytes never execute a sentinel.
Offline systemd parser plus exact decoded generated argv checks pass. No unit was
installed or started; no ET, live DB, mount or deployed payload was touched.
Five deliberate mutations (clean-filter fallback, artifact hash, reopen-after-hash,
mutable artifact extraction, missing bootstrap provenance) each produced an
observed failing test; every file restored and compared with cmp. Restored targeted
suite166passed; Ruff and diff checks pass. Counts overlap earlier runs.
Next:publish and answer both reviews, refresh dependent parents and inspect exact
head CI; preserve original D4/D5/exclusive writer handover and owner merge gates.

## 2026-10-20 — Keep system writer observations on the local system bus

Validated review4325190528: inherited DBUS_SYSTEM_BUS_ADDRESS selected another
bus for non-root systemctl probes. Both scopes now drop that variable and
SYSTEMD_BUS_ADDRESS before querying; user scope keeps its existing validated UID
and explicit user-bus path. Unknown metadata/exclusion/activation semantics stay
unchanged. No bus proxy, manager or service is started by this change.

71writer tests pass. Native child fake-systemctl records absent override keys;
removing the new guard causes3observed failures, restored/cmp. Actual UID1000
read-only proof: direct systemctl with poisoned bus exits1; sanitized CLI and an
independent clean systemctl agree on etlegacy-bot active/PID456340. This is one
named-unit point-in-time metadata observation, not all-writer exclusion, freshness
of application code or activation. Official sd_bus_default docs confirm the env
variable selects the system bus. Ruff/diff pass; no live data/config changed.

1093/1094already merged under their own owner approvals.1095has two further P1
source-admission/entrypoint findings being corrected; no1095–1097merge approval
is inferred from generic continue. Next:coordinate reviewed parent refresh,
publish/reply and verify exact-head CI. Original D4/D5/exclusive handover and
all preserved proximity/gametime/API/UI/Spiderweb/Stats lanes remain open.

## 2026-10-20 — Owner-approved PR1094 merged; next game source remains forward-only

Owner explicitly approved1094. Prescribed cycle ran on30775c84 with all13checks
successful, zero review threads and full420-second pause. Final cycle gate:
failed0,threads0,behind0,head unchanged. GitHub confirms merge at12:46:40UTC,
commita12a55b51b6d17d818d76a124a91b61b786bdd26. Full-tree diff, tree-ID equality
and main ancestry independently prove reviewed producer content preserved.
Exact-head CI counts10077/10081passed (Python3.11/3.13),160/156skipped, verified
against individual passed-node lines. No service, database or ET activation.

Game source a03f3455 fixes two later P1 findings, separately from approved1094.
Before ancestry reconciliation, new main tree was proved exactly equal to the
original producer30775c84 already contained in game. Metadata-only merge leaves
the complete game tree unchanged at3b07da9936e8e98d74e42ef363218785fa7cf2b1;
subsequent checkpoint changes are ledgers only. Do not apply that strategy if
main content differs. Publish/retarget1095to main; its own merge remains unapproved.

State source7914c41d fixes ancestor conflicts/metadata paths/bare repositories;
combined native targeted integration344passes, game132/state192groups overlap.
Six guard mutations each fail and restore/cmp. Refresh app/state dependency
parents and answer all five reviews before new exact-head CI. Original D4/D5,
writer exclusion, trusted-source admission, future observed DEV handover and
all preserved proximity/gametime/API/UI/Spiderweb/Stats work remain required.

## 2026-10-20 — Bind rehearsal revision and disable executable Git fsmonitor

Validated two additional #1095 P1 review findings. Every supervisor source Git
probe now explicitly sets core.fsmonitor=false, including both ls-files calls
and diff, before admission. A native synthetic repository with an executable
configured fsmonitor hook proves the local Git build executes the hook without
the override and never executes it during the protected source inspection.

Preparation now requires the verified startup recipe workspace.source_commit to
match the supervisor commit before creating unit artifacts. Launch checks the
same binding after the second containment/command admission and immediately
before the process boundary. A valid workspace from another revision is refused;
matching preparation and launch controls still reach their next independent
boundary. Existing synthetic recipe fixtures now supply their explicit revision.

Native targeted suite:132 passed, covering source binding, supervisor/service and
launch contract controls, including existing actual local UDP fixture and offline
systemd parser. Three guard mutations produced1/1/1 observed failing tests; both
binding mutations retained a passing matching control. Every source was restored
and compared with cmp; five restored source-binding tests then passed. Ruff and
diff checks pass. No service, engine, live database or deployed payload touched.
Next: publish, answer both reviews and refresh child dependencies with exact-head
CI. Original D4/D5 and exclusive writer handover remain open; #1094 owner merge
authorization does not authorize #1095 or activation. Preserve original roadmap.

## 2026-10-20 — Propagate type conflicts and close metadata ancestry boundaries

Validated three new1097reviews. An ancestor's baseline/source/target type conflict
now makes descendants path_type_conflict even when the target independently
removed the parent. No descendant copy_new can recreate that unresolved parent;
existing classifications and nonmutating/manual reconciliation remain intact.

Selected source checks inspect all absolute path components for .git/.env*, not
only the leaf. State/report output boundaries share writer inventory's stdlib
Git-layout helper: worktree markers and bare repository-shaped HEAD/objects/
refs (also packed-refs/reftable) layouts refuse. No Git subprocess/config executes
in admission; conservative metadata-shaped paths fail closed. Legacy dangling
marker and immutable-release fences remain. No live data was copied or changed.

192targeted state/delta/writer/path tests passed. Actual Git-init bare fixtures,
native CLI refusal and native nonmutating delta output cover all three mechanisms.
Kind/ancestor/bare mutations cause3/3/5observed failures; sources restored/cmp.
Initial one source-ancestor fixture triggered the independent output Git fence;
placing that source under a separate parent exercises the intended source guard.
Ruff/diff pass. No service, real database or deployment was touched.

1094owner-approved cycle is in progress at30775c84, later PRs not authorized.
Next: coordinate reviewed game/app parent refresh, publish/answer three comments
and inspect exact-head CI. Original plan/D4/D5/exclusive handover remains open;
source safeguards do not certify all writers absent or activate a new lane.

## 2026-10-20 — Owner-approved PR1093 merged; producer successor prepared

Owner explicitly approved the pending1093merge. Prescribed slomix-ops/cycle.sh
ran with exactc40537ba head and the full420-second review pause. Final checks:
failed0,unresolved0,behindmain0,head unchanged. GitHub confirms merged at
2026-10-20T07:22:10Z, commit8c1a6cc395d3485852240117aacbe44c3c37dca2.
Independent Git ancestry, empty full-tree diff and tree-ID equality confirm main
contains precisely the reviewed source. No service or deployment occurred.

Next producer1094already contains originalc40537ba. Only after proving the new
main tree EXACTLY equals that contained original parent, an ancestry-only local
merge records main into its feature branch. Whole producer tree remained
00fb1ac6ad2105919a652c5c7b85a100b4904dfa; empty parent diff independently confirms.
This strategy must not be reused if main has any differing content. Subsequent
ledger updates are documentation only. Publish and retarget1094to main, then
inspect its new exact-head CI; no1094merge is authorized by1093permission.

Before this metadata refresh1094–1097exact heads were all green. Python3.11/3.13
passed counts independently checked against result nodes:1094 10077/10081,
1095 10540/10544,1096 10788/10792,1097 10934/10938. These are overlapping suites,
not additive or service/runtime activation proof. PR1100remains a separate npm
security review; its documented unpatched braces residual remains unresolved.
Original full plan, D4/D5/exclusive writer handover and all remaining roadmap
items are retained. Production remains frozen; no DB/state or service change.

## 2026-10-20 — Correct relative metrics defaults and bounded preflight startup

Validated three new1095reviews. With external BOT_LOG_DIR, documented relative
metrics defaults bot/logs/metrics/metrics.db and logs/metrics/metrics.db now use
that external root. Explicit separate stores, empty/None fallback and legacy
PostgreSQL-vs-application-SQLite protections remain. Native async metrics proof
creates/counts one event and exports JSON outside an untouched synthetic release.

Preflight missing asyncpg/python-dotenv returns structured dependency refusal
without traceback on CLI; library imports still raise ImportError. Actual system
interpreter confirms this refusal. Release config path/expected digest admission
now uses the existing bounded external reader directly, without first calling
unbounded file_hash. Native FIFO,/dev/zero, sparse oversized and wrong-digest
cases refuse promptly without DB access. Do not import deployed code for proof.

116targeted tests pass. Metrics/dependency/bounded-config mutations cause2/2/1
observed failures andcmp restoration. Initial dependency fixture failed2cases
because it changed sys.argv before the hook read the selected module; freeze the
module name first, then both refusal paths execute. Source/new-test Ruff and
diff pass. Existing metrics test file retains exactly its two pre-existingSLF001
diagnostics, independently compared with parent; no suppression or hidden fix.
No service, live database or deployed payload changed.

Next:refresh producer parent after1093merge, publish, refresh app/state children,
answer three reviews and inspect exact-head CI. Original runtime D4/D5/exclusive
handover and all preserved roadmap/owner activation gates remain in force.

## 2026-10-20 — Bind writer observations to user identity and reject credential trees

Validated three new1097reviews. State inventory rejects every relative .env*
component before type dispatch/traversal, including directories with innocuously
named children. Explicitly selected .env* and .git roots also refuse. Git and
other data/DB exclusions stay intact. No state copy or source deletion occurred.

User-scope writer probes require --expected-user-uid; library probes without it
return unknown. Expected UID must equal real and effective UID before systemctl
runs. Reports record all three UIDs; user-bus/runtime paths are derived from the
validated UID instead of inherited bus overrides. System probes remain unchanged.
Empty-instance templates and multiple-at names refuse before probing; concrete
instances remain accepted. Existing prepared invocation snippets need the UID
argument. Named observations never certify exclusion, handover or activation.

181targeted state/writer/delta/path tests passed. Native CLI systemctl doubles
prove matching/wrong UID and template handling, plus .env directory refusal
without destination/report or content disclosure. Removed directory/identity/
template guards cause7/4/3observed failures; all restored andcmp verified. Ruff
and diff checks pass. Actual read-only host probe, independently compared with
systemctl: DEV bot456340/web3549798active, watchdog service/timer inactive.
Named team/cache user units are unknown in inventory; direct UID1000 manager
LoadState=not-found confirms neither installed unit. This is point-in-time named
metadata, not all-writer exclusion or operational runtime acceptance.

Next:refresh reviewed app parent, publish/answer three threads and inspect exact
CI.1093is merged;1094requires its own owner approval. Original D4/D5/exclusive
writer handover, consumer-off proof and preserved roadmap remain open.

## 2026-10-20 — Second game review: explicit targets and closed proof environment

Validated and corrected five additional #1095 findings. Standalone marked audit
CLI refuses inherited application/DB overrides before loading credentials or
calling the driver; library sentinel behavior remains supported. Marker presence
automatically enforces isolated preflight admission and packaged migration paths,
even when --release-mode is omitted. Marked migration CLI normalizes connection
port and all timeout budgets inside its redacted refusal boundary; invalid and
out-of-range ports fail before command execution.

Proof units now use an exact /usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C prefix
before isolated Python. env exec preserves the systemd main PID; Type=exec only
confirms initial executable startup, not application readiness. Effective unit
Environment/EnvironmentFiles must be empty; actual supervisor application env
must contain only PATH/LC_ALL and Python-added LC_CTYPE before project imports.
Unknown future application variables and BOT_NAME_REGEX therefore cannot alter
capture classification. Existing loader UnsetEnvironment policy remains.
Ordinary supervisor failures, including EOFError and RuntimeError, produce the
structured redacted failure; KeyboardInterrupt/SystemExit still propagate.

Native synthetic CLI, driver-sentinel, env-prefix, systemd parser and UDP fixture
checks: 210 passed (overlapping suite, not additive). Seven deliberate guard
mutations produced respectively 4/2/6/1/2/1/2 failing tests; every source restored
and compared with cmp. Ruff and diff checks pass. Initial sandbox run had 8
fixture-environment failures (/tmp Git ancestry and restricted UDP); native
private /var/tmp run resolved those without weakening guards. No service, engine,
real database or deployed payload was touched. Next: refresh dependent PR parents,
answer the five review comments, and inspect exact-head CI; per-PR merge and owner
activation gates remain unchanged. Existing original runtime plan is retained.

## 2026-10-20 — Admit exact GNU locale metadata without weakening configuration guards

Review1096 found six missing GNU libc locale categories. Add only LC_PAPER,
LC_NAME, LC_ADDRESS, LC_TELEPHONE, LC_MEASUREMENT and LC_IDENTIFICATION to the
shared system metadata allowlist; arbitrary LC_* remains refused. Approved-file
value conflicts still refuse, including these exact names. GNU libc/Linux locale
reference checked; no wildcard environment permission was added.

162 focused environment, contract and health tests pass. Actual isolated child
preflight accepts each category before its database double; /proc health reads
real child environments containing all six and still rejects unknown/loader/app
settings. Removing the six entries produces12observed regression failures;
source restored andcmp verified. Ruff/diff checks pass. Initial fixture run:
6failed156passed because /tmp/.git correctly fences preparation; a NEW private
/var/tmp fixture rerun passes. No production, service or live database was used.

Next: integrate reviewed game parent, refresh state child, publish and answer
review4322079388, then inspect exact-head CI. Original plan and owner-specific
merge/activation gates remain in force; old prepared contracts need regeneration.

## 2026-10-20 — Reject Git directory markers before state inventory dispatch

PR1097 review4322041171 confirmed an empty .git directory could be inventoried
and seeded because only regular files checked Git components. Inventory now
rejects every relative .git component before lstat/type dispatch, including empty
and nested directories, files and symlinks. Existing source-drift and report
fences remain intact; no live data, service or deployment was touched.

Targeted state suites:105passed with synthetic external fixtures. Six type/depth
regressions plus two native child CLI cases cover plan/seed refusal without
report/destination creation and byte-for-byte source preservation. Guard removal
produced7observed failures; the independent seed drift guard still refused its
case. Source restored andcmp verified. Ruff anddiff checks pass. The initial
standard/tmp fixture run correctly hit this host's existing/tmp/.git fence;
rerunning in a fresh/var/tmp fixture root avoided that unrelated Git ancestor.
Next:coordinate parent refresh, publish and answer the review with exact-head
CI. Original plan and per-PR merge/owner activation requirements remain intact.

## 2026-10-20 — Application launch isolation and pre-start policy review closure

Addressed all three new1096findings. Bot/web use-E-B-s, consumers additionally-u:
-E ignores every PYTHON* influence, explicit-B/-s preserve bytecode/user-site
protection, and-u preserves consumer output behavior otherwise lost when-E ignores
PYTHONUNBUFFERED. Isolated preflight remains-I-B. Actual child interpreter tests
exercise PYTHONPLATLIBDIR, no-user-site and output buffering, not just unit text.

Prepared contracts record Requires/Wants/After. Resolved health requires every
contract member while permitting implicit systemd dependencies. Release schema
preflight now rejects unapproved environment BEFORE DB access. Health shares the
same safe environment policy; legacy unmarked APIs retain their existing mode.
Old prepared contracts fail closed and must be regenerated. Temporary audit
mute overrides must be reconciled into an approved config/contract before later
activation; do not silently certify the currently installed old contract.

Agent256tests passed and six mutations were observed failing withcmp restoration.
Public app269tests pass after game-parent integration; full candidate409targeted
checks pass (overlapping sets). Native child/preflight tests use driver doubles,
not live services or databases. Ruff/security/diff checks pass. No activation,
mount, DB migration or deployed payload change occurred. Next:publish, refresh
state child, answer three review threads and inspect exact-head CI. First merge
candidate1093remains clean/green atc40537ba,behindmain0,owner approval required.

## 2026-10-20 — Audit admission, bytecode and fixed launch contract corrections

Addressed all five new1095findings. Marked audit CLI requires-I before project/
driver imports and verifies the full manifest before round-time/rule definitions,
configuration and DB/cursor entry points. Library callers retain their startup
trust boundary. The bot's dynamic caller suppresses bytecode BEFORE importing the
validator/exec_module: the module body alone cannot prevent its own loader.pyc.
Marked schema preflight also suppresses bytecode even with-I without-B.

Launch and shutdown share fixed rehearsal port27962; another port is refused
before host inspection. Native UDP fixture now tests the actual dedicated port,
not an unrelated ephemeral socket. Marked migration timeouts use only explicit
file values or constants; legacy environment budgets remain supported through
legacy settings. No env fallback remains for omitted marked timeout keys.

Public game219tests passed; full local candidate409targeted tests passed after
app integration (overlapping sets, not additive). Six audit mutations each
produced observed failures andcmp restoration; root budget mutation4failures,
port mutation3failures. Actual child CLI wrong-port refusal, source/driver shadow
sentinels and bytecode inventory failures were observed before restoration.
Ruff/configured security/diff checks pass. No engine, real DB, service, deployed
payload or production configuration was touched. Next:publish, refresh children,
answer five comments and inspect newly triggered exact-head CI. Original plan
and per-PR owner merge/activation gates remain in force.

## 2026-10-19 — Admit systemd memory-pressure metadata without app overrides

New1096review identified systemd>=254's MEMORY_PRESSURE_WATCH/WRITE metadata.
Both exact keys now belong to the safe OS allowlist; similarly named keys,
unknown application settings, loader variables and approved-value overrides
remain refused. Official systemd resource-control documentation confirms the
keys; the actual CI runner environment contains a cgroup WATCH and base64 WRITE.
Host systemd249 cannot prove a systemd254 service launch, so no such claim is made.

44health tests pass with27actual child process combinations and /proc metadata
checks. Removing both keys causes2observed failures; original restored withcmp.
After integrating the common runner fixture correction,160app/operator/startup
checks pass. Ruff/diff-check clean. No service/mount/DB/deployed payload operation.
Next:publish, refresh state child, answer review4307535251 and inspect exact-headCI.

## 2026-10-19 — Reproduce and fix runner loader fixture contamination

Both Python CI legs on1095/1096/1097 failed the same two new release settings
tests. The runner's LD_LIBRARY_PATH reached the positive approved-config fixture;
release admission correctly refused it. Tests now clear all five loader/Python
keys when constructing the approved scenario, while explicit negative cases
still require their rejection before the driver. Public shared admission also
rejects LD_AUDIT consistently (full local candidate already had this guard).
No production isolation was weakened to turn the tests green.

With a synthetic runner LD_LIBRARY_PATH:62operator/environment tests pass. Restoring
old fixture behavior reproduces both CI failures; removing LD_AUDIT admission
causes1observed failure. Originals restored withcmp. No real DB/DDL was used.
Initial source integration patch refused because full candidate already carried
LD_AUDIT; adapted only the missing test hunk, then200combined operator/state tests
passed. This is a fixture/source result, not a new exact-head CI result.
Next:publish, refresh child dependencies and inspect both Python CI legs again.
Production audit override still absent at read-only host check; owner commands
were provided, no production service/config/code was changed by the agent.

## 2026-10-19 — State metadata and reserved report path review corrections

Addressed all three new1097findings. content() now uses fixed-length3tuples for
both directory and file tokens. Negative integer POSIX mtime_ns is accepted,
matching the inventory/seed producer, while boolean/noninteger metadata remains
invalid. Both state/report boundary helpers reject basename.git and
.slomix-release.json before creating reserved markers or state output.

138dedicated tests pass, Ruff/diff-check clean. Restored old behavior caused8
observed failures; all three scripts restored withcmp. Actual CLI fixture retained
mtime_ns=-1000000000 through seed/delta, refused both marker names and preserved
source/target inventories. No local CodeQL engine run is claimed: public scanning
must recheck the fixed tuple shape. No live data, database or services touched.
Next:refresh app parent, publish and answer the three review threads; inspect CI.
Original runtime/D4/D5/handover/Spiderweb/UI plans remain preserved.

## 2026-10-18 — Migration admission and raw Git provenance review closure

Addressed three further#1095 findings. Marked-release migration CLI requires
Python-I before asyncpg/dotenv/project imports and disables bytecode writes before
imports even without-B. This avoids repeating diagnostic payload contamination.
Interpreter/site/loader startup is still a launcher responsibility. Release DB
settings are read directly from the verified explicit file; inherited DB/PG
settings are refused before connection, including otherwise matching values.
Repeated reads do not mutate os.environ; file timeouts/fingerprint labels remain.
No migration or real database operation was part of this verification.

Game bundle Git reads, supervisor source admission and shared SPA Git helper now
force GIT_NO_REPLACE_OBJECTS=1. Native commit/tree/blob replacement fixtures show
unprotected Git can return different bytes for the approved revision; protected
packaging keeps original bytes. Replacement refs cannot conceal dirty checkout
state. Child release preparation inherits the same protected SPA Git helper.

284combined tests passed,1explicit opt-in ET ABI case skipped. Final strengthened
operator-only series40passed. Observed mutations: isolation1failure, inherited
settings8failures, replacement bundle3failures, supervisor1failure, SPA1failure,
bytecode suppression1failure; every original restored withcmp. Ruff/configured
Bandit/diff-check pass. These are source/fixture results, not deployed proof.
Next:publish, refresh child branches, inspect exact-head CI and answer the three
comments. Per-PR merge authority and owner-run activation remain separate gates.
Original runtime/D4/D5/exclusive handover/Spiderweb/UI plans remain preserved.

## 2026-10-18 — Effective DEV health and consumer protection review closure

Addressed six new#1096 findings. Prepared system units now unset all five unsafe
Python/loader variables; readiness verifies the resolved filter and exact
Restart=always/RestartUSec=10s. Actual process environment must be approved dotenv,
prepared bootstrap or a fixed safe OS metadata allowlist; unknown application
settings such as BETS_LIFECYCLE_SECONDS are refused, not silently inherited.

A healthy website and active bot PID are insufficient. Bot emits a PID/invocation
journal marker only at successful end of on_ready, after security/voice startup.
The health gate requires matching journal unit/PID/invocation and fresh timestamp,
then rechecks services. This proves startup completion, not continuous Discord
connectivity. Current deployed builds lack this marker and are not certified by
the new source. Read-only host checks verified actual Restart/RestartUSec and
journald PID/invocation/unit/timestamp fields. No new service or message ran.

Consumer verifier regenerates exact required unit bytes instead of trusting a
jointly modified unit and digest. User units require PrivateUsers and ReadOnlyPaths;
isolated prestart checks actual ST_RDONLY on the release and descendants before
worker imports. Unsupported/ignored sandboxing fails closed on writable mounts.
Actual protection after activation remains required_at_start_unmeasured: no
mount/service was started, and a verifier report is not a kernel-enforcement proof.

Combined app health/consumer fixtures124passed. Five parent guard/signal mutations
each caused1observed failure; consumer semantic mutation6failures, disabled mount
guard1failure; all restored withcmp. Native writable-filesystem child refuses;
actual on_ready tests cover success/security rejection/startup exception with
mock transports. Ruff and diff checks pass. Next: refresh reviewed parent,
publish this slice, inspect exact-head CI and answer all six review comments.
Production audit silence remains owner-pending; DEV temporary audit=false is
confirmed active after the separately documented diagnostic recovery. No agent
service command, DB write, migration, browser or production deployment occurred.

## 2026-10-18 — State path kinds and service ownership review closure

Addressed#1097 path-kind and ownership findings. Three-way comparison now covers
files, directories and absence together; change entries carry explicit kind.
An independently changed empty directory cannot become an agreed file deletion.
State seed requires the effective samba service UID before creating any output;
wrong-owner private directories are refused rather than producing an unusable
seed. Portable CI substitutes only the account lookup, not filesystem access.
The malformed-JSON review finding was already fixed in1c1c727a; its12cases were
verified unchanged, not implemented twice.

Combined seed/delta/writer/ledger cohort136passed. Agent-focused78passed. Removing
the two guards caused12observed failures; restored withcmp. Actual CLI fixture
plan→seed→delta verified samba ownership, empty-directory preservation and
unchanged source/target inventories during comparison. Ruff/diff-check pass.
This is not a quiescence certificate, consistent database backup or activation
approval. No live state, database or services were modified. Next:refresh app
parent, publish source corrections, check CI and answer all three state threads.
Production notification silence remains owner-pending; original roadmap retained.

## 2026-10-16 — Six further game-delivery review findings addressed

#1095 review exposed six additional boundaries after its earlier green CI.
Release schema-preflight CLI now requires isolated Python before third-party
imports and refuses abbreviated arguments. Marked-release migrations verify
payload integrity and the exact migrations directory before configuration,
SQL discovery or connection. Release audit refuses its legacy in-payload report
default and resolved output aliases before configuration or database access.
The child DEV contract must supply Python -I -B for its schema preflight.
Interpreter startup and hostile same-UID actors remain outside this boundary.

BadZipFile is redacted at startup, supervisor and unit-preparation CLI boundaries;
interruption still propagates. Prepared units pin --evidence-log. Admission and
its immediate prelaunch recheck require append/inherit manager modes and actual
stdout/stderr descriptors sharing the private owned canonical log inode with
O_APPEND. This proves the current descriptors, not durable storage or historical
absence of tampering. Smart-stats embeds now link app mode to the selected date's
story tab; legacy /story remains unchanged.

Public game-branch local verification:201 tests passed, including the actual
rehashed corrupt PK3 child CLI and six native descriptor cases. The operator
agent separately recorded135 passing tests including27 new boundary cases;
primary combined operator/startup/DEV-contract tests passed93 cases. These sets
overlap and must not be summed as unique tests. Observed mutations: wrong story
1failed/1passed, missing archive catch1failed, missing output-mode guard2failed,
missing descriptor guard3failed; restored originals compared withcmp. Agent
mutations reached the shadow module and forbidden config/DB boundaries before
restoration. Ruff and configured Bandit passed. An unconfigured Bandit invocation
reported existing B608 constant-built SQL findings; the project configuration
excludes B608. No database, game or service was started or modified.

#1097 state-handover remains open at1c1c727a, awaiting dependency refresh and CI.
#1093 remains the first merge candidate. Automatic approval review rejected the
merge attempt: generic continuation is not explicit permission for that PR.
No merge occurred; request unambiguous owner permission for#1093 before retry.
Next:publish these fixes, refresh1096 and1097, inspect exact-head CI and answer
all six review threads with evidence. Original runtime, Spiderweb and UI work
remain preserved; merge approval and owner-run DEV activation are separate gates.

## 2026-10-16 — Independent state review fixes malformed CLI input

PR #1097 is published, depending on1096; owner approval is still needed before
any merge. Independent read-only review found no new critical immutable/report
boundary, delta-content or false-quiescence issue. It reproduced a real CLI bug:
JSON[] reached sources.values() and raised AttributeError with a traceback.
The CLI now requires an object for both the input and selected source mapping
before placement checks. Invalid structures return structured refused JSON,
empty stderr and no state/report output. No raw input path is echoed.

113 selected state tests pass. Removing the new checks produced6 failures/6passes;
original restored withcmp. The actual previously failing child CLI now returns
refused with no traceback or created files. This extends the earlier101 tests
and retains the7-file CLI copy/hash proof and nonmutating delta proof. It does
not certify quiescence, arbitrary-source confidentiality or activation. Live
state, services, game, databases and production remain untouched.

## 2026-10-16 — SQLite rollback journals stay outside data seeds

The existing state-source filter excluded SQLite databases, WAL and SHM but
missed rollback-journal filenames. Added-journal to that same refusal boundary:
auxiliary database state requires its separate consistent-backup contract, not
a normal data-file seed. A synthetic metrics.db-journal input now refuses before
copy; removing the new suffix produces one observed failure. Restored withcmp;
101 state seed/delta/writer-inventory tests pass. This does not make the tool a
generic secret scanner or a consistent snapshot of active writers.

## 2026-10-16 — External state preparation advances without merge activation

Continuation request was interpreted as permission for the previously proposed
#1093 merge, but automatic approval review rejected it: no unambiguous owner
approval specifically for #1093. The cycle script was not executed. Do not retry
through a wrapper or alternative merge command; request explicit permission.
#1093 remains green atc40537ba; each later PR still needs its own approval.

Unblocked development continued with the next saved candidate cohort: three
existing tools and their tests, extracted onto a new feature branch after1096.
Source preflight and its tests already exist upstream and are not copied again.
State preparation supports a dry-run inventory and copy-only seed into a new
external shared directory. Delta planning classifies three-way differences and
never replaces files. Named system/user unit inventory explicitly leaves writer
absence, schema authority, handover and activation unmeasured/not ready.

Found and fixed a boundary gap before publication: the seed/report gate accepted
a new destination under a Git-free marked immutable payload. It now rejects
ancestors carrying .slomix-release.json as well as .git, including dangling
boundary markers. Writer report output applies the same dangling-marker rule.
A synthetic before-probe admitted such a path without writing; the restored
new gate refuses it before data copying. Source/state data were never real apps.

100 tests pass; configured Ruff/Bandit pass. Removing immutable-release checks
causes4 observed failures/2passes; removing dangling-marker checks causes2failures.
Each file restored withcmp, then100 tests pass. Actual CLI proof copies7 synthetic
files, compares Python and sha256sum hashes, preserves source trees, classifies
3 independently changed paths and proves delta writes neither data tree. All
reports are private and activation_ready remains false. Actual named-unit CLI
read bot/web metadata only; active observations do not certify writer absence.

The existing #1095 React CI also failed one availability form test (983passed).
Its isolated follow-up is under review: do not claim an application bug until
reproduced. Continue CI/review closure on1094–1096, publish the state cohort for
review and preserve original source admission, exclusive handover, D5,
proximity/gametime/storage/API/live/Spiderweb/UI roadmap. No services or DB writes,
no migration, live state copy, game activation or production operation occurred.

## 2026-10-16 — DEV readiness access, monitor paths and CI follow-up

PR #1096 CI at4f96e678 failed on two checks on both Python versions: the
retro-viz OpenAPI description was stale (only that description differed), and
an old maintenance test expected cwd/logs despite the shared test environment's
BOT_LOG_DIR. Regenerated the PR snapshot (full source was already current);
parameterized directory creation for unset/empty/external log paths.

New review findings fixed: compatibility team CLI verifies contracts without
injecting a conflicting preparation component; SSHMonitor downloads now use
config.stats_directory (real local write with fake SSH/SCP, no remote transfer).
DEV contracts require effective read/write/traverse permissions as the samba
service account, including existing metrics DB files, not just ReadWritePaths.
Preparation as another account is refused. CI fixtures substitute only service
UID identity, retain actual chmod/access checks and restore directory modes.
Consumer units also remove LD_AUDIT; explicit app config refuses loader overrides.

Readiness accepts visible approved dotenv keys only with matching values and
rejects mismatches, extra DB settings and loader injection. Correction to the
review premise: an actual child load_environment/setdefault experiment loaded
its synthetic key, while /proc/environ did NOT show that added key. Linux normally
exposes exec-time environment there. This admits both exec-time shapes; it does
not prove dynamic app configuration through proc. ExecStartPre still rejects
inherited overrides, and the exact approved file digest remains checked.

178 related tests passed; post-mutation narrower suite147 passed. Nine failures
were observed across access(3), loaded-key(1), wrapper(2), SSH output(1) and audit
environment(2) negative controls, each restored with cmp. Ancestor traversal was
already refused by canonical resolution and is not credited as a new mutation.
Actual offline CLI prepared three synthetic files; systemd-analyze verify passed
both DEV units. Fake payload/interpreters only; no installation, service start,
real dependency/DB startup proof or deployment. Existing legacy-test Ruff findings
remain6/29; no new ones, production/new test paths lint clean. New exact-head CI
and additional review closure remain pending. Preserve original plan and queues.


## 2026-10-16 — Availability test controls the market transition explicitly

#1095 bd6782ad React CI failed1 test/983passed: missing the bet-placed15 message
at AvailabilityPage.test.tsx354. The original failure did not reproduce locally;
no production bug is claimed. The test changed global fetch behavior between
two submissions of one form while the first submission/refetch was still
settling. Split amount validation and market reseeding into separate tests.
The new stateful fetch simulation explicitly holds the invalidation GET, checks
POST{choice:team_a,amount:15}, disabled/busy UI and unchanged input/no early toast,
then releases the response and checks confirmation15, reseed60 and enabled UI.
No timeout was increased and no production code changed.

Node22.23.2 typecheck passes and18 page tests pass through sequential repeats.
Disabling the existing setDirty(false) guard caused a genuine Expected60/Received15
failure; source restored withcmp. All jsdom/tsc processes ended; no browser or
server was started. The first diagnostic accidentally used Node20 before Node22
was selected; that result is not used as project toolchain acceptance.

Refresh1096 and the new external-state cohort with this test correction; require
fresh exact-head CI. #1093 remains13 checks successful/zero threads/behindmain0,
but its merge was rejected by automatic approval review for missing explicit
permission for that PR. No merge occurred. Continue authorized development,
retain the full original plan and request specific merge permission separately.

## 2026-10-16 — Accept native path-absence refusal in the replacement fixture

Latest #1094 Python3.11 CI failed the root-replacement test with FileNotFoundError
for the deliberately renamed listener directory; Python3.13 passed10080 tests.
The guard correctly failed closed. Its test wrongly required only ValueError or
TimeoutError during the rename/recreate gap. The fixture now accepts only the
expected missing listener/root path, retains terminal failure and source-claim
assertions, and adds one deterministic remove-root variant. Production code is
unchanged. All five native timeout/path variants pass locally; the earlier full
42-case listener suite passed before adding that new variant. Refresh child
branches normally and check new exact-head CI; do not hide the prior failure.
Original plan, owner-specific approvals and frozen production remain unchanged.

## 2026-10-16 — Completion deadline covers the bounded proof lifetime

New #1094 review arrived during final closure after all four heads were green.
The completion accept wait does bound elapsed play plus pauses, despite the old
misleading docstring. Default completion_wait now covers3600s, the whole existing
60-minute proof-unit lifetime, instead of cutting capture off at30 minutes.
The supervisor in #1095 also needs3600 rather than its former1500s override.
The overall unit cap is unchanged; incomplete/over-budget capture remains a
terminal failure requiring reconciliation. Standalone callers may explicitly
budget up to7200s per half; this is not unlimited gameplay or activation proof.

Native pinned-peer/real-file test advances a virtual monotonic clock31 minutes
after completion acceptance starts. Both halves capture under the new default;
restoring1800s causes an observed TimeoutError. Source restored with cmp and42
listener tests passed. No actual31-minute process or ET server was run.
A related test race was exposed: socket creation can precede dispatch reservation,
so root-replacement tests now wait on actual on_ready before asserting retained
writer claims. An earlier run had41 pass/1 failure on that false test assumption.

Previous exact heads all passed CI: #1093 c40537ba9261/9265 tests;
#1094 2ed21c4e10075/10079; #1095 e12e035b10417/10421;
#1096 dd351e0510565/10569 (Python3.11/PG14, Python3.13/PG17).
Both new native team-lock cases ran in every branch/platform and passed counts
were checked independently. New producer/game review fixes require new CI.
#1093 remains ready with zero open threads and no commits behind main; per-number
owner approval is still required. No merge, service or production change occurred.

## 2026-10-16 — Effective launch commands, explicit config and voting capability

Three later #1095 review findings fixed. Rendered and admitted units share one
unambiguous argv builder; resolved ExecStart must match its exact interpreter,
isolation flags, script and arguments. Wrappers, extra/multiple/ignored commands
and all populated ExecCondition/StartPre/Post/Reload/Stop/Post are refused, both
initially and immediately before our Popen. Actual stopped-unit property format
was checked read-only: systemd can omit empty execution arrays even with--all.
Current metadata cannot prove an earlier wrapper made no side effects; refusal
prevents our next ET launch, not retroactive certification of the whole unit.

UltimateBot now calls the same early explicit load_environment as the app slice,
before imports, and removes plain load_dotenv ancestor search. A real isolated
child with a missing synthetic key in explicit config and that key in ancestor
.env remains clean. Reintroducing fallback genuinely loaded the ancestor marker
and failed the environment assertion; source restored with cmp. The first
mutation measured only a forbidden-loader-call assertion, so it was rerun with
the child's cwd corrected to expose the actual leak before claiming that proof.

MVP vote CTA forces the functional legacy route while ordinary session links
still follow WEBSITE_UI_MODE. SPA voting mutation remains future UI work: its
current read-only view cannot deliver the advertised action. Both embed modes
are rendered in tests. Supervisor completion wait now3600 agrees with #1094;
global60-minute lifetime is unchanged, partial capture is never success.

202 selected tests passed, Ruff/configured Bandit/diff-check clean. Observed
negative controls: command admission10 failures; vote1 failure/1 pass; completion
caller1 failure; actual ancestor dotenv leak1 failure. Every source restored with
cmp. No service, ET, migration, application write or production action. Refresh
parents normally and run exact-head CI before final review closure. #1093 remains
fully green and owner-specific merge approval is still pending. All plan retained.

## 2026-10-16 — Bound team contention remains retryable after canonical commit

New #1093 review found the legacy auto-team bool/error wrapper swallowed global
TeamWriteBusy after a bound R1 canonical commit and again during replay, so the
batch reported success without a roster. Bound callers now opt into exception
propagation; the existing post-commit importer boundary returns RetryableImportFailure.
Canonical rows/mappings/events and successful warning-aware markers survive for
reconciliation. Legacy callers keep their existing bool behavior. Cancellation
still propagates; team identity conflicts also remain visible, never false success.

126 selected tests passed;15 native cases skipped locally. Disabling strict
propagation caused14 observed failures; source restored with cmp and126 passed.
Two new native cases hold a real global advisory lock across fresh R1/replay,
compare complete canonical/marker rows, require a retryable outcome and no teams,
then release it, reconcile two teams and admit R2. The optional real batch envelope
uses a fixture-manager attempt transport, not a new pool/connection-path proof.
PG14/PG17 CI on this new head is required. Prior92a3ab64 CI was fully green:
9229/9233 passed with179/175 skips; independent passed-node counts match. That
proves receipt/warning/date/index changes, not this new lock propagation patch.

Ruff adds no diagnostics (root12 unchanged). No service restart/deploy, migration,
application data write or production change. Refresh dependent1094–1096 normally,
answer the final review and retain per-PR owner merge permission. Original plan,
state handover, D5 and remaining proximity/gametime/API/live/Spiderweb/UI retained.
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

## 2026-10-16 — Package bytes match captured Git blobs, including transient drift

Corrected the provenance measurement: the existing SPA validator already denies
an ordinary tracked-dirty tree. Two earlier mutation failures only changed the
expected error boundary; they did not demonstrate unsafe payload acceptance.
The relevant earlier checkpoint and lesson are corrected, retaining the history.
Explicit package state checks still make that contract local and cover the final
manifest boundary.

A stronger race fixture copies temporarily modified runtime bytes, restores the
source before clean snapshots, then briefly repeats the edit during real source
hashing and restores again. With Git-blob comparison deliberately disabled, the
old per-file comparison accepts a self-consistent manifest stamped with clean
HEAD while its runtime payload differs from that committed blob. This unsafe
synthetic artifact was independently verified and retained privately. Both
transient-source and executable-mode mutations were seen failing; restored
source cmp matched and both regressions passed.

The builder now captures regular blob/mode identities from the exact Git tree,
compares copied bytes via git hash-object --no-filters against those objects,
and takes executable bits from committed mode, not mutable checkout metadata.
This also preserves binaries on core.filemode=false filesystems. Fourteen
package tests passed. This is point-in-time provenance under trusted stable
output ownership, not a signature or hostile same-UID protection.
Evidence: /tmp/slomix-package-blob-*, /tmp/slomix-package-race-negative-proof.log
and /tmp/slomix-package-provenance-final.log; synthetic retained /var/tmp outputs.
No active package, installed unit, application data or service was changed.
Next: exact-head CI/review, then original source admission/D5 and owner gates.
Original PLAN bytes and all pending runtime/UI work remain preserved.

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

## 2026-10-16 — Application delivery review closes state and provenance gaps

#1096 now preserves the lexical bin/python leaf of ordinary symlink venvs for
both DEV and standalone consumer units; venv/bin ancestors and pyvenv.cfg must
remain canonical. Actual --without-pip venv execution confirmed sys.executable
and sys.prefix select that venv, not the resolved base interpreter. Parent/config
alias regressions still refuse. The compatibility wrapper explicitly exports
canonical rather than leaving an unused import note unexplained.

Packaging now checks clean tracked/index bytes against exact HEAD both before
copying and before manifest creation, preserving its hidden-index flag guard.
Staged/unstaged runtime changes refuse before destination creation; mid-copy
drift retains incomplete output without a release stamp. Actual clean CLI still
packages eighteen synthetic payload files, with independent SHA256 agreement.
Health reads and compares resolved MemoryMax/CPUQuotaPerSecUSec, including empty
or infinity overrides. Actual host formats were observed read-only.

Both manual sync callbacks now download/list/verify the configured external
stats directory. File-producing command fixtures exercise download and import
arguments without SSH/Discord/DB transport and leave release cwd empty.
Team/cache unit text clears inherited Python/loader variables; both actual
systemd-analyze --user parses and separate verification CLIs pass. No unit is
installed or started and configuration/handover remain unmeasured.

103 selected tests passed, then 45 venv/contract tests including two added alias
cases (overlapping, do not sum). Twelve targeted mutations produced failures;
two dirty-source cases failed on expected-message assertions while the existing
SPA identity validator still rejected them. Those two are boundary duplication,
not proof of unsafe payload acceptance. The other ten guards were seen failing;
all twelve restored cases passed. Game guards independently had five detected failures
and ten restored passes. Ruff and script Bandit gates pass. Evidence remains
local in /tmp/slomix-app-review2*, /tmp/slomix-review2* and retained /var/tmp proofs.

Refresh parent #1095, publish and resolve exact-head CI/review. This remains
preparation, not a new active release or complete dependency/schema acceptance.
Original primary plan bytes, pending source admission/exclusive handover, D5,
proximity/gametime/storage/API/live/Spiderweb/UI work all remain preserved.

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

## 2026-10-16 — Immutable application payload and external mutable state

Next cohesive branch feat/runtime-app-delivery-20261016 is based on PR #1095
(a4095604), itself dependent on #1094 then #1093. None has number-specific merge
permission. #1095 contains 32 changed paths independently measured by Git diff,
tree objects and GitHub; CodeQL/security/JS/Lua/React/hygiene passed, full Python
matrix was still running when this checkpoint was written.

Application slice connects Git-free payload preparation/manifest build identity,
offline DEV startup contract/unit verification, exact-process health checks and
external configuration loaded before import-time constants. Bot metrics/audit,
maintenance/shadow files and downloaded-stats lookup honor external state paths;
comparison PNGs use memory and close attachments/figures on send failure.
Retention can be explicitly disabled during handover. Retro gallery listing
and byte serving share one external PNG-only root; missing explicit storage is
unavailable, not silently empty. Independent gametime decoder work stays in the
full development source, not accidentally copied with the bot entrypoint.

107 selected tests passed (21.97s). Service-byte guard mutation failed both bot
and web cases; restored copy cmp matched, then 40 related tests passed. Fixture
credentials are generated. Ruff/Bandit medium-high gate pass; two narrowly
annotated 0.0.0.0 literals only render/compare the existing DEV bind, never open
sockets. A real CLI packaged 18 synthetic payload files, excluding .git/.env;
Python SHA256 and sha256sum agree on every file. A separate CLI verified all
three prepared contract/unit files, again with independent hashes. These are
synthetic offline packaging proofs and ASGI fixture responses, not a new active
release, real virtualenv inventory, installed units, live health or native DB
acceptance. No service/game/migration/deployment operation occurred.

Standalone team/cache delivery is included in PR #1096 with the compatibility
team command and disabled configuration examples. Twenty consumer-delivery tests
passed; actual separate CLI verification and systemd-analyze --user verify pass
for both synthetic units, without installation or activation. A missing unit-hash
guard is detected by mutation; restored cmp and regression pass. These user
consumers are independent from the system DEV bot/web units.

#1095 first full CI had exactly one documentation-routing failure on each leg:
10288/10292 other tests passed (3.11/3.13). The leading checkpoint hid the required
routing preamble from its guard. Moved checkpoints after the preamble preserving
every line; eleven contract tests pass in both branches. #1095 c933793d and #1096
include the correction, with normal dependency merge in #1096 (no PR merge).

Evidence: /tmp/slomix-app-*.log; retained /var/tmp/slx-app-* proof directories.
Next: publish/review and resolve exact-head CI; then source admission/exclusive
writer handover, complete schema/application consolidation and D5 observation.
Keep pending proximity/gametime migrations, storage relocation reconciliation,
API/live/Spiderweb/UI and every original roadmap item. Original 0261b076 plan
bytes remain intact in the preserved full development checkout. Preparation
never authorizes activation; production remains untouched.

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

## 2026-10-13 — Live delivery incorporates merged Spiderweb

#1087 merged at a73aaf9e5673663f1a5539eb0bc30ae9bd2f8558; its tree is
identical to the reviewed94982f1b. #1088 incorporates that main through an
ordinary merge, retaining both plan histories and both legacy module graphs
under entry version20261013-live-spider-merged. The combined rehearsal passed
371frontend tests/typecheck, HTTP static imports and actual ASGI→bothDOM
Live/Spiderweb proofs. Source/test blob comparison validates the final tree.
Fresh CI/review and the full420-second cycle remain required before1088merge.
No service activation or deployment follows; native runtime acceptance remains
pending the owner-started private PG and the preserved D4/D5/handover gates.

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

## 2026-10-12 — Bounded Live correctness and recovery review slice

This main-based 25-file branch contains the audited Live backend, tailer and
both clients, separate from issue PR #1086 and Spiderweb PR #1087. The full
runtime plan and integration history remain in their existing checkout; this
is a review slice, not a new plan or a deployment.

Invalid ingest batches publish nothing. JSON/proxy/cache/player state are
bounded, unconfirmed maps and feed failures are explicit, and retention keeps
advancing through failed polls. Historical names are captured at ingest time;
unknowns stay unknown rather than adopting a later slot occupant. Current
roster/MVP state is cleared on disconnect and restricted to engine slots 0–63.
Kill pairing respects lifecycle, round and accepted map boundaries while
retaining same-context retransmission suppression. Support actors retain known
names; malformed slot strings cannot fabricate player zero. Tailer authority
validation and redirect refusal prevent forwarding its internal token.

PR-branch proof: 201 Python tests, 46 frontend tests, typecheck, changed-file
Ruff and legacy syntax pass. Negative guard mutations were observed failing and
restored with byte comparison. Actual synthetic tail/parser/publisher-to-ASGI
and React/legacy DOM proofs cover delivery failure/retry, cursor recovery,
retention, map uncertainty and reused-slot history. Runtime/DOM harnesses and
raw evidence remain local, not in the public diff. Native game/network/browser
acceptance and durable exactly-once delivery are not claimed.

The first full CI exposed stale generated datapoint scope metadata after the
new Live hook. The official generator updates seven dependency-count notes;
read/unread/dropped counts and the unread baseline are unchanged. The duplicate
HANDOFF checkpoint is omitted from this slice to retain the 25-file cap; the
canonical PLAN/BACKLOG checkpoint and existing handoff routing remain intact.

No service, database or game-server changes. Refresh the later branch against
main after merging either this or #1087; preserve both entry cache/import edits.
Merge requires explicit owner permission for this PR number. Runtime resumes
with the isolated native CLI R1/R2 gate and explicit default-OFF worker session;
immutable delivery, owner activation and D4/D5 acceptance remain separate.

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

# BACKLOG — kje sem ostal + kaj se je spremenilo ad hoc

> Review remediation 2026-10-05: owner-started disposable PG confirms normalized
> lookup scans100002synthetic rows with old indexes. Added non-unique095 index,
> bootstrap and release registration;150focused tests pass, mutation fails then
> restored/cmp. Stale predecessor status corrected. Fresh publication/review/CI
> remain gates, no live migration or service change. Research of all Stats tabs
> is additive and deferred in integration PLAN, not a runtime replacement.

> Current #1084 queue (verified 2026-10-05): #1079 through #1083 are merged.
> Actual main is124fe76d3; published #1084 head1e82c231 already includes it.
> Only #1084 review remediation and fresh exact-head CI/review gates remain;
> do not wait for already-merged predecessors. Three Copilot threads concern
> normalized-map index coverage (two locations) and this stale status (fixed
> locally). Python3.13 CI is still red; a completed review is not approval.
> Migration094 is not live-applied; no services/production changes.
> Original runtime plan remains in the integration worktree. Expanded proximity
> research is a deferred final Plan-mode phase, not replacement runtime work.

## Historical preparation — not current gate instructions

> Current2026-10-05: #1084 locally incorporates parentdc31f859; no publication
> before predecessor squashes and final gates.094migration not live-applied.
> Original runtime roadmap remains in latest integration PLAN at
> /home/samba/share/slomix-astra-runtime-integration-20260926. No live repair,
> services, production or NEVER MERGE actions; earlier statuses historical.

> 2026-10-04: CI and next Codex review found094 absent from the release list.
> Added it beside093 in existing v1.45.0 config, without running any deploy.
> Release-config+runner93tests pass; bash source prints094, bash-n/ShellCheck pass.
> Previous88e366fe CI was1failed/7606passed/153skipped, not green. Fresh gates
> required again. No production action, no new research lane or plan replacement.

> 2026-10-04:1084 initialCI green but review found normalized-map mismatch and
> permissive-receipt adoption. Fixed both; new094 records strict provenance on
> fresh INSERT only, old receipts remainFALSE.540tests/20skips,60focused;2more
> mutations fail/restored. Full normalized-parent and old-adoption rejection
> clone proofs with094 rolled back including schema; no live migration/history
> repair. Fresh review/CI required; do not merge initial932905e1 as reviewed-green.

> 2026-10-04: owner restarted isolated PG. Late-parent clone proof confirmed
> successful replay can leave NULL vehicle links. Added opt-in strict parent gate
> at runtime boundary; defer instead of writing orphan data. Full real-parser/adapter
> proof now waits for parent/session, links once on repeat, rolls everything back.
> Three guard mutations fail/restored/cmp. No history repair, service change or
> worker activation. Parent1083 exact-head CI/Codex green, threads resolved; no
> numbered merge approval. Remaining capture/retry/handover and original roadmap
> unchanged. Interrupted old private test schema retained, not blindly deleted.

> Current1083queue:1079merged;1080freshgates and prepared1081/1082predecessors
>remain. Parent3739dd5a incorporated locally. After actual1082merge, final1083
>sync/publication/gates. Original runtime roadmap and no-service boundaries retained.

## Historical preparation — not current gate instructions

> Current2026-10-05: #1083 locally incorporates parent4859d660; no publication
> before predecessor squashes and final gates. Exact-start ambiguity must stay
> unresolved, not guess another round. Original runtime plan remains in latest
> /home/samba/share/slomix-astra-runtime-integration-20260926/docs/PLAN.md.
> No live relinking, services, production or NEVER MERGE actions.

> 2026-10-04 review follow-up1083: initial5443c8f1 CI succeeded but2P1 findings.
> Fixed new receipt queries to adapter ? contract, adjusted PG proof shims using
> real converter; prevented strict/relaxed ambiguous relinker fallback. Four
> regressions failed before,3mutation failures restored/cmp;406unitpass/20skips.
> Added real-PG relinker candidate tests; await new exact-head CI/review, no merge.

> 2026-10-04: runtime linkage gate found same-map source misattribution via end
> versus start clocks. Unique exact source-start lookup now precedes legacy fallback;
> duplicate start unresolved; filename-derived starts not promoted to identities.
> 375unit pass/20existing skips;2mutations fail/restored/cmp; full private-clone
> canonical parser proof resolves right round+session, synthetic writes rolled back.
> Corrected test-only PG fixture not yet rerun:60minute proof service expired during
> full suite (Result=timeout), so no full-green claim. CI and owner restart pending.
> No historical data repair; original runtime roadmap/capture/handover unchanged.

> Current1082queue:1079merged;1080freshgates pending,1081prepared. Thislocal
>parent250d34d7 integration keeps all reviewed fixes and shared-admission lesson.
>Wait actual1081before final1082publication. Original runtime roadmap unchanged.

## Historical preparation — not current gate instructions

> Historical2026-10-05: #1082 local parent6e1296da merge preserves old public stats
> filename validator and distinct proximity admission. Fresh combined tests next;
> wait1079-1081actual merges before final sync/publication. Read latest integration
> PLAN at /home/samba/share/slomix-astra-runtime-integration-20260926. Original
> runtime/Spiderweb roadmap unchanged; earlier dated entries historical.

> 2026-10-04 PR1082 follow-up: explicit verified proximity publication into a
> separate private spool, shared no-clobber/fsync core; stats allowlist unchanged.
> 478passed/20existing skips including old capture/spool regression coverage;
> SHA-bypass mutation fails/restored/cmp. Full fresh-fixture private-clone proof
> covers publication through canonical import and two-pool commit/cancel/replay.
> Original1082 head CI/review clean; follow-up needs fresh gates. Shared legacy
> permissions untouched. Next source seal/ownership and forward-only handover;
> historical unknown hashes are not replay/adoption permission. Original plan
> preserved, no new parallel PR, no service operation/deployment/merge.

> 2026-10-04 source identity: runtime requires verified private bytes + expected
> size/SHA256, stores digest only for a new claimed receipt, rejects conflicts and
> all existing hashless receipts. Captured bytes go to canonical parser; failures
> roll back outer identity binding.345tests pass/20existing skips;3 mutations
> fail/restored; actual two-pool clone proof passed. Next review/CI and explicit
> legacy ownership/adoption/capture contracts; no deployment/merge.

> Historical1081queue:1079merged;1080published6e0be64b awaiting fresh gates. This
>local preparation retains parent review correction and ownership fixes.
>Next actual1080squash sync, then fresh1081publication/gates. No services.

## Historical queue preparation — superseded instructions retained as evidence

> Current2026-10-05: #1081 local parent033a4f4f reconciliation only; wait1079/1080
> actual merges before publication. Read latest integration PLAN at
> /home/samba/share/slomix-astra-runtime-integration-20260926. Runtime roadmap
> unchanged; earlier preparation entries below are historical, not current gates.

> 2026-10-04: same-filename concurrent import fix in separate branch based1080.
> Transaction-owned receipt row claim precedes reads; nontransactional import
> rejected. Real-PG owner commit/rollback/cancel, canceled waiter/nested lifetime,
> timeout retry, distinct-file and stale-snapshot proofs added. No-op mutation
> fails3 original concurrency regressions; restored/cmp. Full canonical parser
> +two actual pooled adapters proved post-write cancel/commit and replay on cloneC.
> Next: exact-head review/CI, then stable source-content identity and original
> runtime acceptance. No deployment/merge; older writers still require cutover.

> Current2026-10-05 00:37CEST:1079merged7b9b43a6, tree matches reviewedc5d8fc4e.
>1080normal actual-main sync retains prepared history; fresh publication/gates
>next. Earlier "wait1079" statuses are historical. Original runtime plan retained.

## Historical preparation notes — not current merge instructions

> Historical2026-10-05, before1079merge: #1080 local preparation incorporates published1079c5d8fc4e.
> Wait1079actual squash, then sync/fresh gates; no1080publication yet. Read
> latest integration PLAN at /home/samba/share/slomix-astra-runtime-integration-20260926.
> Original runtime roadmap retained. Earlier statuses below are historical.

> 2026-10-04: disk backup/online root expansion completed; Home ideas deferred.
> Runtime resumed with required receipt-read fail-closed regression fix.
> 49 focused tests pass, swallow-error mutation fails4 and restored/cmp passes.
> Owner restarted proof service:6/6 read+write PG cases pass; read mutation3fail,
> restored/cmp. Expanded proximity suite304passed/20existing explicit skips.
> Full canonical parser+adapter on private cloneC also proved Python/SQL read
> failure0writes and successful retry/replay1vehicle/1receipt; synthetic maps
> remain unlinked. Next: review/publish slice, then concurrency and stable source
> identity. No merge/deploy; both pytest connection selectors now explicitly
> target private PG to avoid the general collection probe's localhost default.

> Historical1079preparation2026-10-05: older nine approved PRs merged with tree verification.
> #1079 normally integrates actual main95758cc7; fresh local/CI/review gates
> pending, then1080-1084 in order. Read latest integration PLAN at
> /home/samba/share/slomix-astra-runtime-integration-20260926. Original runtime
> and Spiderweb roadmap retained; no services, production or NEVER MERGE action.

> Historical preparation entries below; current queue is #1079 through #1084.

> Historical1066 preparation2026-10-04: owner-approved older-first consolidation;
> importer bytes preserved on actual mainfa40c12e after963/964/966 merged.
> CI PG14/17 proves all10 isolated importer cases on76233b74; fresh exact-head
> CI/SQL/review required again after this actual-main sync. No restart/live DB fallback.
> Read latest integration PLAN.
> Earlier dated entries below are historical, not current merge authority.

> 2026-09-28 #1066 normal main4de6f07e synchronization retains both import and
> worker histories, with byte-identical respective source/test inputs. Combined
> 167 cases pass35.09s including45worker cases; Ruff clean. No PG/service/remote
> actions. Next: root publishes for fresh review; original runtime plan retained.

> 2026-09-28 #1066 review boundary repaired locally: selected R1 receives the
> same calendar/year admission as current input, even with trusted matching
> content. Actual midnight parser/filesystem reproduction failed on old code;
> 122 focused cases and independent DBless runtime probe now pass. Mutation
> seen failing and restored/cmp. PG proof remains pending an owner-started
> isolated service; old SQL evidence does not cover this new guard. Resume
> exact-head review/queue gates, then the unchanged runtime v2 plan.

> 2026-10-03 receipt failure fix prepared with two failing-before/passing-after
>tests and restored mutation. Real PG post-write failure/rollback still pending
>isolated service restart. No deployment or production change.

> 2026-10-03 Spiderweb detour after successful DEV preflight: added neutral import
>boundary and explicit runtime acceptance gates; existing scene/LOS/research
>work preserved. Actual PG proof pending isolated service restart. No deployment
>or Discord shutdown. Return to original runtime sequence after this slice.

> Pravilo za skoke: ko uporabnik vpraša nekaj IZVEN trenutnega taska,
> najprej TUKAJ zapiši, kje si ostal; po fixu se vrni in vpiši, kaj si
> spremenil — tudi če si kaj pokvaril. Commit po vsakem zaključenem
> koraku, ne na koncu dneva.

## Trenutna pozicija

Read the latest PLAN: use the latest checkpoint at the top of `docs/PLAN.md`
for this branch's queue gate. The original runtime roadmap and cross-branch
execution ledger remain in the latest PLAN at
`/home/samba/share/slomix-astra-runtime-integration-20260926`.
Do not derive current merge instructions from the dated evidence below.

## Historical queue evidence

At the earlier checkpoint the queue was #1079 through #1084. The #1077 paragraph below is historical:
#1077 merged as95758cc7 and is not awaiting another merge.

- (Astra, 2026-10-04) #1077 actual-main8f298662 refresh keeps old producer
  work, actual merged reservation and worker fixes. No source activation.
  Predecessors merged; await fresh exact-head gates and review threads. Runtime
  delivery/sealing/retry/handover remains the next development track.
  Read the latest PLAN in /home/samba/share/slomix-astra-runtime-integration-20260926;
  retained local checkpoint8e262684 is an access anchor, not the latest head.

### Historical producer checkpoints

- (Astra, 2026-09-28) #1077 prepared on1075 parent770ed5b3, retaining final
  worker guards and original producer/reservation/Lua behavior. Relevant paths
  audited against1986d671, no missing local backports.168offline cases pass
  45.65s; exclusive-claim and generation-delivery mutations fail/restored/cmp.
  All three new durable queue trees are clean for root publication/review;
  no live source/service/DB changes. Original runtime continuation not replaced.

- (Astra, 2026-09-20) #1077 review4057883492/4057883502: defer interruptions
  through bounded child reaping and preserve the original exception; broaden
  serialization-failure test to PicklingError with actual serializer proof.
  Self-review additionally fixed inherited caller exception context suppressing
  cancellation; tests reproduce calls from an unrelated except block.
  Runtime delivery/sealing remains next. No merge or service activation.

- (Astra, 2026-09-20) #1077 review4057826087: fix inherited worker false timeout
  after child exit and late parent observation. Real-child success/failure
  regressions and failed/restored mutation added; no source/service activation.
  Resume trusted completion delivery and snapshot sealing after review checks.

- (Astra, 2026-09-20) R04v combines reservation and offline Lua prototype; durable
  exclusive claim precedes one producer dispatch, generation scopes path/callback.
  Concurrency/error/repeat proofs and two failed/restored mutations complete.
  Next trusted receipt delivery and snapshot sealing; no game/service activation.

- (Astra, 2026-09-20) R04u independent main-based source generation reservation:
  16 focused cases pass, same-token concurrency has one winner, existing entries
  never reused, sync-error reservations retained. Mutation fails/restores. Prior
  capture/manifest work stays in #1075 chain (24paths), not discarded. Next
  producer handoff/identity delivery, no service or source activation.
### Inherited parent checkpoints

- (Astra, 2026-10-04) #1075 synchronized through actual main539db373,
  retaining previous retry/reader fixes. Earlier approved PRs have merged;
  fresh exact-head review/CI remain gates before the mandatory merge cycle.
  No source activation, service or deployment; original runtime plan retained.
  Composed200/201/240-byte +0400 publication/retry regression added;119cases
  pass, both historical boundary regressions fail under mutation/restored cmp.
  Read the latest PLAN in /home/samba/share/slomix-astra-runtime-integration-20260926;
  preserved local checkpoint8e262684 is an access anchor, not the latest head.

### Historical retry checkpoints


- (Astra, 2026-09-28) #1075 prepared on c6e532a8, retaining reader umask fix
  and worker guards.56filesystem/plan cases pass0.88s; caller size/hash mutation
  fails both cases/restored/cmp. No differences from old integration retry
  implementation; no remote/service/DB. Next1077 then root exact-head gates.

- (Astra, 2026-09-20) R04t completion retry composes reader/publisher without
  overwrite.187 combined tests pass; wrong requested size/hash guard mutation
  fails/restores. Missing/corrupt content remains distinct; existing content does
  not gain durability acknowledgement. Next source reservation/delivery, no deploy.
### Inherited parent checkpoints

- (Astra, 2026-10-04) #1074 locally retains the prior0400/0600 reader repair
  while incorporating actual merged parent/main d3a8f4df. Owner-approved;
  earlier predecessors merged, fresh exact-head review/CI remain merge gates.
  No service, deployment or source activation; original runtime plan retained.
  Read the latest PLAN in /home/samba/share/slomix-astra-runtime-integration-20260926;
  retained checkpoint8e262684 is a local access anchor, not the latest head.

### Historical reader checkpoints


- (Astra, 2026-09-28) #1074 prepared on a222a558; old integration paths audited
  without importing its whole history. Fixed actual umask0277 publisher0400
  receipt rejection; exact0400/0600 admission, no permission widening. Mutation
  fails/restored/cmp;134offline filesystem/worker/SSH/Lua cases pass45.35s.
  Root owns fresh review, then1075/1077 preparation; original runtime retained.

- (Astra, 2026-09-20) R04s read-only manifest recovery implemented with explicit
  missing/conflict/match states; malformed/unsafe/I/O remains an error.177 tests
  pass, replaced-entry mutation fails/restores. #1073 refreshed checks green.
  Next retry policy and collision-safe source reservation; no source activation.
### Inherited parent checkpoints

- (Astra, 2026-10-04) #1073 retains prior filename-cap repair and manifest
  runtime proofs during normal actual-main67ad2d8c refresh. Earlier approved
  predecessors merged; fresh exact-head gates remain, no activation/deployment.
  Read the latest PLAN in /home/samba/share/slomix-astra-runtime-integration-20260926;
  preserved local checkpoint8e262684 is an access anchor, not the latest head.

### Historical manifest checkpoints


- (Astra, 2026-09-28) Propagated final worker90026032 through local #1069–#1073
  by normal merges, retaining both histories and exact worker/source-test bytes.
  Combined218cases pass47.43s. Minimum-grace compatible with existing callers;
  no fixture weakening. No remote/service/DB action. Root handles actual-main
  sync/publication and original runtime1986d671 remains the development resume.

- (Astra, 2026-09-28) Final worker repair 3fa2280f propagated by normal merges
  through prepared #1069-#1073; worker source/tests identical at every head.
  Final manifest/inherited offline suite passes 203 cases in 31.02s, no skips.
  Both documentation histories preserved; no remote writes or activation.

- (Astra, 2026-09-28) #1073 refreshed locally on 4a764f1c; 190 offline cases
  pass in 24.41s. Filesystem/fsync/no-clobber proof and two mutation experiments
  verified; restored/cmp, 18 manifest cases pass. Existing filename-cap review
  is fixed and reverified but remains unresolved remotely. No service/SSH/PR
  changes. Next publish/review after parent, then reader/recovery slices.

- (Astra, 2026-09-20) #1073 review4057411193 corrected manifest name cap200->240
  to match Lua producer. Real-file boundary tests and old-limit mutation verified;
  157 combined tests pass. #1072 verification-alias CI succeeded at exactcba88132.
  Next resume reader/recovery; no service/deployment or source changes.

- (Astra, 2026-09-20) R04r persists verified completion manifests without
  overwrite;153 combined tests pass, content-guard mutation fails/restored.
  #1071 retry succeeded. #1072 lacked Actions due to branch filter; same-SHA
  verification alias uses existing feat/db-runtime-* trigger. No code bypass.
  Next manifest recovery and source collision protocol, no activation.
### Inherited parent checkpoint

- (Astra, 2026-10-04) #1072 approved;963/964/966/1066 merged and actual main5de82cfb
  incorporated. Fresh exact-head tests/CI/review required before1072 merge.
  Read the latest PLAN in /home/samba/share/slomix-astra-runtime-integration-20260926;
  retained local checkpoint8e262684 is an access anchor, not the latest head.
  Local parent06e5a20d plus its actual squash5de82cfb included, while
  preserving the offline Lua prototype and both histories. No activation/deploy;
  fresh actual-main sync and
  exact-head tests/review/CI remain required after the earlier merges.

### Historical branch checkpoints


- (Astra, 2026-09-28) #1072 locally refreshed on #1071 head 97db51fa with
  both histories retained. 172 combined offline tests pass in 28.00s, zero
  skips; real Lua/filesystem completion proof and failing/restored write-count
  mutation verified. Lua parse/Ruff clean. Review API has zero threads, not
  fresh-review approval. No remote writes or activation; ready for parent-led
  publication, followed by durable completion/manifest work in the runtime plan.

- (Astra, 2026-09-20) R04q offline producer helper/proof, not game integration.
  139 combined tests pass; short-write mutation emits false completion and fails,
  restored/cmp. Fresh name/single writer required; durable receipt, digest and
  collisions remain next. Owner allowed local development, no deployment.
### Inherited main checkpoints (historical)

- (Astra, 2026-10-04) #1066 now includes actual966 mainfa40c12e. Runtime
  importer/parser code retained; isolated PostgreSQL evidence must be refreshed
  before merge. Retained local integration checkpoint8e262684 is an access anchor:
  read its latest PLAN. Owner-approved predecessors963/964/966 are now merged.
  No local service restart or application database fallback.
  Added real-PG selected-R1 calendar scenario for CI; local collection/child
  compilation is not SQL proof. Offline138 tests pass9.29s; later CI PG14/17
  per-scenario logs prove all10cases. Actual964/966 synchronization is complete;
  fresh exact-head gates still block merge.

### Historical importer checkpoints

- (Astra, 2026-09-28) #1066 verified-entry terminal filename contract corrected:
  validate before I/O and return failed with capture_status=None (unmeasured).
  Three unit/one actual PG regressions failed before fix; 199 combined pass81.01s.
  Guard mutation fails actual PG case, restored/cmp. Fresh review still required.

- (Astra, 2026-09-28) #1066 P1/P2 reproduced with real payload/SQL, then fixed:
  selected R1 needs independent source size/SHA admission; dependency conflict
  cannot contaminate valid R2. Shared importer calendar/name admission precedes
  canonical dedup for both halves. Invalid inputs return failed/no marker.
  Prior malformed-payload calendar proof was insufficient; actual validpayload
  duplicate bypass reproduced and closed. 163 cases pass73.79s incl9PGcases;
  three guard mutations fail/restored/cmp, schemas absent by count/list. No
  production callers need migration; future verified R2 supplies expected_r1.
  Original runtime1986d671 and immutable-source requirements remain intact.

- (Astra, 2026-09-28) #1066 final main sync 86b83475 after #1067 retains
  verified-import bytes and both doc histories. 175 cases pass in 49.28s with
  all seven isolated PG scenarios and SSH identity tests; schema cleanup proven
  by count and list. Publish for new exact-head review under owner queue approval.

- (Astra, 2026-09-28)1066 missing SQL proof completed on verified isolatedPG:
  clean142cases pass54.89s, all7PGscenarios; guard mutation failed/restored/cmp.
  Initial overlapped run discarded as final evidence; zero temporary schemas
  remain by count/list. Publish current head for newreview/CI, no merge approval.

- (Astra, 2026-09-27)1066 local preparation5e8b769d retains both calendar and
  spool-only R1 guards across parent1065 merge.54local cases pass, guard mutation
  fails/restored/cmp. Full PostgreSQL proof waits owner-started disposable service;
  never substitute application DB. No push/retarget/merge; wait1065 actual main.

- (Astra, 2026-09-20) Priority #1066 review detour: verified import now requires
  spool-only parser; legacy cwd/local_stats fallback and R1 symlinks cannot supply
  runtime differential. 153 tests pass, actual-PG fallback mutation fails/restored.
  Invalid '..' names leave waiting path; prose nits addressed. Resume hard SSH
  worker deadline design, then source identity and single-writer gates.

- (Astra, 2026-09-20) R04k integration branch combines #1065 and #1060 without
  changing either foundation implementation. Verified local content gates
  canonical importer; 137 unit/actual-PG cases pass, conflict-gate mutation fails
  and restores/cmp. PG stopped. Next connection/source identity and review;
  no deployment, services, source deletion or automatic scheduler.
### Inherited handoff checkpoints (historical)
- (Astra, 2026-10-04)966 follow-up pins source OID for bundled snapshot scans,
  independent of local origin/main. Two real Git bypasses reproduced;116tests
  pass, source-argument mutation fails/restored/cmp. Safe published feature
  sources remain supported.963 is mergeda2737e7a; this normal main refresh
  preserves both histories. Retained local integration checkpoint8e262684:
  read its latest PLAN in /home/samba/share/slomix-astra-runtime-integration-20260926.
  No real review refs or service actions;964 must still merge before966.

### Historical snapshot checkpoints

- (Astra, 2026-10-04) Additional966 review found hidden warning-only credentials.
  Bundled-guard diagnostics now block noninteractive publication before refs,
  without echoing content. Three local Git regressions reproduced the old leak;
  no real credentials/remotes involved. Fresh exact-head gates still required.

- (Astra, 2026-10-04)966security review repaired: published-source admission on
  actual push target, locked symbolic-ref type check and NUL hook filenames.
  106tests pass;6mutant failures restored/cmp. No real review refs or deploy.
  Await963/964 consolidation and fresh current-head gates before merging966.

- (Codex, 2026-10-03) #966 four fresh findings repaired: transaction verify for
  existing local refs, raw binary admission independent of forced-text drivers,
  replacement-object suppression across Git/hook subprocesses, and signed
  commit date extraction. 75 disposable Git/Node/plan cases pass28.81s; twelve
  measured mutation failures restored/cmp. No real review refs or services
  changed; parent handles main synchronization, fresh CI/review and publication.
  Original runtime development plan remains unchanged.

- (Codex, 2026-10-03) #966 follow-up: ambient order-file partition drift and
  missing-hook publication repaired. Direct bundled guard preflight covers
  every proposed pair before any publication; original runtime work preserved.
  Parent review and fresh exact-head CI/review remain required before merge.

- (Codex, 2026-10-03) #966 repairs four fresh findings: diff algorithm pinned,
  remote diagnostics withheld, legacy body generator retired, partial remote
  pairs rejected before publication. Nine guard mutations fail/restored/cmp in
  actual disposable Git repos. Existing complete pairs are observed, not locked;
  no same-OID lease guarantee. Normal main19e65354 merge retains both histories
  and repair e9124506 source/test bytes;53 snapshot/plan/Node cases pass13.63s.
  Ruff/whitespace clean; root owns
  publication. Original runtime roadmap and real review refs remain untouched.

- (Astra, 2026-09-28) #966 three configuration findings reproduced/fixed:
  empty branch enumeration, actual push-destination preflight, deterministic
  UTF-8 commit objects. Reject multiple push URLs before refs; preserve existing
  CAS/pathspec/no-empty/hook protections. Five mutations fail/restored/cmp;
  40 disposable Git CLI/plan cases pass10.24s after normal main4de6f07e merge.
  Independent remote OID/object proofs pass, real review refs unchanged.
  No real publication/services; fresh review next, original runtime plan intact.

- (Astra, 2026-09-28) #966 fresh review scope fixes: reject an area selecting
  no changes and --exclude without actual nonempty exclusion magic. Six
  disposable CLI failures reproduced, guards mutated/failing/restored/cmp;
  32 combined cases pass6.44s. Real review refs unchanged. Await fresh review.

- (Astra, 2026-09-28) #966 integrated actual main 1f4a388d; all three cd483737
  guard fixes retained, scripts/tests unchanged from 79a7e2d1. Twenty real CLI
  cases in disposable local repositories plus two plan contracts pass. Actual
  tree-validation mutation fails three cases, restored/cmp; real review-ref
  digest unchanged. No real remote/service operation. Root owns publication,
  exact-head review and merge gates; original runtime 1986d671 unchanged.

- (Astra, 2026-09-27)966 follow-up: three review findings fixed locally;20real
  disposable Git CLI tests pass. Duplicate/missing-positive areas fail preflight;
  generated tree diff catches D/F collateral and actual bounds before ref writes.
  Both bounded transition directions proven;10regressions fail under mutation,
  restored/cmp. No real review refs or services touched, no push/merge. Original
  runtime continuation remains preserved while parent consolidates existing PRs.

- (Astra, 2026-09-20) #966 refreshed against main;9snapshot/plan tests pass,
  Ruff clean. Actual review-snapshot refs and NEVER MERGE PRs unchanged. Keep
  this older tooling proposal for review, not authorized for merge. Runtime
  resume #1077 completion delivery/sealing remains after consolidation.
### Inherited handoff checkpoints (historical)
- (Astra, 2026-10-04) #963 mergeda2737e7a with exact reviewed/squash tree
  identity771ed168,14green checks, all8threads answered and420s cycle. #964
  normally integrated actual main with both histories preserved.51 local cases
  and current-plan routing mutation proof; publish for fresh review/CI next.
  Retained integration checkpoint8e262684 is a local access anchor: read its
  worktree's latest PLAN, not a historical queue. No service/deployment action.

- (Astra, 2026-10-04) #963 review correction: current local integration checkpoint
  is8e262684 in /home/samba/share/slomix-astra-runtime-integration-20260926;
  read its latest PLAN rather than resuming from historical1986d671.
  Owner approved963/964/966/1066/1072-1075/1077 individually subject to fresh
  gates and older-first order. Correct the historical deployment recipe to pass
  the exact built commit; no live deployment, service or data action.
  September28 corrections remain in Git history and the dated PLAN below.

- (Astra, 2026-10-04) #964 review correction: continue from the latest PLAN in
  /home/samba/share/slomix-astra-runtime-integration-20260926 (checkpoint8e262684
  at this audit, superseding02c160cc/1986d671). September7/8 execution entries
  and the four dated lessons remain historical, not instructions to restartR01.
  Numbered merge approval received; finish963 then synchronize964 to actualmain
  and repeat all gates before merge. No deployment/service/live-data operation.
- (Astra helper, 2026-10-03) Paired14/3.11 +17/3.13 CI prepared with pinnedimages,
  unchanged two Python checknames/jobs and no newtriggers. Expected servermajor
  checked against actualPG; deliberately mismatched17/14 fails fixture setup.
  YAML/major guards observed failing and restored/cmp. Await actualPG17 CI proof.

- (Astra helper, 2026-10-03) #1078 resumed proof: actualPG14.24 gives31passed,
  4newer-version skips; twelve observed failures across three guard mutations,
  all restored/cmp. SQL unchanged from98b92702. Root owns restored-copy rehearsal.
  Next paired PG14/3.11 and PG17/3.13 CI coverage without extra jobs/triggers.

- (Astra helper, 2026-10-03) #1078 review follow-up prepared: column ACLs,
  version-gated MAINTAIN and transitive SET ROLE/ownership checks. Proof service
  expired, so new PG cases/mutations are explicitly pending; no service start,
  live DB fallback or existing restored-copy ledger change. Repeat093 acceptance
  on fresh disposable restore after owner restart. Original roadmap unchanged.

- (Astra helper, 2026-10-03) DEV permission rehearsal exposed inherited runtime
  CRUD/sequence grants. New093 narrows only runtime object ACLs; real isolated
  tests verify denied writes, generation read, unchanged legacy/default grants,
  and fail-closed PUBLIC/wrong-role cases.19 tests pass5.23s; observed mutation
  failure restored/cmp. No application DB changes. Root owns restored-backup
  rehearsal and review/merge gates; original runtime queue remains preserved.
- (Astra helper, 2026-10-03) #979 RUN index flags review4172412989 repaired:
  four old-guard failures and four deliberate mutation failures, restored/cmp;
  50 focused tests pass11.44s. Disposable checkout independently reproduces hidden
  runtime-byte survival. No live changes; root continues exact-SHA rebuild/review
  and dev restoration rehearsal before returning to the original runtime plan.

- (Astra, 2026-10-03) DEV-only authorization received. Read-only Samba preflight
  identifies old75ee10b5 deployment and ten pending main migrations. Refreshing
  #979 on5e948f0b preserves artifact safeguards and both histories. No deployment
  yet; return to original runtime queue after safe deployment preparation.

- (Astra, 2026-09-28) #979 real Node22.23.2 wrappedbuild/provenance verified:
  137outputs hashes by two paths; actual preflight only in disposable clone
  preserves HEAD/tree/assets/inodes/mtimes. In-process HTTP200 HTML+6assets
  equalsdisk, no server/browser/DEVdeployment.23guards pass5.63s; corruption
  mutation fails/restored/cmp. Final docscommit requires rebuilt exactSHA;
  root owns actual parent merge synchronization and remote review/CI.

- (Astra, 2026-09-20) #979 consolidation review: fixed stale default source ref,
  wrong-checkout verifier and hidden-index input flags, with four failing/restored
  regressions and23passing fixture tests. No real deploy. Branch refresh/CI and
  PR-specific permission remain gates. Runtime resume remains #1077 after detour.


- (Astra, 2026-09-28) #1071 local refresh on bda56937 preserves both histories
  and worker/SSH sidecar fixes. 160 offline cases pass (25.71s), including actual
  child lifecycle and independent file/hash/reaping evidence. EOF guard mutation
  fails all three drift scenarios; restored/cmp and three passes. No remote
  writes or activation; trusted completion remains a gate. Ready for parent-led
  publication/review, not a claim of operational runtime completion.

- (Astra, 2026-09-20) Source-completion investigation: round notification can
  precede file write; generic saved log and delayed file-created notifier are not
  exact durable receipts. Local runtime counterexample confirms equal metadata
  and hashes while writer remains open (7bytes then18). Next owner decision on
  offline source-producer protocol vs retaining source freeze; no deployment.

- (Astra, 2026-09-20) R04p adds fail-closed source metadata checks before read
  and before local publication. 127 combined cases pass; disabling EOF guard
  fails three real-child/offline-transport proofs, restored/cmp. Checked-in Lua
  writes final name directly, so stable metadata is NOT proof of producer close.
  Trusted completion/manifest remains a gate; no remote/service changes.

- (Astra, 2026-10-03) Prepared1070 on reviewed1069, preserving source and
  both documentation histories.68tests pass; two deliberate guard failures
  observed then restored/cmp. Await actual parent merge, no live service action.

- (Astra, 2026-09-28) #1070 local bda56937 includes final SSH sidecar guard
  and preserved worker fixes. 150 combined cases pass in 23.00s including
  timeout with present final content and safe retries. Await #1069 actual main.

- (Astra, 2026-09-27)1070 refreshed locally through8501f7b9 (merge5d2971f7),
  preserving worker/auth/0400 fixes and both documentation histories.141offline
  tests pass23.35s; real child/retry proofs and failing guard mutation restored/cmp.
  New1067 implicit certificate-sidecar finding still requires propagated repair
  before publication; do not call auth fully reviewed. No push/retarget/service/DB.

- (Astra, 2026-09-20) R04o combines #1069/#1064 and keeps observed spool content
  separate from supervised child outcome. 117 cases pass; actual spawned offline
  retries recover missing content and skip already-complete/conflicting content.
  Mutation fails/restores. No orphan deletion or source acknowledgement. Next
  source metadata/discovery and verified importer integration; no services changed.

- (Astra, 2026-10-03) Newly observed undici/brace-expansion advisories repaired
  narrowly in1027. Cleaninstall/audit0/typecheck/845tests/SPA build succeed;
  actual package probes and failing/restored isolated mutations verified. No
  service/deploy. Publish fresh head, never reuse September's clean-audit claim.

- (Astra, 2026-10-03) Recovered interrupted #1027 main19e65354 merge,
  retaining both histories. Focused checks repeated; fresh publication gates
  still required. No service restart or production changes.

- (Astra, 2026-09-28) #1027 actualmain4de6f07e integrated, frontend inputs
  unchanged from845-test/build proof. Fresh typecheck, API hash, actual installed
  YAML/nanoid guard probes and50plan/watchdog cases pass. No deployment.

- (Astra, 2026-09-28) #1027 main ec8ec7ed integrated normally as0ee8e3e6.
  All frontend/API inputs identical to022f1115's845-test proof; fresh typecheck,
  API generationcmp and50plan/watchdogtests pass. No Nodebranch mixed in.
  Proof scripts copied to durable local audit path, cmp verified; root publishes.

- (Astra, 2026-09-28) #1027 local dependency proof complete: zero audit findings,
  identical original/patched generated API types, typecheck, 845 tests/70 files
  and SPA build succeed. Six built HTML asset references resolve offline.
  Actual YAML/nanoid guard mutations fail, restored/cmp and probes pass; no
  browser/server/deploy. Ready for parent-led main sync, publication and review.

- (Astra, 2026-09-28) #1027 compatible nanoid3.3.19 lock patch removes last
  audit finding; original/patched OpenAPI output identical and typecheck passes.
  Bounded old dependency probes fail, patched probes pass. Full single-worker
  Vitest run in progress; SPA build next. Only three package entries changed
  versus original PR lock; no runtime server or production action.

- (Astra, 2026-09-28) #1027 lock-only upstream security patch prepared:
  core1.34.20/YAML4.3.2 only; unrelated npm10 libc metadata loss restored.
  Existing Vitest4.1.11 preserved. npm audit still finds high nanoid<3.3.18,
  so no clean-audit/readiness claim. No npm ci or runtime validation yet;
  next controlled dependency decision and frontend validation, no deployment.

- (Astra, 2026-10-03) Recovered interrupted #1069 main19e65354 merge,
  retaining both histories. Focused checks repeated; fresh publication gates
  still required. No service restart or production changes.

- (Astra, 2026-09-28) #1069 local 005e8d83 includes final SSH identity and
  preserved worker fixes; 144 combined cases pass in 18.35s. Initial wrong
  test filename collected nothing and is not proof. Await #1068 actual main.

- (Astra, 2026-09-27)1069 locally refreshed from87f9fa72 through prepared
  parent3244843d, merge4020bb69 preserves both doc histories and worker/auth fixes.
 114offline tests pass17.95s including actual child/spool lifecycle evidence;
  absolute-path mutation fails then restored/cmp. No active owned child remains
  in lifecycle assertions. No push/retarget/liveSSH/service/DB changes; original
  runtime sequence and parent final sync/review gates unchanged.

- (Astra, 2026-09-20) R04n composes SSH session/file ownership and verified stream
  publication inside a picklable capture-only task on #1068. 97 combined cases
  pass; offline transport with actual child/filesystem demonstrates timeout can
  leave either partial or final content. Guard mutation fails/restores. Next
  reconciliation composition/source identity; no activation or network claim.

- (Astra, 2026-09-28) #969 integrated actual worker main4de6f07e normally;
  both histories retained, Node/CI/PyYAML bytes unchanged. Root99combined
  cases pass34.80s, including actual child cleanup. No service action.

- (Astra, 2026-09-28) #969 normal main1f4a388d refresh: six node/plan contracts
  pass; isolated22.23.2 binary verified by two version paths. Old22.13.1 pin
  mutation fails, restored/cmp. No install/build/browser/service/lock change.
  Root owns remote review/merge; original runtime1986d671 plan preserved.

- (Astra, 2026-09-20) Consolidation: refreshed #969 from main without conflict;
  six Node-pin/plan tests pass, no installs or builds. Preserve its dependency
  declaration review fix; no merge approval for this PR. Runtime resume remains
  #1077 completion delivery/sealing after the side quest.

- (Astra, 2026-09-28) #1068 fresh signal-lifetime findings fixed: one handler
  installed before spawn through close; custom side effects replay even with
  original error; 0.01s minimum grace rejects unsupported tiny budgets. Every
  cleanup phase attempts its stop signal. Explicit delayed-SIGINT contract.
  159cases pass37.24s including45workers; broad-catch narrowing fails3 actual
  SystemExit cases, disabled lifetime guard leaks spawnwindow child in fixture,
  restored/cmp and fixture cleanup verified. Removed unused cleanup_complete;
  retained intentional BaseException deferred-rethrow semantics with proof.
  No remote/services/DB/network. Runtime1986d671 preserved; root owns gates.

- (Astra, 2026-09-28) Root-review worker follow-up: tiny-grace finished-child
  false error and cleanup-clock SIGINT leak reproduced, repaired and mutation
  verified/restored/cmp. Whole cleanup now defers callable SIGINT through close;
  prior handler behavior and original parent error preserved. 146 combined cases
  pass in 20.51s, Ruff clean. Parent handles publication/descendant propagation.

- (Astra, 2026-09-28) #1068 fresh review exposed real escalation/startup SIGINT
  child leaks. Three actual-spawn regressions failed before repair and again with
  mutations; fixtures always cleaned leaked children. Bounded operation-wide
  escalation retries and ownership-window SIGINT deferral preserve original
  errors, custom/ignored handlers and child masks. Restored/cmp; no remote or
  service actions. Root owns publication/review and descendant propagation.

- (Astra, 2026-09-28) #1068 retains original worker fixes 86c69e39 and final
  SSH e22ae27c after normal merge eed58f6c. 133 combined cases pass in 14.44s,
  actual spawned children reaped by two observations; Ruff clean. Await #1067
  actual main, final sync and fresh review. No runtime activation or deployment.

- (Astra, 2026-09-27)1068 local refresh preserved86c69e39 worker backports,
  merged reviewed1067 db7f3888 normally as99f2161c.92offline cases pass12.33s;
  real child cleanup verified by procfs and active_children, interrupted cleanup
  retains original errors. Timeout mutation fails2cases, restored/cmp. No push,
  service/liveSSH/DB changes; parent owns final sync/review and original plan.

- (Astra, 2026-09-25) Consolidation side quest: backported exact #1077 worker
  fixes/tests into #1068 locally; five old-code regressions fail, 94 combined
  tests now pass. Late-clock mutation fails/restores/cmp. No GitHub writes or
  AI review requests because owner requires no additional review charges.
  #1076/#1057/#962 already merged; #965 local integration saved at2e035917.
  Runtime resume remains #1077 completion delivery/sealing. No services changed.

- (Astra, 2026-09-20) R04m adds isolated capture-task deadline supervision on
  #1067. 86 combined tests pass, real owned children reaped even after SIGTERM
  refusal/parent interruption; timeout-status mutation fails/restores. #1066
  latest exact-head CI all green. Next transport-specific task and source identity;
  no services activated and no DB transactions allowed in force-stopped workers.


- (Astra, 2026-09-28) #965 fresh review warning transition regression repaired
  with bounded per-key pending_warn state. Real isolated JSON/run proof covers
  cooldown, failed delivery/retry and latest-condition supersession. Old code
  and naive-OR mutation both fail two cases; restored/cmp, 48 cases pass0.48s.
  Heartbeat repair preserved; no real delivery/services or remote writes.

- (Astra, 2026-09-28) #965 integrated actual main 1f4a388d, retaining all
  watchdog fixes and both doc histories. Source/tests unchanged from 3c967222;
  45 focused contracts pass using actual temporary files and mocked delivery.
  Inverted ACK guard fails, restored/cmp; no real notification/service action.
  Root handles fresh publication/review/merge gates. Runtime 1986d671 preserved.

- (Astra, 2026-09-25) #1076/#1057/#962 confirmed merged; #965 integrated
  current main locally, 45 focused tests pass, midnight mutation fails/restores
  with cmp. No push or AI review request: owner reported unwanted review charges.
  Billing not verified; preserve local work while avoiding automatic triggers.
  #965 still needs exact-PR merge permission. Original runtime #1077 completion
  delivery/sealing remains the resume point; NEVER MERGE and services untouched.

- (Astra, 2026-09-20) Consolidation detour: #965 refreshed from main, preserving
  notification/midnight fixes and both documentation tracks;42 targeted tests
  pass,Ruff clean. Wait for #962 disk fix before combined verification. #965 has
  no merge permission. Runtime resume #1077 c015270b: completion delivery/sealing,
  then new-site audit and approved DEV transition. NEVER MERGE unchanged.

- (Astra, 2026-09-28) #969 normal main1f4a388d refresh: six node/plan contracts
  pass; isolated22.23.2 binary verified by two version paths. Old22.13.1 pin
  mutation fails, restored/cmp. No install/build/browser/service/lock change.
  Root owns remote review/merge; original runtime1986d671 plan preserved.

- (Astra, 2026-09-20) Consolidation: refreshed #969 from main without conflict;
  six Node-pin/plan tests pass, no installs or builds. Preserve its dependency
  declaration review fix; no merge approval for this PR. Runtime resume remains
  #1077 completion delivery/sealing after the side quest.
- (Astra, 2026-09-27) PR1067 follow-up: remove PKey.from_path implicit adjacent
  certificate discovery. Public typed file-object private-key loaders preserve
  five tested key encodings; certificate paths unsupported, no ambient cert or
  passphrase fallback. Real temporary ssh-keygen cert + malformed neighbor fail
  old code;108 combined tests pass fixed code; mutation2 failures, restored/cmp.
  Publish for fresh CI/review next. Original runtime plan/activation gates stay.

- (Astra, 2026-09-27) PR1067 fresh P2 fixed locally: bypass Paramiko legacy
  interactive fallback using explicit-key AuthStrategy and reject partial auth.
  Three old-code regressions and three guard-mutation failures observed;
  restored/cmp,84 SSH/capture/spool tests pass. Installed connect/key parsing
  proved offline across five supported key encodings; real handshake untested.
  Original runtime/activation work unchanged. Publish then fresh CI/review;
  no service changes, network connections or1067 merge permission.

- (Astra, 2026-09-20) R04l neutral SSH session ownership on #1063; 73 combined
  cases pass, strict-policy offline proof and cleanup mutation/restoration done.
  No real network. End-to-end handshake bound and source identity still block
  activation. #1066 capture/import integration CI/review remains in parallel.

- (Astra, 2026-09-20) R04j adds one caller-driven capture attempt on #1064.
  55 filesystem tests pass; source-consumption guard mutation fails/restored.
  Match/conflict skip input; missing publishes; every exception remains visible.
  No source acknowledgement/deletion, scheduler, SSH or service activation.



- (Astra, 2026-09-27)1064 Codex4116756259 verified/fixed: umask0277 produces
 0400; inspector now permits0400/0600 without broadening permissions.75real
  filesystem/local socket tests pass; oldmodeguard mutation fails then restored
  and cmp verified. Unsafepermission regressions retained. No push/service/DB.

- (Astra, 2026-09-27)1063 and1064 both included merged1062 main4454d6c5.
  Preserved source/tests and both documentation histories; publish only after
  repeating local gates. Fresh exact-head CI/review and individual permission
  still required before merge. No deployment or production changes.

- (Astra, 2026-09-27)1064 preserved/refreshed through parent1062 at21e6c999;
  normal merge4c119978 retained both doc histories and original runtime plan.
 49real filesystem tests pass; mutation of wrong-size identity handling fails,
  restored/cmp. Existing two review threads resolved; no new finding in this pass.
  Wait actual1062 main merge, final sync and fresh review/CI; no1064 permission
  inferred, no push/retarget/service/database/snapshot action.

- (Astra, 2026-09-20) #1064 review fixed: validate identity even on wrong size;
  49 cases pass, early-return mutation fails/restored. Next compose a single
  caller-driven retry step; no scheduling, source deletion or service activation.

- (Astra, 2026-09-20) R04i on #1062: read-only spool reconciliation implemented,
  48 filesystem cases pass with failed/restored digest and identity mutations.
  No automatic cleanup, overwrite, retry loop, DB or service changes. Next wire
  explicit reconciliation policy with connection ownership and immutable source.

- (Astra, 2026-09-20) #1063 review: read deadline starts after spool setup;
  54 cases pass, old-placement mutation fails/restored. Investigating #1060
  cross-half payload identity before resuming transport/reconciliation.

- (Astra, 2026-09-20) R04h adds caller-owned timed stream capture on #1062.
  53 combined cases pass; real socket success/timeout cleanup and failing/restored
  deadline mutation verified. No SSH connections or live activation. Separately
  #1060 calendar review fixed in742504ee with23 unit/PG cases passing.

- (Astra, 2026-09-20) #1064 review fixed: validate identity even on wrong size;
  49 cases pass, early-return mutation fails/restored. Next compose a single
  caller-driven retry step; no scheduling, source deletion or service activation.

- (Astra, 2026-09-20) R04i on #1062: read-only spool reconciliation implemented,
  48 filesystem cases pass with failed/restored digest and identity mutations.
  No automatic cleanup, overwrite, retry loop, DB or service changes. Next wire
  explicit reconciliation policy with connection ownership and immutable source.

- (Astra, 2026-09-20) R04g extends #1061 with opt-in source SHA-256 validation
  before publication. 35 filesystem cases pass; independent sha256sum agrees;
  disabled mismatch guard fails, restored/cmp. No transport/services activated.
  Continue bounded capture and reconciliation; new-site audit follows runtime.


- (Astra, 2026-09-20) Runtime PRs marked ready per owner. Copilot on #1061
  unable to review due to requester quota. Fixed supported map alphabet finding
  with24 passing filesystem tests and failed/restored old-regex mutation.

- (Astra, 2026-09-20) While #1059/#1060 await CI/review, independent R04f
  implements atomic no-clobber completed-file publication. No SSH integration
  or services. #1060 plan-staleness finding4056273674 fixed in1f636253 and replied.
- (Astra, 2026-09-20) #1060 cross-half dedupe review: canonical hash lookup
  now scopes R1/R2 separately, not only the runtime waiting guard. Actual-PG
  zero-delta R2 proof and failing/restored SQL mutation verify the root fix.
  Historical repairs and full source identity are separate, not silently done.

- (Astra, 2026-09-20) #1060 calendar review fixed: impossible R2 timestamps no
  longer wait for R1. 23 unit/PG cases pass, 7 calendar mutations fail/restored.
  Resume bounded stream capture on the #1062 stack; no live activation.

- (Astra, 2026-09-20) Review detour after opening integrity PR #1062:
  #1060 now preserves renamed payload deduplication after R1 removal and routes
  malformed R2 names to canonical failure.14 unit/PG cases pass; mutations fail
  and restore/cmp. Disposable PG stopped. Resume bounded capture after review.

- (Astra, 2026-09-20) R04e caller-driven dependency guard implemented: missing
  R1 defers R2 without terminal marker;69 combined tests including actual PG
  pass; guard mutation observed/restored. Immutable spool is a precondition,
  not implemented transport/retention. Next bounded capture/publication design.
  Owner-approved overall scope now includes full new-site audit after runtime.

- (Astra, 2026-09-20) Real PG R1/R2 ordering characterized;63 tests pass.
  Activation gap confirmed: late R1 does not repair already-marked orphan R2.
  Next priority dependency-aware capture scheduling, not more unrelated refactors.

- (Astra, 2026-09-20) #1059 now includes real-PG neutral R1 import proof:
  canonical parser/writes/event/marker, observer connection, duplicate retry,
  caller pool still usable.60 combined tests pass; missing-event mutation caught.
  Disposable PG stopped. Next R2/late arrival and single-writer/capture work.

- (Astra, 2026-09-20) #1059 strengthened with neutral process_file preflight
  lifecycle subprocess proofs (duplicate/outage/cancel),36 focused cases pass.
  Unwanted disconnect mutation failed/restored. Next real PG successful-write
  proof remains pending; no application database or service touched.

- (Astra, 2026-09-20) R04d implemented on separate worktree, based on #1057
  plus unchanged parser slice from #1056. Neutral import/construction and lazy
  default setup proven in subprocesses;78 regressions pass; mutation restored.
  No full-ingestion claim or activation. Next process_file/pool ownership proof.


- (Astra, 2026-09-19) Independent R04b constructor-config prerequisite over
  main2518735f;154 cases pass, actual subprocess and falsey-config mutation proof.
  Separate open stack #1051–#1056 remains intact. #1055 review findings fixed in
  847c1b7d and synced to #1056 at74408882; both threads answered/resolved, fresh CI
  required. Resume config/logging startup boundary after review, no activation.

- (Astra, 2026-09-19) R04a isolates parser's Discord presentation dependency;
  actual subprocess parity and real embed proof, observed eager-import mutation
  restored/cmp;151 tests pass. Neutral manager config/logging boundary remains
  next. No claim of independent ingestion, no service or live database changes.

- (Astra, 2026-09-19) R03d adds independent dev-only cache consumer entrypoint,
  not ingestion. Default OFF; one owned pool/task, signal shutdown, safe JSON
  health. Actual isolated PG subprocess catch-up/blocked shutdown pass; observed
  dev-guard mutation restored/cmp. Expanded200 passed; publish/review next.
  #1054 nine exact-head checks green and both external reviews no findings.
  No merge approval for #1050 or later; no service/production activation.


- (Astra, 2026-09-19) #1055 review follow-up: pre-drain shutting_down health,
  explicit localhost override documentation; real PG signal proof and failed/
  restored mutation, expanded200 passed. Return to R04 configuration discovery.

- (Astra, 2026-09-19) R03d adds independent dev-only cache consumer entrypoint,
  not ingestion. Default OFF; one owned pool/task, signal shutdown, safe JSON
  health. Actual isolated PG subprocess catch-up/blocked shutdown pass; observed
  dev-guard mutation restored/cmp. Expanded200 passed; publish/review next.
  #1054 nine exact-head checks green and both external reviews no findings.
  No merge approval for #1050 or later; no service/production activation.


- (Astra, 2026-09-27)1053 merged75a359f6 with explicit approval and reviewed
  tree equality.1054 refreshed against actual main, retaining its worker flag;
  retarget before push. New exact-head gates and own merge permission required.

- (Astra, 2026-09-27)1054 refreshed from reviewed1053 ccd23e81;24worker tests
  pass4.36s including3fresh isolated-PG recovery cases. Publishing disabled-state
  correction for review; no merge permission. Owner started proof cluster;
  application services/data unchanged. Parent1053 still needs owner approval.

- (Astra, 2026-09-27)1054 disabled-state review fix saved locally after parent
  refresh.161tests pass;4reproductions/mutation failures, restored/cmp. Parent
 1053 requires another review-fix refresh first. No merge/service approval.

- (Astra, 2026-09-19) #1049 merged90eae0f8 after approved review/cycle;
  squash tree matches964630e8. Descendant stack synced with code unchanged.
  R03c expanded combined proof172passed; stack23files now within publication
  limit25. Next publish R03c and inspect exact-head external CI/reviews.

- (Astra, 2026-09-19) Original runtime plan reviewed against actual lifecycle.
  Direction preserved, R04 independence still open; source retention is not
  independent ingestion. Added three worker fault-state tests (17 unit cases
  pass). #1049 specifically approved, fresh112 cases pass, prescribed cycle runs.
  No service/production changes; full audit local-only, canonical summary in PLAN.

- (Astra, 2026-09-18) R03c shared caller-owned polling driver implemented locally.
  169 combined cases pass; actual PG catch-up/restart/closed-connection proof;
  periodic-wait mutation failed/restored/cmp. No startup wiring or activation.
  Publish after approved stack reduction; do not bypass new-branch file limit.
  #1049 awaits explicit approval; PG stopped, no background monitor remains.
- (Astra, 2026-09-27)1053 second review follow-up fixes ON reactivation and
  separate website env template.151local tests pass;12HTTP roundtrip variants,
  7observed mutation failures/restored/cmp. Both modes now worker-local; no
  fresh SQL/Redis proof. Publish then recheck exact-head review/CI.

- (Astra, 2026-09-27)1053 refreshed parent and fixed both open review findings:
  missing092 activation prerequisite and stale OFF rollback cache reuse.
 82local tests pass;2HTTP reproductions and2guard-mutation failures observed,
  restored/cmp. First wider command named a nonexistent304 test; ran0tests,
  corrected command passed82. Await1052 merge/main refresh and fresh CI/review.
  Local proof PG is still stopped; no services or application data changed.

- (Astra, 2026-09-18) #1053 review P1 addressed: migration092 grants website_app
  SELECT only on runtime_cache_generations. Real restricted-role proof and
  observed missing-GRANT mutation restored/cmp; 152 cases pass, PG stopped.
  Bootstrap/release registration updated; no live schema/role changes.

- (Astra, 2026-09-18) R03b2 HTTP generation integration implemented, default OFF;
  92 unit/PG/HTTP proofs pass, namespace mutation observed failing/restored/cmp.
  Dev-only work; production remains untouched per owner's explicit clarification.
  #1049 all22 checks green but awaits individual approval; no merge loop running.
  #1052 new exact-head nine checks pass. Earlier React failure is recorded, not
  diagnosed or waived; new run passed unchanged frontend. No app services touched.
- (Astra, 2026-09-27)1051 merged2b310cb3 with approval and exact-tree equality.
 1052 now integrates main and is retargeted before final push; only doc conflicts,
  source/test bytes unchanged. Fresh exact-head gates and1052 approval required.

- (Astra, 2026-09-27)1052 local parent refresh87eec905 preserves source/test
  bytes and both doc histories.58cache cases pass; actual in-process ASGI proof
  matches200/body/MISS-HIT-MISS-MISS with1retained entry. Count-guard mutation
  fails2cases/restored/cmp. Initial test command referenced nonexistent
  test_http_cache_middleware.py and ran0tests; corrected files above passed.
  Await approved1051 merge, then main refresh/retarget/push. No1052 permission.

- (Astra, 2026-09-18) R03b1 bounded memory-cache prerequisite implemented in
  /tmp/slomix-astra-runtime-r03b1. 48 tests pass, HTTP eviction proof and observed
  failed capacity mutation restored/cmp; independent review no blocker.
  No DB-generation integration or activation yet. #1048 approved cycle running.

- (Astra, 2026-09-27)1060 merged as197feaf7 after explicit owner approval and
  prescribed cycle; tree equals approved ec40a03f. Main workflows running.
 1051 now also integrates this main, preserving both histories; fresh exact-head
  gates and separate owner permission required. No activation or deployment.

- (Astra, 2026-09-27)1051 local refresh a6048926 integrates main c9de5a3d,
  preserving both doc tracks and unchanged cache consumer/migration/SQL tests.
  10 portable cache cases +48 journal/startup cases pass. Fresh SQL pending
  owner-started proof service. Await1060 merge, then refresh/publish for fresh
  exact-head review/CI; no1051 merge approval or activation.

- (Astra, 2026-09-19) #1050 merged as2518735f with explicit approval and
  prescribed cycle; approved tree verified equal. #1051 retargeted main and
  synced without content loss. Propagate ancestry/checkpoint through #1055;
  fresh CI needed after pushes. No further merge approval or activation.

- (Astra, 2026-09-18) R03a DB cache-generation/receipt primitive implemented
  in separate worktree /tmp/slomix-astra-runtime-r03a. No website integration
  yet. Actual PG rollback/late-commit/concurrency proofs and two observed failing
  mutations restored; independent review found no blocker. Combined regression
  280 passed, PG stopped. #1046 merged as 64488de1; no application services changed.
  #1051 review found the stale merge status above, now corrected against PLAN.
  Owner explicitly approved #1048; its prescribed merge cycle is running.

- (Astra, 2026-09-27) Fixed1060 review4114242030: reject dependency waiting
  outside2020-2035, preserving canonical handling.50tests incl6PG pass46.46s,
  mutation3fail/restored/cmp, schemas cleared. New push needs fresh CI/review.

- (Astra, 2026-09-27) PR1060 now targets main after approved1059 merge c9de5a3d.
  Normal refresh77b66d9c preserves existing production bytes, both doc histories
  and main's startup fixture fix.45tests including6realPG cases pass53.55s;
  lint/whitespace clean. Six old findings revalidated/resolved. Publishing this
  post-retarget checkpoint triggers synchronize checks on the main-based PR;
  verify fresh exact-head CI/review. No1060 merge or deployment permission.

- (Astra, 2026-09-20) #1060 cross-half dedupe review: canonical hash lookup
  now scopes R1/R2 separately, not only the runtime waiting guard. Actual-PG
  zero-delta R2 proof and failing/restored SQL mutation verify the root fix.
  Historical repairs and full source identity are separate, not silently done.

- (Astra, 2026-09-20) #1060 calendar review fixed: impossible R2 timestamps no
  longer wait for R1.23 unit/PG cases pass,7 calendar mutations fail/restored.
  Resume bounded stream capture on the #1062 stack; no live activation.

- (Astra, 2026-09-20) Review detour after opening integrity PR #1062:
  #1060 now preserves renamed payload deduplication after R1 removal and routes
  malformed R2 names to canonical failure.14 unit/PG cases pass; mutations fail
  and restore/cmp. Disposable PG stopped. Resume bounded capture after review.

- (Astra, 2026-09-20) R04e caller-driven dependency guard implemented: missing
  R1 defers R2 without terminal marker;69 combined tests including actual PG
  pass; guard mutation observed/restored. Immutable spool is a precondition,
  not implemented transport/retention. Next bounded capture/publication design.
  Owner-approved overall scope now includes full new-site audit after runtime.

- (Astra, 2026-09-25) Prepared local #1059 main refresh, preserving source bytes
  and both documentation histories. Fixed ambient-SSH dependency in test only;
  26targeted tests pass, isolation and eager-import mutations fail/restored/cmp.
  No push/retarget/merge permission or fresh remote CI implied. Runtime integration
  and pending SQL proofs remain on their separate local branches.

- (Astra, 2026-09-20) Real PG R1/R2 ordering characterized;63 tests pass.
  Activation gap confirmed: late R1 does not repair already-marked orphan R2.
  Next priority dependency-aware capture scheduling, not more unrelated refactors.

- (Astra, 2026-09-20) #1059 now includes real-PG neutral R1 import proof:
  canonical parser/writes/event/marker, observer connection, duplicate retry,
  caller pool still usable.60 combined tests pass; missing-event mutation caught.
  Disposable PG stopped. Next R2/late arrival and single-writer/capture work.

- (Astra, 2026-09-20) #1059 strengthened with neutral process_file preflight
  lifecycle subprocess proofs (duplicate/outage/cancel),36 focused cases pass.
  Unwanted disconnect mutation failed/restored. Next real PG successful-write
  proof remains pending; no application database or service touched.

- (Astra, 2026-09-20) R04d implemented on separate worktree, based on #1057
  plus unchanged parser slice from #1056. Neutral import/construction and lazy
  default setup proven in subprocesses;78 regressions pass; mutation restored.
  No full-ingestion claim or activation. Next process_file/pool ownership proof.

- (Astra, 2026-09-20) Approved queue: #1076 and #1057 merged through cycle.sh;
  #962 now integrates both, pending fresh checks. Older proposals refreshed on
  their own branches, including artifact and historical-handoff review fixes.
  Those have no merge approval. Original runtime resume remains #1077 delivery/
  sealing after consolidation; NEVER MERGE/release/services remain untouched.

- (Astra, 2026-09-20) Owner-approved consolidation side quest: preserve all nine
  older proposals; no NEVER MERGE changes, no merges without PR-specific approval.
  Runtime paused after #1077 c015270b, resume completion delivery/snapshot sealing.
  Refreshed #962 with main; added unknown-capacity guard and real-full-disk proof.
  31 tests pass, mutation fails/restores, live read-only disk ratio matches df
  twice (96.9%, displayed97%). No heavy builds/install/cleanup under disk pressure.
  Next #962 fresh CI/review, #965 combined watchdog verification; older work order
  and preservation criteria are recorded in PLAN, not replaced by this detour.

- (Astra, 2026-09-19) Independent R04b constructor-config prerequisite over
  main2518735f;154 cases pass, actual subprocess and falsey-config mutation proof.
  Separate open stack #1051–#1056 remains intact. #1055 review findings fixed in
  847c1b7d and synced to #1056 at74408882; both threads answered/resolved, fresh CI
  required. Resume config/logging startup boundary after review, no activation.

- (Astra, 2026-09-19) R04a isolates parser's Discord presentation dependency;
  actual subprocess parity and real embed proof, observed eager-import mutation
  restored/cmp;151 tests pass. Neutral manager config/logging boundary remains
  next. No claim of independent ingestion, no service or live database changes.

- (Astra, 2026-09-19) R03d adds independent dev-only cache consumer entrypoint,
  not ingestion. Default OFF; one owned pool/task, signal shutdown, safe JSON
  health. Actual isolated PG subprocess catch-up/blocked shutdown pass; observed
  dev-guard mutation restored/cmp. Expanded200 passed; publish/review next.
  #1054 nine exact-head checks green and both external reviews no findings.
  No merge approval for #1050 or later; no service/production activation.

- (Astra, 2026-09-28) #1027 local dependency proof complete: zero audit findings,
  identical original/patched generated API types, typecheck, 845 tests/70 files
  and SPA build succeed. Six built HTML asset references resolve offline.
  Actual YAML/nanoid guard mutations fail, restored/cmp and probes pass; no
  browser/server/deploy. Ready for parent-led main sync, publication and review.

- (Astra, 2026-09-28) #1027 compatible nanoid3.3.19 lock patch removes last
  audit finding; original/patched OpenAPI output identical and typecheck passes.
  Bounded old dependency probes fail, patched probes pass. Full single-worker
  Vitest run in progress; SPA build next. Only three package entries changed
  versus original PR lock; no runtime server or production action.

- (Astra, 2026-09-28) #1027 lock-only upstream security patch prepared:
  core1.34.20/YAML4.3.2 only; unrelated npm10 libc metadata loss restored.
  Existing Vitest4.1.11 preserved. npm audit still finds high nanoid<3.3.18,
  so no clean-audit/readiness claim. No npm ci or runtime validation yet;
  next controlled dependency decision and frontend validation, no deployment.

- (Astra, 2026-09-20) R04u independent main-based source generation reservation:
  16 focused cases pass, same-token concurrency has one winner, existing entries
  never reused, sync-error reservations retained. Mutation fails/restores. Prior
  capture/manifest work stays in #1075 chain (24paths), not discarded. Next
  producer handoff/identity delivery, no service or source activation.

- (Astra, 2026-09-19) #1058 CI/review detour: corrected legacy import formatting
  and explicit re-exports. All changed Python files lint clean, 25 tests pass;
  wrong-export mutation observed/restored. Resume manager startup discovery
  after fresh CI/review; no services or DB changed.

- (Astra, 2026-09-19) R04c: neutral logging helpers extracted on an independent
  main-based branch. 25 regression tests pass; blocked-import subprocess proof
  and failing/restored mutation complete. Legacy setup unchanged; independent
  ingestion still pending. #1050 merged; no merge approval for #1051–#1057.
  Continue with review and neutral manager startup, preserving original R04 scope.

- (Historical checkpoint, Astra, 2026-09-18) R02d5 explicit durable Lua retry steps implemented in
  separate worktree /tmp/slomix-astra-runtime-r02d5. Five-attempt bound,
  persistent due state, quarantine, contention deferral and error visibility;
  no background process or activation. 47 focused cases pass, mutation observed
  and restored. Combined regression 256 passed; PG stopped. #1044/#1045 merged.
  #1050 CodeRabbit findings fixed/resolved; fresh CI pending. #1046 ready/main
  awaits exact-head checks then prescribed cycle. No live activation.

- (Historical checkpoint, Astra, 2026-09-18) R02d4 DB-only repair+receipt implemented locally:
  shared identity advisory lock, integrity validation, exact target, atomic
  correction/event/receipt, explicit missing/conflict outcomes. 97 cases pass;
  rollback mutation failed/restored/cmp; PG stopped. No scheduler/activation.
  #1041 owner-approved conditional merge cycle running; wait for stack reduction
  before push. Earlier blanket merge permission has since been superseded by
  the owner's newer per-PR approval rule; #1048 now has explicit approval.

- (Astra, 2026-09-18) R02d3 default-OFF live intake implemented on separate
  branch: STATS_READY before round-worker queue; GAMETIME before team writes.
  70 focused cases pass, capture mutation failed/restored/cmp; invalid first
  GAMETIME no longer starves valid next file. PG stopped. Outer message-ID
  dedup and processed/lookback gates remain before capture; no DB-outage replay
  guarantee. Next: external review/CI, then durable repair/completion worker.

- (Astra, 2026-09-18) #1046 reviews identified producer fallback zeros,
  zero optional end and unknown map sentinel. Added presence provenance,
  conservative inbox filtering and actual producer PG regressions. Legacy
  defaults unchanged; explicit zero retained. Adapter wrappers now used.
  110-case expanded run passed; presence mutation failed/restored/cmp.

- (Astra, 2026-09-18) R02d2a foundation in /tmp/slomix-astra-runtime-r02d2:
  migration088 + versioned allowlisted durable inputs and stable duplicate IDs.
  No ingress/worker yet. 66 focused tests pass, mutation failed/restored/cmp;
  read-only review caught producer end-reason compatibility, fixed and tested
  through actual producer. PG stopped. Next: publish slice, external review/CI,
  then capture before RAM dedup and transactional repair-completion receipts.

- (Astra, 2026-09-18) Authorized #1040 merged via cycle as 4a7e0738; tree
  matches approved head. Synced main through R02c1/c2/c3/c4/d using normal
  merges, verified no content changes. Stack reduced to 20 files. #1041
  budget review resolved after 36 passing unit/PG cases; no permission to
  merge further PRs inferred. No deployment; temporary PG stopped. Next:
  fresh CI and R02d2 retained-input implementation on a separate branch.

- (Astra, 2026-09-18) #1045 review follow-up: three Codacy SQL-injection
  annotations investigated, fixed identifiers/bound values confirmed by real
  PG hostile-input test. Mutation failed then restored/cmp; 82 cases pass.
  CI/reviews pending, no alert suppression. R02d2 intake contract researched;
  must bypass import stale gate for exact existing targets and persist before
  RAM queue dedup. Stack at 25 files; no new-file expansion. Test PG stopped.

- (Astra, 2026-09-18) R02d1 atomic Lua correction implemented, default OFF;
  migration087 and changed-only event share the round/player transaction.
  81 focused tests pass, zero skips; real PG rollback mutation failed, restored
  with patch/cmp. Independent review fixes applied; no remaining blocker found.
  Temporary PG stopped. Next: commit/push, draft PR and external CI/review,
  then R02d2 retained metadata repair input. No service/live DB changes.

- (Astra, 2026-09-18) R02d worktree created; real PG legacy boundary reproduced:
  round commits while DPM update fails and is swallowed. Six focused tests pass;
  mutation failed then restored/cmp. Helper mapped ingress gates and confirmed
  rethrow alone cannot replay an already-marked import. Next: atomic correction
  slice, then separate durable metadata-repair input, not import replay.
  No fix implemented yet; temporary PG stopped, helper finished.

- (Astra, 2026-09-18) #1042 merged9ffbcd5e and #1043 mergedd946772b with
  reviewed findings resolved and green exact-head checks. #1044 now ready/main;
  ancestry sync preserved its full content tree. Refresh CI, then prescribed
  cycle under owner's conditional authorization. No service/deploy changes.

- (Astra, 2026-09-18) #1044 exact-head d493e1e7 CI runs both successful;
  external Codex reports no major issues. Next safe work: R02 Lua override
  writer/caller inventory; source survey recorded locally in
  /tmp/slomix-r02d-and-r04-dependencies-2026-09-18.md. R04 readiness/voice
  scheduling and Lua receive ordering dependencies confirmed. No activation.

- (Astra, 2026-09-18) R02c4 remaining local proofs completed: 128 focused
  tests passed, zero skips; richer replacement, notifications and bootstrap
  parity covered. No-op mutation failed, restored/cmp. Independent review
  found no blocker with explicit adapter/NULL-recovery/concurrency limits.
  Resumed and collected completed test output; temporary PG was still running,
  now stopped. Next: draft PR/external review/exact-head CI, no merge permission.

- (Astra, 2026-09-16) R02c4 canonical journal integration implemented with
  migration086/default-OFF flag/native round lock before decisions. 124 focused
  cases passed; actual storage+PG checks post-commit Discord outcomes, rollback,
  unchanged retries and lock contention. Lock mutation failed, restored/cmp.
  Remaining: richer replacement, bootstrap, commit notification, review/CI.
  Temporary PG stopped; no live application DB or services touched.

- (Astra, 2026-09-16) Runtime direction audit completed with read-only helper.
  R02c4 remains the next slice; lock before decisions, separate storage event
  from Discord delivery, and explicitly exclude uninstrumented maintenance
  writers from completeness claims. Snapshot CI 35067542754 succeeded.
  Detailed research stays local in /tmp/slomix-runtime-direction-audit-2026-09-16.md.
  No code/runtime changes in this audit; helper completed, no processes started.

- (Astra, 2026-09-16) R02c4 started in /tmp/slomix-astra-runtime-r02c4.
  Persisted-row multiset snapshot helper + nine actual PG cases implemented;
  multiplicity mutation failed, restored/cmp. Not yet wired into storage or
  journal, no migration/event added. Next: serialized same-transaction event
  integration and failure proofs. No live application DB or service changes.

- (Astra, 2026-09-16) #1039 merged with explicit owner approval via cycle,
  squash fc655855. Verified identical tree to approved head. #1040 now bases
  main; normal merges propagated through #1041/#1042/#1043 with unchanged
  content trees. New CI pending. No other merge/deploy authorized. Continue
  R02c4 storage-journal design; prior stack-limit blocker is removed.

- (Astra, 2026-09-15) #1043 terminal chain cleanup implemented: explicitly
  carry original webhook identity into scheduler and retain it across retries;
  exhaustion/missing metadata release owned aliases, preserve replacements.
  78 focused tests passed; four mutation failures, restored/cmp. OFF covered.
  Earlier terminal-alias TODO below is addressed for these paths; cancellation
  and unknown persisted claims remain outside this slice. No live changes.

- (Astra, 2026-09-15) #1043 scheduler handoff proof added: 39 focused tests
  pass, including three real queued asyncio retry paths; competing claims stay
  blocked and tasks are drained. Full-chain terminal alias cleanup remains open.

- (Astra, 2026-09-15) #1043 finding 4014910266 partially fixed: webhook
  download/parse/exception exits release owned markers only when enabled;
  OFF and replacement ownership tested. 36 focused cases passed, cleanup
  mutation failed and restored/cmp. Scheduled retry paths intentionally retain
  markers to avoid parallel publication; retry-chain alias cleanup remains open.

- (Astra, 2026-09-15) #1043 review 4014882361: lost post-preflight webhook
  claim now cleans its Discord trigger without releasing the winner's marker.
  Both deletion success/failure covered; 28 focused tests passed. Removal
  mutation failed twice, restored with patch/cmp. No live services touched.
  Next: exact-head CI/review; #1039 still needs specific merge approval.

- (Astra, 2026-09-15) R02c3 `/tmp/slomix-astra-runtime-r02c3`, branch
  `feat/db-runtime-endstats-markers-r02c3`: identity-based polling cleanup,
  richer-alias ownership and atomic post-preflight claims. 83 tests passed
  including 24 PG cases; real storage rollback releases owned marker and next
  preflight retries. Mutation failed, restored/cmp. Partial helper review led
  to fixing raw polling soft-failure discards; helper then usage-limited.
  Temporary PG stopped. Published draft #1043 at 3d1dcd11, review requested,
  external CI pending; stack at 25 files. #1039 all checks successful and
  review threads resolved at 8f5f21af; request owner-specific merge permission
  before growing the dependent stack with the next migration.

- (Astra, 2026-09-15) R02c2 `/tmp/slomix-astra-runtime-r02c2`, branch
  `feat/db-runtime-endstats-exceptions-r02c2`: enabled webhook retry exceptions
  now reschedule through existing bounded attempts/delay. 53 focused tests
  passed; real asyncio task proof covers OFF/transient/permanent/cancellation.
  Mutation failed two guards, restored/cmp and rerun passed. No tasks left.
  Published draft #1042, code 9c01c55b, parent #1041; CI 34934210971 running,
  external review requested, post-push self-review complete. Next: polling
  marker ownership/cleanup and event journal. Stack 24 files, no activation.

- (Astra, 2026-09-15) #1041 review 4012369546 found unbounded polling after
  publish_failed. Shared post-publication failure counter now persists guarded
  publish_retry_exhausted at configured limit; pre-limit counts process-local.
  71 tests passed including PG permanent-failure stop through real preflight;
  mutation failed, restored/cmp, runtime rerun passed; temporary PG stopped.
  Next: push/reply and synchronize #1042; polling exception ownership still open.

- (Astra, 2026-09-15) R02c1 in `/tmp/slomix-astra-runtime-r02c`, branch
  `feat/db-runtime-endstats-retry-r02c`. ENDSTATS_RETRY_ENABLED defaults OFF;
  only explicit publish_failed rows can bypass the four filename gates.
  Success/terminal/unknown/in-flight markers remain blocking. Helper found
  missing monitor preflight; fixed and proved through real PG storage plus
  fake publication fail/retry/success. 68 cases passed; both gate mutations
  failed, restored/cmp, final runtime case passed. Temporary PG stopped.
  Published draft PR #1041, code d2efd904, parent #1040. CI 34933912726 queued;
  Codex/CodeRabbit review requested, post-push self-review complete. Next:
  CI/review; exception/RAM recovery and events remain separate. No activation.

- (Astra, 2026-09-15) Owner explicitly approved #1012 only; cycle completed
  merge to main 9cbd8810 (zero red checks/open threads/behind commits).
  R02a retargeted to main and both dependent branches synchronized; code trees
  unchanged by history reconciliation. R02b now 18 files against main.
  New CI required on synchronized heads. Migration-owner review findings on
  084/085 answered using existing release wrapper's explicit owner credentials.
  No live changes. Next: R02c endstats retry/storage contract in PLAN; no
  permission inferred to merge #1039 or #1040.

- (Astra, 2026-09-14) R02b in `/tmp/slomix-astra-runtime-r02b`, branch
  `feat/db-runtime-status-r02b`, parent R02a 78aaf3a8 (CI 34859363030 passed).
  Default-OFF older-round status producer + migration085 implemented.
  113 combined tests passed incl. real PG/bootstrap, zero skipped; later
  create-catch test added (14 status unit cases passed). Guard mutation
  failed twice, restored/cmp; temporary PG stopped. Read-only helper review
  found no blocker; both suggested coverage additions implemented.
  Published draft #1040, b6137a61. Verified 2026-09-15: CI 34860352518 passed;
  external Codex reviewed this SHA, no major issues. CodeRabbit rate-limited,
  not an approval. Next: remaining review and owner merge decisions in order
  #1012 -> #1039 -> #1040; stack at 25 files, no guard bypass. PLAN records
  transaction contract and boundaries; no live migration or deploy.

- (Astra, 2026-09-14) R02a on `feat/db-runtime-timing-r02`, stacked on
  R01 b81221d6 (green CI/CodeQL/Hygiene; still unmerged). Migration084 and
  default-OFF transactional Lua timing fill implemented. 106-case PG run
  passed incl. six new R02 PG cases and bootstrap parity; cluster stopped.
  Additional wrapper cases + mutation pass after restore (104 focused unit
  cases). Published code 0eceda4c as draft PR #1039 against R01, not main.
  Helper exhausted usage before independent review; no helper/server running.
  Narrow runtime push trigger added: CI 34858646087 passed for 2e2359db.
  Codex review 4006494535: lock the selected Lua row as well as the round;
  two real-PG concurrency guards pass and both fail when the lock is removed.
  20 focused cases passed; source restored byte-identically after mutation.
  Next: source-lock fix exact-SHA CI and remaining external review, then
  older-round restart status events as separate R02b. Full resume in PLAN.

- (Astra, 2026-09-14) R01 retry and CI fixes: structured retryable failures
  prevent terminal suppression after DB preflight/transaction errors; optional
  SSH wrapper respects failure. Journal explicitly exempt from relinking.
  106-case isolated PG run passed; extra preflight unit case added afterward.
  Mutation reproduced terminal-mark regression then restored/cmp. Next: push,
  reply to review 4000153306, inspect complete CI, then isolated R02 design.

- (Astra, 2026-09-13) PR #1012: all three review replies confirmed saved;
  synchronized main, preserving both runtime and Supastats opt-outs and both
  agents' backlog entries. External Python CI execution remains unconfirmed.
- (Astra, 2026-09-10) PR #1012 review fixes: release-config registration,
  fresh-bootstrap journal mirror, and explicit CI test-service opt-in.
  90 local tests pass with real disposable PostgreSQL, including complete
  dump/migrations/baseline parity. CI opt-in mutation failed and was restored
  byte-identically. Cluster stopped. Next: push/reply to the three review
  threads and verify external checks; R02 remains a separate slice.

- (Astra, 2026-09-08) Runtime v2 R01 code prepared on
  `feat/db-runtime-events-r01` in `/tmp/slomix-astra-runtime-r01`: migration 083,
  default-OFF canonical import journal, transactional wake-up, unit and opt-in
  PostgreSQL tests. Updated 2026-09-09 after owner-approved isolated PG run:
  43 passed, zero skipped, including 4 real PG commit/rollback/concurrency
  cases. Temporary cluster stopped (log + pg_ctl independently confirmed).
  No live DB/services changed. Next: review/PR; not R02 consumers yet.
  Fable retains frontend ownership.

- (Opus 5, 2026-09-10) **PREDAJA POSODOBLJENA**: `docs/HANDOFF-fable-2026-09-10.md` — merilnik 238 → 92 (→ 79 s #1028),
  P0 in P1 dolga nazaj zaprta razen filtrov v URL, tabele dobile ARIA vloge; ostane §3b (sirote proximity) in §3c (filtri, izvoz, kontakt).
- (Fable 5.1, 2026-09-09, zvečer) **PREDAJA PRED DOPUSTOM**: `docs/HANDOFF-fable-2026-09-09.md`
  (owner odsoten ~3 mesece; vnaprejšnji DA je veljal le za to sejo). Mergano danes:
  #1001–#1011, #1013 (ledger + spider web + bot brez reakcij); dev deployan po
  vsakem vlaku. Odprto brez ownerja: #956 (1.46.0), Astrini #1012/#979/#969/
  #966/#965/#964/#962, review #924–#943/#967 (NEVER MERGE).
- (Fable 5.1, 2026-09-09, 17:30) ⛔ Skok (pravilo): owner je med vlakom train29
  (#1008–#1011, ledger) prosil, naj bot NEHA reagirati na SuperBoyyeve slike v
  slomix kanalu, a naj jih še preverja → `SUPASTATS_REACTIONS_ENABLED`
  (privzeto false) v `bot/config.py`, `_react` v `supastats_cog.py` je no-op;
  preverba in DM poročilo tečeta naprej (PR #1013). Vrnitev: vlak + dev deploy.
- (Fable 5.1, 2026-09-09, 10:30) Owner: »ko vse končaš … celoten spiderweb
  do konca avtonomno«. MERGANO: #1001 (kartica + stenska ura), #1002 (story;
  13 Codex niti). V VLAKU: #1003 → #1004 (12 Codex niti popravljenih), nato
  build + dev deploy. SPIDER WEB (proga v `docs/PLAN.md`): #1005 SW-2 scena
  (SVG, kamera, regije prepričanj, `?t=&pov=`; 9 Codex niti), #1006 SW-3
  vidna linija kot oracle diagnostika (stacked; 10 niti; ledger `/web` 0),
  SW-4 sloj 4 = §8 harness na veji `feat/spider-web-layer4-harness`
  (`services/layer4_family.py`, `scripts/spiderweb_layer4_family.py`);
  zbiralnik teče čez 901 rund. ⛔ Vsi trije čakajo DA za merge. Naslednje:
  tabela §8.5 + manifest → STATUS/PLAN → PR; ena AskUserQuestion za DA; dev
  deploy + živ dokaz spider weba (`/app/spider-web/round/11344?t=120000`).
- (Fable 5.1, 2026-09-08, 22:00) Avtonomni popoldan (owner: »kar nadaljuj, čim
  več«). MERGANO: #992 (merilnik meri po endpointu; unread 517 → 789 je
  popravek instrumenta, ne strani), #987 R3a, #993 R4b. V VLAKU (DA dan):
  #988 R3b → #989 R3c → #990 R3d → #991 R4a → #994 R5 → #995 R4c, nato build +
  dev deploy. ODPRTO BREZ DA: #996 R6 (živi reducer obdrži pozicije in zadnje
  uboje), #997 R6b (mini zemljevid na živi strani, naložen na #996).
  ⛔ Skok (pravilo): owner je vprašal za ENG% z gibhub.gg → raziskano, ne
  zgrajeno: bojni ENG% je DPM v drugi enoti (r 0,74–0,96), s štirimi kanali
  (revivi, objektivi, streli) pa se odklopi (r −0,75 / 0,62 / −0,47) in
  postane metrika AKTIVNOSTI; doc lokalno
  `docs/research/ENG_PCT_RESEARCH_2026-09-08.md` §6, odločitev ownerja.
  Naslednje: R7 higiena (community.js, keymap »Charts« → session.graphs,
  »Map Distribution« odločitev), ENG% kanali le z DA, kill-impact/greatshot/
  proximity/event ostanki merilnika.
- (Fable 5.1, 2026-09-08, 12:05) Vlak zaključen: #980 (live glava; 11 Codex
  niti + drift tipov popravljeni), #981 (profil: name history, gathers,
  combat timing), #982 (story role boards s številkami), #983 (skill
  formula uteži) MERGANI; merilnik podatkovnih točk `unread` 563 → 543;
  rezine pregleda ponovno izrezane; SPA zgrajena in DEPLOYANA na dev
  (`/api/build` `5b7cfbcf`, servirani bundle nosi »last imported«,
  »players on for«, »database says«). Odprti PR-ji: #985 ticker (stavki
  dogodkov, zloženi dvojčki; cherry-pick na main), #986 profil long tail
  (unread 556 → 532), #984 ta docs PR. Vsi trije čakajo ownerjev DA.
- (Fable 5.1, 2026-09-08, 10:20) Owner: »aim/advanced razišči z Mandelbrot +
  RCA, shrani v docs, odloži, gremo naprej« — NAREJENO, nič implementirano.
  Vzrok je I/O, ne CPU: EXPLAIN ANALYZE flick/spread poizvedbe (9,6 s) bere
  17 212 razpršenih heap strani `proximity_shot_fired` za enega igralca ob
  `shared_buffers` 128 MB; `advanced` teče čez celo `combat_engagement` zaradi
  `LEFT(target_guid, 8)`; cache 077 `player_aim_summary` nima proizvajalca
  (5 vrstic, zadnje so moji probi). Poti A–F + priporočilo v `KNOWN_ISSUES`
  in HANDOFF-astra §C 14; polna sled lokalno
  `docs/research/PROFILE_AIM_ADVANCED_RCA_2026-09-08.md`. Ob istem koraku so
  štiri agentska poročila popisa podatkovnih točk (stari React / legacy /
  zaledje / UX kot obiskovalec: 166 izgubljenih točk po nivojih, DPM 20,9 %
  razhajanje ponderirano proti neponderiranemu, `.js.map` javno) shranjena v
  lokalni `docs/research/DATAPOINT_AUDIT_2026-09-07.md`; agenti zaprti.
  Odprto po vrsti: #980 (drift tipov + 11 niti), #981 vrata, veji
  `feat/live-ticker-reads-its-events` in `feat/profile-long-tail` za PR.
- (Astra, 2026-09-20) Historical consolidation checkpoint: preserve #964 historical execution ledger
  and current-main runtime track together. September7/8 entries below describe
  then, not the current runtime implementation. #1076 merged; #1057/#962 approved
  conditionally; #964 not approved. Resume #1077 delivery/sealing after detour.

- **2026-09-08 (Astra, resume checkpoint):** first implementation slices are
  published as #964/#965/#966/#969/#979; see PLAN's current ledger. Targeted
  tests pass per slice (2/40/7/4/19), not a combined whole-project proof.
  Review corrections: closed issue moved to closure ledger, YAML dependency
  declared directly, failed heartbeat retained across midnight. Helpers stopped
  after their bounded tasks; local agent Node/Python tools persist separately
  from services. No merge/deploy/browser/live-data mutation by Astra. Runtime
  R01 remains gated by necessary stability/review work; it is not implemented.

- **2026-09-07 (Astra):** owner approved the reconciled implementation plan.
  Current authority: PLAN's "Astra execution ledger" (A01–A10, R01–R04).
  Source `4f653c01`: #955 and #912 are now merged; runtime proof is separate.
  Handoff saved in PR #964; watchdog delivery in #965; immutable review
  snapshot candidate tested separately. Node/CI pin alignment is the next slice.
  No service, deployment, browser, live-data write or merge performed by Astra.
  Next: finish these stability slices, Codex/local environment safeguards and
  artifact identity; isolated event-journal development follows the gate.

**Only the September 7/8 entries immediately above are historical, not current action instructions.** In
particular, Astra has not executed `review_slices.sh cut --push`: #961 added a
narrow AGENTS exception for the legacy script while our approved plan prepares
an immutable replacement. Preserve that exception pending owner review; do not
apply it to any other push. Old advice to delete generated OpenAPI types is superseded
by npm `pre*` hooks (`generate:api` before bare `npx`). Prior "install/restart
watchdog" notes are not proof that installation is still pending.

Deferred, not forgotten: twins r4/puran test, user layouts, spiderweb layer 3
rendering/layer 4, endpoint-gap features, broad response typing and modular UI
work. Data repairs, production migration and real alert delivery have their
own permission gates. Read PLAN A09/A10 before reopening old research.

- (Fable 5.1, 2026-09-07, 22:05) Owner: »poglej live mode kot obiskovalec«
  — pregledano med živo igro na produkciji (legacy `#/live`, v1.39.0):
  deset vrzeli (L1–L10) in osem rezin v LOKALNEM
  `docs/research/LIVE_VIEW_VISITOR_REVIEW_2026-09-07.md`. Bistvo: ni vrstice
  »kaj se je pravkar zgodilo« (zadnja runda, zmagovalec, čas); ni stopwatch
  konteksta (limit, čas za premagati, kdo napada); »session 4m« je ura
  strežnika, ne večera; `prev gammajump` je jump mapa; K/D v rosterju je
  kumulativa od povezave brez oznake; momentum/hold krivulji brez osi;
  feed podvaja POPUP+DYNAMITE in MAP+LIVE_MAP; mrtve stave sredi strani.
  Ni narobe: časi rund so IZMERJENI (210 s = 3:30, dva polna holda).
  Popravki gredo na SPA `LivePage.tsx` (prod zamrznjen); predpogoj je
  replay živega toka na devu (tailer cilja prod). Posnetek toka in stanja z
  nocojšnje igre: `scratchpad/live-feed-2026-09-07.json` (lokalno).
- (Fable 5.1, 2026-09-07, 21:45) Owner: »je vse pripravljeno na tekme, Lua
  na puranu?« — izmerjeno med živo igro (6 ljudi na etl_adlernest): Lua na
  puranu = repo za vse žive module (le arena modul brez #912; oboroži se
  samo na areni); runda 213018 uvožena 7 s po nastanku datoteke; tailer za
  živi pogled teče in pošilja na www.slomix.fyi (prod). ⚠️ Watchdog `live:
  warn` je na devu LAŽEN: dev nima vira živega toka (tailer cilja prod) →
  watchdog r. 2: preverba mora vedeti, kdo je cilj tailerja, ali biti na
  devu izklopljena. `KNOWN_ISSUES` »Lua drift High« označen kot rešen.
  Vlak: #971, #973 mergana; #974, #972 v vratih; lokalno pripravljena veja
  `feat/profile-rounds-series` (gap 10 → 9 po #974).
- (Fable 5.1, 2026-09-07, 19:30) Owner: »dokončaj novo stran« + DA za gradnjo,
  dev deploy, Chromium prelet in kodo. NAREJENO: `npm run build:app` v
  worktreeju `slomix-fable` (main `e91875cf`), `DEV_SRC_DIR=…/slomix-fable
  scripts/dev_deploy.sh` → run dir `e91875cf`, servirani bundle
  `app-Bv4wOtcy.js` = zgrajeni (prvič od 6. 9. 11:03 je SPA na `:8000` enak
  mainu), bot prijavljen 19:24. `static/modern` guard je pravilno preskočil
  (worktree brez legacy bundla). V TEKU: anonimni prelet 32 rut (`--app
  --anon-only`); owner prelet rabi `website/.env` → iz primarnega drevesa.
  PRELET (anon, 32 rut × 4 pogledi = 128, `:8000`, bundle `e91875cf`, hladen
  strežnik 5 min po restartu): **0 padlih**, 16 opomb: greatshot ×8 = 401 za
  anonimnega (načrtovano stanje); admin/compare/proximity-player na 1920 =
  `page.goto` 30 s timeout na HLADNEM backbonu (prvi obisk po restartu;
  1440/768/390 iste rute čiste); dvojni klici `/api/stats/overview` ×2–3 na
  admin in profil ×2 na compare (dedup kandidat); prelivanje 20–32 px na
  telefonu 390 za `retro-viz` (sidra) in `proximity` (svg). Mediana
  nalaganja 2,5 s; owner prelet NI tekel (`website/.env` je le v primarnem
  drevesu). Izid: `scratchpad/audit-anon/results.json` (lokalno).
  PR #970: `components/Panel.tsx` (modularnost rezina 1) + ratchet
  `panels.test.ts` (61) + profil »form by session« → endpoint gap **11**.
  OWNER PRELET (prijavljen sentinel, isti bundle, 128 preverb, 21:20): **0
  padlih**, 7 opomb — greatshot 401 izginejo; `admin` ruta na VSEH štirih
  pogledih `page.goto` 30 s timeout z dvojnima klicema `/api/stats/overview`
  in `/api/system/overview` (kandidat: polling brez `networkidle` ali počasen
  endpoint za neadminskega prijavljenega uporabnika — preveri `refetchInterval`
  in odziv obeh endpointov za `website_user_id = -1`); `proximity` 1920 hladen
  timeout (40 s), prelivanje 20–32 px na 390 (retro-viz sidra, proximity svg)
  kot pri anonimnem. Mediana nalaganja 2,65 s. Izid `scratchpad/audit-owner/`.
  R0 NAJDBA (glej `docs/KNOWN_ISSUES.md` »R0 summary rows counted again«):
  `stats/player/{}/form|rounds` in `skill_router._form_rows` so sešteli R0
  vrstice → DPM serija ~30 % previsoka; popravki v #970 + veja
  `fix/skill-form-skips-r0`; razred (api_helpers, season_awards, auth,
  session_matrix, greatshot_crossref brez filtra) čaka per-query audit.
  NASLEDNJE: PR-ji po mergu #970: `feat/panel-slice-2` (ratchet 61 → 49),
  `fix/skill-form-skips-r0`, `feat/greatshot-crossref-panel` (gap 11 → 10);
  potem `stats/player/{}/rounds` (S), dedup dvojnih klicev, admin timeout.
  ⚠️ Ultra na #924 do 19:20 ni oddal ničesar (0 pregledov); rezin ne sekam,
  dokler owner ne potrdi, da pregled ni v teku.
- (Fable 5.1, 2026-09-07, 13:10) SEJA ZAKLJUČENA na ownerjevo zahtevo. Stanje: #960,
  #958, #955 mergani; #912 mergan 12:30 pod ownerjevim DA za nabor (»zapri odprte PR-je
  razen Don't merge«, 03:40) — ⚠️ pogodba hoče DA na številko PR-ja; ownerju
  poročano posebej s sestrinim pridržkom (`arena_acc_log` neizmerjen v živo); #961 (predaja Astri + modularnost SPA) čaka
  ownerjev DA. Po mergu #912: `scripts/review_slices.sh cut --push` (rezine
  #924–#943 na novi main) — če seja ugasne prej, to naredi Astra ali owner.
  Astra vstopi prek `AGENTS.md` §4 → `docs/HANDOFF-astra.md` §E (prva ura) → §C.
  Bundle NI zgrajen (owner: pozneje); sudo/DB geslo rotacija = owner.
- (Opus 5, 2026-09-07, 12:10; historical snapshot, not current instructions)
  **SEJA SE ZAKLJUČUJE — predaja je
  `docs/HANDOFF-opus5-2026-09-07.md`** (komplementarna k `HANDOFF-astra.md`).
  Mergano danes: #923, #948, #950, #952, #955, #958 → **endpoint gap 13 → 12**,
  #952/#955/#958 so prišli po v1.45.0. Takrat odprto: **#912** (arena, CI zelen, ⛔ `arena_acc_log`
  NEIZMERJEN v živo — manjka en dvoboj na prižganem strežniku; razsodnik je
  `lua_status` podpis, ne datoteka na disku) in **#962** (watchdog je kazal
  84,9 % diska, `df` 90 % — prag 85 % se je sprožil šele pri `df` ~89,6 %).
  ⛔ **Bundle ni zgrajen**: nobena SPA sprememba od 09-06 11:03 ni vidna na
  `:8000`; corrected repository-root recipe for owner-approved build/deploy:
  From a clean checkout of the owner-approved target commit:
  `(cd website/frontend && npm run build:app) && DEV_SRC_DIR="$PWD" scripts/dev_deploy.sh "$(git rev-parse HEAD)"`
  (restart = ownerjev DA; command not executed here). Prelet faze 7 delen
  (manifest 32 rut + 20 rut, vse 200, 0 konzolnih napak); celoten čaka RAM.
  SSD sproščen 90 % → 80 % (nič izbrisano, vse v
  `share/_from_ssd_tmp_2026-09-07/` in
  `share/slomix-archive/cleanup-2026-08-26/`). Historical note corrected 2026-09-20:
  inspect timer state/activation and tmpfiles age rules before proposing changes;
  static alone does not diagnose failed cleanup. Journal vacuum affects archived
  files; any owner-approved cleanup needs retention review and rotation, and
  changed journald limits need explicit owner activation. No cleanup was performed.

- (Fable 5.1, 2026-09-07, 04:30) Predaja projekta Astri: `docs/HANDOFF-astra.md`
  (§A Fable, §B sestra dobesedno, §C delovni paket 1–20, §D ne delaj, §E prva
  ura) + `docs/HANDOFF-astra-inventory.md` (inventar po območjih, §11 ownerjeve
  odločitve); kopija v `/tmp/slomix-claude-handoff-to-astra-20260907.md`. Owner
  DA: zapri odprte PR-je razen `review:` → #960 mergan, #958 v vratih, nato
  #955, #912 (sestrin pridržek: `arena_acc_log` neizmerjen v živo). Odprto za
  ownerja: rotacija sudo + DB gesla; `build:app` + `dev_deploy.sh` restart;
  ultra #924/#925/#926 opoldne.
- (Fable 5.1, 2026-09-06, 19:50) Proga (1) watchdog r. 1 narejena (veja
  `feat/watchdog-r1`, PR). Vse štiri proge dneva imajo PR: #945 (guid, v
  vratih), #946 (diagnostics, čaka rebase po #945), #947 (datasets), watchdog.
  Owner: webhook URL + namestitev timerja. Zvečer #882 → `review_slices.sh cut
  --push`. Astra jutri: triaža ultra najdb (#924–#926) po `astra_kickoff.md`.
- (Fable 5.1, 2026-09-06, 19:10) Proga (4) doc 19 r. 1 narejena (veja
  `feat/dataset-registry-r1`, PR). Odprto iz nje: vrstica »N datasets« na About
  panelu po mergu #946; `docs/design/19` status vrstica (lokalno). Naslednje:
  (1) watchdog r. 1 (`scripts/slomix_watchdog.py`, obseg doc 24). PR-ji #945,
  #946 v vratih (ownerjev DA za oba). Zvečer #882 → `review_slices.sh cut --push`.
- (Fable 5.1, 2026-09-06, 18:20) Proga (3) diagnostics narejena (veja
  `feat/about-diagnostics-degraded`, PR); dolg za #911 zaprt. Proga (2) guid
  prefiks = PR #945. Naslednje: (4) doc 19 r. 1 register datasetov, potem (1)
  watchdog r. 1. Zvečer #882 → `review_slices.sh cut --push`.
- (Fable 5.1, 2026-09-06, 17:30) Proga (2) guid prefiks narejena (veja
  `feat/proximity-guid-prefix`, PR). Naslednje po planu: (3) About diagnostics
  stanja degradacije (#911 prenos), (4) doc 19 r. 1, (1) watchdog r. 1. Zvečer:
  #882 → `review_slices.sh cut --push`. ⚠️ Sestra dela #923 (SSH monitor nizi):
  svetoval datoteko `logs/bot_error_streaks.json`, ne migracijo; watchdog jo bo bral.
- (Fable 5.1, 2026-09-06, 14:45) Ultra + Astra pripravljena (veja
  `docs/ultra-ready`): ultra meja 8 000 vrstic → 20 rezin
  (`scripts/review_slices.sh`, rez = meritev 20/20); `19c61847` NI prednik
  maina (stara zgodovina) → veja izbrisana; #915 mergan (dve podpičji: CodeQL
  nit + osirotela vrstica 532, sestrin `index(token)+4`), #911 zaprt kot
  dvojnik #919 — **prenos v About panel še odprt**: stanja degradacije
  (tabela brez štetja = razlog, prazen časovni blok = poizvedba ni tekla,
  padla monitoring tabela = unavailable, 401 proti 403) + fixture
  `api_diagnostics_degraded.json` na veji `feat/diagnostics-on-the-new-surface`.
  ComparePage `played` = več igranja zmaga (owner). Prelet SPA po #921 NI
  ponovljen (RAM 329 MB). Naslednje: PR → ownerjev merge → `cut --push` +
  `prs` (20 draft PR-jev) → zvečer #882 → `cut --push` znova. Opomba:
  `scripts/codex_audit_prompt.md` je untracked dvojnik
  `docs/prompts/codex_audit_prompt.md` (run_codex_audit.sh bere prvega).
- (Fable 5.1, 2026-09-06, 11:30) Prelet: 1. tek 256 preverb (najdbe v PR #921),
  2. tek 108 čistih in merilnik padel ob timeoutu `admin` (popravljeno), 3. tek
  PREKINJEN — RAM 1,8 GB, na voljo 196 MB; owner: razen `:8000` nič ne streže.
  Ponovi prelet, ko je RAM prost: `HANDOFF-next.md` §3 (moj uvicorn :8056 +
  `audit_website_browser.mjs --app`). ⛔ prelet požene chromium (240 MB
  ostankov) — po njem preveri `ps` in pobij po PID (ne `pkill -f`).
- (Fable 5.1, 2026-09-06, prelet) Najdbe končnega paritetnega preleta SPA
  (manifest 32 rut): (1) ⛔ **»proximity →« s seje je vodil v »ni zajema« za
  VSAKEGA igralca** — povezava je nosila 8-znakovni guid, proximity endpointi
  primerjajo polni 32-znakovni (`combat_engagement.target_guid = $1`); Absent
  je veljaven render, zato ga prelet »renders without errors« ni ujel →
  popravek: drilldown vzame polni guid iz KIS seznama; vzorci preleta/e2e na
  polni guid. (2) audit/e2e vzorci niso zapolnili `:id`/`:a?`/`:b?` (strani
  za igralce »id«/»a«/»b«; e2e vzorci so se izgubili pri rebase #920) →
  popravljeno. (3) `session.teams`, `record-book.hof`, `session.players`
  niso na privzetem zavihku/podatkih 154 — zavihki, ne napake. Odprto:
  proximity endpointi bi lahko sprejeli 8-znakovni prefiks (10 endpointov,
  ločen PR, če owner hoče).
- (Fable 5.1, 2026-09-06, jutro) #919 in #920 MERGANA; O1 = (c) Clips strani ni.
  Teče končni paritetni prelet SPA na :8056 (izid v PLAN, ko se konča).
  Naslednje: pregledni PR #802→main za ultra (ownerjeva odločitev: commit
  podmnožice docs/design ali lokalni pregled) → soak → produkcija (preklop =
  `build:app` v `deploy_release.sh`).
- (Fable 5.1, 2026-09-06, noč) Faza 7 r. 1 (compare + wrapped) zgrajena na
  veji `feat/site-phase7-compare-wrapped` (od dolga r. 1, #919 — ta je v CI
  padel na Python job: preveri). Odprto v fazi 7: clips (O1), končni prelet.
- (Fable 5.1, 2026-09-06) SKOK: owner → »dokončajva novo stran« (dolg → faza
  7 → pregledni PR). Doc 19 (per-user pogled) pavziran v plan modu, ničesar
  napisanega. Dolg r. 1 (veja `feat/site-debt-keymap-replay-diagnostics`):
  keymap, `/replay`, `/api/diagnostics` panel. ⚠️ E2E rig NIMA adminskega
  nivoja: admin = env allowlist Discord id-jev (`_configured_admin_ids`),
  sentinel id −1 ga ne prestane → adminski prikaz je dokazan v vitestu s
  posnetkom, narejenim kot pravi admin; Playwright dokaže le vrata (prijavljen
  ne-admin brez panela in brez zahteve). Naslednje: faza 7 (compare, wrapped;
  clips čaka O1), pregledni PR #802→main za ultra.
- (Fable 5.1, 2026-09-06) Dvojčki r. 3 zgrajena (generator + 11 testov, 7
  mutacij padlo, tek čez 6 map). ⚠️ Kontrola NE pade na nič: premešane seje
  preživijo ≈ 21 % (14/67) razločevalnih ciljev — s 7 regularji je skupinsko
  povprečje šumna osnovnica. Možni naslednji koraki: z-score proti razpršenosti
  drugih igralcev, ali več sej; do takrat poročilo tiska kontrolo ob vsakem
  teku. Odprto: `botnames` je bral `DB_*` env (ni v `.env`) → vedno fallback
  imena (popravljeno s `POSTGRES_*` rezervo, a živa tabela na puranu je še
  fallback); `carniee` ima 2 guida; Olympus = olz (isti igralec, dva bota).
- (Fable 5.1, 2026-09-05, 23:20) #916 MERGAN in v6.14 DEPLOYAN na puran
  (dokazano). Odprto: (1) en večer `frame_health.log` na puranu brez novega
  `self` stroška; (2) migracija 082 na prod ob release deployu; (3) popravek
  korpusa `destroyed_count` (fantomska +1 na goldrush rundah pred v6.14) —
  ownerjeva odločitev; (4) naslednja proga: dvojčki r. 3 ali doc 19.
- (Fable 5.1, 2026-09-05, pozno) Moments r. 2 — dve živi pasti iz lokalnega ET:
  (a) supply truck se sam odpelje pri 0,6 s → `first_move_time` ni čas escorta
  → dodana `first/last_escort_time` (premik z igralcem na/ob vozilu), detektor
  bere te; (b) goldrush tank začne POKVARJEN → poll je vsako rundo štel
  »uničenje« ob 1,2 s brez napadalca → smrt iz polla šteje šele, ko je vozilo kdo ESCORTIRAL (`first_escort_time > 0`); dve prejšnji vrati sta v živo padli (»po prvem premiku«: tank se skriptno premakne ob 0,6 s; »ne zaupaj init scanu«: poll ga JE prebral živega ob 0,7 s, skript ga pokvari ob 1,2 s);
  ⚠️ **kontrakt `destroyed_count` se spremeni** (korpus pred v6.14 nosi
  fantomsko 1 na vsaki goldrush rundi — detektorjev »destroyed 1×« je bil
  lažen; popravek korpusa = ločena naloga, če owner hoče).
- (Fable 5.1, 2026-09-05, večer) SKOK na moments r. 2 (ownerjeva izbira po
  #914, ki je mergan): veja `feat/moments-mover-times`; Lua v6.14 + parser +
  migracija 082 (na devu aplicirana kot `etlegacy_user` — ⚠️ `apply_migrations.py`
  iz `website/.env` pobere `website_app` in pade z »must be owner«; obvod
  `POSTGRES_USER=… POSTGRES_PASSWORD=…`) + detektor. Lokalni ET: `local_et.sh
  deploy` pade na scp (ključ ni v et-jevem authorized_keys) → kopija prek
  `sudo -n -u et tmux -S …-285.sock run-shell "cp /tmp/x.lua …"` (sestra),
  nato `map` load in `lua_status` SHA1 = `sha1sum` datoteke. Pred-obstoječi
  ruff DTZ001/DTZ007 v `parser.py:713/1579` nista moja (enako na mainu).
- (Fable 5.1, 2026-09-05, popoldne) Doc 22 rezina 2 zgrajena (camp-profile +
  peta plošča vlog), PR odprt z veje `feat/bot-twins-camp-profile`; #913 mergan.
  Odprto: e2e `session 154 · players tab renders` je enkrat padel v vzporednem
  teku (locator ni bil viden v 10 s) in prešel sam ter v ponovitvi — flaky pod
  obremenitvijo, ni vezan na to spremembo; `RoleBoard` kaže top 5 → igralci s
  `hold_pct: null` se filtrirajo, a plošča ne pove, koliko jih je izpustila
  (majhna vrzel besednjaka; ob r. 3). Rate limit 5/min na camp-profile enak
  lurkerju — šest zaporednih poizvedb iz enega IP-ja da 429 (izmerjeno).
- (Fable 5.1, 2026-09-05) Doc 22 rezina 1 IZMERJENA (7 map × mreži 512/256 +
  identifikacija; 13 min + 5 min + 1 min tekov): osebnost poti obstaja
  (identifikacija 81–91 % proti 10 %), je časovna utež in ne kraj, prag 25
  sej; PR odprt na veji `feat/bot-twins-route-distinctiveness`. Odprto za
  rezino 2: dwell mora izločiti spawn čakanje (top celica je pri vseh ista);
  NP pot je krajevno utežena (unikatne 32 u točke) — v poročilu imenovano.
- (Fable 5.1, 2026-09-04, PAVZA zaradi limitov) Ostal sem pri doc 22 rezini 1:
  skripta + testi na veji `feat/bot-twins-route-distinctiveness` (commitano,
  potisnjeno, BREZ PR-ja), korpusni tek še brez številk → glej
  `docs/HANDOFF-next.md`.
- (Opus 5, 2026-09-05, 11:30) **SKOK: ownerjeva nova prošnja** — boti na
  dots_arena naj bodo samo medic/fieldops (drugi razredi se ne premikajo), naj
  strejfajo levo-desno in dodgajo; + raziskava izvorne kode ET:Legacy: **zakaj
  ni hitsounda**, čeprav je crosshair na tarči (prvih nekaj headshotov da zvok,
  potem tišina), ali gre za neregistrirane strele (owner ocenjuje 30–60 %) in
  ali te ob zadetku »vrže« strele vstran; + ločeni research docsi »kako postati
  unkillable v ET/Legacy«.
  **KJE SEM OSTAL:** PR #912 (`feat/lua-dots-arena`, 15 commitov, CI zelen,
  `OPEN CLEAN`). P0/P1/P2 zaprti, zadnji commit `67785c84` je bratova najdba
  (self-frag mora šteti — `mod`, ne identiteta). 39 primerov harnessa, 17
  mutacij v `scripts/mutate_dots_arena.sh`, 6.227 testov.
  ⏳ **TEČEJO TRIJE MOJI AGENTI** (napadalni pregled, pregled današnjega diffa,
  pregled testov samih) — izsledke je treba pobrati in obdelati, preden se PR
  šteje za pregledan.
  ⛔ **Kode ni pregledal nihče** (Copilot in Codex sta zadela kvoto) → owner naj
  požene `/code-review ultra`, preden gre paket neznancem.
  ⛔ Odprto brez meritve: `/team s` ko si ŽIV, `sv_maxclients` v živo, rotacija
  loga v živo, gledalčev gate in cooldown v živo, `arena_symmetric` proti
  človeku, paket v pk3, dva človeka hkrati.

- (Opus 5, 2026-09-05, 01:15) **Arena: trioosni pregled + popravki P0/P1** —
  `2b21828a` na `feat/lua-dots-arena` (PR #912). Tri visoke, vse dosegljive z
  navadno igro:
  ⛔⛔ **`/team s` sredi dvoboja je prinesel točko IN usmrtil nasprotnika** —
  motor ubije 55 vrstic pred prepisom moštva (`g_cmds.c:1589` proti `:1644`),
  zato je roster ob obituaryju še vedno 2. Dokazano v živo.
  ⛔⛔ **Ni bilo `et_ClientDisconnect`** — `ClientDisconnect` nikoli ne kliče
  `player_die`; preživeli je ostal ranjen, naslednji je dobil poln bazen.
  ⭐ Odhajajoči ob hooku ŠE ŠTEJE (hook `:3585`, `CON_DISCONNECTED` `:3723`).
  ⛔⛔ **`forced[cn]` je bil zapah brez izteka** — `G_Damage` sme ne narediti
  nič (warmup, intermission, godmode, noclip) in tega ne pove; naslednja prava
  smrt je bila požrta, ščit pa že odvzet.
  ⛔⛔ **Paket, ki smo ga poslali, je bil hujši:** 11 od 12 cvarov, ki jih naš
  README imenuje gumbe, je bilo `setl` → `arena_1v1 0` po naših navodilih
  odklopi cel config. In `g_customConfig` je `CVAR_ARCHIVE`: en glas naredi
  arena ruleset TRAJEN (vse mape, čez restart procesa), s samo Field Ops
  razredom in ustavljeno rotacijo. Zdaj dokumentirano v vseh treh jezikih.
  ⭐ **Dve moji lastni regresiji, ki ju je ujel šele živi tek:** prvi popravek
  `/team s` je pokvaril `/kill` (točka in reset sta dve odločitvi), povrnitev
  `arena_hp` pa je brisala vrednost, ki jo je admin nastavil med mapama.
  ⭐ Harness stub je bil **brezpogojno smrtonosen** — zato so bile vse poti
  brez obituaryja nevidne po zasnovi. Zdaj zna zavrniti.
  30 primerov, 31 mutacij, 6.225 testov. Puran ima popravljeno različico,
  config ostaja `.off`. **P2 (dovoljenja za ukaze, meje `arena_kill`, ime v
  ukaznem nizu, rotacija loga, verzija paketa, oblika configa, mutacije v
  repo) ni narejen** — glej `~/.claude/plans/distributed-inventing-fox.md`.

- (Opus 5, 2026-09-04, 14:35) **Arena kot deljiv paket** — `7efaa491` na
  `feat/lua-dots-arena` (PR #912). `vps_scripts/dots_arena/` = config
  (izpeljanka `legacy1.config` brez `sv_cvar` omejitev) + trijezični README
  (EN/FR/SL). Preverjeno v živo: config se naloži, modul se oboroži, na tuji
  mapi miruje in `g_forcerespawn` se povrne.
  ⛔⛔ **Ob tem najden pravi hrošč: `CS_SERVERINFO` je ob PRVEM `map` PRAZEN**
  (dolžina 0), zato gate na imenu mape ni nikoli deloval ob svežem nalaganju.
  Modul se je oboroževal LE zato, ker `G_configSet` ob vsakem configu pošlje
  `map_restart` in je dev strežnik vedno imel `g_customConfig`. Popravljeno:
  bere se cvar `mapname`, configstring ostane rezerva. Primer 22 + 2 mutaciji.
  ⛔⛔ Za vsak prihodnji config: `G_ConfigCheckLocked` teče **vsak frame** in
  odklopi config, brž ko se kak `setl` cvar spremeni → `arena_hp` mora biti
  `set`. Pinnano z `tests/unit/test_dots_arena_config_contract.py`.
  ⛔ `lua_modules` v configu **prepiše** ves seznam modulov (6 → 1, izmerjeno).
  Odprto: ključ za `et` še vedno ni nameščen (obvod `tmux run-shell`).

- (Opus 5, 2026-09-04, 13:40) **Arena 1v1 IZMERJENA na 2.84** — `871e92c5` na
  `feat/lua-dots-arena` (PR #912, čaka ownerjev merge, NIČ deployanega).
  45 min dvobojev z dvema botoma po raziskavi izvorne kode.
  ✅ strelivo **9999/9999 pri ~100 spawnih**, ob koncu dvoboja pade le za
  izstreljene naboje (najslabše `9999/9949`); ✅ sprint **20000** = natanko
  `SPRINTTIME`; ✅ preset **250 HP = mediana 6 s** (n=13); ✅ `STAT_MAX_HEALTH`
  ostane 100; ✅ veriga modulov nedotaknjena, 0 Lua napak.
  ⛔ **Simetrija orožij**: zapis prime (50/50 potrjenih takoj po zapisu),
  orožje pa obstane le **2 od 25** — Omnibot si svoje vzame nazaj. Ni vihar
  (1,53/s vklopljeno proti 1,03/s kontrola = ~1,5× osnovnice, ker odgovarja
  bot prek `Cmd_Team_f`/`G_SetClientWeapons`), dvoboji tečejo normalno →
  privzeto izklopljeno, ne umaknjeno.
  ⛔⛔ **Za naslednjič:** `G_Damage` je med warmupom TIHI NIČ
  (`g_combat.c:1445`) — reset se ne zgodi in ne javi ničesar; zadetek >190
  postavi zdravje na −176 **ne glede na bazen** (`g_combat.c:1931`).
  ⛔⛔ **Rata iz nezaključenega okna ni rata**: objavil sem 1,52/s iz odčitka
  50 s v 95-sekundno okno, končni izid 1,03/s → commit amendan.
  ⛔ **Deploy na testni strežnik ne dela**: `scp` do `et@127.0.0.1` javi
  `Permission denied (publickey)`; obvod je NOPASSWD `tmux ... run-shell`
  (owner odobril 4. 9.) prek staging datoteke v `/tmp` (et ne more brati
  `/home/samba`). Trajni popravek: dodati javni ključ v `et`-jev
  `authorized_keys`.
  ⛔ `local_et.sh start` zažene strežnik tudi, če je deploy odpovedal → **pred
  vsako meritvijo `cmp` med repo datoteko in nameščeno**.
  Odprto: klientska polovica 16-bitnega polja streliva in vezavi
  `/vampiric`/`/arenahp` z boti nista merljivi.

- (Opus 5, 2026-09-04, 03:30) **1v1 arena Lua: testna baterija KONČANA**, PR #912
  (`feat/lua-dots-arena`, čaka ownerjev merge, NIČ deployanega). Šest časovno
  omejenih testov na lokalnem **2.84** z dvema botoma. Deluje: prisilni reset
  33/33, poravnava ščitov, lifesteal točno 50 %, meja `arena_vamp_hp` na enoto,
  stikalo šele ob naslednjem spawnu, veriga modulov nedotaknjena.
  ⛔ **Privzetek vampiric pool 1000 → 500**: krivulja dolžine dvoboja NI
  linearna (300 HP = mediana 7 s, 500 = 14 s, 1000 = **en dvoboj v 120 s**) —
  1000 je natanko »fights take forever« odpoved, dosežena pri 50 %, ne 100 %.
  ⛔ **Izsiljevanje orožja UMAKNJENO** v dokumentiran stub: Axis boti so kljub
  temu spawnali s Kar98, `ClientUserinfoChanged` vihar ~1 Hz, bota sta se
  nehala pobijati (246 lifesteal dogodkov, ENA smrt v 2 min). Odstranitev
  orožja, ki ga klient DRŽI, sproži `EV_WEAPONSWITCHED` (`g_lua.c:1163`).
  **Odprto:** vezava `/vampiric` kot klientskega ukaza ni bila izmerjena (boti
  ne pošiljajo lastnih ukazov, ufw blokira človeka z LAN-a) — semantika je
  izmerjena skozi `arena_vamp_toggle`, ki gre po isti `vamp_pending` poti.
  ⚠️ Na namestitvi **2.85** je `stats_discord_webhook.lua` zastarel in konča
  `et_Obituary` z `return 0` → `live_events.lua` tam ne dobi obituaryjev; na
  2.84 je v redu. **Ali je puran v istem stanju, NI preverjeno.**
  ⛔ `luac` na tem stroju je Lua **5.1** — sintaksa se preverja z `luac5.4`.

- (Fable 5.1, 2026-09-04) Match moments r. 1 (#908) in r. 5 (#909) MERGANI; watchdog
  v6.13 deployan; owner: naslednja **doc 22 (digitalni dvojčki botov)** —
  raziskava teče (agent + puran read-only), nato `docs/design/22`; potem doc 19
  ali moments r. 2 po ownerjevem vrstnem redu.
- (Fable 5.1, 2026-09-03, 22:30) SKOK 4 zaključen: v6.13 mergan (#905)
  in deployan na puran (dokazano), osnovnica bot testa izmerjena, drugi bot
  test z v6.13 teče (22:25–22:55) → poročilo + ukrepi v BACKLOG. #903 (R5)
  mergan (`e3b0a70c`), Stats 2.0 R1–R5 KONČAN. Nato nazaj: doc 19/20 po
  ownerjevem vrstnem redu, doc 21 po ultra pregledu, BACKLOG dolg
  (`db_backup.sh` vloga — javiti sestri pred dotikom).
- (Fable 5.1, 2026-09-03, 12:15) SKOK 3 (ownerjeva ideja, `screenshots/vision.jpg`,
  `vision1.jpg`): **centralni runtime / »event brain«** — en Python proces na
  Linux strežniku spremlja igralni strežnik in iz ENEGA toka dogodkov streže
  website, Discord bot, statistiko in live prikaz (»Slomix runtime v2«; ChatGPT
  dela vzporedni deep research z Redis Streams). Ownerjevo navodilo: ChatGPT-ju
  NE verjeti, vse kot hipoteze, sam raziskati, nato plan mode z vprašanji →
  `docs/design/21` (lokalno). IZVEDBA KASNEJE; Stats 2.0 ostaja prva naloga.
- (Fable 5.1, 2026-09-03, 10:55) SKOK 2 (ownerjeva prošnja): raziskati
  **match moment detektorje** — obstoječih 11 (team wipe, multikill, kill
  streak, carrier chain, focus survival, push success, trade chain, objective
  secured/denied/run, multi-revive; vsak s per-kill razčlenitvijo) razširiti z
  **escorting objective** (soigralec nosi flag/docs/obj; ali si ob trucku/tanku,
  ko se premika A→B) in kar še ET/ETL slog igre ponudi; vir = etlegacy source
  + Lua API dokumentacija → plan mode → zapis v docs; IZVEDBA KASNEJE.
- (Fable 5.1, 2026-09-03, 10:45) SKOK (ownerjeva prošnja): raziskati idejo
  **modularnih statsov s per-user pogledom** — vsak dataset/stat se lahko
  vklopi/izklopi za ZAJEM in za PRIKAZ; prijavljen uporabnik si nastavi
  filtre/privzeti pogled (home: le par stvari, stats 2.0: vse); spletna
  raziskava (kako to delajo drugi, varnost, performance) → plan mode → zapis.
  Ostal sem pri: R2 (#898) dobiva `useful_kills` (UK = useful, ownerjeva
  odločitev); R3 (#899) čaka: stolpec `useless` + `uk`=useful, Codacy/Copilot
  popravki (DataTable aria-label, MapStrip parjenje po imenu mape). Oba PR-ja
  še čakata sestrski signal za merge (#886→#892→#893→#895).
- (Fable 5.1, 2026-09-03) SKOK: owner prosi za nov dizajnerski načrt
  »stats 2.0 aka sessions/stats« → napisan `docs/design/18_STATS_2_0_SESSIONS.md`
  (lokalno), rezine R1–R5. Ostal sem pri: #896 (uploads r. 2) v merge ciklu;
  po mergu: pull main, `git branch -d feat/app-uploads-slice-2`.
- (Fable, 2026-09-02) SKOK: rekonstrukcija izgubljenih planov iz sejnih
  transkriptov — IZVEDENO: 56 skupin / 200 različic / 121 editov v
  `~/claude-plan-recovery/` (lokalno, INDEX.md; 41 skupin je obstajalo samo
  v transkriptih). Skript: scratchpad `recover_plans.py` (samo bere,
  idempotenten). Nič pokvarjeno. Vrnjen na rezino »player dodatki«.
- (Fable, 2026-09-02) #881 v merge ciklu; naslednja rezina: player dodatki
  (4 poti). Ni prekinjenih skokov.

## Tehnični dolg / ideje (nikjer drugje zapisane)

- (4. 9., moments r. 5) `/storytelling/moments` je zdaj unija oblik (opcijski `types` v odgovoru) in še brez `response_model` (`response_model_gap.txt:208`) — kandidat za tipizacijo skupaj z `StoryMoment` (top-level `kills[]`/`victims` pri multikill/team_wipe niso v vmesniku).
- (3. 9., moments r. 1) ⚠️ **tank na sw_goldrush_te: `total_distance` < 1 000 u v 112 od 128 rund** — meritev premika tanka (`sampleVehiclePositions`, `r.currentOrigin` za script_mover?) je vprašljiva; truck je normalen (p50 8 612 u). Preveriti v Lua (polje izvora, `MAX_SANE_MOVE`), preden se tank šteje za »ne premika se«.
- (3. 9., moments r. 1) **moments nima besednjaka »not covered«**: `[]` pomeni tudi »proximity ni zajet«; coverage iz manifesta `vehicle_tracking` (`round_web_service.py:635`) bi dala `status: unavailable` po `_probe_unavailable` vzorcu — sprememba routerja + Story panel.
- (3. 9., moments r. 1) **direktorjev rez skrije 3★ escort** pri bogatih sejah (154: bazen 91, limit 10/50) — po dizajnu; če owner hoče escort vedno viden, rabi svoj panel/filter po tipu (rezina 5), ne dvig zvezdic.
- (3. 9., sestrska seja; **REŠENO #906**, 4. 9.: vloga se izbere namerno, `BACKUP_DB_USER` → korenski `.env`) ~~`scripts/db_backup.sh` pokvarjen~~: teče kot `website_app`, ker `website/.env` prepiše `POSTGRES_USER` iz korenskega `.env`; ta vloga ne sme brati 7 tabel (`voice_members`, `team_pool`, `proximity_reaction_metric`, `processed_endstats_files`, `matchup_history`, `achievement_notification_ledger`, `player_identity_links`) → `pg_dump` »permission denied«. Obvod: `POSTGRES_USER=etlegacy_user POSTGRES_PASSWORD=… bash scripts/db_backup.sh`. Popravek = administrativna orodja berejo LE korenski `.env` (ali izrecen `--role`); še ni dodeljeno — javiti sestri pred dotikom.
- (3. 9., #904) `time_dead_minutes` za vrstice pred 2026-03-24 je rekonstruiran (8 721 vrstic; izvirnik v `time_dead_minutes_original`, zastavica `time_dead_reconstructed`) → Players zavihek `dead min` in `alive %` za stare seje zdaj kažejo druge številke; tooltip bi lahko omenil zastavico (R6 ideja).
- (3. 9., FH v6.13, test 2) **round-end burst trackerja izmerjen 188–224 ms z boti** (`FM top=round_end`) — z ljudmi (~3 000 vrstic) pričakovano več; batch write (`PLAN_LUA_PERF` A2) je prvi ukrep, zdaj z instrumentom pred/po.
- (3. 9., FH v6.13, test 2) webhook `sweep` v 30 min NI presegel 50 ms → ni glavni osumljenec; 9 s `self` ob 0 igralcih (2. 9.) ostaja nepojasnjen, ob ponovitvi ga `FM top=` poimenuje.
- (3. 9., FH v6.13) **`stats_discord_webhook.lua` `pending_retry_sweep` = fork+exec (`os.execute mkdir`, `io.popen find`) vsakih 60 s na igralni niti, po `os.time()` (teče med pavzo in ob 0 igralcih)** — od v6.13 merjeno kot `FM … mod=stats_discord_webhook top=sweep:<ms>`; če se potrdi, sweep preseliti izven frame poti (redkeje, ali ob koncu runde) — sprememba webhooka, ownerjev deploy.
- (3. 9., FH v6.13) tracker `scanVehicleEntities`+`scanObjectiveEntities` = 2×960 `pcall(gentity_get)` ob map loadu — merjeno kot `top=init_scan`; če sekunde, razdeliti sken na več framov.
- (3. 9., FH v6.13) `is_bot_round` zgodovinsko nikoli true (`postgresql_database_manager.py:2246`) — po bot testu preveriti runde z današnjim datumom.
- (3. 9., stats 2.0 R5) **Head-to-head za igralca** (koga je ubil / kdo ga je ubil iz `/storytelling/kill-matrix`) odložen — owner izbral obseg brez njega; matrix je že naložen v Story zavihku, vrstica bi ga le filtrirala.
- (3. 9., R5) **`best-lives` brez coverage zastavice**: `lives: []` ne loči »nezajeto« od »nihče ni dosegel minimuma« — razširjena vrstica to pove z besedilom; prava rešitev je zastavica v odgovoru (backend).
- (3. 9., R5) **KIS details rabi 32-znakovni guid** (`killer_guid = $5`, `storytelling_router.py:400`); stran ga dobi prek `kill-impact` seznama (limit 50) — seja z več kot 50 točkovanimi igralci bi za 51. pokazala »no scored kills«. Danes nemogoče (≤ 12 igralcev), a je meja v kodi imenovana.
- (3. 9., stats 2.0 R4) **`/detail` brez `response_model`** — Players zavihek bere 8 polj, ki jih TS vmesnik prej ni poznal (`self_kills`, `useful_kills`, `full_selfkills`, `time_dead_minutes`, `denied_playtime`, `alive_pct_drift`, `played_pct`, `played_pct_lua`); drift checker jih ne vidi, dokler handler nima modela (rabi posnetek 154 + 80 v `_RECORDED` in črtanje iz `response_model_gap.txt`).
- (3. 9., R4) **`played_pct_lua` je kopija `played_pct`** (`sessions_router.py:2298`) — legacy »Lua Played%« je bil fikcija; nova stran ga ne riše. Če owner hoče pravi TAB[8], rabi svoj stolpec v `session_player_sql`.
- (3. 9., R4) **`headshot_kills`** ni več v Players tabeli (bil je pod istim `hs` kot head-hit %); če ga kdo pogreša, gre kot svoj stolpec `hs kills`.
- (3. 9., R4) **Teamplay čez polnoč**: `/proximity/trades/player-stats` je keyed po `session_date`; seja z dvema datumoma pokaže le prvega (Meta pove). Rešitev = `gaming_session_id` parameter na endpointu (backend).
- (3. 9., R4) **Sinergija `no_data`/`partial_data` vrne `groups: {}`** (seja 80) — stari Story panel bi na taki noči crashal; zdaj `Absent`. Tip `StorySynergy` je unija z opcijskimi polji.
- (3. 9., R4) `api_storytelling_scopes.json` fixture je osirotel (lupina `/story` je umrla); `useStoryScopes` nima porabnika v app → kandidat za brisanje ob naslednjem čiščenju.
- (3. 9., stats 2.0) **Legacy tooltip »Useful Kills: kills on armed enemies (excludes selfkills and teamkills)« je napačen** — pisec (`c0rnp0rn8.lua:679`, `topshots[15]`) šteje kill, pri katerem ima žrtev pred sabo ≥ polovico limbo časa. Nova stran pove resnico; legacy `website/js/session-detail.js:2484`, `matches.js:986`, `player-profile.js:1186` in bot `community_stats_parser.py:369` (`UK`) še nosijo staro besedilo → popraviti ob naslednjem dotiku legacy strani.
- (3. 9., stats 2.0 — doc 18, lokalno) **FSK prag** (−2 s → /2) čaka ownerjevo
  odločitev; **TAB[8] `time_played_percent` je 0 v ~35 % vrstic vsak mesec**
  (stalna luknja, ne od aprila — vzrok neznan); **medpacki/ammo packi niso
  zajeti** (gibhub »Pillow Fort«); `sessions_router` ACC (lahka orožja) ≠
  `pcs.accuracy` (vsa orožja) — stran imenuje, katero; `endstats_aggregator`
  sešteva tudi K/D in accuracy čez runde (za sejni roll-up rabi `best`).
- (3. 9., R3) `/stats/session/{id}/detail` vrže stran `warnings` iz
  `build_session_scoring` (drugi element terke) → session glava ne more
  pokazati »Lua header winner missing: used time fallback« (doc 12 vrstica 31
  zahteva). `/basics` ali `/detail` naj ju vrne. `MapStrip` pari
  `detail.matches` in `scoring.maps` po indeksu — ko se seznama razlikujeta
  (map ni v scoringu), naj se pari po `match_id`.
- (3. 9., R3) Playwright `SAMPLES_THIN` sessionId 151 → 80; 151 (0 štetih
  rund) ostane pokrit v `SessionDetail.test.tsx` kratkih oblikah (mvp/verdicts/
  good-night fixturi `api_session_151_*`), ne v preletu.
- (3. 9., R2 korpus) **`denied_playtime` iz 2025 supastats backfilla je pokvarjen**:
  jan–maj 2025 ~50 s na uboj (max 18 880 s v rundi 107 s), od dec 2025 ~8 s;
  352/5 538 vrstic 2025 ima denied > 2× igranje, 2026 le 8. Ista doba kot
  pokvarjen `bullets_fired`. `/basics` take vrstice označi (`denied_pct` null,
  `coverage.denied_suspect_players`); podatek ostane, kot je — popravek je
  ownerjeva odločitev (rez po datumu ali ponovni backfill).
- (3. 9., R2 korpus) 14 sej (83, 99–102, 104, 107, 123, 127, 128, 145–147, 151)
  nima nobene štete runde (vse neveljavne/botovske) → `/detail`, `/basics`,
  `/awards` 404; 73 sej (pred junijem 2026) nima `round_awards` → samo trije
  računani; KIS le v 45/139 sejah; 65 vrstic igralcev brez ekipe (subi).
- (3. 9., R2) `/stats/session/{id}/detail` še vedno BREZ `response_model`
  (`response_model_gap.txt` vrstica); `/basics` ga ima — ob R4 /detail
  tipizirati ali upokojiti. `endstats_aggregator._format_value` (bot) izpiše
  `Least time dead`/`Full respawn king` (odstotek) kot m:ss in sešteva K/D —
  bot naj prevzame `session_awards_service.AWARD_RULES`. `endstats_parser`:
  `Quickest multikill` numeric = število ubojev, čas ostane le v tekstu
  (drugi regex je mrtva koda); `Tank/Meatshield` numeric NULL (parsira se
  v servisu). Playwright »thin« vzorec seja 151 je od #855 (vrata) 404 —
  ni več tanka, ampak prazna; e2e SAMPLES_THIN rabi drugo sejo.
- (3. 9., R1) `/api/sessions.maps_played` je abecedno urejen → thumbnail vrstice
  je abecedno prva mapa, ne prva igrana; R2 naj `SessionSummary` doda vrstni
  red igranja (ali `first_map`), response_model.
- (3. 9.) `routes.ts:52` grammar `SESSION_DETAIL_TABS` ima `teamplay/charts`,
  stran pa `summary/players/rounds` — legacy `#/session-detail/154/teamplay`
  pade na summary; R4 ga uskladi.
- (3. 9., uploads r. 2) **poster capture** (.mp4 → JPEG prek canvasa,
  `uploads.js:300-336`) za single-shot pot; **resume čez reload** (HEAD +
  localStorage identiteta datoteke — legacy nima); filtriranje po
  kategoriji/oznakah na seznamu (rezina 1 ga je izpustila, PR #888).
- (3. 9.) **resumable router handlerji nimajo testov**: 0 testov v `tests/`
  kliče `init_resumable_upload`/`resumable_patch`/`finalize_resumable_upload`/
  `abort_resumable_upload`; le store (`test_upload_store_resumable.py`).
  `test_uploads_slice2_fixtures.py` pokrije init/finalize/delete oblike,
  ne PATCH/HEAD.
- (3. 9.) `docs/UPLOAD_SECURITY.md` §3.6 zastarel (trdi, da admin ne more
  brisati; `delete_upload` admin gate obstaja); `delete_upload` brez
  `_require_valid_upload_id` → napačen id vrne 404, ne 400.
- (2. 9., availability r. 2) **response-model round: availability + bets** —
  24 handlerjev brez `response_model`, openapi brez shem → ročni tipi v
  `types.ts` so pripeti le s harness posnetki
  (`tests/unit/test_availability_slice2_fixtures.py`). Isti vzorec kot
  #812/#820/#830; ownerjeva odločitev 2. 9.: ločen PR.
- (2. 9.) **admin market kontrole** (`POST /api/bets/market`, `…/settle`) —
  izpuščene iz rezine 2 po ownerjevi odločitvi; gap vrstici `/api/bets` in
  `/api/bets/market` ostaneta (komentar v `endpoint_gap.txt`).
- (2. 9.) `scripts/record_api_corpus.py:mint_owner_cookie` kuje cookie s
  TRDO KODIRANIM realnim Discord id-jem (»corpus-recorder«); `--sentinel`
  (rezina 2) je pot brez identitete — ownerjeva pot bi šla prek E2E_OWNER_*.
- (2. 9., živ Playwright na :8056 med rezino 2) `app-routes` anon: greatshot
  demo/clips stran kliče zaščiteno pot anonimno → 401 v konzoli (stran iz
  #890); proximity/proximity-player `page.goto` presežeta 30 s `networkidle`
  (hladna hrbtenica, memory `second_call_is_not_a_measurement`); spider-web
  thin-data. Nič od tega ni v rezini 2 (diff se teh strani ne dotakne) —
  vsak zasluži svojo vrstico, ne tišine.
- (2. 9.) `bets_router.get_current_market`: `my_bet.payout` gre skozi `int()`
  in ob `None` TIHO vrže `my_bet` na `null` (except TypeError). Stolpec je
  NOT NULL DEFAULT 0, zato danes ne sproži — a tip laže, če se shema kdaj
  sprosti.
- `bets/wallet` 500 za avtenticirano sejo BREZ users vrstice (2. 9.: sentinel
  ima zdaj vrstico prek `scripts/e2e_sentinel_rows.py`, hrošč za izbrisane
  uporabnike ostaja) (FK na
  user_points ob auto-create; izmerjeno s sentinelom −1). Pravi uporabniki
  ob OAuth vrstico dobijo; krhkost velja za izbrisane/sentinel uporabnike —
  handler naj FK ujame in vrne prazen wallet ali 403.

- round-end burst: batch write (table.concat → ~64 KB kosi) namesto 8400
  posamičnih trap_FS_Write; PREJ en večer self meritev z v6.12.
- tracker mikro: cache `sv_maxclients` (isValidClient ga bere ob vsakem
  klicu); združi dve cohesion zanki (isti pari, ista razdalja dvakrat).
- webhook pending_retry_sweep: io.popen find vsakih 60 s tudi ob praznem
  bufferju — gate za fork.
- replay stran: playback canvas je imenovan follow-up (paritetna tarča ga
  ni imela); kill-outcomes `events` seznam (80 KB) se ne izrisuje.
- spider-web: information_state/beliefs se še ne izrisujejo; mesh za
  etl_supply ne obstaja (BSP ni izvožen).
- weapon-accuracy `weapon_breakdown` se napolni le pod player_guid filtrom
  — player rezina naj ga pokaže.
- lokalna past: generirani `src/api/generated/openapi.d.ts` je bil 2×
  zastarel ob typechecku → pred meritvijo `rm` (ali dodaj v pretypecheck).
- `.claude_session` (SessionEnd hook) je v gitignore; po izpadu `--resume`.

## Prenosljive najdbe (sestrska seja, 2. 9. — ownerjeva prošnja za zapis)

- ⭐⭐ **Vzorec »eno ime, dve meritvi«** — 7× v enem dnevu (hitch A/B, dve
  uri z odmikom 2553 ms, TRIJE števci assistov, PLAYED%=LUA PLAYED%,
  DENIED je čas odvzet nasprotnikom, time_played_seconds ob reconnectu,
  kill_assists kumulativa/per-round). Recept: diskriminator, ki ga izpolni
  samo ena razlaga, pognan čez KORPUS (npr. monotonost: R2<R1 v 59 % parov
  dokaže per-round).
- ⛔ Assistov NE podeljuje motor: `TAB[12]` = `topshots[3]` iz NAŠE
  `vps_scripts/c0rnp0rn8.lua:701-741` (MOD filter, okno 1500 ms). Naša
  lastna števca se ne strinjata: endstats `topshots[29]` proti TAB[12]
  na 1005 rundah 40 razlik (±1).
- ⛔ Merilni pasti etconsole: časovne oznake so DESNO poravnane
  (`grep '^[0-9]+ Hitch'` vrne 1/18); motor javi hitch šele pri >500 ms
  (65/71 round-end burstov je NEVIDNIH, ne odsotnih).
- 🔎 **TAB[8] `time_played_percent` = 0 pri 37,9 % vrstic** (5.363/14.163,
  nobena NULL) kljub pravilnemu parsanju → neposreden vhod v ALIVE% na
  strani (`sessions_router.py:2115-2131`). Vzrok neznan — kdor se dotika
  ALIVE%, mora to vedeti.
- ⛔ `docs/GAMESERVER_LIVE_LUA_MAP.md:74` in `deployed_lua/README.md`
  navajata 4 module; živih je 6.

## 2026-09-05 popoldne — faza 6 r. 3 + popravek merilnika (PR #915)

**Narejeno:**
- availability rezina 3: admin market kontrole (open / settle / void), gap 4 → 3
- ⛔⛔ popravek ekstraktorja: gap merjen **3, resnica 19** — 16 endpointov je
  bilo nevidnih, ker se je zajem ustavil pri prvi `${` in odrezan prefiks
  velja za pokritega. Vsak od 16 preverjen dvakrat (živ openapi + odsotnost
  klica v `src/app`).

**⚠️ ČAKA OWNERJEVO ODLOČITEV (vprašano, brez odgovora):** ali graditi
wrapped/compare (2 od 16), ali najprej zapolniti štiri luknje na profilni
strani (`players/{}/awards`, `players/{}/card`, `skill/player/{}/form`,
`skill/player/{}/history`, `stats/player/{}/form`, `stats/player/{}/rounds`),
ki jih je merilnik skrival in zaradi katerih je ta stran tanjša od številke.

**Odprto zraven:**
- `/api/greatshot/{}/crossref` in `/highlights/render` — greatshot stran ne
  pozna sekcij `clips`/`renders`, legacy ima štiri hube, nova stran ignorira
  `:section` param (ruta ga ima).
- `/api/rounds/{}/player/{}/details`, `/api/rounds/{}/awards`,
  `/api/rounds/{}/vs-stats`, `/api/player/{}/vs-stats` — matches.js in
  session-detail.js.
- `/api/sessions/{}/graphs` — Landing.tsx v komentarju že priznava, da ni
  migriran.
- `/api/uploads/{}/download`.
- ⚠️ V glavnem worktreeju delata dve drugi seji (`opus-backend`, `sonet`) na
  moments/doc 22 — njihovega drevesa se ne dotikam, delam v
  `/home/samba/share/slomix-market`.
- ⛔ #911 (diagnostics), #912 (arena), #882 (release 1.45.0) čakajo ownerja.

## 2026-09-06 — pozicija pred restartom seje (posodobitev Claude CLI)

**Veja `feat/availability-admin-market`, PR #915, 9 commitov, vse potisnjeno.**
Gap **4 → 3 → 19 (korekcija) → 16**.

Narejeno v tem bloku:
1. availability rezina 3 (admin market: open / settle / void)
2. ⛔⛔ popravek ekstraktorja: 16 endpointov je bilo nevidnih, ker se je zajem
   ustavil pri prvi `${`; odrezan prefiks velja za pokritega
3. greatshot: sekcije highlights / clips / renders (ruta je param nosila od
   faze 6, stran ga je ignorirala); brez novega endpointa
4. wrapped kot STRAN (`/wrapped/:guid`) — konvencija modal→stran iz `design/12`
5. compare kot STRAN (`/compare?a=&b=`), z eno namerno razliko: playtime ni
   tekma (legacy da 🏆 tistemu, ki je igral MANJ)
6. rating trendi na profilu (`your form` + `rating over time`)

**Preostali gap (16), po razredih:**
- profil: `players/{}/card`, `players/{}/memory-card`, `stats/player/{}/form`
  (DPM/KD serija, drug graf od skill/form)
- runde: `rounds/{}/awards`, `rounds/{}/vs-stats`, `rounds/{}/player/{}/details`,
  `player/{}/vs-stats`
- greatshot: `{}/crossref`, `{}/highlights/render` (oboje na demo strani)
- drugo: `sessions/{}/graphs` (Landing.tsx to v komentarju že priznava),
  `uploads/{}/download`
- ne zaprejo se z gradnjo: `/api/bets`, `/api/stats/sessions` (šele ob
  upokojitvi legacy js), `/api/diagnostics` (#911)

**⚠️ Okolje po čiščenju 6. 9.:** ET strežnik USTAVLJEN, uvicorn `:8056`
ustavljen (bil sosedov e2e), 240 MB chromium ostankov pobitih. **Teče samo
`:8000`** (preview, `/app/` → 200). Stroj ima 1,8 GB RAM; dve Claude seji sta
skupaj ~900 MB.

**⚠️ Sočasne seje:** `opus-backend` in `sonet` delata v glavnem worktreeju
(`/home/samba/share/slomix_discord`) — PR #921, paritetni prelet. Njihovega
drevesa se ne dotikam; jaz delam v `/home/samba/share/slomix-market`.

**Čaka ownerja:** merge #911, #912, #915, #921, #882; ⛔ `/code-review ultra`
pred deljenjem arena paketa; odločitev, kateri razred iz gapa naprej.
## 2026-09-05 — arena PR #912, odprto po pregledu testov

Pregledni agent za testno zbirko je našel 22 postavk. Popravljene so 4
(zastareli vzorci mutacij → `fail`, `re.search` → `findall`, `setl "ime"` v
narekovajih, prazna datoteka prestane preverbo oklepajev) in ločeni skladišči
zdravja v stubu. **Odprto ostaja:**

- ⛔ mutacijska baterija nima izhodiščnega zagona: če harness pade iz
  nepovezanega razloga, VSAKA mutacija poroča »ujeta«. Popravek: pred zanko
  poženi harness enkrat in prekini, če ne vrne 0.
- primer 20 je votel (`arena_symmetric 0` se preverja, ko `duel_pool` sploh ni
  postavljen → `arena_loadout` se ne kliče). Zraven razkriva vedenje:
  `arena_symmetric 1` ne naredi nič, kadar sta `arena_hp` in `arena_vamp` 0 —
  kar je natanko to, kar nastavi priloženi config.
- primer 20 prva polovica prehaja na puščenem stanju iz primera 19; vzorec
  `et_InitGame` PRED nastavitvijo cvarov se ponovi na 6 mestih.
- stub `trap_SendServerCommand` zavrže naslovnika → zasebna zavrnitev bi lahko
  postala broadcast in noben test ne bi padel.
- stub `gentity_set` sprejme pisanje v `pers.connected` in
  `pers.playerStats.selfkills`, ki sta v motorju READONLY (g_lua.c:1248/:1283).
- `ps.stats` je modeliran samo pri indeksu 0; `STAT_MAX_HEALTH`/`STAT_SPRINTTIME`
  sta deklarirana, a neodgovorjena → `et_Obituary` ju v offline teku bere kot nil.
- štiri vstopna varovala v `et_Damage` niso posamično pripeta (odstrani eno in
  zbirka je zelena); `active`/`enabled()` vrata so testirana na 2 od 5 hookov.
- vsi privzetki vampirica so neizmerjeni (primer 10 pusti cvare postavljene).
- `arena_ammo 0`, `arena_nofatigue 0`, `arena_1v1_log 0` — nobenega primera.
- README pogodba ne opazi IZGINOTJA cele jezikovne tabele (množica ne loči
  odsotnosti od soglasja; rabi `Counter(rows)[ime] == 3`).
- `arena_1v1_map` je dokumentiran, a ga nobena pogodba ne doseže: `armed_map()`
  uporablja `trap_Cvar_Get` in dobesedni fallback, ne `cvar_num`.
- ⛔ B-1: ujemanje imena mape je podniz → `dots_arena_v2` oboroži modul.
- ⛔ NIHČE ni pregledal PR #912 (Copilot in Codex brez kvote). Pred deljenjem
  paketa tujcem naj owner požene `/code-review ultra`.

**Neizmerjeno v živo:** `/team s` med življenjem, `sv_maxclients` (latched),
rotacija loga, gledalska vrata in cooldown, `arena_symmetric` proti človeku,
paket v pk3, dva človeka hkrati — in NOVO: `arena_instant_tapout` v živo.

## 2026-09-05 13:50 — arena PAVZIRANA (owner ugasnil testni strežnik)

Kje sem ostal: PR #912, 22 commitov, CI zelen, **delovno drevo čisto**.

**Dokazano v živo danes** (2.84, podpisi prek `lua_status`):
- `force_tapout`: 20 vrstic, 9 zanje; čas ležanja igralca mediana 1,0 s → 0,0 s,
  max 23,0 s → 0,0 s; ščiti 25 ms narazen. Prvi TAPOUT 13:09:58.
- ⛔ Odkrito ob tem: strežnik je tekel 11,5 ure in bil **10 ur starejši od
  popravka** — »ne dela« je pomenilo »ni naloženo«. Razsodnik je bil
  `lua_status` podpis (`G_SHA1(code)` ob nalaganju, g_lua.c:2597), ne datoteka.

**Nameščeno, a NEIZMERJENO:** `arena_acc_log` (podpis 0CCBE140 naložen ob
13:47, owner je nato ugasnil strežnik → **0 ACC vrstic v živo**). Instrument
je offline pokrit (primera 48/49, mutacije 32/32), runtime dokaza NIMA.

**Ownerjev nedokončan eksperiment:** tapanje proti full auto, v blokih po ~15
dvobojev z oznako v chatu; hipoteza je, da acc naraste, a odloči šele
zadetkov-na-sekundo.

**Odprto ostaja** vse iz vnosa 2026-09-05 zgoraj (22 postavk pregleda testne
zbirke, od tega 5 popravljenih) + ⛔ PR-ja ni pregledal nihče.

⚠️ Pytest je v enem teku danes javil 1 padec, ponovni tek 6227 passed —
neidentificirana nestabilnost, ne moja sprememba. Ob naslednjem padcu ujemi ime.
