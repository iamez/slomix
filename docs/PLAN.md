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

**Zadnja posodobitev:** 2026-09-03 (Fable 5.1, uploads rezina 2)

## Track: runtime v2 R01 (Astra)

### R02d4 atomic retained-input repair — local implementation 2026-09-18

Branch feat/db-runtime-lua-repair-r02d4, parent #1048 fa6ef789. DB-only attempt
locks source identity then input then round/players; retain shares advisory lock.
Checks payload version/digest/normalized identity before and after locking.
Exact target only, missing/ambiguous/revision conflicts return explicit outcomes.
Migration089 receipt commits with correction/event, including nested adapter
transaction/savepoint. No scheduler, retries/backoff or revision arbitration yet.
97 focused cases passed, zero skips, two existing warnings; Ruff clean. Actual
PG proves receipt failure rolls correction/event back, concurrent duplicate
applies once, revision arrival waits then conflicts, and missing target retries.
Mutation replacing outer transaction with connection failed assert600==1800;
restored with patch/cmp before final run. Temporary PG stopped. Read-only review
identified case-sensitive target lookup inconsistent with parser-preserved map
case; fixed with lower/btrim lookup and normalized ambiguity tests. Not all round
writers share the advisory lock,
so target uniqueness is not protected against a nonparticipating concurrent insert.
Receipt records completed attempt, not permanent equality of live round data.
Local commit awaits approved #1041 stack reduction before publishing new paths.
Final local follow-up: 105 focused cases pass after normalized-map fix and input
ID validation. Reverting normalized lookup failed both mixed-case target tests
(missing_round instead of applied; applied instead of ambiguous_round); restored
with patch/cmp and full rerun. Ruff clean, temporary PostgreSQL stopped again.

Published draft #1049 after #1041 merged. CI caught an omitted round_id
coverage decision for lua_correction_receipts (two contract failures; 6981
other cases passed on Python 3.11). Added the justified relinker exemption:
receipt target is historical transaction provenance, not a repairable link.
All seven coverage contracts pass; removing the exemption reproduced the
failure, restored with patch/cmp. No migration or live-data change involved.
The additional file waits for #1042 to merge before pushing within the
25-file stack limit. #1042 has all 22 checks green and its merge cycle active.

### R02d3 intake wiring — started 2026-09-18

Separate branch feat/db-runtime-lua-intake-r02d3, parent #1046 b5b34195.
Initial feat/bot-* name missed the existing runtime push CI filter; renamed
to feat/db-runtime-* before treating any CI state as merge evidence.
Default-OFF inbox gate + configured source identity. STATS_READY captures after
identity/ghost gates but before RAM metadata queue/worker dedup; GAMETIME captures
after identity fallback before team storage/correlation. Persistence errors must
prevent volatile dispatch, not issue success. No worker/repair/DB-outage recovery
claim. Preserve OFF callers with no adapter. Prove real PG storage despite later
dispatch failure and zero downstream work on storage failure.

Implemented and locally verified: 70 focused tests passed, zero skips in final
selected run, two existing websockets warnings; Ruff clean. Earlier broader
selection also reported existing test_stats_ready_file_selection module skipped
because _extract_stats_filename_timestamp is unavailable; not claimed covered.
Actual PostgreSQL proves retained input after queue refusal/exception and later
team-storage failure; input storage failure prevents RAM/worker dispatch.
Removing the STATS_READY capture failed with assert 0 == 1; restored/byte cmp.
Read-only review caught invalid GAMETIME starving later files; validation now
returns False per file and actual polling-loop test proves invalid then valid
input, marking only the valid file handled. Temporary PG stopped after proofs.
Capture remains AFTER outer Discord message-ID dedup/rate limits/task scheduling
and GAMETIME processed-index/lookback gates. No all-ingress/backfill guarantee;
DB failure redelivery of the same Discord message remains an explicit gap.
No automatic correction worker yet. New feature remains default OFF.

### R02d2a durable correction inbox foundation — started 2026-09-18

PR #1046 external review follow-up: preserve producer measurement presence in
_correction_present_fields while leaving legacy zero defaults unchanged. Inbox
omits missing/invalid measurement defaults, retains measured zero, omits missing
zero round end, and rejects unknown map sentinel. Optional end_reason clarified.
Use transaction-aware adapter fetch_val/fetch_one and ? parameters; dependency
remains the adapter, not the Discord bot. Initial expanded run: 110 passed;
presence-filter mutation failed both degraded producer cases, restored/cmp.
Follow-up local review: unknown/empty/null end reason also falls back to NORMAL;
only recognized explicit reason is now marked present. 76 focused inbox/producer
tests pass after this addition. Legacy display defaults remain unchanged.

