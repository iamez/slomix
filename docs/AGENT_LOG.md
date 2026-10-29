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

## 2026-10-21 — Publish proximity foundations without importing later lanes

Admission tests include three later ingest-dependent cases; publishing the file
unchanged before the ingest module exists breaks that boundary. Retain those
cases in the full candidate until the ingestion slice. Keep schema096/100 bytes
identical and append only their blocks to the current bootstrap, rather than
copying the full candidate schema with unrelated pending migrations. Fresh-process
admission recovery proves local persistence, not producer authentication or DB
commit.40offline tests pass;34native PG cases remain explicitly pending.

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

## 2026-10-11 — Generated API prose and handoff preambles are contracts

A router docstring changes the frozen OpenAPI description even if its schema
is unchanged. Refresh dump_openapi and the datapoint ledger when removing a
field reader. Explain deliberately retired transport heuristics in decisions;
never grow the unread baseline to hide them. Keep HANDOFF-next's mandatory
routing/authority preamble before the first dated heading, not below updates.
The20OpenAPI/ledger/history checks cover these three CI failures.

## 2026-10-11 — Filtered loss and cached module graphs need explicit evidence

Raw ring-head advancement does not prove a renderable event was lost. Track
last evicted sequence per allowed type and apply the requested filter to that
bounded watermark. For legacy JS changes, invalidate the full import chain;
updating only the leaf URL cannot help a cached parent. Home and Live must
import the same versioned tonight module. Parse imports rather than searching
comments, and verify actual HTTP bytes/cache headers without invoking lifespan.

## 2026-10-11 — Empty Live pages still carry state transitions

Treat feed status, gap evidence and age expiry independently of events.length.
An empty successful response must clear a displayed error; a failed request
must render unavailable immediately; gap-only responses invalidate derived
scores. Run row expiry for every poll outcome so silence cannot preserve old
rows indefinitely. DOM tests execute the legacy module, including filter clicks.

## 2026-10-11 — Live sequence recovery requires a worker identity

A per-process counter alone cannot distinguish a restarted worker whose head
has overtaken the prior cursor. Reset client deduplication and cached feed pages
on changed stream identity; clear derived legacy state and serialize polling.
Hidden telemetry consumes sequence IDs, so numeric holes alone do not prove
lost renderable events. Use server gap metadata and keep transport fields
server-owned. A failed configured upstream must not report successful silence.

# AGENT_LOG — durable lessons for the next agent

- **2026-10-04 · A migration has three delivery artifacts.**
  Add the numbered SQL, fresh-bootstrap schema, and active MIGRATIONS entry in
  the latest release config. Validate test_release_config_contract.py as well
  as test_apply_migrations.py locally: otherwise --only/--validate can block the
  next owner deployment even when parser and migration SQL tests pass. Updating
  the list is not permission to execute a migration or deploy frozen production.

- **2026-10-04 · Receipt provenance is enforced state, not a caller warning.**
  A matching hash proves source bytes, not whether earlier ingestion enforced
  parent linkage. Strict replay of permissive ON CONFLICT imports can falsely
  succeed while stored links remain NULL. Migration094 defaults old receipts
  to FALSE; strict insertion stamps TRUE atomically, never upgrades on conflict.
  Require that persisted provenance before accepting strict replay. Normalized
  map identity must also agree across preflight, parser and later relinker.

- **2026-10-04 · Successful replay is not proof of repaired linkage.**
  Vehicle ON CONFLICT DO NOTHING preserves an earlier NULL round_id even when
  replay resolves the correct parent. A fresh forward-only runtime can defer
  initial import until an exact parent/session exists, instead of inheriting
  Discord's broad historical relinker. Pending is not acknowledgment; retain
  sealed input and distinguish retryable absence from ambiguous identity and
  query failure. This policy cannot adopt already-unlinked permissive receipts.
  Test fixtures must support the failure branch too: missing fallback columns
  initially made a mutation fail from SQL abort, not from the intended false
  success; add those fixture columns and prove the actual acceptance failure.

- **2026-10-04 · Ambiguity must survive every retry path.**
  Refusing duplicate source identities at ingestion is insufficient if a later
  relinker invokes a matcher that chooses its first exact/canonical hit. Stop
  both strict and relaxed duplicate branches before fallback. Tests must force
  the fallback to return a candidate: an empty fake hid the bypass. New shared
  adapter-facing receipt SQL uses ?; raw asyncpg fixtures translate through the
  real adapter converter, rather than constraining production to fixture syntax.

- **2026-10-04 · Compare the same clock before nearest-round fallback.**
  Proximity's end timestamp passed as target is compared to rounds.start; a later
  same-map/R1 round can beat the exact original source start and select a wrong
  session. Private synthetic clone proof observed this, not historical corruption.
  Prefer unique exact map/round/header-start identity; ambiguous identity remains
  unresolved. Do not promote filename-derived fallback starts into header identity.
  Keep legacy fallback semantics for absent exact matches. Test journal_db already
  creates a minimal rounds table; extend that private fixture rather than recreate.
  Check remaining proof-service lifetime before suites: RuntimeMax interrupted a
  run and its teardown; connection-closed errors are not a successful guard proof.

- **2026-10-05 · Reconcile shared admission APIs, not only conflict markers.**
  An older runtime slice exported validate_stats_filename for manifest/import
  callers while proximity publication parameterized the same private helper.
  Retain the public stats validator and separate proximity admission; choosing
  either conflict side loses a contract. Run both caller families and composed
  long-name/read-only retries. Widening stats admission must fail the dedicated
  test; restore the mutation with apply_patch and verify exact bytes with cmp.

- **2026-10-04 · Private spool is a destination, not a chmod of shared input.**
  DEV local_proximity is a symlink to the shared legacy source. A default find
  reported zero files because it did not traverse that command-line symlink;
  find -H plus independent du apparent-byte census measured1085files/1093542894B.
  Keep Samba permissions intact and publish verified copies privately. Reuse
  atomic publication mechanics behind separate explicit filename policies;
  accepting proximity files must not loosen the community stats allowlist.
  A post-link fsync error leaves final evidence: reconcile, never overwrite.

- **2026-10-04 · Verify the bytes that the parser actually consumes.**
  Hashing a path and reopening it leaves a replacement window. Capture bounded
  bytes, verify trusted size/digest, parse that immutable payload, and commit its
  identity with the receipt/data. Never stamp today's hash onto an old hashless
  receipt as proof of yesterday's content. Same-size rapid writes may not change
  observed metadata; metadata checks are supplementary, not the content proof.
  Full handover must exclude legacy writers that do not enforce the new digest.

- **2026-10-05 · Separate current instructions from pre-merge history.**
  A new closure paragraph does not make contradictory wait instructions in the
  same current section safe. Put an explicit historical heading before the old
  preparation text and state the next actual PR gate once. Preserve evidence,
  but never leave both "merged" and "wait for this merge" as current directions.
  The guard must inspect the entire current section, not just its first bullet:
  stale queue prose before that bullet previously escaped both document tests.
  BACKLOG current position now routes to PLAN instead of duplicating PR numbers;
  old queue/anchor evidence is retained under its own historical level-2 heading.

- **2026-10-04 · Prefix-only test selection missed a legacy caller.**
  test_proximity*.py omits proximity_sprint_pipeline_test.py. A transaction
  contract change therefore passed the selected315 tests but failed full CI.
  Discover paths/callers and pytest naming patterns, not only the modern prefix.
  Update participating test adapters; do not weaken the production guard.

- **2026-10-04 · Lock absent receipts before checking them.**
  Two READ COMMITTED import transactions can both read no receipt and double an
  aggregate while leaving only one receipt. Reserve/lock the filename row with
  an UPSERT that preserves the flag, then read and write within the same TX.
  Unlike SELECT FOR UPDATE on an absent row, reservation creates something to
  serialize on. Real-PG proofs must observe pg_blocking_pids, cancellation,
  outer transaction lifetime and actual observer rows, not elapsed sleep alone.
  Higher isolation can raise serialization failure; retry the whole transaction.
  Nontransactional and old-version writers cannot participate safely. This is
  filename concurrency protection, not content identity or a general lease.

- **2026-10-04 · Unknown receipt state is not an absent receipt.**
  The proximity optional-column helper swallows schema-query errors; the old
  receipt read also swallowed query failures. Both could authorize aggregate
  updates after an outage. Read the required receipt directly, inside the import
  transaction before writes; let failure abort import. Receipt-write tests that
  mock this read cannot prove the read boundary. New regression tests and a
  restored swallow-error mutation demonstrate this distinction; real-PG tests
  and canonical parser+adapter clone proof now pass. Transaction placement alone
  is not concurrent serialization.

