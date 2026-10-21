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



## 2026-10-21 — Proximity schema/admission slice, not activation

Source base3551ca21; extracted existing candidate9c09267c schema096/100 and
admission implementation.40passed/34PGskipped; fresh-process admission recovery
and two observed guard failures/restored cmp. PostgreSQL acceptance remains
pending an explicitly disposable target. Bootstrap adds only the two exact
migration blocks; all prior bytes remain. Next identity/receipt, then queue.
D4/D5 and exclusive writer handover remain open. No push/merge/service authority.

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