Separate branch feat/db-runtime-lua-inbox-r02d2, parent f4dd404e (#1045).
First bounded slice: normalized/versioned allowlisted payload, durable input
row and duplicate receipt. API never updates existing inputs; direct SQL is
not protected by an immutability trigger. Preserve distinct payload revisions; never
choose a winning revision by arrival time. No ingress wiring, worker, automatic
repair or outage recovery claimed in this foundation. Positive exact identity
required; legacy incomplete metadata rejected, not assigned by time proximity.
Next slices must wire capture BEFORE RAM dedup and atomically couple repair
completion with correction/event. DB-down capture and source receipts remain
explicit gaps. Prove committed visibility, duplicate/revision retention,
concurrent intake and rollback on isolated PostgreSQL before publishing.

Foundation implemented: migration088/bootstrap/release, normalized input helper,
fixed parameterized INSERT and digest-checked duplicate receipt. Source identity
is configured, not a webhook URL. Unknown payload keys excluded; strict positive
round identity required; optional end_reason must belong to END_REASON_ENUM.
Different revisions stay
separate, with no automatic precedence. Real producer compatibility added after
review caught initial lowercase-only reason validation. Test initially expected
TIMELIMIT; actual existing normalization is NORMAL, corrected explicitly.
66 focused tests pass, zero skips, two existing websockets warnings; Ruff clean.
Real PG proves committed visibility, new-adapter replay, concurrent duplicate
waiting, distinct revisions/sources, outer rollback and conflict refusal.
Digest-comparison mutation failed with DID NOT RAISE ValueError; restored using
patch/cmp before rerun. Temporary PG stopped; no live writes or activation.
Remaining: external review/CI, ingress wiring, bounded durable repair scheduling,
revision arbitration and correction-completion receipts. No restart/DB-outage
or fully independent ingestion proof claimed by this foundation.

2026-09-18 approved stack checkpoint: owner specifically approved #1040 after
the numbered request. cycle.sh completed required pause and reported red=0,
threads=0, behind=0, unchanged SHA; merged as 4a7e0738. Squash tree identical
to approved f1bd3bf5. Normal main merge into R02c1 had four squash-history
conflicts; retained existing child additions and verified zero content diff.
Ancestry propagated through R02c2/c3/c4/d with zero content diff at every step.
Stack now 20 files vs main (was 25), allowing separate R02d2 work. No deploy.
#1041 existing polling-budget finding revalidated with 36 unit/PG cases and
resolved with evidence; this is not merge approval for #1041. Test PG stopped.
#1045 Codex review at aeaaf345 reports no major issues; f428d34a checks passed
except Codacy action_required, whose parameter-binding disposition and hostile
input runtime proof are posted. Fresh ancestry-head CI must be collected.

### R02d Lua correction boundary — atomic implementation, 2026-09-18

R02d1 implemented behind EVENT_STREAM_ENABLED + LUA_CORRECTION_EVENTS_ENABLED
(default OFF). Native adapter transaction locks and revalidates round identity,
updates metadata/canonical ID/player duration and DPM, and records changed-only
round_lua_corrected plus ID notification atomically. Migration087, bootstrap and
release registration agree. Lua linking remains best-effort AFTER commit, not
part of the event receipt. No-op retries emit no event; canonical conflicts fail
closed. Duration uses nonnegative integer seconds, matching the real DB column.

Verification: 81 focused tests passed, zero skips, two existing websockets
deprecation warnings; Ruff clean. Real isolated PostgreSQL with production
adapter transaction/ContextVar (pool checkout stubbed) proves success, retries,
lock contention and rollback on player/event/notification/canonical failures.
Transaction-to-connection mutation failed three rollback cases with
`assert (600, 1700000000) == (1800, None)`; restored with patch/cmp before rerun.
Independent read-only review found no remaining blocker after INTEGER fixture
and duration/source-round validation fixes. Temporary PG stopped after tests.
Remaining: commit/push, draft PR, exact-head CI and external review. This is not
automatic correction recovery: retained-input repair remains R02d2 below.
Missing/nonpositive source starts retain weaker legacy identity semantics.

Historical discovery evidence:

2026-09-18 review follow-up: draft #1045, code aeaaf345; CI still running.
Codacy flags three possible SQL-injection sites. Inspected identifiers are
fixed FIELDS entries and values/notification ID are bound parameters. Added
real-PG hostile-key/value proof: SQL-looking end_reason stored verbatim,
unknown assignment key/session/canonical overrides ignored, tables intact.
Allowlist-removal mutation failed with `multiple assignments to same column
"winner_team"`; restored/cmp. Expanded focused suite: 82 passed, zero skips;
temporary PG stopped. Alerts need reviewer disposition, not silent suppression.
Stack contains 25 files vs main; no new-file expansion before stack reduction.
R02d2 must persist before RAM queue/dedup and must not reuse the stale-import
gate: that gate rejects an existing exact round, precisely the repair target.

Worktree /tmp/slomix-astra-runtime-r02d, branch feat/db-runtime-lua-overrides-r02d,
parent R02c4 8fd71059. Isolated PG characterization now proves legacy partial
commit: round duration/winner commit (600s/2), rejected player DPM correction
leaves player duration 1800s; error is suppressed and later linking is reached.
Actual override SQL runs; canonical-ID and Lua-link side effects are stubbed.
Six focused tests passed (one real PG plus five existing exact-identity guards).
Mutation skipping round UPDATE failed the runtime assertion; restored/cmp,
rerun green. This discovery preceded the opt-in implementation above.

Independent caller/gate audit: initial importer and bot already mark file
success before override; RAM/DB/session gates prevent re-entry, STATS_READY's
duplicate fetch returns True without applying correction, pending metadata is
popped from RAM. Moving only bot mark_processed or rethrowing an error is not
recovery. Do not label a committed import RetryableImportFailure.
R02d1: opt-in atomic correction transaction implemented above, preserving
OFF/exact-target guards; not deployed or activated.
R02d2: separate metadata repair entry with retained payload/identity and its
own completion/retry state, independent of file-import dedup. Define Lua linking
coverage/lock ordering explicitly. Atomic correction is not automatic recovery.
Temporary PG stopped after proof; no live service or data changes.

### R02c4 endstats storage journal — in progress, 2026-09-16

2026-09-18 external checkpoint: draft #1044 at d493e1e7; CI 35316821230
and 35316784558 both SUCCESS at this exact SHA. External Codex comment
5726371027 reports no major issues. No inline findings observed in this pass;
this is not owner merge approval. Next R02 discovery target is
_apply_round_metadata_override: round metadata, canonical ID, player duration/
DPM and Lua linking currently have separate best-effort boundaries. Map callers
and transaction contexts before designing one atomic correction event.
R04 extraction must remove Discord readiness and voice-cadence dependencies
from SSH monitoring and preserve receive-before-worker Lua metadata ordering.
These are verified code dependencies, not completed independent ingestion.

2026-09-18 checkpoint: collected completed full focused run, 128 passed,
zero skips, two existing websockets deprecation warnings. Added richer DB-only
replacement (new event, no second Discord call), commit-only notification and
rollback silence, migration/release/default-flag checks and fresh-bootstrap
parity. No-op guard mutation produced two events instead of one and failed;
restored with patch/cmp before final run. Independent read-only review found
no blocker, but does not replace external PR review or exact-head CI.
Tests use a same-connection adapter stand-in; production ContextVar binding
was inspected, not exercised by that stand-in. Direct retry after Discord
exception does NOT prove recovery through the persisted NULL filename gate.
Concurrent journal contexts are not a full two-process publication proof.
Temporary PG was found still running on resumption and stopped immediately
after collecting test output; no application services were touched.

Implementation checkpoint: canonical storage now enters gated journal context
inside the native adapter transaction, before success/quality reads. Lock the
round, compare logical before/after multisets, insert round_endstats_changed
and ID-only NOTIFY on that same connection only for changed R1/R2 data.
Migration086, release registration and bootstrap SQL mirror added; new
ENDSTATS_EVENTS_ENABLED defaults false and requires global EVENT_STREAM_ENABLED.
124 focused cases passed, zero skips, two existing websockets warnings. Actual
handler + isolated PG proves committed event visible before mocked Discord
success/False/exception and no duplicate event on identical storage retry.
Storage/event/NOTIFY failure rollback, R0/R2/missing-round, OFF and concurrent
same-round waiting covered. Removing FOR UPDATE failed concurrency guard;
restored via patch/cmp and rerun. Ruff clean. Temporary PG stopped.
Remaining before slice completion: richer DB-only replacement proof, full
bootstrap parity, commit-only notification visibility, fresh review and CI.
No independent runtime/delivery guarantee or live activation claimed.

Direction audit (2026-09-16): original design 21 and R01-R04 remain aligned,
but independent ingestion and consumer catch-up are still future work. Snapshot
commit 364473ca passed exact-head CI 35067542754. Read-only independent review
and parent inspection require the round lock BEFORE success/quality reads, not
only before DELETE. Storage commit precedes Discord and final success marking;
this event cannot establish exactly-once delivery. Test publication False and
exceptions after commit separately from storage rollback.
Confirmed additional writers include repair_endstats_round_assignments,
reprocess_missing_endstats, backfill_vs_stats_subjects and manager round deletion.
R02c4 covers only the canonical pipeline; audit remaining direct/dynamic/cascade
writers before consumers assume complete correction coverage or activation.
Do not expand this slice to all maintenance scripts. No new infrastructure or
live activation is needed for this development step.

Worktree /tmp/slomix-astra-runtime-r02c4, branch
feat/db-runtime-endstats-journal-r02c4, based on R02c3 c4857ae7.
First foundation implemented: capture all persisted logical awards/VS columns
as multisets, ignoring generated IDs/clocks but preserving duplicate counts.
Numeric field is REAL in bootstrap; normalize float NaN to PostgreSQL equality.
Require caller transaction; caller must serialize round writers separately.
Nine isolated real PostgreSQL cases passed, no skips, including reorder/new
IDs/clocks, NaN, equal-count value changes, GUIDs, duplicate multiplicity and
round exclusion. Counter-to-set mutation failed the duplicate test; restored
with patch/cmp. This helper is NOT connected to the runtime producer yet.
Remaining: per-round serialization, migration/event contract and registration,
same-connection journal/notify integration, rollback/concurrency/OFF/bootstrap
proofs, review and exact-head CI. No claim that R02c4 is complete or activated.

2026-09-18 current checkpoint: #1042 merged as9ffbcd5e after all22 checks
passed and the prescribed pause; final gates zero red/open threads/behind,
unchanged head, squash tree identical to6929d143. #1043 retargeted main;
normal merge preserved all non-document content and both review findings remain
resolved. Recheck exact-head CI before the next conditionally authorized merge.
No deployment, service restart or live migration occurred.

### Current checkpoint — 2026-09-16

Owner explicitly authorized #1039. Prescribed cycle completed with zero red
checks, unresolved threads or behind commits and unchanged SHA. API confirms
merge fc65585568280049459adab08f373af4662de11d; its tree exactly matches
approved 8f5f21af. No deployment, live migration or activation occurred.
R02b retargeted to main via REST (old gh edit failed on projectCards), then
normal ancestry merges propagated through R02c1/c2/c3 without force. Each
merge tree compared identical to its pre-merge tree. 12 timing and 14 status
unit tests rerun successfully. New exact-head CI required after these pushes.
#1040/#1041/#1042/#1043 have NOT been authorized for merge. Next development:
separate endstats storage journal slice, using the local R02c4 design; the
approved timing merge removes the previous 25-file stack barrier. Historical
checkpoints below retain their original verification context.

### R02c3 polling exception marker ownership (2026-09-15; locally verified)

Handoff regression now asserts scheduler claim identity equals the webhook's
actual owner for all three scheduling exits. Passing None deliberately on the
unresolved-round path failed the assertion; restored with patch/cmp. This
guards the connection between handler and scheduler, beyond isolated helper
tests. Review/CI still pending; no activation or merge.

Latest review continuation: webhook passes its original claim explicitly into
the scheduler; a per-chain map retains that identity through rescheduling.
Exhaustion and missing metadata release only its still-owned original/alias
markers. Successful/DB-terminal processing retains handled RAM markers as before.
OFF keeps legacy filename discard; enabled callers with no claim do not remove
unowned markers. 78 focused cases passed (two existing websockets warnings),
including real bounded asyncio chains with alias replacement during DB await.
Four terminal-cleanup mutation cases failed (original/richer remained), restored
with patch/cmp. No pending test tasks, live services or PG changes. This closes
the exhaustion/missing-metadata alias gap below, not cancellation recovery,
cross-process exclusion or unknown persisted DB claims. External review pending.

Review 4014910266 partially addressed: retain webhook claim and release its
owned names after download/parse failure or caught exception. OFF remains
unchanged; a replacement claim survives cleanup. 36 focused cases passed,
including actual handler execution with synthetic SSH/parser/Discord failures.
Removing download cleanup failed the enabled regression; restored with patch/cmp.
Do NOT release immediately after scheduling a retry: that task bypasses the
in-memory entry gate and premature release permits a competing polling attempt.
Retry-chain alias cleanup/ownership transfer still needs a dedicated design and
proof; keep this review thread open. Persisted NULL/terminal claims still block
recovery even when RAM is released. No live runtime activation or PG rerun.

Follow-up proof: 39 focused tests passed. Three actual asyncio scheduler
cases (unresolved round, not ready, publication False) each create exactly one
pending retry, increment attempt count once and reject a competing RAM claim.
Synthetic external adapters; all test-created tasks cancelled and awaited in
finally. This proves handoff exclusion, not full-chain terminal alias cleanup.

Review follow-up 4014882361: a webhook losing its claim after DB preflight
now deletes the trigger, matching the existing duplicate path. Discord deletion
failure remains non-critical and the winning attempt retains its marker.
28 focused tests passed; actual async handler with injected preflight ownership
and mocked Discord deletion exercises both deletion outcomes (not live Discord).
Cleanup-removal mutation failed both cases: "Awaited 0 times"; restored via
patch/cmp and rerun. Full PostgreSQL suite was not rerun for this cleanup-only fix.

Branch `feat/db-runtime-endstats-markers-r02c3` in
`/tmp/slomix-astra-runtime-r02c3`. Enabled polling/webhook entry claims are
atomic after DB preflight; capture identity and propagate it to unowned richer
aliases. Polling exception cleanup releases only matching ownership identities,
not another attempt's existing alias or a later replacement claim. OFF retains
legacy set behavior. Persisted unknown/terminal markers still govern retry;
this adds no event, replay guarantee or cross-process lock. Test ownership
replacement, foreign aliases, OFF behavior and actual storage rollback/retry.

83 combined cases passed, zero skips, including 24 real PostgreSQL cases.
Injected award constraint failure rolls storage/claim back; owned RAM marker
is released and the next real preflight + handler call reaches storage again.
Synthetic parser/resolver/readiness/publisher only; no SSH/Discord/live DB.
Identity-guard mutation removed a replacement marker and failed with
set() != {'original'}, restored with patch/cmp; ownership tests passed again.
Helper's partial review identified remaining raw polling soft-failure discards;
those now use the same identity-aware release, with a foreign richer-alias
not-ready regression. Helper then hit usage limit; no complete final helper
approval claimed. Parent self-review/lint/83-case final run completed.
Cancellation retains existing behavior, and other scheduler/webhook cleanup
paths are not all owner-aware. Successful claims remain process-local for the
existing processed-set lifetime. No cross-process lock or exactly-once claim.
Temporary PG stopped, confirmed by pg_ctl and shutdown log. Next: PR/review/CI,
then endstats journal design. Stack reaches 25 files; never bypass the guard.
Published draft #1043, code 3d1dcd11, base #1042 branch. Codex/CodeRabbit review
requested, post-push self-review complete; external CI pending. #1039 verified
at 8f5f21af: all checks successful, both review threads resolved. Next authority
gate is owner-specific permission for #1039 merge (not deploy/activation).
Only #1012 was previously authorized and merged; do not infer the rest.
Follow-up: expanded foreign-alias route regression across all three polling
soft exits (not-ready, unresolved round, failed publication). Eight ownership
tests passed; no runtime behavior changed in this follow-up. #1043 CI still
running at check; development continues with review/test work, not an assumed
permission to merge #1039.

2026-09-18 merge checkpoint: #1041 merged via required cycle as a2b72550;
all final gates passed and squash tree equals approved8df7215b. #1042 now targets
main; normal synchronization preserved all non-document content. Existing review
finding fixed and reviewer-confirmed; zero unresolved threads. Refresh exact-head
main-target checks before next conditional-authorized cycle. No deploy/activation.

### R02c2 bounded webhook retry after exceptions (2026-09-15; in progress)

Worktree `/tmp/slomix-astra-runtime-r02c2`, branch
`feat/db-runtime-endstats-exceptions-r02c2`, based on R02c1 02c2113a.
With ENDSTATS_RETRY_ENABLED only, the webhook retry task's exception handler
reschedules through the existing delay/attempt budget instead of only removing
its task reference. Keep OFF behavior and asyncio.CancelledError propagation.
No filename state reclassification: a committed unknown/NULL claim still blocks
the next attempt, and publication ambiguity is not solved. Prove real asyncio
tasks retry a preflight DB exception, exhaust a permanent failure finitely,
and leave no child tasks running. Polling RAM recovery and journal remain next.

Local proof: 53 focused tests passed, zero skips. Four new tests execute real
asyncio scheduler tasks with injected DB failures: OFF one attempt, transient
failure then terminal gate two attempts, permanent failure max three attempts;
call counts and completed task counts agree. Cancellation propagates without
rescheduling. Disabling exception rescheduling failed two guards (`1 == 2`,
`1 == 3`), restored with patch/cmp; all four passed again with runtime output.
No database/server/Discord was started; fixtures simulate DB and reaction only.
Not a durable scheduler or a cure for ambiguous publication/NULL claims.
Read-only helper review found no blocker. Budget is per retry chain: later
external triggers may start a new chain. Cancellation preserves existing task-
map cleanup behavior; test task creation wraps asyncio directly, not bot startup.
Published draft PR #1042 against `feat/db-runtime-endstats-retry-r02c`, code
9c01c55b. CI 34934210971 in progress; external Codex/CodeRabbit requested.
Post-push self-review complete; no helper/task/server left running. Next:
polling exception marker ownership (do not discard another task's claim),
then transaction journal. Stack is 24 files against main; no guard bypass.

2026-09-18 owner authorization update: owner explicitly permits subsequent
merges when review has been performed, findings inspected/addressed (or justified
as not applicable), and checks pass. This supersedes the earlier per-number
approval workflow for this runtime work. Mandatory cycle.sh final checks/pause
remain; no deployment or service action is authorized by this update.
#1041 preflight: budget finding resolved with fix e7948055 and 36-case actual-PG
revalidation; exact prior head2c43da1e checks green, no unresolved threads.
Refresh main-target CI on this documentation checkpoint before merge cycle.

### R02c1 explicit failed-publication retry (2026-09-15; locally verified)

Worktree `/tmp/slomix-astra-runtime-r02c`, branch
`feat/db-runtime-endstats-retry-r02c`, based on R02b 9344a47b. Before adding
endstats events, fix one verified entry gate: a persisted success=false,
error_message=publish_failed row currently prevents another attempt at all
four filename gates (including poller preflight). New ENDSTATS_RETRY_ENABLED defaults OFF; enabled gates
exclude only that exact failure state. Keep successes, terminal duplicate/
supersede/unresolved markers, NULL/in-flight and unknown states terminal.
No historical backfill or automatic reset of RAM markers. Existing retry
budget/activity/lookback policy remains; no exactly-once publication claim.
Prove real polling/storage flow: failed publication persists marker, next poll
reaches storage and successful publication, third poll skips. No real Discord
or live database. Exception/RAM recovery and event emission remain later slices.

Implemented: shared exact-state SQL gate at all four entry points. Helper
review found the initially missed monitor preflight in webhook_handler_mixin;
fixed it and extended PG proof through that real preflight and real storage.
68 combined tests passed, zero skips (19 real-PG cases); two existing websocket
deprecation warnings. Synthetic parser/resolver/readiness/publisher replace
external inputs, not the filename queries or transactional awards storage.
Two connections verify committed award/claim counts against fetched rows.
Disabling the helper caused `assert 1 == 2`; reverting only monitor preflight
caused `assert False` before the retry. Both mutations restored with patch/cmp;
final preflight + storage retry test passed. Temporary PG stopped, independently
confirmed by pg_ctl and log. No live services, data or flags changed.
Published as draft PR #1041 against `feat/db-runtime-status-r02b`, code
d2efd904. Post-push self-review complete; exact-code CI 34933912726 queued at
checkpoint. Codex and CodeRabbit review requested. Stack is 23 files against
main; no helper/server active. No merge permission inferred for this PR.
Next: review this prerequisite, then separately handle exception/RAM
recovery and endstats event storage. Do not call this full endstats recovery.

Review follow-up 4012369546: the earlier assertion that existing retry budgets
covered polling publication failures was incorrect. Added shared counting after
explicit False publication results, using endstats_retry_max_attempts across
entry paths in this process. At exhaustion, guarded SQL persists
publish_retry_exhausted; all gates block it, even after RAM markers are cleared.
Counts before exhaustion are process-local (restart resets them); this is not
a durable lifetime budget or cross-process exactly-once guarantee. Existing
unknown/NULL claims remain blocking. 71 combined tests passed incl. 22 PG cases.
Budget mutation failed with publish_failed != publish_retry_exhausted; restored
with patch/cmp, both runtime paths passed again. Temporary PG stopped by pg_ctl,
shutdown confirmed in log. No live data, services or configuration changed.

### R02b restart-status contract (2026-09-14, Astra; locally verified)

Worktree `/tmp/slomix-astra-runtime-r02b`, branch `feat/db-runtime-status-r02b`,
stacked on R02a 78aaf3a8. No merge, activation, live migration or deploy.
Contract: require EVENT_STREAM_ENABLED and ROUND_STATUS_EVENTS_ENABLED (both
default OFF). Keep existing restart heuristics; only journal actual completed
to cancelled/substitution transitions for R1/R2, on the canonical import
connection. Guard the update against stale selection; no event on a no-op.
Record old/new status and causing round ID, no player data. Event + status +
ID-only NOTIFY commit atomically; enabled-path errors must reach import rollback
and retry eligibility rather than the detector's legacy best-effort catch.
Migration 085 extends event checks; register release and mirror bootstrap.
Prove commit visibility, rollback, concurrent no-op, R0 exclusion, both flags,
and failure propagation. Existing OFF behavior and complete-match guards stay.
This is not all status writers, historical replay, or independent ingestion.

Implementation and local proof complete: 113 combined cases passed, zero
skipped, including six real status-PG cases, R01/R02a regressions and full
fresh-bootstrap parity. Later real-create-catch unit added: 14 status unit
cases passed. Parser/current INSERT/stat writers are stubbed in canonical PG
proof; real detector and outer import transaction run. Actual create method's
catch returning None is separately pinned; process_file rejects None inside
its transaction. Both statuses, R0/no-op, concurrency, commit-only notification,
event/NOTIFY rollback and retry without terminal marker are exercised.
Mutation removing completed-status predicate failed both no-op guards with
`assert not True`; restored with patch and cmp before the combined run.
Temporary private PG stopped, independently confirmed by pg_ctl and log.
Reviewer status_contract_audit found no blocker; recommended enabled complete-
match protection and real-create-catch tests, both now added. Separate roster/
counterpart reads remain heuristic, not newly proven concurrency-safe.
Published as draft PR #1040 against `feat/db-runtime-timing-r02`; code b6137a61.
Verified 2026-09-15: exact-SHA CI 34860352518 SUCCESS; Codex external comment
5666250588 reviewed b6137a61 and reported no major issues. CodeRabbit did not
complete its review (rate limit), so no approval is inferred. Post-push diff
self-review complete. R02a 78aaf3a8 passed CI 34859363030. No live changes.
Next: finish external review and request owner-specific merge decisions in
dependency order #1012 -> #1039 -> #1040. The stacked diff is now 25 files
against main; do not bypass the push guard to grow the stack. Remaining R02
writers are Lua metadata/DPM and endstats; then consumer receipts/catch-up,
then independent Linux capture/import. No active test server/helper remains.

2026-09-15 follow-up: sanitized template now explicitly sets the status flag
false. Fourteen status unit cases passed; changing that template value to true
failed its contract guard, restored with patch and cmp. #1012 merge explicitly
authorized by owner and completed: squash 9cbd8810, cycle reported zero red
checks, unresolved threads and behind commits, unchanged SHA. Verified merged
through both cycle output and GitHub PR state. Dependent branches synchronized
without runtime code changes; #1039 now targets main, #1040 still targets #1039.
R02b stack is now 18 files against main, so the previous 25-file boundary no
longer blocks a separate next slice. #1039/#1040 still need individual merge
permission. No deploy or activation. Next development slice: R02c as below.

**Next slice discovery (not implemented):** endstats storage already has an
adapter transaction in `_store_endstats_and_publish`; bind its native connection
for the event before transaction exit. Existing success/quality decisions and
awards/VS replacement need per-round serialization and complete normalized row
comparison, not counts, to distinguish a real change from a publish retry.
The storage event cannot mean Discord delivery: correlation/publish/handled
markers occur afterward, and richer replacements intentionally skip publishing.
Polling and webhook retry check filename existence even for failed claims;
polling's outer exception also retains its RAM marker. An enabled journal must
repair and test these retry paths before claiming recovery. This remains a
separate R02c contract, not an excuse to activate incomplete consumers.

### R02a timing-fill slice (2026-09-14, Astra)

Branch `feat/db-runtime-timing-r02`, worktree `/tmp/slomix-astra-runtime-r02`,
stacked on R01 b81221d6 (PR #1012 CI/CodeQL/Hygiene confirmed success).
R01 merged with explicit owner permission on 2026-09-15 as 9cbd8810.
R02a is development only; both event flags default OFF.
Published as draft PR #1039, base `feat/db-runtime-events-r01`, code 0eceda4c.
Update 2026-09-15: retargeted #1039 to main after R01 merge. Synchronized
main in 8b2b60ab; resolved squash-history conflicts with a byte-identical R02a
tree (new main was exactly R01 b81221d6). Fresh checks required for this head.
Source-lock review resolved after proof and CI; owner-role review answered:
deploy_release.sh already exports root-env owner credentials to the runner.
No migration, service restart or activation occurred. #1039 is not authorized
for merge. Its diff against main is now 13 files.
Push CI now narrowly includes `feat/db-runtime-*`; PR targets stay main/develop.
Exact commit 2e2359db passed CI run 34858646087. The branch-pattern guard passed
and failed when the runtime pattern was removed, then was restored with cmp.
Later review fixes require their own exact-SHA CI; do not transfer this result.

- New immutable migration 084 extends the journal for `round_timing_reconciled`;
  initial import keeps its partial unique index, later transitions append.
  Register in release config and mirror in canonical dump.
- One producer: NULL duration -> timing from exactly one usable Lua row.
  R1/R2 only, at most 100 rows/poll, row locks + SKIP LOCKED. Timing, scoped
  canonical ID, event metadata and ID-only NOTIFY share an adapter transaction.
  Event/commit failure rolls back; NULL remains eligible on the next poll.
- Two flags required: EVENT_STREAM_ENABLED and ROUND_TIMING_EVENTS_ENABLED.
  OFF preserves the existing path. ON excludes R0 and ambiguous Lua matches;
  canonical-ID work is restricted to changed rows, not the historical corpus.
- Not covered: corrections to already-present duration, restart status repair
  of older rounds inside canonical import, Lua override/DPM writers, endstats,
  proximity. No consumers/finalization claim, production migration or deploy.
- Verification: 106-case isolated PostgreSQL run passed (zero skipped), including
  six R02 PG cases for commit-only notification, no-op repeat, concurrency,
  rollback/retry, exclusion of R0/ambiguous sources, initial-event compatibility,
  repeated NULL-to-value transition and 100-row bound; bootstrap parity CLEAN.
  Cluster stopped (shutdown log + pg_ctl). Later wrapper tests confirm no
  fallback legacy writes after an enabled-path failure. Disabled-guard mutation
  failed with AttributeError on transaction(), restored by patch and cmp.
- Deployment caveat: keep EVENT_STREAM_ENABLED=false until R02 code AND 084
  are installed. Original R01 SQL without the conflict-index predicate cannot
  target 084's partial index. Persistent canonical-ID conflicts fail the whole
  bounded batch and require investigation; no silent timing-only partial commit.
- Independent helper review was not performed: helper hit its usage limit before
  reviewing. External Codex review arrived afterward; finding and proof below.

- External Codex review 4006494535 identified an unlocked selected Lua source.
  Candidate selection now locks both round and source with SKIP LOCKED. Two
  real-PG tests prove a concurrent source update is skipped then retried with
  its committed value, and source relinking cannot pass the fill transaction.
  20 focused cases passed (eight PG, twelve unit). Removing the source lock
  failed both new guards (`assert 1 == 0` and missing LockNotAvailableError);
  restored by patch and byte-identical cmp. This does not cover changes made
  after the fill commits or concurrent insertion of another usable source.
  Restored PG rerun: eight passed. Temporary cluster stopped, confirmed by
  pg_ctl and shutdown log; no live services or data changed.

**Resume checkpoint:** clean code is in PR #1039; R01 #1012 is b81221d6 with
successful CI 34813122019, CodeQL 34813122027 and Hygiene 34813122066.
First refresh both PRs/review comments and the source-lock fix CI. R02a local proof is recorded above;
104 additional focused unit cases passed after wrapper tests were added.
No helper or test server remains running. Next R02b candidate is
`_detect_and_mark_restarts`: it changes an OLDER round's status on the current
import connection, and its broad catch must not swallow journal failure.
Then Lua overrides/DPM and endstats transaction producers; consumers and the
independent Linux ingest remain later stages, not already implemented.

### R01 position

Last updated: 2026-09-14. Owner priority: system runtime; frontend stays with
Fable. Worktree `/tmp/slomix-astra-runtime-r01`, branch
`feat/db-runtime-events-r01`. Code and isolated PostgreSQL proof complete;
PR #1012 open. NOT merged, live-migrated, enabled or deployed.

- 2026-09-14: CI actually ran: Python 3.13 had 6736 passed, 153 skipped,
  two failures in round-ID coverage (journal exemption missing). Added the
  explicit immutable-history exemption; no relinker may rewrite journal IDs.
  Review 4000153306 exposed terminal failure marking after rollback. Added a
  tuple-compatible retryable failure result; DB preflight/acquisition/write/
  NOTIFY/COMMIT failures leave no terminal DB/RAM marker. Known parse rejects
  remain terminal. Optional SSH monitor now propagates failed result rather
  than reporting success. Existing poll/activity/lookback limits still apply;
  this is retry eligibility, not a durable scheduler or exactly-once replay.
  Real isolated PG run: 106 passed, including canonical failed-journal import
  followed by successful round/event/marker commit (parser/stat writers stubbed),
  plus full fresh-bootstrap parity. Additional preflight unit case added after
  review. Retry flag mutation failed two guards, showing the terminal-mark log;
  restored by patch and cmp. Test cluster stopped. All live services unchanged.

- 2026-09-13: confirmed all three review replies persisted. Synchronized
  main 75ee10b5, retaining Supastats and runtime default-OFF flags and both
  backlog lanes. GitHub previously reported conflicts and only static checks;
  do not describe Python CI as green until an actual run is observed.

- Review follow-up (2026-09-10): fixed all three reported gaps: migration 083
  now ships in the newest release config and canonical fresh-bootstrap dump;
  CI explicitly opts into its loopback PostgreSQL service. Local runs retain
  the private-socket gate; CI requires GITHUB_ACTIONS plus exact test host,
  database and role. No application DB fallback. Added workflow/connection
  guards and exact journal DDL mirror check.
  Isolated rerun: 90 passed, zero skipped, including four real journal PG
  tests and full dump/migrations/baseline parity (`Validation: CLEAN`).
  The omitted-release-config test was seen failing before the fix. Mutation
  of CI opt-in to false failed (`assert 'false' == 'true'`), restored with
  patch and cmp. Temporary PG stopped; log and pg_ctl confirmed independently.
  This is local evidence, not a claim that GitHub Actions has executed the
  updated workflow; external CI status must be checked after push.

- R01: migration 083 and neutral initial-import emitter on the existing
  canonical importer transaction; `EVENT_STREAM_ENABLED=false`. R1/R2 only,
  unique round/type, versioned source metadata, validation-warning flag,
  transactional ID-only NOTIFY. No live migration, consumer or backfill.
- Verify disabled/no-table behavior, retry deduplication, canonical wiring,
  event failure rollback and notifications at commit using isolated PostgreSQL.
  Owner approved temporary PostgreSQL. On 2026-09-09 all four PG tests passed
  on a fresh PostgreSQL 14.24 cluster with a private Unix socket, no TCP
  listener, 16 MB shared buffers and no live-DB fallback. Two connections
  proved pre-commit invisibility, commit-only NOTIFY, rollback of round/event,
  missing-table rollback when enabled, OFF without migration, no R0, and one
  event for two concurrent attempts. COUNT and row fetch independently agree.
  Cluster stopped immediately; shutdown log and `pg_ctl: no server running`
  both confirmed it. Test data/logs remain local in the disposable /tmp cluster.
- Local verification: 21 new unit cases plus 18 neighboring importer cases
  pass (39 total); includes emitter and COMMIT failures. Disabled guard
  mutation failed with `AttributeError: 'NoneType' object has no attribute
  'is_in_transaction'`; restored by patch and `cmp` passed. New files lint
  clean; importer has the same 20 pre-existing Ruff findings as base HEAD.
  Minimal Python environment lacked `discord`; rerun used the existing full
  venv read-only, without installing anything. Success counters/logs now run
  after COMMIT. Combined rerun: 43 passed, zero skipped (39 unit + 4 PG).
  PG proof exercises the real emitter/SQL; canonical importer wiring and
  COMMIT failure are separately tested with mocks, not a full ingest replay.
- R02: map and journal post-commit corrections before consumers.
- R03: per-consumer receipts and durable catch-up, not maximum-ID cursors.
- R04: independent Linux Python capture/import/retry plus watchdog; remove
  Discord lifecycle/metadata dependencies before claiming independent ingest.

## Proga: nova stran (Fable)

### Kje smo

> **Predaja 10. 9. 2026 (owner ~3 mesece odsoten): `docs/HANDOFF-fable-2026-09-10.md`** — vrstni red za vrnitev
> (prejšnja, 9. 9., ostaja kot posnetek tistega večera: `docs/HANDOFF-fable-2026-09-09.md`)
> je §3 tam (ownerjeve odločitve → merilnik → dolg nazaj strani). Spider web je zaključen (STATUS), release 1.46.0
> (#956) čaka ownerja, Astrini PR-ji so nedotaknjeni.

Nova SPA (website/frontend/src/app) — faza 5 ZAKLJUČENA, faza 6 v teku.
Prod ZAMRZNJEN na v1.39.0 (ownerjeva odločitev 2026-08-28); dev soaka;
deploy NI naloga.

| stanje | vrednost |
|---|---|
| izdana verzija (dev) | v1.44.0 (2026-09-02); vlak 1.45.0 = #882 |
| endpoint gap (H1) | **8** — prešteto v `tests/data/endpoint_gap.txt` 9. 9. ob 00:30 (8 po `/api/players/{}/card` R3e; prej 9 (9 po `/api/stats/matches/{}` R3b in `/api/rounds/{}/player/{}/details` R3a); prej 11 (⛔ 9 → 11 je korekcija merilnika: klic, ki se konča z interpolacijo, je oblika `{}`, ne prefiks — `/api/stats/matches/{}` in `/api/sessions/{}` sta bila skrita; prej 9 po `/api/stats/player/{}/rounds` v #975) |
| proximity inventory pending | **0** (#884) |
| merilnik podatkovnih točk (`docs/parity/datapoints.json` unread) | 583 → **420** po spider webu (9. 9. zjutraj) → v PR-jih #1008 (tier-4 odločitve: planning brez vrstic; `/storytelling/scopes` ostane nepokrit in viden — hook ostane zaradi H1/inventarja, ki ju je owner zamrznil; promotion prefs ostanejo odprte do posnetka druge veje), #1009 R4g proximity igralec, #1010 R4h proximity po datumu, #1011 R4i greatshot/Home/diagnostika; odloženo: profil aim/advanced (17, ownerjeva pot A–F) |
| zgrajene strani faze 5 | proximity (6 rezin + 8 outcome instrumentov), player profil, team comparison, replay, spider-web SW-1 |
| zgrajene strani faze 6 | availability r. 1 (#887), uploads r. 1 (#888), live (#889, kurzor feeda popravljen po reviewu), greatshot (#890) |
| availability r. 2 (ta veja) | linked formi (settings, kanali prek link-tokena, DELETE), promotions (status+jobs, preview z recipients, schedule), betting (bazen, multiplikator, stava, denarnica; BREZ admin kontrol — owner 2. 9.); fixturi povezane stopnje prek dev sentinela (`scripts/e2e_sentinel_rows.py`) + harness posnetkov |
| uploads r. 2 (ta veja) | upload form (single-shot ≤ 50 MiB z XHR napredkom + cancel; resumable init/PATCH/finalize z 409 resync, HEAD resync, stall guard, abort), delete na detailu (dvostopenjsko); fixturi iz ŽIVEGA kroga s sentinelom (init→PATCH→finalize→detail→DELETE) |
| delovna površina | 2. 9.: 41→4 worktreejev, 400→43 lokalnih vej, #891 mergan; protokol v memory `worktree_cleanup_protocol_2026-09-02.md` |

## Proga: spider web do konca (Fable 5.1, 9. 9. 2026) — owner: »celoten spiderweb naredi do konca avtonomno«

Stanje slojev je v `docs/SPIDERWEB_STATUS.md`; spec `docs/PROXIMITY_SPIDER_WEB_SPEC_2026-07.md`.
»Do konca« pomeni: vse, kar spec dovoli brez ownerjevih vrat (Lua/prod) — narisano, izmerjeno
ali z zapisanim razlogom, zakaj ne.

| rezina | kaj | stanje |
|---|---|---|
| SW-2 platno | legacy kamera (axonometrična, vleka/kolešček/plan), floors po višini, p90 obroč, oznake brez premika, regije prepričanj pod team/player POV z obzorjem, merilo 512, POV po igralcu, trenutek v URL; `lib/spiderWeb.ts` + 48 prenesenih testov, SVG s tokeni | PR odprt 9. 9. |
| SW-3 vidna linija | `edges[].line_of_sight` iz W6-validiranega BSP tracerja (99,92 %), SAMO v world POV kot **oracle diagnostika** (§6.1: prosta pot je nujen, ne zadosten pogoj; nikoli vir prepričanja); null z razlogom, kjer mape ni v etmain; na sceni preklop »line of sight (oracle)« + izpostavljenost (koliko živih nasprotnikov ima čist žarek) kot diagnostična številka, ne metrika | PR odprt 9. 9. (stacked na SW-2) |
| SW-4 sloj 4 harness | §8 referenčna implementacija: (igralec, runda) nabor, mediana ZNOTRAJ runde, kronološka delitev blokov 70/30, bootstrap po blokih (max-T), zamrznjen družinski manifest s hashem; kandidati, ki so danes izračunljivi: gibanje v nepokrit prostor (sloj 3), izpostavljenost (W6 LOS), poravnava z valom (oracle diagnostika, ne za ladjo), geometrijska izolacija (diagnostika); izid = tabela §8.5 v `docs/research/` (lokalno) + povzetek v STATUS; **na stran gre le, kar preživi §8.4** | IZMERJENO 9. 9.: 901 rund, 57 blokov; kontrola dpm prestane, šum pade; nič ne gre na stran (tabela v STATUS) — PR |
| SW-5 dokumenti | STATUS/PLAN/BACKLOG vrstice, ledger vrstice `replay/round/{}/web` na 0 | sproti |

⛔ Ne v obsegu (ownerjeva vrata ali brez podatkov): Lua C1–C7 zajemi, `etl_supply` mesh (BSP ni v
indeksiranem etmain), W4b navigacijski graf (rabi validacijo proti opazovanim potem — raziskava, ne
rezina), objavljanje 12 neobjavljenih meshov (odločitev »premalo rund za bajte v javnem repu«).

## Proga: Astra (Codex CLI) — delovni paket predaje (7. 9. 2026)

Vir resnice za Astrino delo: **`docs/HANDOFF-astra.md`** (§C vrstni red 1–20 s
fazami: 1 = brez ownerjevih odločitev, 2 = po odločitvah, 3 = dolg; §D »ne
delaj« z razlogi; §E prva ura) + **`docs/HANDOFF-astra-inventory.md`** (popoln
inventar odprtega dela po območjih z `[S|M|L]`, virom, odvisnostjo in dokazom;
§11 = zbrane ownerjeve odločitve). Ista predaja brez sprememb je bila oddana
kot `/tmp/slomix-claude-handoff-to-astra-20260907.md` (ownerjeva zahteva).
Pravilo: Astra ob vsakem koraku posodobi TA razdelek (pozicija, PR, dokaz);
prečrta, kar je zaprto; ne premika prioritet brez ownerja.

- Pozicija 7. 9. 04:30: main po #960; #958 v vratih, #955 in #912 sledita
  (ownerjev DA 7. 9.: »zapri odprte PR-je razen Don't merge«); rezine #924–#943
  ponovno sekane po zadnjem mergu; bundle `static/app` NI zgrajen (RAM);
  prelet faze 7 NI ponovljen (RAM). Prvo Astrino delo = §C 1–2 (triaža ultra,
  watchdog r. 2), medtem ko čaka na ultra najdbe.
- 7. 9. 12:40 — owner: nova stran se bo »ful spreminjala«, dizajn na točkah ni
  všeč, telemetrija se zdi minimalna → izmerjena revizija modularnosti:
  `docs/SPA_MODULARITY.md` (verdikt po dimenzijah, 8 rezin sanacije, pravila),
  `website/frontend/AGENTS.md` (pravila), `docs/DESIGN_PUNCHLIST.md` (ownerjeve
  pripombe). Vrinjeno v Astrin §C kot 1b. Bundle se NE gradi (owner).

## Proga: štiri točke do Astre (6. 9. popoldne)

Vrstni red: (2) proximity guid prefiks (PR #945) → (3) diagnostics stanja
degradacije (PR #946) → (4) doc 19 r. 1 register datasetov (PR #947) → (1)
watchdog r. 1 (obseg `docs/design/24`, lokalno).

- **(2) proximity guid prefiks — NAREJENO 6. 9.** Izmerjeno: 34 polnih guidov →
  23 prefiksov; edini kolizijski prefiksi so botovski (`OMNIBOT0` ×9, `OMNIBOT1`
  ×4), ljudje 21 → 21. `LEFT(guid,8)=` je seq scan (61 ms, en_US collation);
  `storytelling_kill_impact.killer_guid_canonical` je indeksiran → resolver
  `proximity_helpers.resolve_player_guid` (canonical → `player_track` fallback →
  cache 10 min; 32 znakov passthrough; bot prefiks in slaba oblika = 400; miss =
  prefiks nazaj = prazen izid, ne 500). Vezan v 17 handlerjev (15 query-param +
  `/proximity/player/{guid}/profile|radar`), `/storytelling/kill-impact/details`
  primerja `killer_guid OR killer_guid_canonical`. AST varovalo v
  `tests/unit/test_proximity_guid_prefix.py` (vsak handler s `player_guid` mora
  klicati resolver ali biti v seznamu izjem z razlogom; mutacija videna pasti).
  SPA: drilldown vedno ponudi »proximity →«; e2e trdi, da `/proximity/player/D8423F90`
  pokaže profil. Odprto: `response_model` za `/profile` in `/radar` (ni v tem PR).
- **(3) diagnostics stanja degradacije — NAREJENO 6. 9.** Prenos iz zaprtega
  #911 v About panel (`components/DiagnosticsReport.tsx`): tabela brez štetja =
  razlog (pravi 0 ostane »0 rows«), prazen `time` = poizvedba ni tekla, padla
  monitoring tabela = `unavailable` (⛔ main je za `{count:0, error:"query
  failed"}` izpisoval »voice 0 rows« — živ hrošč, popravljen), 401/403 = odgovor
  (potekla seja / endpoint ne šteje računa za admina), sekciji `time` in `pool`
  novi. Backend: `response_model=DiagnosticsReport` z `exclude_unset` (odsotno
  ostane odsotno; `exclude_none` je varovalo pinnalo na eno ruto) → gap
  response_model −1. Fixture `api_diagnostics_degraded.json` (konstruiran, z
  `_note`). Mutacija (vrstni red `count`/`error`) videna pasti; oba posnetka
  brez izgube skozi model (`test_diagnostics_response_model.py`).
- **(4) doc 19 r. 1 — register datasetov — NAREJENO 6. 9.** Ni greenfield:
  poenotenje treh obstoječih stvari — `_PROFILE_SECTIONS`/`_HEAVY_SECTIONS` z
  IZMERJENIMI stroški (aim 16 887 ms, advanced 11 077 ms hladno) v profilnem
  routerju, oblika `formula_registry.py` (vnos = stvar + status + surface, brez
  tipa) in `routes.data.json` kot imenski prostor `page_key`.
  `services/dataset_registry.py` (34 vnosov: 14 profilnih sekcij, 8 sejnih,
  12 proximity/derived) + `GET /api/datasets` (tipiziran, javen, read-only,
  `DatasetRegistry{registry_version,count,datasets}`); profilni router
  IZPELJE `_PROFILE_SECTIONS`/`_HEAVY_SECTIONS` iz registra (en vir; »heavy« =
  ≥ 5 s hladno). Pravila, ki jih testi pinnajo proti VIRU, ne kopiji:
  `default_visible_on` ⊆ ključi `routes.data.json`, `depends_on` ⊆ ključi,
  `parity_key` = `data-parity`, ki ga SPA res renderira, `collection_toggle` =
  Lua `isFeatureEnabled` sekcija ali bot `*_ENABLED` (nikoli web-layer zastava,
  doc 19 §5). Kontrola: lažen `page_key` → test pade (videno, obnova `cmp`).
  SPA: tip `DatasetDescriptor`/`DatasetRegistry`, hook `useDatasets`
  (`staleTime: Infinity`), fixture `api_datasets.json` (GENERIRAN iz registra,
  z `_note`), e2e `datasets.spec.ts` (Playwright doseže endpoint, ≥ 30 vnosov,
  `aim` ni na profilu). Openapi posnetek osvežen (+148 vrstic). Brez UI —
  vrstica na About panelu pride po mergu #946 (isti panel). R. 2 (tabela
  `user_page_layouts`, column picker) po doc 19 §9 — ownerjeva odločitev.
- **(1) watchdog r. 1 — NAREJENO 6. 9.** `scripts/slomix_watchdog.py`:
  opazovalec, nikoli zaganjalnik (systemd ima `Restart=always`; ročni zagon
  zmaga v tekmi za vrata — 2026-08-05). 9 preverb kot ČISTE funkcije nad
  zbranimi vhodi (enote `systemctl show` z `LoadState` — neobstoječa enota je
  `unknown`, ne »inactive«; `/health`; DB `SELECT 1` + `pg_stat_activity`;
  runde proti kadenci `server_status_history` (300 s = »bot živi«); `/api/live/
  status` `newest_age_seconds`; mtime kolektorja `~/slomix-server-logs`;
  `frame_health` stalli ≥ 500 ms v 30 min prek `frame_health_report`; disk +
  journald; `lua_round_teams` proti `rounds`; + `logs/bot_error_streaks.json`
  sestre (#923: `version`, `written_at`, `alerted`)). Ravni ok/warn/fail/
  **unknown** (ni meritve ≠ ok). Politika (`decide`, čista): alarm ob prehodu v
  fail (web in lua_webhook šele ob 2. zaporednem), dedup 1×/h na ključ,
  »recovered« enkrat, dnevni heartbeat po 09:00. Stanje `logs/watchdog_state.json`
  (`version`), poročilo `logs/watchdog_last.json`, Discord webhook
  `WATCHDOG_WEBHOOK_URL` (samo https; brez njega izpis). Config iz KORENSKEGA
  `.env` (`dotenv_values`, nikoli `website/.env`), `WATCHDOG_DB_USER` privzeto
  `etlegacy_user`. Enoti `deploy/systemd/etlegacy-watchdog.{service,timer}`
  (oneshot, 5 min) — namesti OWNER. **Dokazi:** 24 unit testov (kontrole:
  odstranjena enota = unknown; brez dedupa dvojni alarm); živ `--once --dry-run`
  na dev: vseh 9 `ok` (disk 84,7 %, tik pod 85), `bot_streaks` unknown (bot še
  ni pisal datoteke); simuliran izpad (`WATCHDOG_WEB_URL=http://127.0.0.1:1`,
  ločeno stanje): tek 1 = `live`+heartbeat, tek 2 = `web` alarm (2× zapored),
  tek 3 = tišina (dedup), obnova = `recovered` ×2 enkrat, tek 5 = tišina.
  **Ownerjeva dejanja:** Discord webhook → `WATCHDOG_WEBHOOK_URL` v `.env`;
  `sudo cp deploy/systemd/etlegacy-watchdog.* /etc/systemd/system/ && sudo
  systemctl daemon-reload && sudo systemctl enable --now etlegacy-watchdog.timer`.
  R. 2 (ni tu): SSH sonde na puran (tailer `pgrep`, `ls -t stats/`), `watchdog`
  ključ v `/api/diagnostics` + vrstica na About panelu (po #946), popravek poti
  v `~/slomix-server-logs/bin/pull_puran_console_log.sh` (zunaj repa, owner).

## Naslednji koraki (vrstni red) — owner 6. 9.: **dolg → faza 7 → pregledni PR**

0. **Dolg r. 1 (6. 9., MERGAN #919)**: keymap 7 rut zares preslikanih (guard:
   zgrajena ruta ne sme nositi `phase-N` — videti pasti na starem keymapu),
   `/replay` → preusmeritev na `/proximity` (edina nezgrajena ruta umaknjena
   iz `routes.data.json`), `/api/diagnostics` kot admin panel na `/admin`
   (anonimni ne pošlje zahteve) → **vrzel endpointov 4 → 3**.
1. **Faza 6 — preostanek**: availability rezina 3 = admin market kontrole
   (`/api/bets/market`, settle) — ownerjeva odločitev, kdaj; `/api/bets` in
   `/api/stats/sessions` se zapreta šele z upokojitvijo legacy js.
3. **Spider-web follow-upi** (3D kamera, belief regions, label placement;
   W6) — premaknjeno ZA paritetno fazo 6: polish ne prehiteva paritete
   (razlog zapisan 2. 9.).
4. **Faza 7**: r. 1 (6. 9., **MERGANA #920**) = `compare` (`/compare/:a?/:b?`, šest
   legacy vrstic iz profilnega endpointa, barva = boljša stran) in `wrapped`
   (`/profile/:id/wrapped`, canvas 1080×1920 v žetonih — brez gradienta,
   radius 0, pravilo pripeto v testu — + dejstva kot besedilo, copy/download);
   obe kot RUTI (dizajn sistem nima modalov), povezavi v glavi profila;
   `PickPlayer` seljen iz Rivalries v `components/`. **O1 zaprta 6. 9.:
   owner (c) → Clips strani NI** (33. zaslon odpade; 32 rut). `/rounds` že
   preusmerjen. Ostane: končni paritetni prelet (SPA, vse rute × 4 viewporti
   × anon/owner — `scripts/audit_website_browser.mjs --app --manifest`), potem
   pregledni PR-ji za ultra (glej točko 5 — rezine; ⛔ `19c61847` je bil hash
   iz stare zgodovine).

2. **Faza 6 r. 3 + popravek merilnika (6. 9., veja `feat/availability-admin-market`, PR #915):**
   admin market kontrole (open / settle / void, `POST /api/bets/market`);
   greatshot sekcije highlights/clips/renders (ruta je `:section?` nosila od
   faze 6, stran ga je ignorirala — brez novega endpointa); rating trendi na
   profilu (`skill/player/{}/form` + `/history`).
   ⛔⛔ **Popravek ekstraktorja:** legacy zajem se je ustavil pri prvi `${`,
   zato je odrezan prefiks (`/api/players`) veljal za pokritega, brž ko nova
   stran kliče karkoli globljega. 29 legacy klicev nosi interpolacijo s
   segmentom za njo. Merodajno število po mergu izpiše
   `pytest tests/integration/test_endpoint_gap.py` — vsaka nova vrstica pride
   z zapisanim razlogom, ne kot tiha zamenjava števila.
   ⚠️ `compare` in `wrapped` iz te veje sta bila ODSTRANJENA: #920 ju je
   mergal medtem, in mainovi različici sta ostali.
5. **Ultra pregled = 20 rezin (6. 9.)**: meja ≤ 8 000 vrstic / 500 datotek na
   pregled, koda od proda 93 k → `scripts/review_slices.sh` (obratna baza:
   `review-base/NN-<območje>` = main z območjem na v1.39.0; glava `review/NN` z
   mainovim drevesom — GitHub zavrne glavo, ki je prednik baze; draft
   PR-ji »review: … — NEVER MERGE«, telesa `docs/review/SLICES.md`, vodnik
   `docs/REVIEW_GUIDE.md`, spiderweb `docs/SPIDERWEB_STATUS.md`). Rez = meritev
   20/20. Vrstni red (owner): 01 proximity+spiderweb+Lua (5 301) → 02 backend
   routerji (6 411) → 03 SPA lib (7 708) 7. 9. opoldne; ostale po dnevih.
   ⛔ po #882 (v1.45.0) `cut --push` znova. Nato triaža najdb (Astra, zanka
   `docs/process/MANDELBROT_RCA.md`) → 1–2 tedna teka na dev → pogovor o
   produkciji. **Astra predaja**: `AGENTS.md`, `docs/prompts/astra_kickoff.md`,
   `docs/AGENT_LOG.md`, `~/.codex/*` (memory `astra_codex_handoff_2026-09-06`).
   **Watchdog proga** (Astra, po triaži): obseg `docs/design/24_WATCHDOG.md`
   (lokalno) — opazovalec + Discord alarmi z dedupom, nikoli zaganjalnik;
   dokaz = simuliran izpad → alarm ≤ 2 min, noč brez izpada → 0 alarmov.
6. **Raziskovalne proge (owner 4. 9.: doc 22 naslednja, pred doc 19 / moments r. 2):**
   - `docs/design/22` (lokalno, **napisan 4. 9.**) — **»digitalni dvojčki« botov**:
     `player_track.path` (200 ms, 74 480 življenj, regularji 28–63 sej/mapo)
     → profil igralca (vozlišča, dwell = nova kemp metrika, tempo); Omni-bot
     0.91 na puranu = en `.way` graf na mapo, per-bot le `OnBotJoin` +
     `bot.SetRoles` + kamp čas + tempo → **»njegovi cilji, njegova kamp mesta,
     njegov tempo«**, ne dobesedna pot; rezine 1–5 v docu; odločitve za ownerja.
     **Rezina 1 izmerjena 5. 9.** (`scripts/backtest_route_distinctiveness.py`,
     veja `feat/bot-twins-route-distinctiveness`): polovica igralca najde
     SVOJO drugo polovico med desetimi v 81 % (@512) / 91 % (@256) proti 10 %
     naključja, kontrola 0–20 %; a »najbližja točka« da 2–6 u → osebnost je
     ČASOVNA UTEŽ, ne kraj; prag sej 25 (pod njim 63 %); dwell 10–22 %, top
     celice skupne (spawn čakanje) → rezina 2 ga izloči. #913 mergan 5. 9.
     **Rezina 2 zgrajena 5. 9.** (veja `feat/bot-twins-camp-profile`): metrika
     »drži položaj« = `GET /storytelling/camp-profile` (tipizirana; hold =
     ≤ 96 u od sidra ≥ 4 s, still = speed < 10 ≥ 3 s; prvih 3 s življenja
     izven SEZNAMA mest; < 60 s živ → `null`, ne 0) + peta plošča vlog na
     Story strani. Izmerjeno pred gradnjo: 90 % počasnih točk so postanki
     < 1,2 s (delež počasnih točk NI kemp → epizodna metrika); obe definiciji
     stabilna lastnost igralca (Spearman polovic +0,61…+0,95). Živ dokaz:
     seja 154 hold 11–18 %, seja 120 16–23 %, hladno 0,9–1,1 s, toplo 3 ms.
     #914 mergan 5. 9. Naslednje: r. 3 (per-bot `.gm` profil iz `top_cells`
     + tempa) — owner je 5. 9. izbral **najprej moments r. 2** (spodaj).
   - **Moments r. 2 (doc 20 §7.2) — MERGANA #916 in DEPLOYANA na puran
     5. 9. 23:16** (sha256 = main, `FH watcher version=6.14`; migracija 082
     na prod ob naslednjem release deployu; odprto: en večer
     `frame_health.log`). Vsebina: Lua v6.14 (`first/last_move_time` na
     `VEHICLE_PROGRESS`, nova sekcija `VEHICLE_DESTROYED` iz `et_Damage`
     veje pred `isValidClient` — izvor g_combat.c:1857 kljuko sproži za vsako
     entiteto), parser + migracija 082 (3 stolpci na `proximity_vehicle_progress`,
     JSONB seznam uničenj, brez nove tabele), detektor `escort_mover` z
     `timestamp_source: "first_move"` in `destroyed_by`. Testi: harness
     `tests/lua/vehicle_tracking_harness.lua` v CI (3 mutacije padle), parser 5,
     escort 13. Runtime: lokalni ET 2.85 (:27961) z boti, 5 rund — dve pasti
     v živo (supply truck se sam odpelje ob 0,6 s → `first_escort_time`;
     goldrush skript tank ob 1,0 s »ubije« prek `G_Damage` → smrt brez
     igralca šteje šele po prvem escortu) in ena o motorju (kljuka teče PRED
     odštetjem zdravja). ⚠️ Kontrakt `destroyed_count`: korpus pred v6.14
     nosi fantomsko +1 na goldrush rundah (popravek = odprta naloga).
   - **Dvojčki r. 3 — zgrajena 6. 9.** (veja `feat/bot-twins-profile-generator`):
     `scripts/build_bot_twin_profiles.py` → `server/omnibot/twins/` (profil na
     bota z `ReactionTime`, `<mapa>_twins.gm` z vlogami + kamp časi na
     njegovih razločevalnih ciljih, tabela imen s `profile=` in pravim
     razredom) + `docs/design/23_TWINS_REPORT.md` (lokalno). 5 dvojčkov,
     43 ciljev; ⚠️ kontrola (premešane seje) preživi ≈ 21 % — pragi iz
     kontrole, številka je v poročilu. Deploy na puran + bot test = owner;
     r. 4 = harness bot proti človeku (+ kontrola proti tujemu profilu).
   - `docs/design/19` (lokalno) — **modularni statsi + per-user pogled**:
     register datasetov + `user_page_layouts` + column picker/sekcije/home
     v 6 rezinah; zajemna stikala ŠELE zadnja in le s coverage zastavico.
   - `docs/design/20` (lokalno) — **match moments: escorting objective +
     ET-specifični detektorji** (Lua zajem → importer → detektor → Story).
   - `docs/design/21` (lokalno) — **runtime v2 / event brain**: owner 3. 9.
     odločil: ena meja domene, LOČENI procesi (bot/web bralca, baza trajni
     cilj); prva rezina = `events` tabela + `pg_notify` iz »runda končana«;
     ⛔ **šele po ultra pregledu** nove strani, ne prej. Brez Redis Streams,
     brez enega procesa.

| ratchet | stanje |
|---|---|
| endpoint gap | **8** — (9. 9. 00:30, R3a–R3e) ⛔ isti dokument je 6. 9. navajal 3 IN 16; nobena ni bila prešteta, obe sta bili zapisani ob spremembi in nato zastareli. Zgodovina: 4 → 3 (rezina 3) → 19 (korekcija ekstraktorja 5. 9.) → 16 (faza 7) → 13 (5 zaprtih 6. 9.) → 12 (#955) → 11 (#970) → 10 (#974) → 9 (#975) → 11 (korekcija merilnika 8. 9., trailing interpolacija). Merilo je `grep -vcE '^\s*(#|$)' tests/data/endpoint_gap.txt`, ne spomin |
| proximity inventory pending | **0** (#884) |

## Proga: Stats 2.0 — ena stran »Stats / Sessions« (Fable 5.1)

**Zadnja posodobitev:** 2026-09-03 (Fable 5.1, R4 mergan; R5 v PR-ju)

Owner (3. 9.): »Sessions« + »Sessions 2.0« → ENA stran; seznam po datumu in
id-ju s thumbnailom; ob kliku najprej jedrnat summary (basics tabela +
tekstovne nagrade v gibhub slogu), podrobnosti za klikanje do power userja.
Dizajn: `docs/design/18_STATS_2_0_SESSIONS.md` (lokalno). Odločitve: vzdevki
nagrad (tabela v backendu) · Smart Stats = zavihek session strani · ACC =
hits/shots lahkih orožij.

| rezina | obseg | stanje |
|---|---|---|
| R1 | en arhiv `/sessions` z levelshoti, `#id`, BOX, mape, »one half missing«; `/sessions2` redirect; podnav brez podvojitve | #897 merged |
| R2 | backend `GET /stats/session/{id}/basics` + `/awards` (response_model, vrata `/detail` + brez botov, KIS null=not covered, pravila agregacije nagrad z vzdevki, korpusni tek `scripts/audit_session_basics.py`) | **MERGAN** #898 (`ace66e3d`, 3. 9.) |
| R3 | summary: glava z BigScore + trak map z levelshoti + figure; `DataTable` (nov, doc 11) s 17 stolpci in tooltipi (`uk` = useful (legacy), `useless` svoj — owner 3. 9.); nagrade v stavkih; night score + MVP; ostalih 5 panelov za »more ▸«; Playwright thin = seja 80 | **MERGAN** #899 (`965c2928`, 3. 9.) |
| R4 | zavihki Players (21 legacy stolpcev + razširitev na `DataTable`; »Lua Played%« opuščen = kopija Played%) · Rounds (`RoundsTab`, `/rounds` upokojen → `/sessions`) · Teamplay (5 barov sinergije + trade tabela po datumu; `no_data`/`partial_data` = `Absent`) · Story (`SessionStory` kot zavihek; `/story/session/:gsid` → `/session-detail/:gsid/story` prek `PARAM_REDIRECTS`); slovnica zavihkov ENA kopija v `routes.ts`; e2e `session-tabs.spec.ts` (154 + 80, 5 zavihkov) | **MERGAN** #902 (`f3f06cdc`, 3. 9.) |
| R5 | **MERGAN** #903 (`e3b0a70c`, 3. 9.) —  power user: vrstica igralca ▾, KIS details, povezave | — |

Odprto (owner): FSK prag, potrditev vzdevkov, Charts zavihek.

## Proga: match moments (doc 20, lokalno) — Fable 5.1

**Zadnja posodobitev:** 2026-09-06 (Fable 5.1, dvojčki r. 3 v PR-ju)

| rezina | vsebina | stanje |
|---|---|---|
| 1 | `escort_mover` detektor (12.) brez Lua: `proximity_vehicle_progress ⋈ proximity_escort_credit` po 4-ključu + `round_key_filter_sql(alias="vp")`; pragi iz meritve (`ESCORT_MOVER_*` v `base.py`: 1 000 u, delež ≥ 0,25; 3/4/5★ pri 0,25/0,5/0,75); `time_ms` = konec runde (`timestamp_source`); prvi test, ki poganja SQL detektorja (stub); korpus: **19 = 19** (detektor proti SQL, sprejete runde); ⚠️ **v privzetem rezu (10) se ne prikaže v NOBENI seji** (bazeni 50–90 momentov, zvezdice so trda meja) → vidnost = rezina 5 (filter po tipu / svoj panel), ownerjeva odločitev | **MERGAN** #908 (`bd8561e7`, 4. 9.) |
| 2 | Lua: `first/last_move_time` moverja + `et_Damage` pripis uničenja (ownerjev deploy protokol) | — |
| 3 | Lua: zajem escorta NOSILCA (`proximity_carrier_escort`) + migracija + parser | — |
| 4 | detektor escorta nosilca + fixture varovalo »medic ≠ escort« | — |
| 5 | **vidnost (owner 3. 9.)**: `/storytelling/moments?types=escort_mover` (backend filter) + majhen panel »objective escorts« v Story zavihku pod momenti; direktorjev rez nespremenjen; oznake po tipu | **MERGAN** #909 (`6d61805d`, 4. 9.) — `types=` filter + panel `story.escorts` |

## Proga: frame-health v6.13 — watchdog za VSE Lua module + bot test (Fable 5.1)

**Zadnja posodobitev:** 2026-09-03 23:00 (Fable 5.1, v6.13 deployan in izmerjen; proga čaka na pravi večer)

Owner 3. 9.: watcher razširiti na vseh 6 modulov, izboljšati, bot test (~30 min)
za polno obremenitev; RCON `testmode` in deploy za ta PR izrecno predana.

| korak | vsebina | stanje |
|---|---|---|
| 0 | osnovnica: bot test z v6.12 (18:37–19:07, 6 botov, `testmode on/off`) | **izveden**: 2 stalla ≥ 100 ms, 0 ≥ 500, 2 motorjeva hitcha v 30 min — obremenitev z boti strežnika ne muči; `is_bot_round` deluje (komentar na #905) |
| 1 | skupni FH blok (`FH init mod=`, `FM wall mod self top`) v 6 modulih; tracker: `lt`/`paused` na gap vrstici, kapica 300→3000, `init_scan` meritev; `tests/lua/frame_health_modules_harness.lua`; identity test | **MERGAN** #905 (`33126213`) |
| 2 | `scripts/frame_health_report.py` (pripis: Σ self v oknu gapa = naš Lua, ostanek = motor/gostitelj) + test | narejeno |
| 3 | PR, CI, ownerjev merge | **MERGAN** #905 |
| 4 | deploy na prazen puran (scp na ŽIVE poti, map load, `FH init mod=` 6×, sha256 prej/potem; ⛔ nikoli `lua_restart`) | **IZVEDEN 3. 9. 22:2x** — 6/6 sha ujema, 6× `FH init … mod=` + `FH watcher`, motor 6× »loaded into Lua VM«, brez napak |
| 5 | drugi bot test z v6.13 (22:25–22:55) → poročilo; ukrepi v BACKLOG | **IZVEDEN**: 2 gap, 2 `FM` (obe tracker `round_end` 188–224 ms); webhook `sweep` in `init_scan` < 50 ms; 3 motorjevi map-load hitchi; komentar na #905. Naslednje: odčitek pravega igralnega večera |

Osnovnica iz obstoječih logov (report, 2. 9., prazen strežnik): stall 363 s,
naš Lua 16 %, residual (motor/gostitelj) 84 %; 3. 9. do 18:00: 36 s, 22 % / 78 %.

## Proga: lag na puranu + Lua optimizacija (sestrska seja)

**Zadnja posodobitev:** 2026-09-02 (Fable — predaja koordinacije)

Watcher v6.12 ŽIV na puranu (deployan + dokazan 2. 9.). Naslednji večer
igre = meritev (`~/.etlegacy/legacy/proximity/frame_health.log`; zbiralnik
vleče na sambo). Delitev populacij (sestrska seja): A = round-end burst
(naš), B = med pavzo — ⚠️ »ne more biti naša« pokriva SAMO tracker
(levelTime med pavzo zamrzne); webhookov io.popen sweep teče po os.time()
tudi med pavzo in NI izključen. Razsodi meritev prek `self`. Optimizacija bursta: batch write,
šele PO enem večeru self meritev. Sestrska seja koordinira optimizacijo Lua.

## Proga: časovna polja (Opus 5)

**Zadnja posodobitev:** 2026-09-03 (Opus 5 — faza 3 IZVEDENA, proga zaključena)

Dva ločena hrošča v istem deploy oknu (~20. 3. 2026) sta pustila bazo v
stanju, kjer sta obdobji **nezdružljivi**: staro ima engine alive%, a ~2×
napihnjen mrtvi čas (Lua je limbo čas prištevala znova ob vsakem 5-sekundnem
tiku); novo ima pravilen mrtvi čas, a `time_played_percent` je bil od
2026-04 ničla, ker ga aktivna uvozna pot ni pisala. Ker sta komplementarni,
se da vsako obdobje popraviti iz signala drugega.

| faza | kaj | stanje |
|---|---|---|
| 1 | uvozna pot piše `time_played_percent` + parnostno varovalo piscev | ✅ **#885** `f71906ac` |
| 2 | backfill `time_played_percent` iz surovih datotek | ✅ **#886** `fb35e09b`; izveden 2. 9. (+4.666, kontrola 22/22), **ponovljen 3. 9. po restartu bota: 0 rešljivih vrstic — končano** |
| 3 | rekonstrukcija zgodovinskega `time_dead_minutes` iz engine alive% | ✅ **IZVEDENA 3. 9.** — 8.721 vrstic, migracija 081, izvirnik ohranjen v `time_dead_minutes_original`; `dead > played` 80 → 0, `ratio > 100,5` 43 → 0 |
| 4a | per-row varovala v plausibility auditu (4 nova pravila) | ✅ **#892** `75ebdeee` |
| 4b | agregatni razred (»porazdelitev se je premaknila«) | ✅ **#895** `c213346f`, 7 trend pravil |
| 4c | oborožitev namesto utišanja (`Rule.armed_from`) | ✅ **#900** `eea9b617`; po fazi 3 obe dead-time pravili nista več oboroženi (ni več česa izvzeti) |
| 5 | zastareli zapisi, ki so to skrivali | ✅ **#893** `0003e589` |

⭐⭐ **RCA, ki je obseg faze 3 obrnil (3. 9.):** »R2 se je maja 2025 spremenil«
je bila napačna diagnoza. Meja je **datum vpisa**, ne seje: vse vrstice za
2025-01…05 so bile vstavljene 2025-12-20 (bulk uvoz). Primerjava
datoteka ↔ baza ↔ rekonstrukcija (n = 8.369) pokaže, da je **Lua napihnila
enotno ~2,2×** v vseh štirih celicah, uvoznik pa je datoteko prepisal dobesedno
**razen pri bulk R2**, kjer jo je obravnaval kot kumulativo tekme in razdelil
sorazmerno s časom (`× played_R2/(played_R1+played_R2)`, mediana 1,000,
**97,8 %** vrstic znotraj ±10 %). Dve napaki, ki se v mediani skoraj izničita
(1,058) in po vrsticah ne (le 18,2 % znotraj ±10 %).

✅ **Izid rekonstrukcije (3. 9.):** 8.721 vrstic, 26.337 → 12.338 min, mediana
faktorja 1,92. Porazdelitev se čez mejo zdaj ujema v vseh kvartilih
(p25 0,169 / med 0,212 / p75 0,257 proti 0,153 / 0,203 / 0,255 po meji; prej je
bila predmejna mediana 0,365). Preostalih 11 nemogočih vrstic sedi v rundah, ki
jih cevovod že izloča (1× `orphan_r2`, 2× `is_valid = FALSE` bot rundi).

⭐ **Neodvisna potrditev:** agregatno pravilo `pcs_dead_time_share_monthly`,
zgrajeno in umerjeno na pokvarjenih podatkih tri dni prej, je prej javljalo tri
pojasnjene premike (2025-05 +46,5 %, 2026-04 −53,1 %, 2026-05 −41,4 %), zdaj pa
**nobenega** — mesečna serija je ravna 0,19–0,23 čez vseh dvajset mesecev.

⚠️ **Najdba ob strani:** `scripts/db_backup.sh` je tekel kot `website_app`
(ker `website/.env` prepiše `POSTGRES_USER`) in ta ne more brati 7 tabel →
`pg_dump` je odpovedal. Odpovedal je glasno, kar je pravi izid, a razhajanje
med korenskim in website `.env` za administrativna orodja ostaja odprto.

✅ **Bot restartan 3. 9. ob 11:25** (`etlegacy-bot`, dev enota, NOPASSWD;
`etlegacy-web` nedotaknjen): 21 cogov, 98 ukazov, brez napak. Ponovni zagon
backfilla: **0 rešljivih vrstic**; ostane 16 ničelnih v treh rundah
(14 neparsljivih zajemov, 2 vrednosti 101,2 %).

⭐⭐ **Faza 4c: tri »znana« pravila so bila UTIŠANA, kar mutira cel senzor.**
`acknowledged` utiša celo pravilo, torej bi tudi SVEŽA ponovitev iste okvare
padla v isto tišino — natanko tako, kot je pet mesecev minilo prvič. Zato
`Rule.armed_from`: zgodovina se še vedno šteje in prikaže (nov stolpec
»pre-arming«), a izhodne kode in dnevnega alarma ne drži odprtih. Izmerjeno:
`dead > played` 80 vrstic, **nobene po 2026-04-01**; `ratio` 43, nobene po
istem datumu; `tpp = 0` 16, nobene po 2026-09-03. Utišanih pravil: **0**.
Živih kršitev: **0**.

⭐ **Ključna meritev (odklepa fazo 3):** po backfillu `alive_pct_drift` prvič
po 5 mesecih spet deluje — 290 parov, engine 79,3 proti izračunanemu 79,3,
povprečna |razlika| **0,15 o. t.**, le 2 para (0,7 %) nad 2 o. t. To potrjuje
oboje: ALIVE% se premakne zanemarljivo IN formula za staro obdobje drži.

✅ **Backfill ponovljen 3. 9.** po restartu bota; 0 rešljivih vrstic ostane.
Konec-do-konca dokaz, da uvozna pot spet piše `time_played_percent`, pride
šele z naslednjim uvozom (naslednji večer igre) — do tedaj je dokazano le,
da datoteka, ki jo bot poganja, vsebuje stolpec (54 stolpcev v `INSERT`).

⭐⭐ **Razrešeno 3. 9.: »tretja raven« je R2, ne igra.** Ločeno po rundah je
**R1 raven skozi vso predpopravkovo obdobje** (delež mrtvega časa 0,44–0,50),
R2 pa teče pri ~0,22 do 2025-04 in od 2025-05 skoči na R1 raven. Torej
`time_dead_minutes` na R2 vrstici pomeni **eno stvar pred majem 2025 in
drugo po njem** — isti vzorec kot popravek 2026-04, eno rundo globlje.

⭐⭐ **Faza 3 je s tem odločljiva, in odgovor je ločen po rundah:**

| era | runda | n | razred B (baza < 0,9 × rekon) | mediana faktorja |
|---|---|---|---|---|
| zgodnje 2025 | **R1** | 2.708 | **0,15 %** | 2,238 |
| pozno (2025-05..2026-03) | **R1** | 1.724 | **1,28 %** | 2,195 |
| zgodnje 2025 | R2 | 2.596 | **37,1 %** | 1,031 |
| pozno | R2 | 1.693 | 10,0 % | 1,992 |

**R1 = en sam čist mehanizem čez vso ero**, R2 ne. Trije neodvisni razsodniki
(3. 9., razširjeni vzorci):

| razsodnik | pokritost | rekon / razsodnik | baza / razsodnik |
|---|---|---|---|
| izmerjeni dead po popravku (n=4.447, prej 344) | 2026-04→ | R1 **1,0000**, R2 0,9993 | — |
| `round_awards` (endstats.lua, n=126) | 2026-01..03 | R1 **1,0020**, R2 1,0053 | 1,96 / 1,74 |
| `player_track` (proximity, n=888) | 2026-02-11→ | R1 0,9166, R2 0,9335 (metoda vrzeli podceni ~8 %) | 1,94 / 2,00 |

⚠️ **Zunanja razsodnika pokrivata SAMO 2026-01..03** (~2.200 vrstic od 8.700).
Za 2025-01..04 (5.304 vrstic) ni neodvisnega vira — tam stoji rekonstrukcija
na mehanizmu (branje stare Lue) + na tem, da je R1 faktor identičen v obeh
erah (2,238 proti 2,195).

⭐ Kje bi prepis **poslabšal**: proti `player_track` je rekonstrukcija bližja
na **80,7 %** vrstic, baza na 19,3 %; mediana napake pade z **1,125 min na
0,289 min**. Razčlenjeno: pri parih, kjer se kandidata skoraj ne razlikujeta
(≤0,5 min, n=118), je izid vseeno; pri napihnjenih (n=727) rekonstrukcija
zmaga v 83,2 %, pri hudih (n=41) v 97,6 %.

⭐ **Nova najdba 2. 9.:** `revives_given` je 0 na vseh 5.538 vrsticah pred
2025-12 — vsaka vseskozna revive lestvica se tiho začne decembra 2025.

## Proga: SSH monitor / alarmiranje (Opus 5) — PR #923, ODPRT

Sprožil ownerjev alarm na #privat 6. 9.: »Ssh Monitor Failing / 3 consecutive
failures / Error reading SSH protocol banner«.

**Štiri rezine, vse na veji `fix/ssh-monitor-says-what-it-knows`:**

1. `55a0e555` — monitor pove, kar ve: dva vzroka pod enim imenom ločena
   (`[banner/read timed out — remote slow]` proti `[socket closed under the
   read — local]`), `banner_timeout/auth_timeout=45` na vseh petih mestih,
   okrevanje se objavi, proximity dobi glas.
2. `d909fb68` — »consecutive« končno pomeni zaporedne: `STREAK_WINDOW` 30 min
   na **enem** mestu velja za vseh devet ključev (šest jih ni imelo reseta —
   ⚠️ ne sedem od osmih, prešteto je šest od devetih).
3. `7f3dba7a` — Full Jitter razmik pollerjev + **en** ponoven poskus listinga,
   samo za `remote slow`. ⛔ Iskanje je prvo postavko obrnilo iz »zgradi pool«
   v **ne gradi poola**: `connect()` ni thread-safe (paramiko #1904), naše
   operacije tečejo v nitih izvajalca.
4. `443818b7` — nizi preživijo restart (`logs/bot_error_streaks.json`).
   ⛔⛔ Restart ni izgubil le zgodovine, **odložil je naslednji alarm**.
   ⛔⛔ `STREAK_WINDOW` velja tudi ob **branju**, sicer bi trajnost ustvarila
   lažni »Recovered« za izpad, ki je minil pred restartom.
   Datoteka in ne tabela: alarmna pot ne sme viseti na tem, o čemer alarmira;
   brez migracije torej brez prod deploya.

**Stanje: MERGANO** 6. 9. ob 18:02 (`5aca4a76`, squash), z ownerjevim
dovoljenjem. Vseh 8 zahtevanih checkov zeleno; Codacy `fail` s 3 issues ni
zahtevan in je bil identičen že pred rezino 4.

⚠️ **Na dev botu še ne teče.** Ownerjev restart 6. 9. ob 17:17 je bil PRED
mergem in je zagnal `ed0dfe22`, kjer od #923 ni nobene vrstice. Popravki
stopijo v veljavo šele ob naslednjem restartu — ⛔ ownerjeva poteza,
`sudo systemctl restart etlegacy-bot.service` na devu.

**Odprto, izrecno nedokončano:** ena povezava na cikel namesto ena na datoteko
(predelava produkcijske poti, svoja rezina in svoj pogovor).

## Odprte ownerjeve odločitve

- doc 19 (per-user pogled): zajem globalno ali per-server; zgodovina ob
  izklopu (priporočilo: nič retroaktivno); admin UI ali config (config v1);
  anonimni localStorage (odloži).
- doc 20 (match moments): pragi R/T backtest; vir oživljanj (2 tabeli);
  `sub_type` ali nov tip; `proximity_team_cohesion` 1,28 M vrstic brez bralca.
- doc 21 (runtime v2): gostitelj (dev), lastnik deploya (owner) — odprti, a
  nenujni do ultra pregleda.
- puranov cron `0 20 * * * kill etlded` (vrže igralce sredi igre) — pogojni
  kill ali prestavitev.
- `scripts/local_et_setup.sh` P1: produkcijski webhook v lokalnem strežniku.
- hosting ticket, če watcher potrdi populacijo B (host stall).