- **2026-10-04 · Pytest has two independent connection selectors.**
  The private journal fixture uses RUNTIME_EVENTS_TEST_SOCKET, but the global
  collection hook probes POSTGRES_TEST_* with a localhost default. Pin both to
  the approved disposable cluster for local integration runs. An authentication
  rejection during collection is not evidence that the private PG fixture failed.

- **2026-10-04 · Recheck repaired boundaries through their composition.**
  Filename length and restrictive-umask admission had separate regressions.
  A capture -> receipt -> repeated retry proof now combines200/201/240-byte
  names with0400 payload/manifest files, preserving bytes/inodes/modes. Both
  old200-byte and0600-only guards fail this composed proof when reintroduced.
  Keep component tests and add the cross-boundary case; green components alone
  do not establish caller compatibility or authenticated source provenance.

- **2026-10-04 · Historical labels do not repair active continuation links.**
  A dated ledger can still contain an imperative pointing to an obsolete hash.
  Keep its evidence, but route every handoff/inventory/known-issues entry point
  and the ledger preamble to the latest PLAN checkpoint. Test the whole entry
  set so repairing the top-level prompt does not leave a second stale path.

- **2026-10-04 · Scan synthetic review changes against their pinned source.**
  A mutable local origin/main can describe another branch and hide restored
  baseline content from a hook's diff/intersection. Pass the immutable source
  OID explicitly to snapshot preflight; do not use ambient tracking refs to
  narrow its changed-file set. Test a published feature with differing main.

- **2026-10-04 · Noninteractive publication must stop on scanner warnings.**
  The interactive hook can return success while warning about an assignment.
  Capturing that diagnostic hides the decision from the owner. Snapshot
  preflight now rejects any bundled-guard diagnostic before creating refs,
  without echoing its possibly sensitive contents. This is not a complete
  credential detector; its existing pattern/placeholder limits still apply.

- **2026-10-04 · A bounded review diff does not bound transferred ancestry.**
  A new parent commit transfers its reachable objects too. Require source
  history already reachable on the exact destination before publishing review
  refs; otherwise an unselected file in the parent can also be uploaded.

- **2026-10-04 · No-deref verification alone does not reject symbolic refs.**
  Git2.34 still accepts a matching symbolic OID. Check symbolic type while
  transaction locks are held before committing immutable review refs.

- **2026-10-04 · Quoted filenames cannot safely be fed back as Git paths.**
  LF/TAB/quotes can silently skip content/raw-data checks when Git prints a
  quoted name. Carry NUL-delimited filenames through enumeration/intersection.

- **2026-10-03 · Immutable snapshots must read real objects and verify refs.**
  A pinned commit OID does not disable refs/replace. Set GIT_NO_REPLACE_OBJECTS
  for every Git subprocess, including direct blob reads and publication hooks.
  Numstat binary classification can be forced to text by attributes/drivers;
  reject raw NUL-bearing blobs on both sides independently, retaining numstat
  as an additional conservative veto, not claiming all configuration invariant.
  Metadata-only git show can emit signature diagnostics under log.showSignature;
  explicitly suppress signature display for date extraction. Verify existing
  local refs inside the same update-ref transaction as creates, even when none
  are new. A preflight dictionary alone races; the transaction protects only
  that operation, not later external writers. See primary Git documentation:
  https://git-scm.com/docs/git-update-ref,
  https://git-scm.com/docs/git-replace,
  https://git-scm.com/docs/git-show,
  https://git-scm.com/docs/gitattributes.

- **2026-10-03 · Snapshot determinism includes order files; hooks are local.**
  Pin diff ordering as well as its algorithm, including metadata-only git show:
  it still fails on a missing configured order file. A fresh clone does not
  inherit active hooks, and an arbitrary executable hook proves nothing about
  protection. Snapshot publication now directly executes the bundled guard for
  all proposed create-only refs before the first write, then keeps normal push
  hooks enabled. Require inspection tools first: suppressed missing-grep errors
  otherwise turn an unperformed scan into apparent success. Override order-file
  config inside the direct guard too: its suppressed diff errors otherwise
  skip inspection entirely (measured unsafe publication in a local fixture).
  Capture guard
  diagnostics because they can contain the very content being blocked. This
  retains the existing guard's documented detection limits, not a complete
  history/credential audit or protection against a malicious local checkout.

- **2026-10-03 · Snapshot partition identity includes the diff algorithm.**
  Pin Myers for both planned numstat and generated-tree validation; otherwise
  the same source/base pair can produce different boundaries and false conflicts.
  Consumer formats must migrate with producers: the old area-body generator
  silently converted immutable -pNNN measurements to zeros and is now retired.

- **2026-10-03 · Remote Git diagnostics and partial pairs fail closed.**
  Capture stdout/stderr on remote operations, including successful pushes:
  transport and hook messages may echo URL credentials. Report operation/exit
  status only; this deliberately sacrifices raw hook diagnostics. Reject partial
  remote pairs before any local refs or push: Git may elide an unchanged ref and
  its lease check. Create absent pairs atomically with absence leases; existing
  complete pairs are only observed, never guaranteed against external writers.

- **2026-10-03 · Receipt failure can lie about committed ingestion.**
  Proximity receipt errors were swallowed. A Python failure could commit data
  without a receipt; a SQL failure could roll back while import_file returned
  success. Propagate receipt failure through the transaction and require an
  observer-based post-write failure/retry proof. In synthetic vehicle fixtures,
  changing map alone does not avoid the unique key: session/date/start/vehicle
  identity must differ. Assert the data write actually happened before injecting.

- **2026-10-03 · Read-only ACL checks need more than table privileges.**
  PostgreSQL documents column ACLs separately and allows NOINHERIT memberships
  to remain reachable through SET ROLE. PG16 separates SET from MEMBER; earlier
  versions use MEMBER for SET reachability. PG17 adds MAINTAIN. Inspect effective
  table/column/sequence rights and ownership of every reachable role; do not
  "repair" unrelated roles globally. New coverage is prepared, not runtime-proven
  while the disposable proof service is stopped (see PLAN checkpoint).

- **2026-10-03 · GRANT SELECT does not make existing permissions read-only.**
  Default ACLs are copied onto newly created tables/sequences. Runtime migration
  tests with a pristine role missed DEV's pre-existing website CRUD defaults.
  Reproduce inherited grants before migration; revoke only scoped runtime
  objects, retain legacy/default ACLs, and verify effective rights through both
  catalog queries and actual denied SQL. Fail closed if unrelated PUBLIC or
  inherited role privileges still authorize writes; do not revoke those globally.
  Test SET LOCAL ROLE must be RESET before releasing a successful savepoint.

- **2026-10-03 · Artifact provenance does not certify the RUN index.**
  A clean tracked status can hide locally changed runtime files behind
  assume-unchanged or skip-worktree. Checkout of a new commit preserves these
  bytes when its blob is unchanged. Reject both flags across the entire RUN
  index before status/fetch/staging; parse NUL records and propagate Git errors.
  Source-only guards cannot protect the separately maintained runtime clone.

- **2026-10-03 · Unchanged lock bytes do not preserve a clean security audit.**
  After a usage-limit pause, the previously clean frontend lock had newly
  observed undici and brace-expansion findings. Refresh the advisory result
  before merge, retain its date, and independently prove installed guard behavior.
  Run mutation probes in isolated copies, not packages used by concurrent tests.

- **2026-09-28 · Receipt recovery must accept safe modes its publisher creates.**
  umask0277 turns a requested0600 manifest into0400. Read-only recovery now
  admits exactly0400/0600 without chmod, retaining owner/type and drift checks.
  Actual publish/read proof verifies unchanged mode/inode/bytes; group/other,
  executable and special-bit modes remain rejected. Apply the publisher/reader
  boundary check to metadata receipts as well as payload spool entries.

- **2026-09-28 · Validate selected dependencies as well as current inputs.**
  The earliest supported R2 can select a previous-year R1 across midnight;
  matching trusted bytes do not establish calendar admission. Both import
  paths reuse current-input validation for selected R1 before canonical calls.
  Verified capture remains match while dependency=invalid is terminal, not a
  fabricated content conflict. Prove this with the actual filesystem selector,
  not only a mock returning an invalid name; DBless proof is not SQL proof.

