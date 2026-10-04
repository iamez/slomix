# AGENT_LOG — durable lessons for the next agent

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