- **2026-09-28 · Validate terminal input before stricter lower-layer validation.**
  Verified import called spool inspection before filename admission, so malformed
  names raised instead of returning the promised failed result. Move shared
  validation first and label capture_status=None as unmeasured, not a match or
  absence. Actual valid-payload PostgreSQL regression proves rejection; unit
  spies additionally prove no filesystem inspection or importer call occurred.

- **2026-09-28 · A dependency is not admitted by verifying its consumer.**
  A retained conflicting R1 inside a private spool contaminated verified R2.
  Why: path isolation does not certify dependency content. Apply: validate the
  parser-selected R1 against independent trusted source size/SHA metadata before
  canonical import, and expose dependency state separately from R2 capture.

- **2026-09-28 · Malformed payloads cannot prove filename admission.**
  Prior calendar tests failed on payload parsing, while valid duplicate content
  bypassed canonical filename validation and gained a success marker. Apply:
  validate filename/calendar before dedup for both halves and test actual valid
  payloads already present in the DB. Terminal admission failure has no marker.

- **2026-09-28 · Snapshot identity and remote admission depend on Git configuration.**
  show-ref exits1 for an empty branch set; for-each-ref gives a valid empty set.
  Origin's fetch URL need not be its push URL: resolve one push destination and
  inspect/publish that same endpoint, retaining create-only CAS for races. Fail
  before ref writes for multiple URLs rather than promise cross-remote atomicity.
  Pin commit-tree UTF-8: i18n.commitEncoding otherwise changes commit headers
  and OIDs for identical source/base inputs. Test with actual disposable Git
  repos, genuine hooks, distinct bare remotes and independent object inspection.

- **2026-09-28 · A flag named exclude does not make a Git pathspec negative.**
  Passing a plain path through --exclude expanded snapshot selection; accepting
  an empty area silently lost requested coverage. Validate actual exclusion
  magic and nonempty measured changes before all ref writes. Disposable local
  remotes prove rejection without refs/push hooks, and exact successful scope.

- **2026-09-28 · Build cwd is not necessarily deployment source.**
  dev_deploy.sh defaults SRC to the primary checkout, even when invoked from
  a feature worktree. Pass DEV_SRC_DIR="$PWD" from that worktree's root in
  an owner-approved recipe. Execute the documented recipe against disposable
  build/deploy probes to prove both paths match; do not deploy to test prose.

- **2026-09-28 · A local resume hash is not a public handoff reference.**
  Preserve unpublished work with its exact host worktree, branch and read-only
  object/ancestry checks. A fresh remote clone must obtain owner-provided source
  or wait for reviewed publication; an older public PR is context, not the same
  implementation. Separate first-session onboarding from approved continuation.

- **2026-09-28 · Cleanup ownership includes loop control and handle close.**
  Guarding process calls alone leaves SIGINT windows in the supervising clock
  and loop. Correction after follow-up review: installing cleanup deferral itself
  leaves an ownership window. Install once before spawn through handle close;
  restore/replay even when the operation failed, preserving its exception over
  a handler error. Observe death independently of elapsed time. Tiny positive
  grace is now rejected below0.01s, and every phase attempts its stopping signal.
  SIGINT can wait until timeout+cleanup; document that latency, never promise
  immediate cancellation or successful reaping after an OS-level cleanup failure.

- **2026-09-28 · Spawn ownership and the whole escalation path need interruption guards.**
  CPython creates the OS child before Process._popen is assigned: real SIGINT
  there can leave a child invisible to Process.pid and active_children. Defer
  main-thread callable SIGINT handlers through the entire child lifetime (not
  only until ownership exists), restore before delivery, and never pass a blocked
  signal mask into the child. Protect status,
  terminate, kill and join together with finite cleanup phases, not join alone.
  Actual child/procfs tests reproduce both gaps; synthetic persistent operation
  failures must raise an unreaped error rather than claim successful cleanup.

- **2026-09-28 · Observation transitions need pending state separate from ACK history.**
  A delivered warning followed by unknown and another warning cannot use the old
  notified_level alone. An observed-level OR fixes only the first attempt: it
  loses the transition during cooldown or after a failed retry. Persist one
  pending-warning bit per key until warning ACK or superseding nonwarn data;
  keep latest payloads and delivery history separate, without a historical queue.

- **2026-09-27 · Planned Git path slices are not actual tree differences.**
  Restoring a file over a source directory can implicitly remove unselected
  children. Validate generated trees against the exact selected path set and
  line/file limits before publishing refs; reject unsafe D/F splits. A baseline
  tree entry is not an index leaf: restore selected descendant blobs instead.
  Reject duplicate area identities and empty/exclusion-only pathspecs before
  Git's implicit whole-tree selection or dictionary replacement loses scope.

- **2026-09-27 · Publication modes are filtered by the process umask.**
  open(mode=0600) under umask0277 creates0400, still readable by its owner.
  Reconciliation must accept that safe publisher output without chmod widening;
  exact0400/0600 admission preserves group/other/execute/special-bit rejection.

- **2026-09-27 · Calendar-valid dates can still overflow adjacent-day lookup.**
  Year0001 passes strptime but subtracting a day can raise OverflowError. Runtime
  dependency admission now matches the canonical2020-2035 year range without
  importing presentation/configuration. Tests cover outside years, both accepted
  bounds. Correction2026-09-28: the old PG0001 fixture had invalid contents;
  its failed marker did not prove valid-payload admission. Shared importer
  admission now rejects0001 before dedup with failed/no marker, proven using
  valid payloads. Do not treat calendar parsing alone as arithmetic safety.

- **2026-09-26 · Retargeting a stacked PR does not necessarily start required CI.**
  #1059 base changed from a feature branch to main. Its push CI passed, but the
  default pull_request triggers did not include edited, leaving required hygiene
  and CodeQL contexts absent. Publish the real follow-up checkpoint normally and
  verify all required checks on the NEW head; never bypass rules or credit old
  head checks to the new SHA. No workflow/settings changes are needed here.

One entry per fact. Format: date · fact · why it matters · how to apply.
Newest first. This is the repo-side memory that any agent (Codex, Claude,
Copilot) can read and append to; private agent memories are not visible
across tools, this file is. Never put credentials, private names or raw
data here.

- **2026-09-20 · Cleanup waits can be interrupted too.**
  Catching cancellation only around the first worker join leaves the termination
  joins vulnerable. Defer their exceptions, finish escalation within a fixed
  cleanup budget, close the reaped process, then propagate the original error.
  Inject interruptions into each join; use fixture cleanup so a failed regression
  does not itself leave a live worker. OS cleanup failure must remain explicit.
  Capture the supervisor's own exception explicitly: sys.exc_info in finally
  may instead describe an unrelated exception being handled by its caller.

- **2026-09-20 · Observation time is not child exit time.**
  After a bounded join, a late parent clock read cannot prove an already exited
  child exceeded its budget. Use observed liveness for timeout intervention and
  preserve completed/failed exit status otherwise. Test with a real child and
  an isolated supervisor clock jump, keeping multiprocessing waits real.

- **2026-09-20 · Reserve and consume producer dispatch separately.**
  An existing generation directory is not permission to rerun its writer.
  Persist an exclusive claim before dispatch and retain it even after failures;
  interrupted handoff may strand a generation but must not overwrite its data.
  Keep generation identity on both producer path and completion callback.

- **2026-09-20 · A failed reservation may still own its namespace.**
  Atomic mkdir prevents two same-token writers from reserving one generation.
  A later fsync failure can leave that directory; retry must refuse reuse even
  when empty. Never infer an empty directory is free. Keep source reservation,
  immutable payload completion and durable receipt delivery as separate states.
- **2026-09-20 · Retry must match the requested identity, not only stored bytes.**
  A self-consistent existing completion receipt can describe a different requested
  snapshot. Compare caller size/hash before returning content_present; otherwise
  return receipt_conflict without writes. Retrying after sync failure observes
  content but does not retroactively establish its crash durability.

- **2026-09-20 · A recovered manifest and its payload are separate observations.**
  Reader distinguishes missing manifest from missing payload and content conflict.
  Duplicate JSON keys, unsafe paths, malformed content and concurrent replacement
  must raise, never appear absent. A complete receipt recovered after directory
  sync failure can match bytes but still does not authorize source deletion.

- **2026-09-20 · A receipt must accept every supported producer basename.**
  Lua accepted240-byte names while manifest publishing capped200, stranding valid
  captures. Aligned240 and tested actual filesystem publication at200/201/240,
  rejection241, final254-byte name against pathconf. Test boundary composition,
  not merely each component's individually reasonable limit.

- **2026-09-20 · Two external checks can hide absent GitHub Actions.**
  Stacked runtime CI push filter matches feat/db-runtime-* only; the Lua-scoped
  prototype branch did not trigger Actions. Verify workflow runs for exact SHA,
  not merely a green CodeRabbit/Codacy list. A same-SHA matching verification ref
  runs existing checks without changing code; keep its purpose explicit.

- **2026-09-20 · Check ET write counts before signalling writer completion.**
  Local and upstream g_lua.c return FS_Write byte count, but FCloseFile returns
  no durability status. Offline prototype rejects short/missing counts and signals
  only after close returns. This does not establish fsync, exclusive filenames or
  durable receipts; those need separate protocols before enabling source capture.
- **2026-09-20 · Verified R2 bytes do not isolate the parser's R1 search.**
  The legacy finder also searches cwd/local_stats. Construct runtime managers
  with allow_legacy_r1_fallback=False; import_verified_file requires this mode.
  Exact/same-day/midnight searches then remain in the input directory and reject
  symlink R1 entries. Retained immutable R1 remains a caller precondition.
  Actual-PG proof must include a plausible external R1, not merely an empty cwd.


- **2026-09-20 · Clean Git status does not prove committed build inputs.**
  assume-unchanged and skip-worktree can hide changed tracked bytes. Reject these
  flags on provenance inputs or compare exact committed blobs before certification.

- **2026-09-20 · Deployment provenance must identify the executed verifier.**
  A script launched from another checkout must use the verifier in its configured
  source, and resolve a default remote target only after refreshing its ref.
  Keep source-ref refresh distinct from modifying the running clone.

- **2026-09-08 · A non-symlink file can have a symlink parent.** Checking
  only static/app missed static/ pointing outside the checkout; build cleanup
  could delete external provenance before rejecting the dirty source. Apply:
  validate all source/output path components before the first unlink or build,
  and run website/static parents before activation. The parent-symlink mutation
  was seen deleting the proof in a disposable fixture; restoration verified.
- **2026-09-20 · STATS_READY is round timing, not exact-file completion.**
  Repository webhook defaults to immediate intermission emission; stats writer
  schedules SaveStats3000ms later and also writes on shutdown. Generic saved log
  lacks exact file identity. A synthetic open-writer proof retained equal stats
  and hashes before a later append. Do not promote these hints into completion
  receipts; require a producer protocol and identify deployed code separately.

- **2026-09-20 · Stable SFTP metadata does not prove producer completion.**
  Checked-in c0rnp0rn8.lua SaveStats writes final filenames directly. Compare
  required regular-file mode/size/mtime on handle and path before read and EOF
  to reject observed drift before publication, but do not infer writer closure
  or inode identity. Same-size/same-mtime changes can escape metadata checks;
  trusted digest and immutable-source completion contract are still required.

- **2026-09-20 · Retry result must preserve worker and content separately.**
  A timed-out SSH close can leave verified final bytes; reconciliation must return
  both timed_out and match, not report worker success or assume missing content.
  Inspect before spawning the next attempt, skip match/conflict, leave orphan
  partials untouched. Local inspection is not covered by the child's deadline.

- **2026-09-20 · Transport close timeout can follow successful publication.**
  A real disposable child with an offline SSH seam published verified bytes then
  blocked in file close. Supervisor reaped it as timed_out while final bytes and
  independent sha256sum remained correct. Treat worker status and spool state as
  separate facts; retain source and reconcile, never delete/overwrite on failure.
- **2026-09-25 · A descendant fix does not protect an unmerged prerequisite.**
  Worker cancellation fixes present on #1077 were absent from #1068. Before
  merging a stacked prerequisite, backport its applicable fixes with regression
  proofs, without importing unrelated descendant features. Compare the resulting
  files against the reviewed descendant and retain exact PR merge authorization.

- **2026-09-20 · Forced child termination skips application cleanup.**
  A disposable spawned capture task can be terminated and reaped after a deadline,
  including SIGTERM refusal. This boundary is not appropriate for shared locks,
  queues or DB transactions. Reconcile any partial/final spool state and retain
  source; child exit is not a durability or import acknowledgement. Supervise
  only the exact child Process object created by this caller, never services.

- **2026-09-25 · Review triggers can have a billing consequence.**
  An owner request to avoid additional charges applies to manual AI review
  requests and potentially automatic reviews after PR creation or pushes.
  Local tests/review can proceed without those triggers. Repository settings
  do not prove account billing is disabled; verify separately, and do not
  mistake a budget notification for an enforced usage stop.

- **2026-09-25 · Logging subprocess tests must disable unrelated SSH behavior.**
  A fresh checkout exposed inherited SSH_ENABLED=true in a dev logging fixture.
  Explicitly disable SSH and automation in the child; test true/false parent
  values. Do not enable SSH_ENABLED_DEV_OVERRIDE or weaken the application guard.
  Removing child isolation reproduces the guard failure. Production code unchanged.

- **2026-09-20 · Squash merge status is not an ancestry predicate.**
  The historical handoff in docs/HANDOFF-opus5-2026-09-07.md reported seven
  false negatives from ancestry-only checks. Verify the PR's merged state and
  main's actual content before declaring old work missing. Artifact identity,
  cold-cache sampling, directory mtime and shared stash ownership each retain
  their separate dated entries below; do not combine them into one lesson.

- **2026-09-07 · Measurement is not delivery acknowledgement.** Watchdog
  observations/failure streaks must persist even when the notification fails,
  but alert timestamps, recovery reset and daily heartbeat dedup advance only
  after successful POST. Otherwise failed recovery/heartbeat delivery disappears
  until another transition/day. Apply: persist pending latest-condition alerts,
  acknowledge each successful batch of at most ten embeds, and test retries
  across reloaded state. A crash between POST and acknowledgement can duplicate
  delivery; do not claim exactly-once. Dry-run must skip both state and report
  writes, including when output directories do not yet exist.
- **2026-09-20 · Content reconciliation is not durability or import completion.**
  A link can succeed before directory fsync fails. Inspecting size and SHA-256
  can recognize the existing complete file without overwrite, but cannot prove
  the directory entry will survive a crash or that PostgreSQL imported it.
  Keep those acknowledgements separate; never delete the retained source merely
  because inspection returned match. Operational read errors are not absence.

- **2026-09-20 · A timeout around a worker is not a stopped transfer.**
  Legacy SSH listing awaits an executor future under wait_for; cancelling that
  wait does not forcibly stop its synchronous work. Runtime capture instead
  requires a timeout-aware reader, caps each read by remaining monotonic budget,
  and checks again after read before publication. This still does not bound
  SSH setup or filesystem fsync, or interrupt a reader which ignores timeouts.
  Preserve these distinctions when integrating the connection owner.

- **2026-09-20 · A complete-length transfer is not an integrity proof.**
  Runtime spool publication can now validate an expected SHA-256 before linking
  the final name. Obtain that expectation from a trusted immutable source
  snapshot, not from the just-received bytes. Without it the API remains
  size-only; the optional parameter is not evidence of transport integration.
  Test equal-length corruption and compare successful output by another tool.
- **2026-09-20 · Verify importer identifiers from the parser, not helper prose.**
  A neutral real-PG fixture supplied 32 hex characters but the canonical regular
  stats parser stored 8 via short_guid. The first test's 32-character assertion
  was wrong; corrected after inspecting the actual parser and observing DB rows.
  Do not change persistence semantics to satisfy a mistaken test expectation.

- **2026-09-20 · Explicit configuration is not enough if imports initialize the process.**
  The manager previously imported dotenv and configured root logging before its
  constructor could inspect supplied config. R04d moves legacy setup behind
  the default loader while preserving dotenv-before-log-path selection. Test in
  fresh processes with forbidden imports; also pin unchanged sys.path and root
  handlers. Import-only callers intentionally no longer initialize logging.


- **2026-09-20 · Header-free payload equality is not cross-half identity.**
  An unchanged cumulative R2 has the same payload hash as R1. Canonical import
  and neutral duplicate preflight must scope successful hashes by half before
  treating them as mirrors. A disposable-PG test proves R2=0 plus its own event;
  removing the SQL half filter loses that half. Same-half cross-match identity
  still needs a stronger source contract; do not infer it from this narrow fix.

- **2026-09-19 · A neutral process needs neutral configuration.**
  shared.config reexports BotConfig and its validation requires Discord. The
  cache entrypoint reads explicit environment without dotenv or that validator,
  defaults OFF before network, and owns its native pool/task. Prove independence
  by actual subprocess imports, catch-up and signals, not just a coroutine test.
  A dev label/local host is not attestation that the chosen database is dev.


- **2026-09-19 · Source retention does not prove independent ingestion.**
  Design21 section7a overstates bot/web independence. Files waiting on the source
  can be replayed later while the writer still stops with Discord readiness.
  Trace startup, cadence and metadata transport before claiming bot/web-off DB
  continuity; keep that R04 acceptance proof separate from durable cache receipts.

- **2026-09-18 · A closed asyncpg connection may raise InterfaceError.**
  It is not a PostgresError. A polling worker that retries only database-server
  errors can stop permanently on a closed connection. Retry InterfaceError only
  when the acquired native connection confirms is_closed; propagate other
  interface errors to avoid hiding misuse. Prove reacquisition with actual PG.

- **2026-09-18 · Generation keys need a bounded memory backend.**
  Reading only the current namespace never touches expired older keys; lazy
  deletion of the requested key cannot reclaim them. Clear-on-generation-change
  alone also allows late old requests to insert again. Bound count and retained
  string bytes, prune expired entries on writes, and test late old-epoch writes.
  State per-worker storage limits separately from RSS and serialization peaks.

- **2026-09-20 · Verify importer identifiers from the parser, not helper prose.**
  A neutral real-PG fixture supplied32 hex characters but the canonical regular
  stats parser stored8 via short_guid. The first test's32-character assertion
  was wrong; corrected after inspecting the actual parser and observing DB rows.
  Do not change persistence semantics to satisfy a mistaken test expectation.

- **2026-09-20 · Explicit configuration is not enough if imports initialize the process.**
  The manager previously imported dotenv and configured root logging before its
  constructor could inspect supplied config. R04d moves legacy setup behind
  the default loader while preserving dotenv-before-log-path selection. Test in
  fresh processes with forbidden imports; also pin unchanged sys.path and root
  handlers. Import-only callers intentionally no longer initialize logging.


- **2026-09-20 · Header-free payload equality is not cross-half identity.**
  An unchanged cumulative R2 has the same payload hash as R1. Canonical import
  and neutral duplicate preflight must scope successful hashes by half before
  treating them as mirrors. A disposable-PG test proves R2=0 plus its own event;
  removing the SQL half filter loses that half. Same-half cross-match identity
  still needs a stronger source contract; do not infer it from this narrow fix.
- **2026-09-20 · Undefined disk capacity is not zero usage.**
  A zero denominator must produce unknown, not healthy 0%; used>0 with free=0
  is instead measurable 100%/fail. Compare collector ratios with df used/available
  bytes, not exact displayed integers: df rounds its displayed percentage upward.

- **2026-09-20 · A failed reservation may still own its namespace.**
  Atomic mkdir prevents two same-token writers from reserving one generation.
  A later fsync failure can leave that directory; retry must refuse reuse even
  when empty. Never infer an empty directory is free. Keep source reservation,
  immutable payload completion and durable receipt delivery as separate states.

- **2026-09-19 · Lint modified legacy files as well as new modules.**
  R04c's new files passed Ruff but its legacy re-export block failed CI I001.
  Include every changed Python path in local lint. Module-attribute aliases
  retain the legacy function identities without unused-import ambiguity;
  mutation-test the export identity rather than assuming an alias is correct.

- **2026-09-19 · Parser parity needs nonempty players and a controlled clock.**
  The committed legacy sample_stats_files parse headers but zero player rows.
  Header parity alone cannot certify R2 player calculations. Supply valid player
  lines with a known differential and freeze the parser's generated timestamp
  when comparing subprocess outputs. A blocked-import subprocess proves absence
  of Discord/config dependencies more strongly than checking imports in pytest.

- **2026-09-19 · A neutral process needs neutral configuration.**
  shared.config reexports BotConfig and its validation requires Discord. The
  cache entrypoint reads explicit environment without dotenv or that validator,
  defaults OFF before network, and owns its native pool/task. Prove independence
  by actual subprocess imports, catch-up and signals, not just a coroutine test.
  A dev label/local host is not attestation that the chosen database is dev.


- **2026-09-19 · Logging emission is separate from process setup.**
  Importing bot.logging_config creates its log directory. Runtime-only callers
  can use shared.database_logging without that side effect; legacy exports stay
  compatible. Prove the boundary in a fresh subprocess with forbidden-import
  hooks, then mutate an import after definitions so a circular-import collection
  error does not masquerade as an executed boundary guard. Manager startup still
  needs its own extraction; moving dotenv imports can change log-directory order.

- **2026-09-18 · Verify release registration from the evaluated array.**
  A migration filename appearing somewhere in a shell config does not prove
  membership in MIGRATIONS: even a comment passes a substring assertion.
  Inspect the evaluated Bash array and compare exact entries. Commenting out
  migration 090 reproduced the missing-registration failure; restore with cmp.

- **2026-09-18 · Every new round_id table needs a linkage decision.**
  The schema-driven coverage contract also applies to runtime receipt tables.
  lua_correction_receipts records the target of a committed correction, so
  generic relinking must not rewrite its historical provenance. Add a justified
  exemption and run test_round_id_coverage_contract.py alongside PG proofs;
  focused transaction tests alone did not catch this CI failure.

- **2026-09-18 · Measure the pre-push hook's actual comparison range.**
  New branches compare with the main merge-base; existing branches compare
  with their previous remote tip, intersected with paths changed vs main.
  A three-file update can correctly pass while its dependent stack has26files.
  Do not mistake total stack size for the hook's update size or bypass the hook.

- **2026-09-18 · Test retention against the actual normalized producer.**
  Lua correction metadata uses END_REASON_ENUM (uppercase), not raw webhook
  text. A lowercase-only inbox validator rejected valid producer output while
  synthetic fixtures without end_reason passed. Reuse the canonical enum and
  exercise WebhookRoundMetadataService before retaining input; raw timelimit
  normalizes to NORMAL, not a new TIMELIMIT value.

- **2026-09-18 · Correction fixtures must preserve integer seconds.**
  A REAL fixture accepted values the live INTEGER player-duration column
  rejects. Use INTEGER in boundary proofs; validate finite, nonnegative,
  integral durations before SQL. Canonical helpers that swallow collisions
  cannot establish atomic correction success: enforce conflicts in the same
  native transaction as metadata, DPM and its journal event.

- **2026-09-18 · Post-import correction failure is not import failure.**
  The importer and bot mark the file successful before Lua overrides; ingress
  RAM/DB/session gates can skip any retry and pending metadata is popped.
  Rethrowing or moving only the bot marker cannot guarantee recovery. Give
  corrections their own atomic boundary and retained-input retry contract;
  do not misclassify an already committed import as RetryableImportFailure.

- **2026-09-15 · Retry ownership must travel with the chain.** Capture the
  original webhook claim explicitly when scheduling, retain it across attempts,
  and release it only on retryable terminal exits. Looking up the current alias
  owner at cleanup time can release a replacement. Immediate release while a
  retry is pending instead permits competing polling publication. Prove both
  pending exclusion and terminal alias cleanup with actual asyncio tasks.

- **2026-09-15 · A post-await duplicate needs the same trigger cleanup.**
  Another endstats attempt can claim a filename during DB preflight. The
  losing webhook must delete its notification just like the initial duplicate
  path, but must not release the winner's marker. Inject ownership during the
  awaited DB call and exercise both successful and failed Discord deletion.

- **2026-09-15 · A filename is not an attempt identity.** Polling cleanup
  must compare its claim object with the current owner before removing a RAM
  marker. A later retry may own the same filename, and richer selection may
  select an alias already owned elsewhere. Exception and soft-failure paths
  both need the identity guard; a raw set.discard silently defeats it.

- **2026-09-15 · Test the gate before the handler too.** Endstats had four
  filename gates, including monitor preflight in webhook_handler_mixin.
  A direct handler retry passed while real polling still rejected the failed
  filename. Exercise preflight plus handler/storage; preserve terminal and
  NULL/unknown states when narrowly allowing explicit publication failures.

- **2026-09-14 · Best-effort catches are unsafe around opt-in journal writes.**
  Restart detection used to swallow errors. With the status producer enabled,
  failures must reach the canonical import rollback; actual status update,
  event and notification share that transaction. Guard completed status in
  the UPDATE, not only the earlier SELECT, to avoid journaling stale no-ops.
  Atomic recording does not prove the restart heuristic itself correct.

- **2026-09-14 · Lock the selected source, not only the destination.** A
  NULL-only timing fill can commit stale Lua values if its source changes
  concurrently. Lock both selected rows with SKIP LOCKED until commit; prove
  both source-first skip/retry and fill-first blocked relinking on real PG.
  This is not a guarantee against later changes or newly inserted sources.

- **2026-09-14 · Initial-event dedup is not update-event dedup.** A timing
  source can undergo value -> NULL -> value across a repair. A permanent
  round/type or content-hash key would hide the later real transition. R02a
  keeps only the initial import key unique; row-locked NULL-to-value fills
  emit each actual transition and repeated successful fills are no-ops.
  Consumers still cannot use sequence ID as commit order.

- **2026-09-14 · Rollback is not retry eligibility.** FileTracker treats
  success=false processed_files rows as terminal too; UltimateBot also cached
  them in RAM. DB/preflight/transaction failures must return a structured
  retryable result without either marker. Keep deterministic parse failures
  separate. R01 proves a failed journal import can retry and commit; existing
  activity/lookback windows still limit automatic recovery.

- **2026-09-10 · A migration has three installation paths to keep aligned.**
  R01 initially added SQL alone, omitting the latest release config and the
  canonical dump used before deploy_clean's baseline. Register it in the
  release array and mirror DDL in the dump; run release-contract and real
  fresh-bootstrap parity tests. A local opt-in PG test also needs an explicit
  CI path or its only real SQL coverage silently skips in the matrix.

- **2026-09-08 · Import success must be logged after transaction exit.**
  `pg_notify` participates in the import transaction and can fail at COMMIT;
  the emitter returning does not prove persistence. R01 moves success counts
  and logs after COMMIT; a canonical-import test injects commit failure and
  checks that no success is reported. Updated 2026-09-14: transient failures
  now leave no terminal processed-file marker, so a later poll can retry. This mock is
  wiring evidence, not real PostgreSQL transaction proof. Initial journal
  events are not final-round events: validation warnings and post-commit
  correlation/Lua/endstats changes remain distinct facts.

- **2026-09-07 · Commit, artifact, process and data are separate evidence.**
  The handoff audit found merged SPA source newer than the served bundle.
  Why: a healthy endpoint and matching git revision do not identify static
  assets. Apply: record source/build identities and process start time before
  live proof; never close a runtime obligation from a merge alone.
- **2026-09-07 · Canonical import is earlier than data finalization.**
  At the 2026-09-07 audit, `process_file()` committed stats before later updates;
  `processed_files` is also written after that commit. Why: a Discord-only
  emitter misses other inputs and a first event cannot promise final stats.
  Apply: emit transactionally in the canonical importer, deduplicate the first
  event durably and cover late changes before enabling consumers.
- **2026-09-07 · Record the safety-policy snapshot when reviewing tooling.**
  At `4f653c01` the review cutter contradicted the general force/no-verify ban;
  #961 subsequently added a narrow legacy-script exception. Why: simultaneous
  handoffs change policy while audits run. Apply: preserve the written exception
  without extending it; the approved Astra plan prepares an immutable replacement
  with ordinary hooks. Do not confuse preparing the replacement with deploying it.
- **2026-09-07 · Configured Codex hooks are not necessarily active.**
  The local hook was hardened and credential-bearing saved approvals sanitized,
  but hooks/list still reports both hooks untrusted. Apply: owner reviews /hooks;
  never claim lifecycle enforcement from synthetic subprocess tests, and never
  log real tool input to prove integration. Rotation remains a separate action.

- **2026-09-07 · A directory's mtime is not its contents' mtime.** `ls -la
  <dir>` reports when the directory entry list last changed (a file added or
  removed), not when files inside were written; a rebuilt bundle that reuses
  its file names leaves the directory mtime untouched. Ask the files:
  `find <dir> -type f -printf '%T@ %p\n' | sort -n | tail -1`. This is how a
  13-hour-old SPA bundle looked fresh on 2026-09-07 (sister session).
- **2026-09-07 · A cold cache changes how many calls a measurer sees, not
  only how long they take.** The same page produced 2 observed API calls in
  one window and 40 in another, depending on whether the backbone was warm.
  Every recorded number states cold/warm, and nothing is compared with a
  number taken right after a restart (sister session; see also
  `docs/AGENT_LOG.md` 2026-08-29 "second call is not a measurement").
- **2026-09-07 · `git stash list` before `git stash pop`.** A stash left by
  another session on the same working tree pops into a clean tree as
  conflicts that look like your own. On a shared box, list first and pop by
  index, or do not stash at all — commit to the branch (sister session).
- **2026-09-07 · An artefact is not a commit.** `/api/build` reports the git
  commit the process runs from; the SPA bundle it serves is a build product
  with its own age. Both were checked on 2026-09-07 and only the commit was
  current. `scripts/dev_deploy.sh` now refuses a bundle older than its
  source (exit 3, #960); when a deploy "looks right", also compare the
  bundle's newest file against the last commit touching `src/app`.
- **2026-09-06 · One row's age carries two meanings; say both.** (Review of
  #949 by the sister session.) `server_status_history` stops moving when the
  bot is down AND when its monitor loop fails on every tick (the loop survives
  its own exceptions, `monitoring_service.py:277-279`); it never moves at all
  when `MONITORING_ENABLED` is off; and `logs/bot_error_streaks.json`'s
  `written_at` moves only on errors and resets (the idle endstats loop returns
  before its SSH call nine ticks in ten), so it is not a heartbeat either.
  Apply: a liveness finding names every cause the signal cannot separate, an
  empty table is `unknown`, a database that cannot be asked is `unknown`, and
  a threshold is read from the config that sets the cadence, not hard-coded.
- **2026-09-06 · `systemctl is-active` on a unit that does not exist says
  "inactive".** The watchdog reads `LoadState` first: a unit that is not
  installed on this host is `unknown`, not down — dev runs `etlegacy-*`,
  production `slomix-*`. Why: "inactive" invited starting a second copy by
  hand (2026-08-05). Apply: never derive "not running" from `is-active`
  alone; the watchdog never starts anything, it proposes the command.
- **2026-09-06 · A register is three existing lists made one, not a fourth
  list.** The profile endpoint's section allowlist (with measured costs), the
  formula registry's entry shape and routes.data.json's page keys already
  existed; `services/dataset_registry.py` unifies them and the profile router
  now derives its allowlist from it. Why: two lists of the same thing drift
  the day one is edited. Apply: before adding a registry/allowlist, grep for
  `frozenset({` and `get_registry` — derive, then pin the derivation in a test.
- **2026-09-06 · A window must apply on READ, not only in memory** (sister
  session, #923). Persisted error streaks without the 30-minute window on
  load woke up with yesterday's streak and announced a recovery for an outage
  that ended before the restart. Apply: any persisted counter carries its
  window into the loader; absent key = never failed OR recovered OR expired.
- **2026-09-06 · A payload can carry a zero AND an error; read the error
  first.** `/api/diagnostics` reports a failed monitoring table as
  `{count: 0, last_recorded_at: null, error: "query failed"}`; the About panel
  checked `'count' in m` and printed "voice 0 rows". Why: the zero is a
  placeholder, the error is the fact. Apply: in every reader, branch on
  `error` before any count; keep a constructed degraded fixture next to the
  recorded healthy one so the branch has something to fail on.
- **2026-09-06 · Guid prefix collisions exist only among bots.** Across every
  proximity guid source, 34 full guids map to 23 prefixes and the two shared
  prefixes are `OMNIBOT0`/`OMNIBOT1`; every human prefix is unique. Why: an
  8-char key is therefore a lossless lookup for humans and an honest 400 for
  bots. Apply: `resolve_player_guid` in `proximity_helpers`; never push
  `LEFT(guid,8)=` or `LIKE` into a main query (seq scan, en_US collation) —
  resolve once through the indexed `*_guid_canonical` column, then bind `=`.
- **2026-09-07 · The services no longer run from the working tree.**
  `/home/samba/share/slomix-dev-run` is a clone kept on `main`; venvs and
  the big read-mostly corpora are symlinks into the agents' tree, `.env` is
  a copy whose four absolute paths point at the run dir, static bundles are
  copied by `scripts/dev_deploy.sh` (no vite build on a 1.8 GB box). Why: a
  checkout in the working tree was a silent deploy twice on 2026-09-06.
  Apply: deploy to dev with the script; unit files live in `deploy/systemd`;
  a fresh venv per service is the next isolation step.
- **2026-09-06 · Scripted edits: count the token before adding an offset.**
  `s.index("\n  };") + 4` on a five-character token slid a `;` past the
  inserted block: one statement lost it, an empty statement appeared later.
  Legal TypeScript, so typecheck and 675 tests stayed green; CodeQL saw one
  half. Apply: after a scripted edit, diff the neighbourhood, and grep
  `^;$` / the moved character, not only the test suite.
- **2026-09-06 · A hash in a document may predate the history rewrite.**
  `docs/HANDOFF-next.md` carried `19c61847` as the base for the review PR;
  the rewrite of 2026-08-27 changed every hash and the real #802 merge is
  `87a7063d`. Why: a PR with a non-ancestor base shows the whole history as
  its diff. Apply: `git merge-base --is-ancestor <hash> origin/main` before
  building on any quoted hash.
- **2026-09-06 · Ultra review accepts ≤ 8 000 changed lines / 500 files.**
  Code changed since production (v1.39.0) is ~93 k lines, so reviews are cut
  by area with `review-base/NN-<area>` branches (main with the area reverted
  to v1.39.0) → `main`. Apply: measure `git diff --numstat` before opening a
  review PR; never merge a review PR.
- **2026-09-06 · "Who is building this" is not "is it built".** A sister
  session rebuilt compare/wrapped because it searched open PRs for someone
  *building* the routes; the merged (squashed) work shows no diff against
  main. Apply: `git ls-tree -r origin/main <path>` and `git log
  HEAD..origin/main` first.
- **2026-09-06 · `openapi.d.ts` is regenerated by npm `pre*` hooks, not by
  merges.** `npx tsc` after a merge fails on other people's code because the
  gitignored file is stale; `npm run typecheck` regenerates it. Apply: use the
  npm scripts, or `npm run generate:api` before bare `npx`.
- **2026-09-06 · Codex CLI loads no project instructions unless `AGENTS.md`
  exists** (`codex debug prompt-input "ping"` renders the developer messages
  without a model call and showed zero). Apply: keep `AGENTS.md` under the
  `project_doc_max_bytes` limit and re-run that command after editing it.
- **2026-09-05 · The Lua damage hook fires at the top of `G_Damage`.** It
  sees the target's health *before* the hit and fires for every entity,
  including `script_mover`. Apply: vehicle-health logic must not treat the
  hook value as post-hit.
- **2026-09-03 · `website/.env` overrides `POSTGRES_USER`.** Admin tools
  (`apply_migrations.py`, backups) picked `website_app` and could not own or
  read 7 tables. Apply: run admin tools with the root `.env` role explicitly.
- **2026-09-02 · `npm run build` is the legacy host; the SPA is `build:app`.**
  A wrong target succeeds and a live sweep then measures the OLD bundle.
- **2026-08-30 · `pkill -f` / `pgrep -f` match the shell that runs them.**
  Find a process by port (`ss -ltnp`) and kill by PID.
- **2026-08-19 · R0 (`round_number = 0`) rows are still being written and
  are read by nothing.** Any unfiltered sum doubles kills and damage. Apply:
  `round_number IN (1, 2)` or the `player_match_stats` view, always.
- **2026-08-18 · `rounds.actual_time` is the stopwatch target, not the
  measured duration** (overstates ~15 % of rounds). Apply:
  `shared/round_time.py`.
- **2026-09-07 · Review snapshots are not exempt from publishing guards.**
  Restoring a historical baseline can reintroduce a credential even when the
  source is already public. Apply: SHA-versioned review refs, at most 25 files
  and 8,000 changed lines per part, normal Git push with the real hook; scanner
  rejection blocks publication. Never refresh old review PR refs or bypass a
  scanner because a snapshot will not be merged. Local integration tests prove
  historical literal rejection; they do not certify all repository history.
- **2026-09-07 · Bundle mtime does not identify its source or target.**
  A fresh-looking SPA can belong to another commit or contain changed assets;
  checking after checkout already changes the run tree on failure. Apply:
  commit before `npm run build:app`, retain generated provenance, and validate
  exact target/input/output identity in a private staging directory before dev
  checkout. SKIP_STATIC no longer bypasses this check. Legacy provenance is
  separate; keep its existing bundle rather than copying unverified bytes.

# 2026-09-27: Cache rollback is an invalidation boundary

Follow-up: isolating only OFF is insufficient. ON/OFF/ON can retain the same
database generation if writes occurred while events were disabled. Both modes
need lifetime/transition isolation; worker-local response reuse also in ON mode
is the explicit tradeoff. Root env examples do not configure website/.env:
mirror required flags there and test their parsed defaults.

Reusing an unversioned OFF namespace can revive pre-activation responses after
an ON generation change. Keep OFF entries unique per middleware lifetime and
observed mode transition, and capture the token before awaiting. This also
isolates OFF workers; do not claim shared OFF cache reuse. Two ASGI proofs retain
the backend across both same-app toggles and app recreation. Both fail without
the namespace guard; source restored and cmp verified. Full cached HTTP/browser
TTL behavior and actual Redis restart behavior remain separate activation checks.
# 2026-09-28 — Immutable remote creation requires an atomic absence precondition

An ls-remote preflight followed by ordinary push is not create-only: a racer
can create an ancestor ref between the commands and the push will fast-forward
overwrite it. Reproduced using real disposable bare repositories for either or
both members of a review pair. Use an explicit empty expected value per missing
ref (`--force-with-lease=<ref>:`) together with atomic pair push. Despite the
option name this permits creation only, never replacement; all hooks remain
enabled. Installed git-push documentation states the named ref must not exist.
Regressions verify unchanged raced OIDs and no partial counterpart publication;
removing leases fails all three cases, then restoration is checked by cmp.
Do not replace this with generic force or a tracking-ref-inferred lease.

# 2026-09-27 — Explicit key-only SSH must reject partial authentication

Paramiko5 legacy SSHClient authentication can invoke auth_interactive_dumb
after a public-key result requests another factor, despite allow_agent=False
and look_for_keys=False. Use the modern AuthStrategy hook with one explicit
PKey.from_path key and require both an empty remaining-method list and an
authenticated transport. Default AuthStrategy iteration alone is insufficient:
it treats a returned partial-method list as success. Regression exercised the
installed legacy auth; offline installed connect tests cover RSA/ECDSA PEM and
OpenSSH plus Ed25519 OpenSSH. No real handshake claim. Missing, malformed and
encrypted keys must fail without prompt/fallback. Keep strict host-key policy.
# 2026-09-27 — Correction: PKey.from_path discovers adjacent certificates

The earlier key-only SSH note used PKey.from_path; that still discovers a
neighboring key_path-cert.pub and can offer a different certificate identity.
Actual generated OpenSSH certificate and malformed-sidecar regression tests
proved both behaviors. For the explicit private-key-only contract, read that
file once and use public RSAKey/ECDSAKey/Ed25519Key.from_private_key file-object
loaders. Do not pass a path-aware loader or certificate path; encrypted keys
fail without prompting. Existing five key-format proofs and complete-auth guard
remain; no real handshake was tested. This corrects the earlier implication
that disabling legacy auth alone removed all ambient identity discovery.
# 2026-10-05 — An index name in EXPLAIN is not bounded key access

Proximity exact identity applies LOWER(BTRIM(map_name)); a raw leading map key
does not match that expression. Owner-started disposable PG14 with100002rows
chose sequential scans for both canonical and strict queries. A normalized
non-unique expression index puts all three identity predicates in Index Cond.
Tests must inspect those conditions and buffer work, not only index presence.
Retain ambiguity detection and NULL-session parents; never make this UNIQUE or
partial on session readiness. TEMP local-buffer timing is not cold production
latency. Preserve migration/bootstrap/release parity; apply only via owner deploy.

## 2026-10-16 — Outside-Git proof outputs must have outside-Git ancestors

An existing /tmp/.git causes private bundle/workspace/service and bot-fixture
preparation to reject /tmp outputs as designed. Use a newly owned private
/var/tmp proof directory when that marker exists; do not remove the marker or
weaken the outside-Git guard. AST imports alone also miss existing-module
configuration integration and fixture exports; include their matching changes
and run collection before claiming the extraction is complete.

## 2026-10-16 — Prepared units and their manifest are separate integrity surfaces

A valid startup-contract JSON does not prove its sibling service files are
unchanged. Compare actual unit bytes against the freshly rebuilt contract,
then recheck both hashes and contract after observation. Mutating this byte
guard was observed failing for both roles. Keep all preparation proof distinct
from installed-unit, dependency, schema, active-process and activation evidence.

## 2026-10-16 — Keep the handoff routing preamble before the first H2

Execution-ledger guards read the section preceding the first H2. Inserting a
checkpoint at byte zero hides the authority/safety routing even if it remains
later in the file. Insert newest checkpoints after the complete preamble and
run test_execution_ledger_history_contract. Both original CI legs detected
this placement mistake; the correction preserves all original lines.

## 2026-10-16 — Verify systemd empty-property claims on the actual manager

Explicitly request --all for the supervisor property contract, but distinguish
portability from a reproduced incident: this host returns explicitly selected
empty properties both with and without --all. The real reader accepted the
stopped proof unit's empty namespace/cgroup. Regression guards the command
flag; no service restart is needed for this read-only evidence.

## 2026-10-16 — Migration-created indexes and snapshot constraints differ

Migration 036 creates the session-team uniqueness object with CREATE UNIQUE
INDEX; the schema snapshot adds a UNIQUE constraint. Source inspection proves
these distinct installation paths. Check the actual index keys/validity and
use ON CONFLICT column inference for this shared tuple. A pg_constraint-only
probe or ON CONSTRAINT target cannot represent the migration-created object.
Native upgraded-schema acceptance must remain separate from unit SQL stubs.

## 2026-10-16 — Preserve the venv interpreter's lexical leaf

Resolving bin/python to the base executable loses pyvenv.cfg discovery. Permit
that executable leaf link while keeping its bin/venv ancestors and config file
canonical, then pin target bytes and verify sys.prefix through the lexical
command. The observed standard venv test selected the intended prefix. This
is interpreter selection evidence, not a dependency inventory certificate.

## 2026-10-16 — A clean artifact does not certify dirty runtime source

SPA provenance already rejects an ordinary tracked-dirty snapshot; Git ls-files
flags alone do not. That snapshot cannot certify bytes copied at another time.
Keep local tracked/index guards, compare copied bytes to captured commit blobs,
and preserve unstamped partial outputs. A transient edit/restoration fixture
proved why self-consistent manifest hashes plus clean snapshots are insufficient.

## 2026-10-16 — Source admission must precede project imports

A tracked-clean Git tree can still contain untracked or ignored import shadows.
The supervisor CLI starts in -I mode, delays project imports until a closed
source/index inventory and exact commit pass, and disables bytecode writes. Use
a dedicated clean checkout and external environment/state; generated inputs
cannot be treated as source. Protocol fixtures do not prove installed-unit or
physical-engine admission.

## 2026-10-16 — Extend mapping alphabets with a new migration

The transport accepts periods/pluses in map names. Python binding validation and
SQL checks must accept the same alphabet. Preserve 099 even before its PR merges
when retained installations/candidates already reference its checksum; append104
and update the effective schema/release contract. Never edit live ledger hashes
to make a rewritten migration appear valid.

## 2026-10-16 — ReadWritePaths and proc environment are separate evidence

Systemd writable scopes do not confer filesystem permissions. Prepare this DEV
contract as its service user and require actual effective directory access and
write access to existing state files. A fresh child proved setdefault-loaded env
keys are absent from /proc/environ on this host; do not claim dynamic settings
were observed there. Compare visible approved values, preserve strict pre-start
inherited-override rejection, and keep application/config digest proof separate.
External state routing must include exposed SSHMonitor downloads, and compatibility
wrappers must preserve verification-mode CLI semantics as well as preparation.

## 2026-10-16 — Additive aggregates require durable replay receipts

A canonical rebuild must preserve proximity receipts whenever it preserves the
additive teamplay/crossfire/heatmap aggregates. Clearing only the receipt permits
double application on replay. Release explicit round links, retain admission and
hash flags, and compare complete receipt/aggregate rows after rollback and reset.
Bound import marker recovery must also preserve the journal validation warning;
missing original warning text requires an explicit warning, never false success.
Legacy date repair must refuse bound sources before deletes until reconciliation
has separately admitted the original sources. Legacy schema setup and runtime
workers must share the same usable unique-index admission predicate.

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

## 2026-10-16 — SQLite rollback journals stay outside data seeds

The existing state-source filter excluded SQLite databases, WAL and SHM but
missed rollback-journal filenames. Added-journal to that same refusal boundary:
auxiliary database state requires its separate consistent-backup contract, not
a normal data-file seed. A synthetic metrics.db-journal input now refuses before
copy; removing the new suffix produces one observed failure. Restored withcmp;
101 state seed/delta/writer-inventory tests pass. This does not make the tool a
generic secret scanner or a consistent snapshot of active writers.

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

## 2026-10-21 — PR #1101 review: strict relational provenance and recoverable admission

- Addressed reviews 4337378411/8425/8436/8445/8462: release v1.45.0 explicitly lists unmerged migrations 096 and 100; admission source IDs use the existing lowercase RoundIdentity alphabet; shared publication refuses unreadable/non-private temporary modes before the atomic link, preserving restrictive 0400 and ordinary 0600 without chmod.
- Migration 100 adds unique parent indexes and composite foreign keys: source/round/canonical ID must name the SAME stats mapping; filename/canonical ID/SHA-256 must name the SAME strictly linked receipt. Migration 096 requires runtime_parent_gate IS TRUE (NULL must not pass SQL CHECK). No merged migration was edited, no backfill or historical receipt adoption is introduced. Exact bootstrap blocks match both migration files.
- Local proof: 292 passed, 49 disposable-PG cases skipped; shared spool, completion, manifest read/retry, release contract and fresh-process admission recovery included. Source/mode/release guard mutants visibly failed 1/3/1 cases and source bytes were restored with cmp. Ruff and diff checks passed. New SQL rejection, post-link receipt mutation and three in-memory SQL guard-mutant cases await disposable CI PostgreSQL; skipped tests are NOT database proof.
- Prior published head CI job log independently confirms 42 schema cases passed and the sole Python 3.11 failure was the missing release config entries (11120 passed,161 skipped). That old SQL execution does NOT validate the new relational constraints. No database/service/browser was started and no production or DEV state changed.
- Continue the preserved runtime plan after fresh CI/review; #1101 still needs its own explicit owner merge permission. Existing approval for #1095–#1097 does not extend here.

## 2026-10-25 — PR #1101: actual PostgreSQL proof and rejected column-ACL review premise

- Verified public source head 9db6212a8c52905d4b45515affeda496856d3049 against CI run 39654495446, both Python jobs SUCCESS. PostgreSQL 14 / Python 3.11 job 119411051105: 11140 passed,161 skipped,11 subtests; PostgreSQL 17 / Python 3.13 job 119411050977: 11144 passed,157 skipped,11 subtests. Each job executed all 57 proximity schema cases, including 49 database cases, eight direct/PUBLIC column-ACL cases, three inherited-access refusals and three observed SQL guard mutations. Schema case counts independently agree via parsed log records and line counts.
- This closes the previous missing disposable-PG proof for the Oct21 relational constraints. Native PG executed the mismatched stats parent, legacy/unlinked/hash-mismatched receipt, nullable gate, post-binding receipt edits, migration replay and SQL mutant cases. Local services/databases were not started or changed.
- Review 4340613934 / PRRT_kwDOP4ZX3s6u52sJ is a false positive: the claimed column-ACL test failures are contradicted by both actual CI logs. PostgreSQL REVOKE documentation explicitly states table privilege revocation also revokes corresponding privileges on every column: https://www.postgresql.org/docs/17/sql-revoke.html . Existing REVOKE ALL covers direct website_app and PUBLIC column grants; inherited access intentionally remains a refusal. No redundant column enumeration or SQL/bootstrap change is needed.
- Evidence is in the public CI jobs; private downloaded logs remain outside git. Continue the original runtime plan and review queue. PR #1101 remains unmerged and still needs its own explicit owner merge permission; approvals #1095–#1097 do not extend to it.

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
