# PLAN — edini vir resnice za tekoči načrt

## Current consolidation checkpoint — 2026-10-04

Owner approved963/964/966/1066/1072/1073/1074/1075/1077, one at a time with
fresh exact-head review/CI and postmerge verification. No merge yet.
963 now changes the historical deployment recipe AND its tests; do not reuse
33be0bbe or d8238e0c payload-identity claims for the corrected head.
43 focused tests pass, including actual disposable deploy preflight, and the
omitted-target / historical-scope mutations fail then restore/cmp.

LOCAL-ONLY runtime resume: last saved integration checkpoint8e262684, on branch
refactor/db-runtime-team-assignment-20260926 in
/home/samba/share/slomix-astra-runtime-integration-20260926.
Read that worktree's latest PLAN; the local checkpoint is not fetchable from GitHub.
Read-only verification:
`git -C /home/samba/share/slomix-astra-runtime-integration-20260926 cat-file -e '8e262684^{commit}'`.
02c160cc and1986d671 are retained historical checkpoints, not current targets.
Original runtime capture/retry/handover then Spiderweb/proximity/UI plan unchanged.
NEVER MERGE924-943/967 and held956 remain excluded; no service/deployment actions.

## Historical checkpoints — superseded, retain evidence as of each date

> 2026-10-04 fresh review correction: owner approved963/964/966/1066/
>1072-1075/1077 subject to individual fresh gates; do not merge with findings.
> Runtime integration checkpoint8e262684 supersedes02c160cc; read latest local
> PLAN in the worktree below. Four reproduced failures cover stale global date,
> stale backlog and actual deployment-target mismatch in both documented recipes.
> Pin the exact built HEAD in owner-only deployment advice. Preflight proofs
> use only disposable clones, actual artifact helper/deploy script and mock Vite,
> never the live run clone or services. Historical labels have paragraph scope.

> 2026-10-04 older-PR consolidation: #963 refreshed onto actual main0b22b014.
> At this initial refresh both document streams were retained and payload/test
> bytes matched33be0bbe. The later06f044a7 recipe/test correction invalidates that
> payload identity for subsequent heads. This was not a deployment.
> Integration checkpoint02c160cc was current then, superseded by8e262684 above.
> Older queue is reviewed before1079-1084. Hold956 and NEVER MERGE924-943/967.
> Fresh tests, exact-head CI/review and numbered authorization precede merge.
> Validation:17 focused contracts pass, including execution of the documented
> recipe against disposable build/deploy probes. Deliberately adding a static
> timer enable recipe fails the historical-cleanup guard; restored and cmp match.
> No actual build/deploy/service command executed. Historical handoff/test
> blobs still match reviewed33be0bbe; current source/runtime behavior is unchanged.

> #963 preservation refresh 2026-10-03: normal main194b1e6e merge retains
> historical handoff corrections and both histories. Handoff/test bytes unchanged
> from33be0bbe; root17 executable recipe/Node/plan contracts pass0.49s.
> No actual deployment, timer or service operation. Await final main sync and
> fresh review/CI before any separately authorized merge.

> #963 fresh-review correction 2026-09-28: actual main4de6f07e normally
> integrated with both histories retained. Three new findings independently
> reproduced and corrected; 13 focused document/plan contracts pass. Actual
> local resume object/branch/ancestry verified read-only; no claim that the hash
> is available to a fresh GitHub clone. Document mutations failed and all files
> restored/cmp. No real deploy, review-ref, service or remote operation. Root
> owns publication, thread replies and fresh exact-head review/CI gates.

> LOCAL-ONLY runtime resume 1986d671 (2026-09-28 clarification): the retained
> implementation is on this owner's host at
> /home/samba/share/slomix-astra-runtime-integration-20260926, branch
> refactor/db-runtime-team-assignment-20260926. It is not fetchable from GitHub.
> Read-only identity check on that host:
> `git -C /home/samba/share/slomix-astra-runtime-integration-20260926 cat-file -e '1986d671^{commit}'`
> and `git -C /home/samba/share/slomix-astra-runtime-integration-20260926 log -1 --oneline`.
> Read its latest PLAN before continuing; later commits preserve the checkpoint.
> A fresh clone without this host must obtain an owner-provided bundle or wait
> for reviewed slice publication, not pretend this local hash is a public ref.
> Public queue context is PR #1077 (not equivalent to the later local work).

> Current #963 main-sync checkpoint 2026-09-28: ec8ec7ed normally merged,
> including reviewed #1067 SSH and #965 watchdog changes; both documentation
> histories and d8431e06's historical corrections retained. Preserve runtime resume 1986d671.
> 10 focused document/plan contracts pass; unchanged guard tests retain their
> earlier observed mutation failure and restored/cmp proof. Historical content
> is not current host evidence. Root owns publication and fresh review gates;
> this documentation detour does not replace the original runtime roadmap.
> No production, service, real review-ref or remote operations were performed.

> Historical checkpoint: only the immediately following September28 paragraph
> predates that synchronization; later October checkpoints retain their dates.

> Current checkpoint 2026-09-28: #963 historical handoff corrections are a
> documentation-only queue detour. Main 9ef42671 contains #1065; #1066 SQL
> proof and #1067 SSH review are recorded in the integration checkpoint.
> Preserve runtime resume commit 1986d671 and the #1067 → #1068 → #1069 →
> #1070 dependency chain. No service, production or NEVER MERGE action.
> Earlier dated checkpoints below describe their date, not current authority.
> Verification: 10 document/plan contracts pass; actual historical-document
> mutations adding timer enable recipes with --dry-run and --now each fail the
> cleanup guard, restored with byte-for-byte cmp. Build recipe paths validated
> without executing build/deploy; no current host-data measurement is claimed.
> 2026-10-03 #1078 CI coverage: retain exactly the existing two Python check
> names/jobs, pairing Python3.11 with PostgreSQL14 and Python3.13 with PostgreSQL17
> (not a cross product). No triggers or extra jobs added. Images pinned to root's
> Docker registry manifest digests verified independently against response bytes.
> ACL fixture now compares actual server_version_num with the expected CI major;
> expected17 against actual14 fails setup instead of skipping new coverage.
> Parsed-YAML contract pins pairing, hashes, check names and unchanged job/trigger
> inventory. Hardcoding14 service image causes1 test failure; disabling actual-major
> check causes2 failures; restored/cmp for both. This proves guards, not PG17 SQL
> behavior: that still requires the actual17 CI leg to finish successfully.
> Final local suite with expected14:35 passed,4 version-skipped52.70s; Ruff and
> whitespace checks pass. Timing is this run, not a performance comparison.

> 2026-10-03 #1078 resumed after owner restarted private proof service. On actual
> PostgreSQL14.24, root suite31passed/4version-skipped24.83s; helper independent
> repeat31passed/4skipped31.55s. Guard mutations observed: column check removed
> gives8 DID NOT RAISE failures; reachable-role traversal removed gives3 failures;
> ownership check alone removed gives1 failure. All three edits restored with
> apply_patch and cmp against saved exactSQL. Real SESSION AUTHORIZATION website
> followed by SET ROLE proves two-hop NOINHERIT table/sequence/owner capabilities.
> All fixtures rolled back in postgres disposable schemas; root's restored DB
> was untouched. Three MAINTAIN cases and PG16 membership-options case still
> require real newer PostgreSQL; no PG17 runtime claim or version simulation.

> 2026-10-03 #1078 review4172501633/636/639 follow-up, PREPARED NOT PG-VERIFIED:
> unmerged093 now also rejects effective column privileges, PostgreSQL17 MAINTAIN,
> and table/sequence rights or ownership reachable through transitive SET ROLE.
> Version-specific reachability uses PG16+ SET and PG14/15 MEMBER; unrelated
> role grants remain untouched. Official references:
> https://www.postgresql.org/docs/14/functions-info.html and
> https://www.postgresql.org/docs/16/functions-info.html distinguish membership
> semantics; https://www.postgresql.org/docs/17/functions-info.html documents
> column privileges/MAINTAIN; https://www.postgresql.org/docs/17/role-membership.html
> explains SET versus INHERIT. Added isolated regression fixtures for column
> PUBLIC/group grants, real session-authenticated two-hop NOINHERIT role changes,
> owner-with-revoked-grants, MAINTAIN and PG16 non-SET membership compatibility.
> Proof service expired before these changes: no restart or fallback connection
> attempted. Static registration/Ruff/whitespace pass; actual PG tests and guard
> mutations are PENDING owner restart. PG16/17-specific cases require that actual
> server version, not simulated version strings. Only PG14 is installed locally.
> Prior093 restore/checksum proof below describes older SQL, not this revision;
> repeat on a fresh disposable restore, never edit the old migration ledger.
> Root reports live DEV has no additional SET-reachable website roles; these
> bypasses are regression/contract risks, not newly observed live grants.
> Original runtime plan remains preserved; do not deploy or merge on this note.

> Root's independent restored-DEV rehearsal, 2026-10-03: official migration
> runner as etlegacy_user applied exact093 from6396b222 (unchanged in subsequent
> test/docs commits), checksum verified. Ledger95; rounds3474/playerrows22501
> unchanged. Actual website generation SELECT succeeds; journal/receipt SELECT,
> generation INSERT and sequence nextval are denied. This is the private restored
> backup, not the live application database; root reports no live writes.

> 093 follow-up: require effective generation SELECT as well as denied writes.
> An attempted no-grants/wrong-role fixture stopped earlier with permission denied
> for runtime_events, so it did not exercise that positive postcondition. Replaced
> it with an explicit ineffective-GRANT SQL fault injection; disabling only the
> positive postcondition then fails DID NOT RAISE, restored/cmp. Final focused
> suite20 passed6.85s. This fault injection is not a claim of a production GRANT
> failure. All SQL ran in the explicitly configured disposable cluster only.

> 2026-10-03 DEV rehearsal follow-up: inherited default ACLs grant website_app
> CRUD on newly created runtime tables and rights on their sequences; migration
> 092's additive SELECT grant does not restrict them. New093 revokes only six
> runtime table grants and their owned serial/identity sequences, then grants
> generation SELECT. Legacy and default ACLs remain unchanged. Effective-grant
> assertions fail closed on PUBLIC/inherited privileges or a wrong runner role.
> Real private-PG tests reproduce083-092 with permissive defaults, prove old
> generation INSERT succeeds, and verify093 via catalog permissions plus actual
> denied SQL. Transaction-owned fixtures roll back fully; root's restored copy
> and live databases were not touched.19 focused PG/journal/plan tests pass5.23s;
> disabled093 mutation fails runtime_events SELECT permission, restored/cmp.
> Fixture corrections: SET LOCAL ROLE survives successful savepoints (RESET ROLE
> required); identity-column UPDATE is rejected before ACL checks, so use a
> nonidentity column to prove authorization. Existing083-092 remain immutable.
> Next: root independently rehearses093 on the restored backup, fresh PR/CI/review
> and specific merge permission before DEV deployment. Runtime roadmap unchanged.

> 2026-10-03 #979 review4172412989: reject RUN assume-unchanged/skip-worktree
> index flags before status, source fetch, staging or deployment. Four actual
> disposable Git regressions first failed against the old guard; both flags
> with clean and hidden modified runtime bytes now fail closed. Preflight and
> activation paths preserve RUN HEAD, index and assets; an independent disposable
> checkout confirms unchanged target blobs would retain the hidden runtime bytes.
> Deliberately disabling the new guard fails all four cases; restored and cmp
> verified. Focused artifact/Node/plan/watchdog suite:50 passed11.44s; Ruff,
> bash syntax and whitespace pass. One initial mutation invocation rejected an
> invalid pytest --showlocals=no option (exit4, no tests); corrected invocation
> produced the four actual failures. No live service, deployment or DB action.
> Root must rebuild exact-SHA artifacts, publish, obtain fresh CI/review and
> PR-specific merge permission. Original runtime roadmap remains unchanged.

> 2026-10-03 DEV preflight: owner authorizes updates/restarts on Samba only;
> production is a separate host and remains excluded. Local address inspection
> confirms 192.168.64.116 belongs to Samba. Read-only transactions through both
> bot/web roles show 84 ledger entries and no new 083-092 entries; running web
> and run checkout agree on75ee10b5. Main5e948f0b postmerge workflows all pass.
> Refresh #979 onto actual main before exact-SHA artifact rebuild and review.
> Preserve both document histories during normal merge. No live mutation,
> migration or restart performed; no PR-specific merge authority inferred.
> Next: refreshed artifact proofs/review, backup and migration rehearsal, then
> approved DEV update. Runtime v2 activation and original roadmap stay gated.

> #979 real artifact acceptance, 2026-09-28: normal merges preserve original
> 94cf8e3d, actual main ec8ec7ed, Node pin ea5f2ab3 and dependency repair022f1115.
> Clean committed source338f5b9b built with actual Node22.23.2/npm10.9.8 through
> npm run build:app (not mocked Vite), after npm ci --ignore-scripts/typecheck.
> Provenance records exact SHA and all137 output hashes; independent hashlib
> and sha256sum agree, and all recorded input hashes match actual files.
> Actual dev_deploy.sh with DEV_PREFLIGHT_ONLY=1, explicit offline SHA and ONLY
> a disposable run clone succeeds. Run HEAD/tree and old asset bytes, inodes,
> mtimes and independent hashes remain unchanged; temporary staging is removed.
> In-process Starlette static HTTP requests return200 for HTML and six referenced
> assets with bytes equal to built files. No listener, browser, actual DEV run
> clone, service, network deployment or production operation was used.
> All23 artifact guards pass5.63s; disabling output equality fails corruption
> detection with DID NOT RAISE, restored/cmp. Ruff/bash syntax/whitespace clean.
> Codacy annotation106142970471 at helper line28 reviewed: subprocess uses an
> argv list, no shell; all helper callsites supply fixed Git subcommands/options,
> source path is a separate -C argument. Trusted local PATH/toolchain remains a
> prerequisite, not an untrusted execution boundary; no scanner disabled.
> Proof script/disposable clone remain local under
> /tmp/slomix-artifact-livebuild-kLb7dL. This closes missing-real-build evidence,
> not live deployment acceptance. Rebuild/reverify after this documentation
> commit because exact-SHA provenance must change even for documentation commits.
> Parent must integrate actual merged #969/#1027, then fresh CI/review/merge cycle.
> #1071 actual-parent checkpoint 2026-10-03: #1070 merged194b1e6e at04:21:17Z
> after owner confirmation and420s gates. Reviewed/squash treesfd38bcde match.
> Normal actual-main merge retains every stability test and both histories;
> runtime source/tests byte-identical toa1ead937. Repeat focused gates, retarget
> to main and publish for fresh review/CI. No approval inferred for1071 merge.

> #1071 security-baseline refresh 2026-10-03: normal parent965a2494 merge
> includes actualmaincc6b0a4d. Both histories retained; runtime source/tests
> unchanged from2915eae9 and dependency manifests match main exactly.
> Focused capture/worker/Node/plan validation repeated before local commit.
> Await actual #1070 merge and fresh publication review; no service changes.

> #1071 local refresh 2026-10-03: normal merge of parent72b2cd06 retains
> actual mainb25d4020 and the reviewed duplicate-lesson correction. Both plan
> histories preserved; runtime source/tests byte-identical to e3c2e2f5.
> Root78 capture/worker/Node/plan cases pass44.68s with actual child cleanup
> and filesystem outcomes. No live SSH/DB or service action. Await actual
> #1070 merge, next main synchronization and fresh publication gates.

> #1071 actual-main propagation 2026-09-28: normal parent539f77fc merge
> incorporates4de6f07e, preserving both histories and exact source/tests44a05106.
> Prior29case10.52s proof remains applicable; combined downstream repeat follows.
> Runtime1986d671 retained. No remote/services; fresh publication gates remain.

> #1071 published-parent refresh 2026-09-28: normally merged #1070 28271ad8;
> both histories and final worker e8f05dbd bytes retained. Twenty-nine composed
> stability/capture/plan cases pass10.52s, offline with real owned children.
> No remote/DB/service action; original runtime1986d671 unchanged. Actual
> #1068 squash-main sync and fresh exact-head review remain publication gates.

> #1071 local parent propagation 2026-09-28: normal merge of #1070 locald4c0f5b8
> retains final worker90026032 source/tests exactly and both doc histories.
> Twenty-seven stability/SSH-capture tests pass10.72s. Existing callers use
> supported grace budgets; no fixture weakening. Root owns actual-main sync and
> final publication/review. No services/network/DB; runtime1986d671 preserved.

> #1070 main refresh 2026-10-03: #1027 mergedcc6b0a4d through420s gates;
> reviewed/squash trees a7f31e32 match. Inherit its dependency patches with
> both document histories retained. Runtime source/tests unchanged from72b2cd06;
> rerun focused gates before fresh review/CI. No service or deployment action.

> Review follow-up 2026-10-03 for #1070: remove only the duplicated
> 2026-09-20 content-reconciliation lesson from AGENT_LOG; preserve its earlier
> identical entry and every distinct lesson. Runtime code and tests unchanged.
> Fresh exact-head review and CI remain required before merge.

> Actual-main checkpoint2026-10-03 for1070: #1069 mergedb25d4020
> at02:58:00Z after420s gates; reviewed/squash treesd2482893 match exactly.
> Normal merge retains both documentation histories. Source/tests byte-identical to55cd33dc after conflict resolution; earlier68-case and restored guard proof remain applicable.
> Publish for fresh exact-head review/CI. No service or production action;
> original runtime roadmap, NEVER MERGE exclusions and held956 unchanged.

> Current1070 preparation2026-10-03: normal merge of reviewed1069 head3e2ffad5
> retains both documentation histories and exact supervised/worker/test bytes
> from539f77fc. Root68combined cases pass44.01s, including actual owned child
> timeout, cleanup and filesystem retry evidence. Disabling existing-content
> admission fails both match/conflict cases with "Existing content must not
> spawn capture"; restored/cmp. Actual1069 squash-main sync still required
> before publication and fresh exact-head review. No live SSH, DB or services.
> Original runtime plan and bounded queue authority retained; no SaaS expansion.

> #1070 actual-main propagation 2026-09-28: normal parent09a62009 merge
> incorporates #1068 squash4de6f07e, retaining both doc histories and unchanged
> runtime source/tests from28271ad8. Prior19case9.80s proof applies to identical
> code; combined downstream rerun follows. Runtime1986d671 preserved, no remote
> or service action. Fresh exact-head review remains a separate publication gate.

> #1070 published-parent refresh 2026-09-28: merged #1069 4007e597 with
> published worker e8f05dbd and both doc histories. Nineteen composed capture/
> plan cases pass9.80s; worker bytes remain unchanged. No network/DB/services.
> Original runtime1986d671 preserved; actual #1068 squash-main sync and fresh
> exact-head review remain root publication gates, not completed by this merge.

> #1070 local parent propagation 2026-09-28: normally merged #1069 local593edbbc,
> retaining final worker90026032 bytes and both histories. Seventeen supervised
> SSH-capture cases pass9.98s, including real bounded children; configured0.2s
> grace/default compatible with minimum0.01s. Root owns later actual-main sync,
> publication/review. No remote/service/network/DB changes; runtime1986d671 kept.

> Current #1070 checkpoint, 2026-09-28: normal parent merge bda56937 retains
> final SSH identity e22ae27c and worker fixes 86c69e39. Combined 150 cases pass
> in 23.00s: real child outcomes remain separate from observed content, retries
> do not re-read already matching content, and procfs/active_children confirm
> cleanup. Actual supervised tests live in test_runtime_ssh_capture.py, not a
> separate supervised test file. Local preparation only; actual main sync and
> fresh exact-head gates still required after #1069. No services or live SSH.

>1070 local refresh2026-09-27: live sourcef4d11cb6/base1069 normally merged
>prepared1069 at8501f7b9 as5d2971f7. Both documentation histories retained;
>spool conflicts preserve0400 inspection fix; worker/auth/source tests match
>parent.141offline tests pass23.35s, including actual child/filesystem retries:
>failed/missing and timed_out/missing retry once; timed_out/match skips recapture.
>Independent sha256sum confirms retained final bytes; procfs and active_children
>confirm reaping. Disabling existing-content guard fails2cases with forbidden
>spawn assertion; restored/cmp, Ruff clean. No live network/service/DB changes.
>BLOCK publication until the newly reported1067 implicit key certificate-sidecar
>loading fix propagates through1068/1069, followed by actual main sync and fresh
>exact-head review/CI. No1070 merge permission inferred. Original plan preserved.

> Actual-main checkpoint2026-10-03 for1027: #1069 mergedb25d4020
> at02:58:00Z after420s gates; reviewed/squash treesd2482893 match exactly.
> Normal merge retains both documentation histories. All frontend/API inputs byte-identical toef1410b9 and its845-test/build proof; six Node/plan contracts freshly pass0.36s.
> Publish for fresh exact-head review/CI. No service or production action;
> original runtime roadmap, NEVER MERGE exclusions and held956 unchanged.

> Security refresh2026-10-03: live npm audit found two affected package groups,
> undici7.29.0 and brace-expansion2.1.4, despite September28's audit0. Narrow
> lock patch advances only these entries to7.29.1/2.1.7 with registry integrity;
> jsdom's undici^7.24.5 and minimatch's brace-expansion^2.0.1 permit them;
> no overrides or
> unrelated metadata changes. Clean npm ci --ignore-scripts succeeds; separate
> npm audit JSON reports0 across268 dependencies. Fresh typecheck,70files/
>845tests259.88s(singleworker), SPA build2.58s pass; generated API SHA61f4c4a5
> unchanged. Actual BalancedPool factory receives original TLS identity callback
> without network requests; actual brace expansion preserves ordinary output and
> bounds nesting. Isolated-copy guard mutations each fail, restored/cmp and pass.
> Initial brace probe incorrectly expected[] instead of literal fallback; corrected
> from installed implementation, not counted as a security regression failure.
> Proof script remains local in slomix-runtime-audit-20260927-dkSfCn.
> Upstream sources: github.com/nodejs/undici/security/advisories/GHSA-w293-vg96-wgc3
> and github.com/juliangruber/brace-expansion/security/advisories/GHSA-qhr7-859c-m2p7.
> These are development dependencies; no live production exploit claim. No service,
> browser or deployment. Fresh exact-head CI/review required; runtime plan intact.

> Recovery checkpoint 2026-10-03, #1027: resumed the interrupted normal
> merge of actual main19e65354 after the usage-limit interruption. Both
> documentation histories retained; no source changes lost.
> 54 Node/watchdog/plan tests pass1.34s. All frontend/API inputs remain identical to022f1115; earlier845-test evidence is historical, not a fresh full-suite claim.
> Fresh exact-head review/CI required after publication. Original runtime
> roadmap and local-only1986d671 retained; no service/deployment action.

> Current #1027 checkpoint 2026-09-28: normal actual-main4de6f07e integration
> preserves both histories. All frontend/API inputs still byte-identical to
> 022f1115's845-test/build proof; not claiming that suite rerun. Fresh typecheck
> passes; generated API SHA remains61f4c4a5b04489b01fe4913df6ac43ef1474a262f0dc873076acea0463ade05d.
> Root repeats bounded actual installed YAML/nanoid probes successfully and50
> plan/watchdog contracts pass0.68s. No service/browser/deployment action.
> Publish for fresh exact-head gates; original runtime1986d671 remains queued.

> #1027 actual-main synchronization, 2026-09-28: normally merged ec8ec7ed
> as0ee8e3e6, preserving both document histories. Explicit git diff from845-test
> head022f1115 over ALL website/frontend and docs/api/openapi.json is empty;
> previous845-test and real SPA build evidence applies to identical inputs, not
> a freshly rerun full suite. No unmerged Node-pin branch imported; local proof
> uses22.23.2 while current workflow remains22.x. Fresh typecheck succeeds,
> regenerated API types cmp/SHA match original baseline61f4c4a5, and50 focused
> plan/watchdog tests pass0.60s. Whitespace clean. Dependency and artifact proof
> scripts safely copied/cmp-verified to the local durable runtime audit directory;
> temporary fixtures retained. Parent owns publication and fresh exact-SHA gates.

> #1027 completed local dependency proof, 2026-09-28: Node22.23.2/npm10.9.8,
> npm ci --ignore-scripts, typecheck and 70 files/845 Vitest tests pass (single
> worker, 273.39s). build:app succeeds in 2.33s; offline HTML validation resolves
> all six referenced local assets as nonempty files. This is not a browser/live
> deployment proof. Existing Vite future-native-loader and Tailwind sourcemap
> warnings remain; jsdom emitted canvas/navigation warnings, no failed tests.
> npm audit JSON twice reports zero vulnerabilities; npm ls/explain independently
> confirms core1.34.20, YAML4.3.2, nanoid3.3.19 and Vitest/mocker4.1.11.
> Original-lock API generation equals patched output byte-for-byte. Actual
> installed-package guard mutations reproduce missing YAML budget exception and
> nanoid zero-size subprocess timeout (1s, child reaped); both restored with cmp,
> then both bounded probes pass. No tracked generated artifacts or service changes.
> Local proof script: /tmp/slomix-deps-security-proof-20260928.cjs; baseline install
> /tmp/slomix-deps-baseline-5lbaDz. Next actual-main synchronization and fresh
> exact-head review/CI; original runtime plan follows queue consolidation.

> #1027 follow-up, 2026-09-28: upstream nanoid3.3.19 is compatible with
> postcss8.5.25's existing ^3.3.16 range, removing the remaining high advisory
> https://github.com/advisories/GHSA-2v37-7h3g-55p8 . Targeted lock-only update
> and restored unrelated libc metadata leave exactly three changed lock entries
> against original f0d263c2: core, YAML and nanoid; package.json remains identical.
> Node22.23.2/npm10.9.8 clean install and audit report zero vulnerabilities;
> npm explain independently confirms the expected installed dependency paths.
> Same committed OpenAPI JSON generates byte-identical types with original and
> patched locks (cmp and SHA25661f4c4a5b04489b01fe4913df6ac43ef1474a262f0dc873076acea0463ade05d).
> Temporary no-save downgrade failed with npm's `Cannot read properties of null
> (reading 'edgesOut')`; no concurrent/partial-install comparison is credited.
> Reinstalled patched lock, then used separate original-lock npm ci for the
> comparison. Bounded original-package probes reproduce YAML merge-budget bypass
> and nanoid zero-size timeout; patched probes pass. Typecheck passes. Full tests
> and SPA build remain pending at this checkpoint; no server/browser/deployment.

> #1027 dependency preparation, 2026-09-28: Node22.23.2/npm10.9.8 targeted
> lock-only/ignore-scripts update advances @redocly/openapi-core1.34.19->1.34.20
> and js-yaml4.3.1->4.3.2 without overrides. openapi-typescript7.13.0 already
> permits core^1.34.6; registry metadata shows unchanged engine/dependency
> requirements except the YAML patch, and upstream core has no source changes.
> npm10 stripped18 unrelated libc selectors; restored those exactly from HEAD.
> Structural lock comparison proves only the two intended package entries differ;
> package.json and Vitest/mocker4.1.11 retained. No node_modules installation.
> Sources: https://redocly.com/docs/cli/v1/changelog and
> https://github.com/nodeca/js-yaml/security/advisories/GHSA-2883-xcg3-v3hh .
> Fresh npm audit removes those YAML/Vitest findings but reports one remaining
> high nanoid<3.3.18 advisory GHSA-2v37-7h3g-55p8; audit is NOT clean. No blanket
> audit fix applied. Next owner/root decision on narrow additional patch, then
> npm ci, generator output comparison, typecheck/test/build:app and fresh CI.

> Recovery checkpoint 2026-10-03, #1069: resumed the interrupted normal
> merge of actual main19e65354 after the usage-limit interruption. Both
> documentation histories retained; no source changes lost.
> 17 capture/Node/plan tests pass5.77s; actual spawned-child and filesystem proofs repeated. Capture source/tests unchanged from09a62009.
> Fresh exact-head review/CI required after publication. Original runtime
> roadmap and local-only1986d671 retained; no service/deployment action.

> #1069 actual-main checkpoint 2026-09-28: #1068 merged4de6f07e;
> normal merge retains both histories and exact shared/test code from4007e597.
> Thirteen real owned-child SSH capture/plan cases pass4.74s after sync; prior
> 220-case42.00s gate covers unchanged worker/SSH/spool/watchdog code. Original
> runtime1986d671 retained. Root may retarget/publish for fresh exact-head review;
> this local proof is not CI or merge readiness. No remote/network/DB/services.

> #1069 published-parent refresh 2026-09-28: normal merge e8f05dbd preserves
> both doc histories and exact final worker/source-test bytes. All 220 offline
> worker/SSH/task/capture/spool/watchdog/plan cases pass42.00s, including real
> owned-child cleanup and synthetic capture proofs; no network/DB/services.
> Original runtime1986d671 retained. Actual #1068 squash-main synchronization
> and fresh publication/review remain required; root owns remote operations.

> #1069 local parent propagation 2026-09-28: merged final worker90026032,
> retaining both histories and exact worker/source-test bytes. Eleven real
> spawned SSH-capture fixture cases pass4.85s; callers use0.2s grace or default,
> compatible with new0.01 minimum. Worker lifetime SIGINT latency contract
> retained. No remote/service/network/DB changes. Original runtime1986d671
> remains resume point; actual-main sync and fresh review remain root gates.

> Current #1069 checkpoint, 2026-09-28: normal parent merge 005e8d83 retains
> worker fixes 86c69e39 and SSH identity guard e22ae27c byte-for-byte. Combined
> 144 cases pass in 18.35s, including real child success/corruption/read-block/
> close-block with independent filesystem digest and process cleanup checks.
> Initial command used nonexistent test_runtime_ssh_task.py and executed no
> tests; corrected test_runtime_ssh_capture.py run above is the actual evidence.
> Local preparation only; wait #1068 actual main and fresh exact-head gates.

>1069 local refresh2026-09-27: live source87f9fa72 normally merged prepared
>1068 parent3244843d as4020bb69. Three doc conflicts retained both histories;
>worker cleanup and SSH explicit-key authentication source/tests equal parent.
>114 offline worker/SSH/capture/spool cases pass17.95s, including actual child
>completion/corruption/read-timeout/close-timeout and independent sha256sum.
>Every owned lifecycle child absent from procfs and active_children after reaping;
>close timeout can retain a complete final file, so status is not spool state.
>Absolute remote path guard removal fails DID NOT RAISE ValueError; restored/cmp.
>Ruff clean. No live network, service/DB/snapshot operations, push or retarget.
>Await actual parent/main synchronization and fresh exact-head CI/review plus
>individual approval; original runtime roadmap preserved after consolidation.

> Current #969 checkpoint 2026-09-28: normal integration of actual worker
> main4de6f07e preserves both document histories and exact Node/PyYAML/CI
> bytes6f423762; worker source/tests equal main. Root99node/watchdog/plan/
> real-child worker cases pass34.80s. Prior actual binary and restored failing
> pin mutation apply to unchanged files. Fresh exact-head CI/review required.
> Runtime resume1986d671 and bounded queue authorization remain unchanged;
> NEVER MERGE, held release956, services and production remain excluded.

> Current #969 checkpoint 2026-09-28 after watchdog merge ec8ec7ed: normal
> integration preserves both documentation histories and exact Node/PyYAML/CI
> source and test bytes from ea5f2ab3. Root54node/watchdog/plan cases pass1.33s.
> Earlier actual22.23.2 two-path proof and restored failing old-pin mutation
> apply to identical files. Publish for new exact-head review/CI, then owner-
> authorized current-queue merge gates. No service/install/production action.
> Original runtime1986d671 retained; NEVER MERGE and held release956 excluded.

> Current #969 checkpoint 2026-09-28: normal integration of main 1f4a388d
> preserves both histories and the exact Node pin/PyYAML declaration. Six
> node/plan contracts pass in 0.30s. Actual isolated binary reports v22.23.2
> via --version and 22.23.2 via process.versions.node. Restoring old22.13.1
> fails the frontend engine-floor guard; restored/cmp. No npm installation,
> build, browser, system toolchain, dependency lock or service change. Root
> owns publication and final review/merge gates. Runtime resume1986d671 and
> dependency consolidation remain current; older checkpoints are historical.

> Node pin slice follow-up (Astra, 2026-09-08): PR #969 review identified
> PyYAML as an undeclared direct test dependency despite green CI. Declared
> PyYAML==6.0.3 in requirements-dev and added a declaration contract. Validate
> with the isolated agent venv; no service environment changes.

> Current #1068 checkpoint 2026-09-28: #965 merged ec8ec7ed; normal main sync
> 9fb9d3db retains both document histories and worker/source test bytes90026032.
> Root independently passed159cases37.50s before sync and207worker/SSH/spool/
> capture/watchdog cases37.06s after sync. SIGINT lifetime and0.01minimumgrace
> contracts below are current; prior narrower deferral notes are historical.
> Publish for fresh exact-head CI/review; all five outstanding findings need
> evidence-backed replies. Owner's current-queue exception remains bounded;
> original runtime1986d671, NEVER MERGE, release956 and services stay excluded.

> #1068 lifetime ownership correction 2026-09-28: fresh review reproduced tiny
> positive grace leaving an owned child, a second-getsignal cleanup transition,
> and dropped custom SIGINT side effects when launch also failed. Install one
> callable-SIGINT deferrer before any child exists and retain it through close;
> replay the restored handler even after an operation error, preserving that
> error if the handler also raises. SIGINT cancellation is deliberately delayed
> up to timeout plus shutdown, coalesced to one callback; no immediate promise.
> Require shutdown_grace >=0.01 before spawning, and always attempt each phase's
> stopping signal before its elapsed budget limits waiting. OS inability to reap
> still raises RuntimeError; no absolute startup/kernel bound or service claim.
> Final 159 combined cases pass37.24s, including45real-child worker cases and
> 114offline SSH/capture/spool cases. Real SIGINT during join tests default,
> custom-return and SystemExit policies with/without original operation errors;
> procfs/active_children and closed handles prove ownership release. Replacing
> BaseException cleanup handling with Exception fails3 SystemExit cases; removing
> lifetime deferral fails actual spawn-window ownership. Restored/cmp each time;
> deliberate-failure fixture cleanup reaped its own children. CodeQL663's broad
> catch is intentional deferred cancellation, not suppression; CodeQL662's
> cleanup_complete variable is removed. No remote/service/network/DB operation.
> Original runtime1986d671 and previous worker fixes remain preserved. Root
> owns publication, fresh exact-head review and merge gates.

> #1068 root-review follow-up, 2026-09-28: reproduced false unreaped error for
> an already-finished real child with accepted grace=1e-20, and real SIGINT in
> cleanup clock/loop control bypassing reaping. Status is now observed before
> expiry checks; callable SIGINT deferral covers the entire cleanup ownership
> scope including exitcode and handle close. Handler replay happens restored and
> only after cleanup; original parent errors retain precedence. Custom, ignored
> and SystemExit handlers are verified at close. Both mutations fail as expected,
> restored/cmp; final 146 combined cases pass in 20.51s including 32 worker cases.
> Ruff/whitespace clean. SIGKILL/default SIGTERM, arbitrary injected CPython
> exceptions and uninterruptible OS waits remain outside the guarantee. No
> remote/service/SSH changes. Supersedes the narrower startup-only deferral below.

> Owner exception recorded 2026-09-28: the live message explicitly approved
> #1067, then instructed continued merging of the remaining current PR queue
> without repeated permission prompts when reviewed, corrected and green.
> Eligible IDs: #963, #964, #965, #966, #969, #979, #1027, #1066, #1068-#1075,
> #1077. Exact-head CI, addressed review findings and the prescribed merge cycle
> remain mandatory. Excludes NEVER MERGE #924-#943/#967, held #956, services and
> production. This is a bounded owner exception, not standing authorization for
> unrelated future PRs; it does not change the repository's general policy.

> #1068 interruption repair, 2026-09-28: real spawned children reproduced leaks
> from kill/is_alive interruptions and actual SIGINT after OS spawn before
> CPython attaches Process._popen (three failures; fixtures forcibly cleaned up).
> Main-thread callable SIGINT handlers are temporarily deferred until ownership
> exists, then restored before delivery; ignored/custom behavior and child masks
> are preserved. Both escalation phases now retry all operations within bounded
> grace deadlines. Persistent status/kill failures raise truthful unreaped errors.
> Original parent errors still win after successful cleanup. Regression mutations
> repeat all three failures; restored/cmp. Final 140 focused tests pass in 17.04s,
> including 26 worker cases; Ruff and whitespace clean. Procfs and active_children
> independently confirm child cleanup. No real SSH, service or remote writes.
> Arbitrary exceptions injected inside private CPython startup and uninterruptible
> OS waits are not claimed safe/bounded. Propagate this repair into descendants
> before their final publication; original runtime roadmap remains unchanged.

> Final main synchronization 2026-09-28: #1067 merged 1f4a388d, reviewed tree
> equality verified. Normal main merge c99badb6 preserves worker backports and
> final SSH identity. Repeat combined gate: 133 passed in 13.69s. Publish #1068
> against main for fresh exact-head CI/review under owner's autonomous green
> queue authorization. No service activation, production or snapshot changes.

> Current #1068 checkpoint, 2026-09-28: final reviewed #1067 e22ae27c merged
> normally as eed58f6c; both document histories preserved. Worker source/tests
> remain identical to preserved 86c69e39; SSH source/tests equal e22ae27c.
> Combined 133 cases pass in 14.44s, including real spawned-child completion,
> failure, parent/cleanup interruption and SIGTERM refusal. Timeout observations
> 2.004s/2.204s; procfs and active_children both confirm cleanup. Ruff clean.
> Prior seen-failing late-observer mutation remains applicable to identical
> worker bytes. Await actual #1067 main integration, then rerun/publish/review.
> Owner's bounded queue exception is recorded above; no services enabled.

>1068 refresh checkpoint2026-09-27: started from preserved local86c69e39,
>NOT obsolete remote69a0ef29; normally merged reviewed parent1067 db7f3888
>as99f2161c. Both doc histories retained, worker/source test bytes unchanged.
>92 offline worker/SSH/capture/spool/integrity cases pass12.33s. Actual spawned
>children complete/fail/time out and are absent from both procfs and active_children;
>SIGTERM-resistant children are killed/reaped even when cleanup joins raise.
>Actual Paramiko RejectPolicy test opens no network connection; capture proof
>uses a local socket pair. Restoring late-observer timeout bug fails two cases
>(timed_out instead of completed/failed); restored/cmp. No remote pushes, services,
>live SSH, DB or snapshot operations. Await parent approval/actual main sync and
>fresh exact-head CI/review. Original runtime plan preserved after consolidation.


> #965 warning-transition delivery repair, 2026-09-28: review reproduced a
> delivered warn -> unknown -> warn being suppressed forever by notified_level.
> One bounded per-key pending_warn bit now distinguishes a new observed warning
> transition from delivery history. It survives cooldown and failed delivery,
> clears on successful warning ACK or a superseding nonwarn measurement, and
> always renders the latest condition rather than queuing historical warnings.
> Two actual run/state-file regressions fail on old code; replacing the pending
> bit with a naive observed-level OR also fails cooldown and failed-POST retry.
> Restored/cmp; 48 watchdog tests pass in 0.48s, Ruff/whitespace clean. JSON read
> independently agrees with load_state; mock delivery counts, latest reason and
> ACK timestamps prove retry behavior. Existing heartbeat-midnight repair remains.
> No real webhook, collector, service or remote operations; root owns publication.

> Current #965 checkpoint 2026-09-28: normally integrated actual main 1f4a388d
> after #1067 merged. Watchdog source and both test files remain byte-identical
> to reviewed 3c967222, retaining original 2e035917 and the disk fix. All 45
> focused contracts pass, including real temporary state/report files with
> in-process mocked collectors/webhook only. Inverting delivery success fails
> with last_alert_at 1788742800.0 instead of 0; restored/cmp and full rerun pass.
> No real notification, service or database operation. Root owns publication,
> fresh exact-head CI/review and merge gates. Runtime resume 1986d671 unchanged;
> older checkpoints below describe their dates, not current queue authority.

> Current965 checkpoint2026-09-27: approved1055 merged194993f7; exact tree
>matches reviewed0e66f238. This branch now normally integrates that main,
>preserving source/test bytes and both documentation histories. 43focused
>tests rerun after sync. Publish for fresh exact-head CI/review; no965 merge
>approval, service activation or NEVER MERGE changes. Earlier waiting notes
>below are historical; original runtime roadmap remains unchanged.

>965 preservation checkpoint2026-09-27: start from local2e035917, not older
>remote c8fa8e41; normally integrate main as44df616a, preserve both doc histories.
>Watchdog source/tests byte-identical to2e035917.43focused cases pass0.43s,
>Ruff clean. Inverting delivery-success guard advances an unconfirmed timestamp
>and fails the retry test; restored/cmp. Separate in-process synthetic transport
>with actual persisted files proves failed pending1/ACK0, success pending0,
>two delivery attempts and no third-cycle duplicate. No Discord request, live
>collector/service action or production data. Await1055 merge then final refresh
>and publish for fresh exact-head review; no965 merge approval.

> Current #969 checkpoint 2026-09-28: normal integration of main 1f4a388d
> preserves both histories and the exact Node pin/PyYAML declaration. Six
> node/plan contracts pass in 0.30s. Actual isolated binary reports v22.23.2
> via --version and 22.23.2 via process.versions.node. Restoring old22.13.1
> fails the frontend engine-floor guard; restored/cmp. No npm installation,
> build, browser, system toolchain, dependency lock or service change. Root
> owns publication and final review/merge gates. Runtime resume1986d671 and
> dependency consolidation remain current; older checkpoints are historical.

> Node pin slice follow-up (Astra, 2026-09-08): PR #969 review identified
> PyYAML as an undeclared direct test dependency despite green CI. Declared
> PyYAML==6.0.3 in requirements-dev and added a declaration contract. Validate
> with the isolated agent venv; no service environment changes.
>Current1067 checkpoint2026-09-27: approved1065 merged9ef42671 at20:36:29Z;
>squash tree equals reviewed1f6562f0. Actualmain normally integrated; explicit
>private-key-only sidecar repair preserved fromc63f8ac5. Repeat combined gate,
>publish/reply and request fresh exact-head review. No1067 merge permission,
>network/service/applicationDB action. Original runtime roadmap preserved.

> PR1067 explicit-identity correction, 2026-09-27: follow-up review proved that
> PKey.from_path silently loads key_path-cert.pub. A real temporary ssh-keygen
> certificate changed the offered identity; a malformed neighbor broke auth.
> Both regressions failed on old code. Load the named private-key contents once
> through public typed from_private_key file-object APIs instead; no sidecar
> lookup, certificate-path substitution or passphrase prompt. Five existing
> RSA/ECDSA/Ed25519 encoding proofs still pass. Certificate paths explicitly
> fail closed. All108 SSH/capture/spool/reconcile tests pass. Reintroducing
> from_path failed both sidecar guards; restored/cmp. Earlier from_path claims
> below are superseded by this correction. No live handshake/network/services
> or DB actions; next fresh exact-head CI/review. Original plan remains intact.

>Current1067 checkpoint2026-09-27: approved1064 merged f9327cae at20:22:36Z;
>squash tree c627a055 equals reviewed00f16c55. Actualmain integrated normally,
>all doc histories and source fixes preserved. Publish after repeated local gates
>for new exact-head CI/review; no1067-specific merge approval. No services,
>application DB or real SSH activated. Original runtime roadmap remains intact.

> PR1067 key-only authentication correction, 2026-09-27: installed/pinned
> Paramiko5 legacy authentication can call auth_interactive_dumb after partial
> public-key authentication even with agent/discovery disabled. Three new
> regression cases failed on old code. The modern AuthStrategy hook now loads
> exactly the explicit key with PKey.from_path and requires complete public-key
> authentication; partial responses never reach SFTP, password or interactive
> fallback. Actual installed SSHClient.connect exercised offline with synthetic
> transport and real RSA PEM/OpenSSH, ECDSA PEM/OpenSSH and Ed25519 OpenSSH keys.
> Missing/malformed/encrypted keys fail closed; no passphrase prompt. Guard
> removal failed all three cases; restored/cmp. Combined SSH/capture/spool gate:
> 84 passed. No real SSH handshake, external connection, service or DB action.
> Next: publish for new exact-head CI/review; no1067 merge permission. Original
> runtime plan and activation gates below remain intact.

>Current1067 checkpoint2026-09-27: approved1063 merged d047554c at19:59:44Z;
>squash tree equals435268ef. Actual main now integrated normally, documentation
>histories and implementation bytes preserved. Repeat local gates then publish
>for fresh exact-head CI/review. No service, network or application DB action;
>no1067-specific approval recorded yet. Earlier checkpoints below are history.

>1067 refresh checkpoint2026-09-27: integrated reviewed1063 parent435268ef
>normally as eb72ec88; retained documentation histories and source/test bytes
>from9f86bd69.73combined cases pass, including real Paramiko RejectPolicy against
>a generated unknown key offline (no network) and real local socket publication.
>Omitting SSH close registration fails cleanup-after-SFTP-close-error assertion:
>['sftp-close'] != ['sftp-close', 'ssh-close']; restored/cmp and all73 pass again.
>Existing review threads empty. Await1063 actual main merge before final sync,
>retarget/push and fresh exact-head CI/review. No1067 permission, no connections
>or service changes. Phase timeouts do not bound DNS/handshake/cleanup as a whole;
>the later dedicated worker remains an activation gate. Original plan preserved.

>Current1065 checkpoint2026-09-27: approved1064 merged f9327cae at20:22:36Z;
>squash tree c627a055 equals reviewed00f16c55. Actualmain integrated normally,
>all doc histories and source fixes preserved. Publish after repeated local gates
>for new exact-head CI/review; no1065-specific merge approval. No services,
>application DB or real SSH activated. Original runtime roadmap remains intact.

>1065 refresh checkpoint2026-09-27: integrated reviewed1064 parent3422cd3e
>normally as ab5b17e4. Source/test bytes equal0e3d100a; both doc histories retained.
>55real filesystem cases pass0.63s/0.66s, including partial failure, publication
>race and failed directory fsync followed by content inspection without reread.
>Mutation forcing a source read on match fails AssertionError: Source must not
>be consumed; restored/cmp, Ruff clean. Content presence is not a durability or
>import acknowledgement. Await1064 actual main merge before final sync/publish;
>no1065 merge approval, no network, services or application DB changes.
>Original runtime plan preserved; dependency consolidation only.


>1064 restrictive-umask review2026-09-27: reproduced publication under0277
>creating0400 successfully while reconciliation rejected its own output. Inspector
>now accepts exact0400/0600 owner-readable private regular files without chmod;
>group/other/execute/special permissions remain rejected.75actual filesystem and
>local socket cases pass0.71s. Real0400 file matches expectedabc, stat length3,
>mode unchanged. Reinstating strict0600 guard fails regression; restored/cmp;
>Ruff clean. No permission widening, service/DB changes, push or merge. Original
>runtime plan preserved; fresh review/CI remains required after publication.

>Current1064 checkpoint2026-09-27: approved1063 merged d047554c at19:59:44Z;
>squash tree equals435268ef. Actual main now integrated normally, documentation
>histories and implementation bytes preserved. Repeat local gates then publish
>for fresh exact-head CI/review. No service, network or application DB action;
>no1064-specific approval recorded yet. Earlier checkpoints below are history.

> Current 1064 checkpoint 2026-09-27: approved parent1062 merged4454d6c5;
>squash tree equals reviewed21e6c999. Actual main now merged normally here.
>Documentation histories preserved; source/test bytes unchanged from5264909e.
>49 filesystem/stream tests are the local gate; prior failed/restored guard
>mutation retained. Retarget to main and publish for fresh exact-head CI/review;
>no 1064 merge approval, service activation or application database writes.
>Original Runtime v2 plan remains intact; this is dependency consolidation.

>1064 refresh checkpoint2026-09-27: normally integrated reviewed parent1062
>21e6c999 as4c119978, preserving both documentation histories. Reconciliation
>implementation/test bytes equal5264909e; both existing review threads resolved,
>including wrong-sized inode replacement detection before conflict.49actual
>filesystem tests pass0.56s, including private publication, independent SHA-256,
>missing/match/conflict, read failures and inode replacement. Reinstating the old
>wrong-size early return fails DID NOT RAISE RuntimeError; restored/cmp. Ruff
>clean. Wait for approved1062 merge, then sync actual main and refresh exact-head
>CI/review before any1064 merge decision. No push, service, DB or snapshot changes.
>Original runtime roadmap remains unchanged; this is existing-PR consolidation.

> Current 1063 checkpoint 2026-09-27: approved parent1062 merged4454d6c5;
>squash tree equals reviewed21e6c999. Actual main now merged normally here.
>Documentation histories preserved; source/test bytes unchanged froma570431c.
>54 filesystem/stream tests are the local gate; prior failed/restored guard
>mutation retained. Retarget to main and publish for fresh exact-head CI/review;
>no 1063 merge approval, service activation or application database writes.
>Original Runtime v2 plan remains intact; this is dependency consolidation.

>1063 refresh checkpoint2026-09-27: normally merged reviewed1062 head21e6c999
>as6c1579b6. Capture source/tests byte-identical to a570431c.54socket/filesystem
>cases pass0.54s; real socket EOF publishes exact3bytes, missing EOF times out
>without publication. Moving deadline before file setup reproduces TimeoutError
>Capture deadline exceeded; restored/cmp. Ruff clean. Existing reviewed fix is
>retained, not reimplemented. Await approved1062 merge, then sync/retarget/push
>for fresh exact-head CI/review. No1063 merge approval or service activation.

> Current1062 checkpoint2026-09-27: approved1061 merged8afc46b1 at15:56:34Z,
>0failed/0threads/0behind/unchanged head; squash tree equals d00f5de2. This
>branch integrates that main normally; implementation/test bytes preserved.
>Publish now for fresh exact-head CI/review; no1062 merge permission and no
>service or production changes. Earlier waiting checkpoints are historical.

>1062 refresh checkpoint2026-09-27: normally integrated reviewed1061 d00f5de2
>as7f72ccc7; source/integrity test bytes unchanged from1a024ce4.35filesystem
>cases pass0.33s; independent sha256sum agrees with exact bytes/stat length.
>Removing digest mismatch guard fails equal-length-corruption test with DID NOT
>RAISE ValueError; restored/cmp. Ruff clean. Await approved1061 merge, sync
>actual main, retarget before final push, then fresh exact-head review/CI.
>No1062 merge permission. Optional digest is content verification, not source
>authentication, scheduler wiring or a production activation guarantee.


> Current1061 checkpoint2026-09-27: approved1055 merged194993f7; exact tree
>matches reviewed0e66f238. This branch now normally integrates that main,
>preserving source/test bytes and both documentation histories. 24focused
>tests rerun after sync. Publish for fresh exact-head CI/review; no1061 merge
>approval, service activation or NEVER MERGE changes. Earlier waiting notes
>below are historical; original runtime roadmap remains unchanged.

>1061 now integrates main0d43b3da (approved1054 squash) as c994b186. Source
>and tests remain unchanged from28009e87;24filesystem cases pass0.22s after
>sync. Publish this four-file slice for fresh exact-head CI/review; no1061
>merge permission. Earlier waiting notes below are historical.

>1061 refresh checkpoint2026-09-27: merged main normally as761fff59, retained
>both documentation histories. Production/test files byte-identical to28009e87.
>24actual filesystem tests pass0.23s; restoring the restrictive map regex fails
>the dot/plus cases with Invalid stats filename, restored/cmp. Ruff clean.
>Verified the old finding's implementation and resolved its thread. This is
>no-clobber publication only, not trusted transport or automatic ingestion.
>Refresh once more after approved1054 lands, then publish for fresh exact-head
>CI/review. No1061 merge approval and no service/deployment changes.

>1054 merged with owner approval as0d43b3da at15:06:08Z on2026-09-27;
>0failed/0threads/0behind/unchanged head, squash tree matches6d06c58b.
>1055 now integrates that main normally; only seven PR paths remain. Retarget
>to main before publishing this checkpoint. Fresh exact-head CI/review required;
>no1055 merge permission. Earlier waiting notes are historical.

>1055 refresh checkpoint2026-09-27: normally integrated reviewed1054 head
>6d06c58b as e0d6c699; retained both documentation histories.54focused cases
>pass18.54s including5real isolated-PG cases and actual process shutdown/replay.
>Entry module unchanged from847c1b7d. Disabling explicit dev guard fails2cases
>with DID NOT RAISE ValueError; restored/cmp and26entry tests pass0.36s.
>Ruff/whitespace clean; schema count0 and independent list empty. Await approved
>1054 merge, then sync actual main, retarget before push and repeat exact-head
>CI/review.1055 itself is NOT approved. No service/deployment/app-data changes.


>1054 review follow-up2026-09-27: stopped state now clears current error_type,
> while failed retains diagnostics. Stop-event and task-cancellation cases both
> reproduced OSError in stopped before fix and with cleanup removed; restored/cmp.
>26tests incl3isolated PG pass2.08s before proof service timeout at16:09CEST.
> Fresh exact-head CI/review required after push; no1054 merge approval.

> Latest1054 checkpoint2026-09-27: approved1053 merged75a359f6 at13:28:51Z,
> prescribed420s cycle0failed/0threads/0behind/unchanged head, squash tree equals
> reviewed ccd23e81.1054 integrates main without changing worker implementation;
> retained its default-OFF flag and documentation. Retarget before final push;
> fresh exact-head review/CI and explicit1054 approval still required.

>1054 refresh2026-09-27: merged reviewed parent ccd23e81 normally. Clear stale
> error_type on both disabled transitions while retaining confirmed generation,
> unsupported count and last-success time. Four async worker reproductions fail
> before fix and with the fix removed, restored/cmp.161local cases previously
> passed; fresh21worker unit+3realPG lifecycle cases pass4.36s on refreshed parent.
> Actual polling catches late lower IDs, receipt failure rolls back/retries and
> closed connections reacquire. Fresh exact-head CI/review and owner merge
> permission remain required; parent1053 is reviewed but not merged.
>1053 follow-up2026-09-27: fresh review found ON reactivation could revive an
> old generation when events were disabled during writes. Both ON/OFF namespaces
> now include the captured middleware-lifetime/mode-transition token. All cache
> reuse is worker-local, including Redis-backed ON mode; generation changes still
> invalidate independently in each worker. This trades cross-worker reuse for
> safe reactivation/restart, not a measured performance improvement. Website
> env example now declares all three flags default OFF with091/092 prerequisites.
>151local cases pass,12ASGI mode-roundtrip combinations;7reproduction/mutation
> failures observed, restored/cmp. Fresh CI/review required; no1053 approval.

> Current1053 refresh (2026-09-27): parent1052 refreshed by ordinary merge,
> preserving both documentation histories. Two open review findings addressed:
> activation comment requires091/092; OFF cache namespaces are unique per
> middleware lifetime and observed mode transition, captured before awaits.
> This prevents rollback from reviving pre-activation entries; OFF workers no
> longer share cached responses, trading cache reuse for safe restart boundaries.
>82local cache tests pass; two real ASGI rollback cases fail before the fix and
> when its namespace guard is removed, restored/cmp. Backend retained across
> app lifetimes is simulated with memory, not a new Redis/PG integration proof.
> Fresh exact-head CI/review pending; no1053 merge permission or activation.

> Current1052 refresh (2026-09-27): local87eec905 normally merges refreshed1051
> eed90b28, preserving both documentation histories. Memory backend/test files
> remain byte-identical to original3d9da0e0.58cache regression cases pass1.29s;
> standalone in-process ASGI proof returns200 with MISS/HIT/MISS/MISS, correct
> bodies, handler calls1/2/1 and one retained entry. Removing count eviction fails
> 4<=3 and HIT!=MISS; restored/cmp. No listener, browser, database or service.
> Owner-approved1051 merged as2b310cb3 at06:42:21Z after the prescribed cycle;
> squash tree equals reviewed eed90b28.1052 now integrates that main, is retargeted
> to main before final push, and requires fresh CI/review and its own approval.
> Original independent-runtime/recovery then new-site audit remains
> the plan; earlier checkpoints below are historical.

> PR1060 merged with explicit owner approval on2026-09-27 at06:25:44Z as197feaf7.
> Required cycle ended0red/0threads/0behind/unchanged head; squash tree equals
> ec40a03f. Main workflows are running, not yet all confirmed green. PR1051 now
> integrates this main as well; fresh exact-head CI/review and its own merge
> permission still required. No service action, deployment or migration applied.

> Historical local cache refresh checkpoint (2026-09-27): PR1051 refreshed from
> c4770f5a by normal merge of main c9de5a3d (a6048926). Both documentation tracks
> retained; consumer/migration/SQL proof files are byte-identical to c4770f5a.
> 10 portable cache contract cases and48 journal/startup regression cases pass.
> Fresh local SQL is pending owner restart of the isolated proof service; old
> SQL results below are historical, not a fresh run. Wait for approved1060 merge,
> then refresh once more and publish for exact-head CI/review. No1051 merge
> permission, service action or deployment. Runtime identity/recovery work remains
> on its separate integration branch; earlier checkpoints below are historical.

> PR1060 review4114242030, 2026-09-27: waiting admission now uses the canonical
> 2020-2035 year range, avoiding year0001 previous-day underflow. Invalid years
> go to canonical processing, not dependency lookup. Added outside/boundary unit
> cases and real PG failed-marker proof for0001.50tests passed46.46s, including
> six PG subprocess cases; disabling the year guard fails3tests, restored/cmp.
> Ruff/whitespace clean; neutral schema count0 and independent list empty.
> Fresh exact-head CI/review required after this fix; no merge approval inferred.

> PR1060 refresh, 2026-09-27: parent1059 merged as c9de5a3d. This branch now
> integrates that main without changing the1060 importer/runtime implementation.
> Preserved both documentation histories, all six SQL scenarios, and main's
> ambient-SSH startup-test fix.45 targeted unit/real-PG tests passed53.55s;
> changed small Python files lint clean. Six previously addressed review threads
> revalidated and resolved before refresh. Fresh exact-head CI/review required;
> no merge permission for1060 or service activation. Current broader runtime
> work remains in the separate integration worktree; historical notes follow.

> Startup prerequisite #1059 update (2026-09-26): published refresh65f5dc60 by
> ordinary fast-forward and retargeted to main89a2fd38. Ten-file diff self-reviewed;
> 26targeted tests pass3.86s and four neutral SQL subprocess scenarios previously
> passed on that exact code. Independent read-only review found no concrete
> regression,12tests passed plus8-thread/one-logging-init probe. CI36197446590
> all8jobs passed; CodeRabbit status success; review threads empty. Required
> repo-hygiene and CodeQL checks did not start on base-edit alone (their workflows
> lack edited/dispatch triggers). This real documentation checkpoint also gives
> the now-main-targeted PR a synchronize event; re-check ALL gates on its new SHA.
> No merge/deploy performed or approved. Older LOCAL/unpublished notes below are
> historical. Production bytes remain unchanged from921af249.

> #1027 completed local dependency proof, 2026-09-28: Node22.23.2/npm10.9.8,
> npm ci --ignore-scripts, typecheck and 70 files/845 Vitest tests pass (single
> worker, 273.39s). build:app succeeds in 2.33s; offline HTML validation resolves
> all six referenced local assets as nonempty files. This is not a browser/live
> deployment proof. Existing Vite future-native-loader and Tailwind sourcemap
> warnings remain; jsdom emitted canvas/navigation warnings, no failed tests.
> npm audit JSON twice reports zero vulnerabilities; npm ls/explain independently
> confirms core1.34.20, YAML4.3.2, nanoid3.3.19 and Vitest/mocker4.1.11.
> Original-lock API generation equals patched output byte-for-byte. Actual
> installed-package guard mutations reproduce missing YAML budget exception and
> nanoid zero-size subprocess timeout (1s, child reaped); both restored with cmp,
> then both bounded probes pass. No tracked generated artifacts or service changes.
> Local proof script: /tmp/slomix-deps-security-proof-20260928.cjs; baseline install
> /tmp/slomix-deps-baseline-5lbaDz. Next actual-main synchronization and fresh
> exact-head review/CI; original runtime plan follows queue consolidation.

> #1027 follow-up, 2026-09-28: upstream nanoid3.3.19 is compatible with
> postcss8.5.25's existing ^3.3.16 range, removing the remaining high advisory
> https://github.com/advisories/GHSA-2v37-7h3g-55p8 . Targeted lock-only update
> and restored unrelated libc metadata leave exactly three changed lock entries
> against original f0d263c2: core, YAML and nanoid; package.json remains identical.
> Node22.23.2/npm10.9.8 clean install and audit report zero vulnerabilities;
> npm explain independently confirms the expected installed dependency paths.
> Same committed OpenAPI JSON generates byte-identical types with original and
> patched locks (cmp and SHA25661f4c4a5b04489b01fe4913df6ac43ef1474a262f0dc873076acea0463ade05d).
> Temporary no-save downgrade failed with npm's `Cannot read properties of null
> (reading 'edgesOut')`; no concurrent/partial-install comparison is credited.
> Reinstalled patched lock, then used separate original-lock npm ci for the
> comparison. Bounded original-package probes reproduce YAML merge-budget bypass
> and nanoid zero-size timeout; patched probes pass. Typecheck passes. Full tests
> and SPA build remain pending at this checkpoint; no server/browser/deployment.

> #1027 dependency preparation, 2026-09-28: Node22.23.2/npm10.9.8 targeted
> lock-only/ignore-scripts update advances @redocly/openapi-core1.34.19->1.34.20
> and js-yaml4.3.1->4.3.2 without overrides. openapi-typescript7.13.0 already
> permits core^1.34.6; registry metadata shows unchanged engine/dependency
> requirements except the YAML patch, and upstream core has no source changes.
> npm10 stripped18 unrelated libc selectors; restored those exactly from HEAD.
> Structural lock comparison proves only the two intended package entries differ;
> package.json and Vitest/mocker4.1.11 retained. No node_modules installation.
> Sources: https://redocly.com/docs/cli/v1/changelog and
> https://github.com/nodeca/js-yaml/security/advisories/GHSA-2883-xcg3-v3hh .
> Fresh npm audit removes those YAML/Vitest findings but reports one remaining
> high nanoid<3.3.18 advisory GHSA-2v37-7h3g-55p8; audit is NOT clean. No blanket
> audit fix applied. Next owner/root decision on narrow additional patch, then
> npm ci, generator output comparison, typecheck/test/build:app and fresh CI.

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

**Zadnja posodobitev:** 2026-10-04 (Astra, historical handoff review corrections)

## Consolidation follow-up: artifact review #979 — 2026-09-20

Preserve this older preflight proposal and fix three reviewed provenance gaps:
refresh source origin/main before default target resolution (explicit commits
remain offline); run the verifier from DEV_SRC_DIR rather than launcher checkout;
reject assume-unchanged/skip-worktree flags on tracked build inputs. All four
new regressions failed before fixes and when guards were deliberately reverted,
then restored/cmp.23 disposable-clone build/preflight tests pass, Ruff/bash syntax
clean. Only Vite is a tiny fixture executable; no actual app build, browser,
real run-clone operation, service or network deployment. Source-ref fetch is
now allowed before staging; RUN fetch/checkout/services still require validation.
This branch still needs current-main integration and fresh CI before merge;
no owner permission for #979. Approved batch is #1076/#1057/#962 only. Original
runtime completion delivery/sealing resumes after consolidation, then new-site
audit and owner-approved reversible DEV transition. NEVER MERGE remains untouched.

## Proga: Astra watchdog delivery acknowledgement

Consolidation update 2026-09-25: #1076, #1057 and #962 are merged; main is
89a2fd38. Locally integrated main into #965, retaining both documentation tracks.
45 watchdog/delivery/plan tests pass, including the disk-capacity change and
actual run() with isolated state files and stub transport. Midnight retention
mutation fails with `AssertionError: assert 1 == 2`; restored and cmp verified.
No live webhook, service, database or deployment action. No #965 merge approval.
Owner requires no additional GitHub charges: no AI review requests, remote
pushes or new PRs until automatic-review billing safety is established. Local
review and tests continue; account billing settings have not been verified.
Original runtime resume remains #1077 c015270b completion delivery/sealing,
then the new-site audit and separately approved reversible DEV transition.

Consolidation update 2026-09-20: refreshed current main with a normal merge,
retaining both documentation tracks.42 focused watchdog/delivery/plan tests pass;
Ruff clean. #962 remains a separate disk-formula change; combine and rerun after
its approved merge. Only #1076/#1057/#962 currently have explicit merge permission;
#965 preparation is authorized, its merge is not. Original runtime resumes at
#1077 c015270b completion delivery/snapshot sealing, then new-site audit and
owner-approved reversible DEV cutover. No services or real webhooks activated.

Zadnja posodobitev: 2026-09-08 (Astra). Implemented, locally verified; not deployed.
Contract: observations and failure streaks persist before delivery; notification
dedup and heartbeat acknowledgements advance only after successful delivery.
Failed delivery retries next cycle; dry-run writes neither state nor report.
Proof: 40 targeted tests pass; targeted Ruff and diff whitespace checks pass.
Real run/send_webhook with an in-process HTTP transport stub: failed alert,
successful retry, failed recovery, successful retry, then a silent healthy cycle
(four POST attempts, no network). Mutation acknowledging a failed POST was seen
failing (`last_alert_at` unexpectedly nonzero), restored and checked with `cmp`.
Dry-run tests cover existing/missing output paths and reject save attempts.
Discord batches are capped at ten and acknowledged separately; partial failure
retries only the undelivered remainder. Pending notifications follow the latest
measurement: resolved undelivered failures are superseded, not replayed as history.
Next: root review, then branch/PR flow. Real Discord delivery requires owner-approved
test; existing legacy timestamps cannot retroactively prove past delivery. A crash
after POST success but before state save can duplicate a notification.
No service changes, real webhook, disk formula or cadence changes.
PR #965 review 3951724563: pending daily heartbeat now survives midnight until
acknowledged, or is replaced by the newly due day's heartbeat (at most one).
Actual run with local stub: failed 23:58 -> successful retry 00:03 -> silent
00:08 -> next day's normal 09:05 heartbeat; on-disk dates/pending count checked.
Mutation disabling pending-heartbeat retention failed (`1` attempt vs expected
`2`); restored file matches snapshot by `cmp`. Main was merged normally and
both existing plan additions preserved. Next: root push and review reply.

## Track: runtime v2 R01 (Astra)

### Consolidation: historical Opus handoff #963 — 2026-09-20

Historical checkpoint only; current queue and authority are recorded above.

Preserve historical measurements, not obsolete operating instructions. Normal
main integration restores the tracked docs/HANDOFF-astra.md reference. Correct
release attribution (#952/#955/#958 after1.45.0), timer static-state inference,
journal rotation/config activation advice and bundled lessons. Local journalctl
manual confirms vacuum handles archived files and rotation precedes vacuum when
combined; no cleanup or service action executed. Git ancestry independently
confirms the release sequence; GitHub confirms #912 merged2026-09-07.
#912's historical live arena duel caveat is not proven resolved by its merge:
owner-controlled live verification remains separate. #962 is approved in the
consolidation queue, with current-main checks/runtime proof required before merge.
All host measurements in the old handoff remain explicitly historical. Original
runtime resume is #1077 completion delivery/sealing, then new-site audit and
approved reversible DEV cutover. #963 has no merge permission.
### R04p source stability parent refresh — 2026-09-28

Local normal merge of reviewed capture parent bda56937 into #1071 preserves
both documentation histories, worker interruption/late-exit fixes, strict SSH
authentication and explicit-key-only loading (no certificate sidecars).
160 focused offline cases pass in 25.71s, including actual spawned children,
filesystem publication and installed Paramiko transport seams. Growth, handle
mtime drift and named-path drift fail before publication; procfs and active
children independently confirm reaping. Successful bytes agree with sha256sum.
Disabling EOF metadata verification makes all three drift cases publish and
fail; restored file compares byte-for-byte with its backup and all three pass.
Ruff and whitespace checks pass. No real SSH, service, DB or remote PR changes.
Equal metadata still does not prove producer closure; trusted completion and
immutable digest remain activation gates. Next: publish/review this refreshed
slice after its parent merges, then continue the original runtime plan.

### R04p remote metadata stability guard — 2026-09-20

Completion investigation: STATS_READY is emitted on intermission (default send
delay zero), whereas checked-in stats writer delays SaveStats by3000ms and also
has a ShutdownGame path. Generic Stats saved log has no filename/digest; deprecated
on_created notifier merely sleeps3s. None establishes durable exact-file closure.
Executed synthetic local proof: path stat/open-handle fstat and two hashes agree
while writer remains open, then append changes7bytes to18. No live-server claims.
Before source-side expansion, ask owner whether to develop an offline producer
completion protocol (recommended, no deploy) or keep source frozen and continue
other runtime work with this activation gate unresolved. Do not substitute a
delay heuristic. Detailed research/proof stay local, no game/Lua/service changes.

Discovery: checked-in c0rnp0rn8.lua SaveStats writes directly to the final stats
name (FS_WRITE, header/player writes, close); legacy SSHHandler uses sftp.get.
This is code evidence, not verification of deployed Lua or remote corpus. Neither
path supplies an immutable snapshot manifest. Keep trusted source identity and
producer completion as activation gates; equal metadata does not prove closure.
SSHCaptureTask now requires regular-file mode/size/mtime from lstat before open,
expected size agreement, and matching handle/path metadata before reading and
again at EOF BEFORE local publication. Missing metadata fails closed. Paramiko
stat/lstat semantics checked against official SFTP API documentation.
127 combined tests pass. Real spawned task/filesystem with offline SFTP seam
rejects growth, handle mtime drift and named-path drift without publishing final;
rejects symlink/directory/missing fields/wrong size before opening remote file.
Mutation disabling EOF verification publishes invalid final and fails all three
drift cases; restored/cmp. Ruff/whitespace clean. No actual SSH or service changes.
Limitations: no inode identity, writer lock, same-size/same-mtime detection or
parent-path symlink protection. Digest and immutable-source preconditions remain.
#1070 reported checks green, no inline findings at refresh, no merge permission.
Next: source completion/manifest contract and verified importer composition;
original runtime-first/new-site audit/reversible dev sequence remains unchanged.

### R04o supervised capture reconciliation — 2026-09-20

Normal ancestry merge combines #1069 with #1064; documentation conflicts retain
both tracks. capture_ssh_once inspects first, skips match/conflict without spawn,
otherwise supervises one SSH task and inspects again only after the child is
reaped. Result preserves observed content and child outcome independently:
timed_out+match is possible and is not converted into worker success. No source
ack, deletion, retry loop, import or service activation. Inspection remains a
byte-bounded local filesystem operation outside the child deadline; no overall
wall-clock bound is claimed. Caller must keep private spool/snapshot immutable.
117 combined tests pass. Real child/filesystem with offline SSH seam proves
retry after corruption/interrupted read succeeds without touching orphan parts;
retry after close timeout reuses verified final without a new child. Existing
conflict remains unchanged. Disabling preinspection short-circuit fails two
tests with Existing content must not spawn capture; restored/cmp, Ruff clean.
#1069 all reported checks green; no individual merge permission inferred.
Next trusted source metadata/discovery and integration with verified importer;
single-writer handoff/dev failure matrix remain gates. New-site audit follows
runtime completion as originally planned; production remains untouched.

### R04n concrete SSH capture task — 2026-09-20

On #1068: picklable SSHCaptureTask carries only explicit configuration into the
spawned worker. Opens SFTP/file there, streams through existing size/SHA/EOF
publication, closes file before session, never deletes/acknowledges the source.
Absolute canonical remote path and absolute local spool required. Caller still
supplies trusted immutable source metadata; no remote discovery/hash guarantee.
97 combined tests pass, including real spawned-task/filesystem proofs with an
offline connection seam: successful bytes independently checked by sha256sum,
corruption rejected, blocked read terminated leaving only a .part, blocked close
terminated with a complete final retained. Both terminated children confirmed
absent by procfs and active_children. No actual SSH/network proof is claimed.
Removing the absolute remote path guard fails DID NOT RAISE; restored/cmp.
Next compose retry reconciliation with supervised capture and verified import;
trusted source identity, bounded discovery/retention, single-writer handoff and
owner-approved dev failure matrix remain activation gates. Original sequence:
runtime first, then new-site/design/security audit, then reversible dev cutover.
No merge permission inferred, no service/live database/production changes.

### Consolidation: preserve Node pin #969 — 2026-09-20

Normal merge of current main retains shared exact .nvmrc CI inputs and explicit
PyYAML development dependency. Four pin-contract and two plan-contract tests pass.
This refresh preserves the reviewed version; it does not claim a current security
release audit, frontend build or system toolchain upgrade. Fresh CI/review required.
No merge permission for #969; only #1076/#1057/#962 currently authorized. Original
runtime resumes after this consolidation detour at #1077 completion delivery and
snapshot sealing, followed by new-site audit and approved reversible DEV cutover.

### R04m consolidation safety backport — 2026-09-25

Locally backported the exact worker and regression-test changes from #1077
c015270b into #1068 before its eventual merge. Five regression cases fail the
old implementation: late observation misclassifies a finished child, and cleanup
interruptions can abandon a child or replace the original parent interruption.
94 worker/SSH/spool/integrity/capture/plan tests now pass; Ruff/whitespace clean.
Real spawned children checked against procfs and active_children; Process objects
closed. SIGTERM/SIGKILL timeout cases measured 2.003s/2.205s including cold spawn
with a 2s deadline and 0.2s grace. No hard OS scheduling bound is claimed.
Late-clock mutation fails both finished-child cases, restored with cmp proof.
No network, DB, services or production changes. Owner reported unwanted GitHub
review charges: keep this commit local, no push or automated review request.
#1068 still requires PR-specific merge approval and fresh merge-base/CI review.
Do not merge the whole #1077 descendant into this prerequisite. Original plan
continues with trusted completion delivery/immutable sealing at #1077, then the
new-site audit and separately approved reversible DEV cutover.

### R04m disposable capture worker supervision — 2026-09-20

Contract: explicitly spawned capture-only child, monotonic operation deadline,
terminate/join then kill/join escalation, result only after reaping. Completed,
failed and timed_out remain separate; parent cancellation also enters cleanup.
No DB pool/shared queues/locks/descendant processes in tasks. No task return
payload or exception text crosses process boundary. Forced stop can skip finally
and leave partial/complete spool state, so retain source and reconcile on retry.
Startup counts against deadline but OS startup/uninterruptible kernel waits
cannot be hard-bounded; cleanup has two bounded grace windows and raises if it
cannot reap. This is an internal primitive, not SSH activation or service control.
Prove real child success/failure, blocked task and SIGTERM refusal with procfs
and active-child checks before integrating a transport-specific task.
Verified 86 combined worker/SSH/capture/spool tests pass. Actual spawned children
complete/fail, time out under SIGTERM and escalate after SIGTERM refusal; exit
codes -15/-9 agree with absence from procfs and active_children. Parent join
interruption also reaps, unpicklable startup leaves no task child. Two runs of
timeout proofs measured about 2.00s/2.20s with 2s budget and 0.2s grace (cold
spawn included). Mutation reporting timeout as completed fails both cases;
restored/cmp. Ruff/whitespace clean. No remote connection or service/DB changes.
Python termination semantics verified against official multiprocessing docs;
do not use this boundary for transactions/shared locks or claim hard OS bounds.


### R04l explicit SSH session ownership — 2026-09-20

On #1063: neutral RuntimeSSHConfig and caller-driven open_runtime_sftp context.
Explicit host/user/port/absolute key and known-host paths; strict RejectPolicy,
no agent/key discovery/password or ambient bot config. Close SFTP before SSH,
including failure during setup/body/cleanup. Caller closes its file handles.
Phase budgets are NOT an overall deadline: DNS, subsystem negotiation and close
can block. Hard-bound worker/process design remains an activation gate; do not
use an executor cancellation as proof of stopping transfer. Paramiko API checked
against installed signature and https://docs.paramiko.org/en/stable/api/client.html.
73 combined tests pass: recorded phase failures/cleanup and real offline Paramiko
unknown-host rejection, no hosts mutation. Initial offline fixture lacked logger
transport; fixed the fixture only. Cleanup mutation fails, restored/cmp; Ruff
clean. No real SSH connection/server, credentials, service or DB changes.
Not an activated source transport or end-to-end network proof.

### R04j single-attempt capture reconciliation — 2026-09-20

Contract: inspect before source iteration; content_present skips input but is
not a durability/import acknowledgement; conflict preserves file without reading
source; missing publishes through existing verified no-clobber primitive.
All exceptions propagate, including source FileExistsError, races and post-link
sync errors. A later caller-driven attempt re-inspects. No loop, scheduler,
connection creation, source deletion or service activation. Caller owns bounded
source, timeouts and cleanup. Verify interrupted transfer, racing publication,
ambiguous sync failure and retry with no source consumption.
Verified 55 combined filesystem cases pass. Removing match/conflict short-circuits
fails two tests with Source must not be consumed; restored/cmp. Real filesystem
proof preserves inode/bytes on repeat and leaves one winning file after a race.
Ruff and whitespace clean; external review/CI required. This composes publication
and reconciliation, not the SSH connection owner or automatic retry scheduler.


### R04i read-only spool reconciliation — 2026-09-20

Review 4056550742: wrong-size entries now skip reads but still pass descriptor/
name stability checks before conflict. All 49 filesystem tests pass. Restoring
the early return fails replacement-after-open regression; restored/cmp. Ruff
clean. Review 4056550740 case-count spacing corrected. Fresh CI required.

Contract: inspect a caller-retained immutable private spool entry against required
size and SHA-256, returning missing/match/conflict. Missing is only final-entry
ENOENT; directory/access/I/O failures propagate. Never delete/replace files or
write DB markers. Open no-follow/nonblocking, require owned regular0600 file,
bound reads and compare descriptor/name identity before certifying content.
Match does not certify durability after failed fsync or import completion.
This is a primitive, not automatic retry policy, full source identity or transport
activation. Verify actual post-link-fsync failure, conflicts and replacement race.
Verified 48 combined filesystem cases pass: actual directory-fsync failure still
permits content inspection, wrong same-size bytes conflict, symlink/FIFO/unsafe
entries rejected and I/O errors propagate. Removing digest and identity guards
fails 2 cases, restored/cmp. Ruff/whitespace clean. This does not yet implement
retry scheduling or make ambiguous durability safe for source deletion.

### R04h bounded stream capture — 2026-09-20

Review4056389676/4056392696: start the read deadline inside the generator,
after spool setup.54 combined tests pass; advancing the clock during real file
opens preserves the full read budget. Old placement fails Capture deadline
exceeded, restored/cmp. Ruff clean; no service/DB changes. Fresh CI required.

Contract: caller-owned synchronous reader honours bounded read and settimeout;
capture sets per-read timeout capped by remaining monotonic deadline, verifies
size and required source SHA-256, requires EOF, then publishes via R04f/g.
No connection/authentication, executor, scheduling or source close ownership.
Deadline covers stream consumption, not filesystem durability or SSH handshake;
blocking readers which ignore timeouts cannot be forcibly cancelled here.
Verified53 combined capture/spool/integrity cases pass. Real local sockets prove
success and stalled-EOF cleanup. Disabling post-read deadline fails DID NOT RAISE;
restored/cmp. Ruff clean. No remote SSH, database or service changes. Next integrate
connection lifecycle and explicit source identity/reconciliation before activation.

### R04i read-only spool reconciliation — 2026-09-20

Review 4056550742: wrong-size entries now skip reads but still pass descriptor/
name stability checks before conflict. All 49 filesystem tests pass. Restoring
the early return fails replacement-after-open regression; restored/cmp. Ruff
clean. Review 4056550740 case-count spacing corrected. Fresh CI required.

Contract: inspect a caller-retained immutable private spool entry against required
size and SHA-256, returning missing/match/conflict. Missing is only final-entry
ENOENT; directory/access/I/O failures propagate. Never delete/replace files or
write DB markers. Open no-follow/nonblocking, require owned regular0600 file,
bound reads and compare descriptor/name identity before certifying content.
Match does not certify durability after failed fsync or import completion.
This is a primitive, not automatic retry policy, full source identity or transport
activation. Verify actual post-link-fsync failure, conflicts and replacement race.
Verified 48 combined filesystem cases pass: actual directory-fsync failure still
permits content inspection, wrong same-size bytes conflict, symlink/FIFO/unsafe
entries rejected and I/O errors propagate. Removing digest and identity guards
fails 2 cases, restored/cmp. Ruff/whitespace clean. This does not yet implement
retry scheduling or make ambiguous durability safe for source deletion.

### R04g capture integrity contract — 2026-09-20

Stacked on #1061: add an optional expected SHA-256 to completed-file publication.
Validate canonical lowercase 64-hex metadata before consuming the stream; hash
incrementally and reject mismatch before fsync/link, cleaning only our temporary
file. Existing destinations remain untouched. Omission preserves the size-only
API, not integrity assurance. The future transport must supply a trusted digest
of its immutable source snapshot; hashing received bytes alone proves nothing
about source identity. No SSH/service/DB activation. All 35 filesystem cases pass,
including independent sha256sum against the abc known-answer vector. Disabling
the digest mismatch guard caused DID NOT RAISE on equal-length corruption;
restored with apply_patch and cmp. Changed Python files pass Ruff. #1061 has all
reported CI checks green at 28009e87; individual merge permission still required.
Next: bounded transport, trusted source metadata and explicit retry reconciliation.


### R04f immutable spool publication — 2026-09-20

Review4056287646: aligned map alphabet with existing transport (dots/pluses),
retaining explicit rejection of '..'.24 filesystem tests pass; old regex
mutation fails both supported-name cases, restored/cmp. No service/DB changes.
Owner requested non-draft review workflow: runtime #1052–#1057/#1059–#1061
marked ready; research NEVER MERGE drafts untouched. Explicit Copilot request
on #1061 returned quota-limit message, not a substantive review. Do not count
COMMENTED status alone as review completion. Continue Codex/CodeRabbit triage.

Independent main-based primitive publishes only completed stats streams into an
existing private0700 owner directory. Strict basename allowlist; positive bounded
expected size; temporary0600 .part file; file fsync then same-directory atomic
no-clobber hard link and directory fsync. Existing files/symlinks never replaced.
Transfer/type/size failures clean temporary file; post-link sync failure can leave
complete final file visible and must be reconciled, not overwritten. No startup,
SSH calls, retention cleanup or importer wiring. Caller must bound source chunks
and timeouts and guarantee immutable remote snapshot: length is not integrity.
Runtime filesystem proof and size-guard mutation included; next integrate with
bounded capture and explicit retry/reconciliation, preserving original plan.
New-site/design/functionality/security audit remains after runtime completion,
then owner-approved reversible dev transition; production unchanged.

### R03d independent cache-consumer process — 2026-09-19

Review follow-up: #1055 reports shutting_down before an active worker drains;
the worker's confirmed generation/error fields are preserved. Unit observation
asserts the report precedes cleanup; actual PG blocked-process signal output
includes shutting_down then stopped. Missing-report mutation failed, restored
apply_patch/cmp; expanded200 passed, zero skips, two existing warnings. Example
now explicitly requires overriding POSTGRES_HOST=localhost. PG stopped; no live
activation. Both review findings addressed; fresh exact-head checks required.

Branch feat/db-runtime-cache-entry-r03d, stacked on #1054 at78be6156.
Module entrypoint `python -m shared.runtime_cache_main` has no Discord/BotConfig
or website dependency. This hosts only the cache consumer, NOT source ingestion.
Original design21 direction retained; R04 still must extract source capture,
cadence and non-Discord metadata delivery. No deployment or service changes.

Default OFF exits before config, signal handlers or pool. Enabled requires all
three consumer flags, exact BOT_ENVIRONMENT=dev, explicit POSTGRES_HOST/PORT/
DATABASE/USER and TCP password. Host is loopback IP or absolute Unix socket;
no DNS/remote fallback, dotenv loading or guessed database credentials. Optional
RUNTIME_CACHE_DB_SCHEMA defaults public, one validated identifier. This guards
configuration, NOT database identity: reviewed dev credentials/target remain an
owner activation requirement. Do not run it against the application DB yet.

One empty native pool (max1) reconnects through the existing worker; connect5s,
query/attempt10s, stop drains11s before cancellation, pool close5s then terminate.
SIGTERM/SIGINT clean owned tasks/pool; unexpected errors exit1 with class only.
JSON health every5s describes this consumer only, including last success age,
unsupported count and last confirmed generation. Missing schema/grants are
unavailable, not idle; the process never creates/migrates schema. Health is not
proof of ingestion continuity, cache freshness or system-wide availability.

26 entrypoint unit cases; disposable PG subprocess proofs cover catch-up and
SIGTERM idle / SIGINT while blocked on a table lock, receipts counted by SQL
COUNT and fetched rows, no remaining process connections. Dev-guard mutation
failed both rejection cases (DID NOT RAISE ValueError), restored apply_patch/cmp.
Expanded200 passed, zero skips, two existing websockets warnings; Ruff clean.
Disposable PG stopped after proof; publication/review still pending. Parent #1054
exact78be6156 has nine successful checks, Codex/CodeRabbit completed no findings.
First push rejected by credential hook on a dummy unit-test password literal;
replaced with a generated ephemeral fixture value, without hook bypass.
Next: finish review/publication; then R04 extraction contract, not activation.


### R03c caller-owned durable cache polling — 2026-09-18

2026-09-19 original-plan/Mandelbrot/RCA audit: design21 section7 direction
preserved (shared domain, separate processes, PostgreSQL, cache first). Its
section7a claim that readers are already independent is historical overstatement:
source retention enables replay, but endstats/proximity still await Discord
readiness and STATS_READY still enters through Discord. R04 must remove those
writer/transport dependencies. Endstats voice/dead-hour cadence is not the same
gate as proximity. Shared config is a bot-config reexport whose validate requires
a Discord token: neutral entrypoint validation is an explicit extraction gate.
Initial-import events are not final round completion; count by event semantics,
not all journal rows. Coarse HTTP generation and periodic polling are deliberate
first steps; per-session invalidation/NOTIFY latency optimization remain later.
Added three worker edge proofs: acquisition cancellation cleanup, nonclosed
InterfaceError propagates, unsupported events visible while valid work succeeds.
17 worker unit cases pass; expanded combined rerun172 passed, zero skips, two
existing warnings. Owner-approved #1049 merged90eae0f8 with full tree equal to
964630e8, after fresh112 repair/inbox/override/coverage/bootstrap cases passed.
Normal sync through #1050/#1051/#1052/#1053/R03c changed only seven PLAN lines.
No activation. Local full audit kept outside tracked research.

Local branch feat/db-runtime-cache-poll-r03c, parent #1053 at 1e36a993.
Reusable shared driver only: caller awaits run and owns cancellation/connection
factory. No service/startup wiring or process activation. Three opt-in flags,
including new RUNTIME_HTTP_CACHE_WORKER_ENABLED, default OFF with no acquisition.
Initial/periodic receipt-based scan, bounded batches and connection release per
batch; yield under full backlog, interruptible idle/error waits, attempt timeout.
Explicit state separates last confirmed generation/success from current failure;
unsupported events remain counted. No NOTIFY dependency or MAX-ID cursor.
Known DB/I/O/timeout failures retry; programming failures propagate visibly.
Closed native connections are retried only when InterfaceError and is_closed
agree; other interface errors remain failures. Restart relies on DB receipts.

Independent review found the closed-connection case; fixed with real PG proof.
17 new lifecycle/PG cases passed; expanded cache/HTTP/bootstrap/release suite
169 passed, zero skips, two existing warnings; Ruff clean. Real PG proves late
lower-ID catch-up without notifications, restart idempotency, receipt-error
rollback/recovery and closed-connection replacement. Unit timeout releases
connection before retry, cancellation drains, idle stop interrupts long wait.
Removing periodic timeout caused observed TimeoutError; restored apply_patch/cmp.
PG stopped and confirmed by pg_ctl/log. No live DB, dev service or prod changes.

Publication originally waited for stack reduction (28files against hook limit25).
After approved #1049 merge the measured diff is23files; no hook bypass required.
#1050 is retargeted main with fresh CI required and no merge approval inferred.
Next: publish R03c/external review, then independent
runtime entrypoint/ownership plus activation gates. R04 ingestion extraction
is not completed by this driver; Discord/website-off ingestion is still future.

### R03b2 committed-generation HTTP namespace — 2026-09-18

Owner scope clarification: all runtime work targets dev only. Production stays
untouched on its existing release; deployment/restarts are separate approvals.
Branch feat/db-runtime-http-generation-r03b2, parent #1052 at 30a1cd7f.
Default OFF behind EVENT_STREAM_ENABLED, RUNTIME_HTTP_CACHE_EVENTS_ENABLED and
new RUNTIME_HTTP_CACHE_NAMESPACE_ENABLED. Cacheable anonymous GETs verify the
committed DB generation through the current shared adapter with a one-second
read timeout. Missing/invalid/unavailable generation bypasses cache get/set and
returns no-store plus BYPASS-GENERATION. Cancellation propagates. Namespace
combines generation and existing backend namespace, captured for the request.
No consumer loop, no live flag changes, no deployment. The dev-only restriction
is operational scope, not an environment-name guard in the helper.

92 focused unit/actual-PG/HTTP cases passed, zero skips, two existing warnings.
Real PG rollback/uncommitted generation stays invisible; receipt failure rolls
generation back; committed consumer effect invalidates two HTTP worker caches.
Missing schema bypasses a warm cache. Redis startup fallback, old in-flight
response, absent flags, bad values, cancellation and timeout are covered.
Pinning namespace to generation0 failed both worker and actual-PG tests with
HIT != MISS; restored apply_patch/cmp, full 92-case rerun passed. Ruff clean.
Disposable PG stopped. Review initially requested the PG proof, now included.

Limitations before activation: consumer lag still serves the prior namespace;
R03c must schedule durable catch-up. HTTP/browser TTL and independent inner
caches are unchanged. Benchmark cold/hot lookup cost and load, check website
role grants, and define cache purge on administrative generation reset/restore.
New middleware log omits DB error text; existing adapter logging is unchanged.
Next: publish/review R03b2, then lifecycle/polling and explicit health semantics.
Published draft #1053. Final independent review found no blocker after adding
the PG proof. Post-push review clarified the reader docstring: it never creates
schema or writes rows, but the shared adapter owns connection-pool behavior.
External review found missing website_app SELECT privileges. Added migration092
(091 unchanged), conditional SELECT-only grant, bootstrap mirror and release
registration. Actual restricted-role reader succeeds after migration, cannot
UPDATE generation or read receipts; role creation/grants rolled back in isolated
PG. Role-absent/idempotent paths covered. Removing GRANT failed with permission
denied, restored/cmp. Expanded 152-case suite passed, no skips, two existing
warnings; Ruff clean, PG stopped. No live role or migration changes.

### R03b1 bounded memory cache prerequisite — 2026-09-18

Branch feat/db-runtime-cache-memory-r03b1, parent #1051 at 112f2524.
Before adding DB-generation namespaces, bound abandoned namespaces and late
old-request writes. Memory backend now defaults to 256 retained entries and
8 MiB of retained key/JSON string objects per worker; FIFO eviction on writes,
expired-entry sweep on writes, and uncacheable replacements remove old values.
These are conservative storage budgets, not measured optimal capacity or RSS
limits; dictionary/tuple overhead and transient serialization are not included.
No runtime-generation namespace integration yet, no activation or deployment.

48 focused cache/middleware tests passed, including in-process HTTP MISS/HIT/
eviction/recomputation, concurrent writes, Unicode byte budget, abandoned epochs,
late writes and replacement at capacity. Removing eviction failed `assert 4 <= 3`;
restored with apply_patch and verified cmp. Independent review found no blocker;
its concurrent mutation-time run also observed byte/count failures (not a failure
of restored code). Ruff clean. Next: publish for review, then generation reads
with fail-closed cache bypass and multi-worker/in-flight proofs in R03b2.

### R03a transactional HTTP-cache generation receipts — 2026-09-18

2026-09-19 checkpoint: owner-approved #1050 merged as 2518735f after all22
checks, resolved reviews and fresh79 isolated-PG/retry/bootstrap/release cases.
Prescribed cycle ended with zero red checks/threads/behind and unchanged head;
squash tree equals approved00e061ec. #1051 retargeted main; normal merge77f8ed47
resolved squash-history conflicts and preserved its entire pre-sync44914a22 tree.
Descendant sync follows; fresh exact-head CI required. #1051+ not merge-approved.
No deployment, service operation or live database change. Temporary PG stopped.

Branch feat/db-runtime-cache-receipts-r03a, parent #1050 at 0f0c8e73.
Migration 091 adds consumer/event receipts and shared DB cache generation.
Explicit default-OFF primitive serializes on the generation row, consumes bounded
known event/schema batches without a MAX-ID cursor, and commits generation plus
receipts atomically. Caller-held transactions are rejected. Unsupported pairs
remain unacknowledged and explicitly counted; they cannot occupy the valid batch.
No HTTP namespace integration, listener, background task, activation or deploy.
Receipt means DB generation advanced, not every worker/browser cache invalidated.
Batch bound limits processed events, not SQL scan cost; benchmark before rollout.
Website role permissions and independent inner caches remain integration gates.

Read-only review found no concrete blocker. Real PG proofs include concurrent
consumers, late lower-ID commit, rollback at receipt/generation/COMMIT failure,
idempotent empty retry, source consumer isolation, unknown schema visibility,
bounded remainder and OFF behavior. Transaction mutation failed 1 != 0; removing
the early row lock failed the observed pg_stat_activity lock-location assertion.
Both restored via apply_patch/cmp. Initial focused run 62 passed, no skips;
extra observed-lock regression passed. Full cross-stack regression: 280 passed,
zero skips, two existing warnings; Ruff/whitespace clean. Disposable PG stopped,
verified by pg_ctl and shutdown log. Next: external review and exact-head CI.
Published draft #1051. #1046 merged as 64488de1 with approved tree verified;
#1048 now ready/main, and ancestry sync through #1049/#1050/#1051 preserved
all implementation content. Fresh CI required after these pushes. No activation.
Review follow-up: corrected BACKLOG's stale #1046 status to merged 64488de1
and labelled older checkpoints historical. Owner explicitly approved #1048;
its prescribed merge cycle is running. Further PRs still require specific approval.

### Accepted delivery sequence — 2026-09-20

Owner explicitly includes the new website/design in the final dev transition.
First prove independent runtime capture/import/recovery; then audit new-site
implementation against original design, functional journeys/data parity, auth
and permissions/API security, mobile/accessibility/performance and absent/error
states. Fix findings, integrate runtime+site, then owner-approved reversible dev
cutover. Production remains frozen. Build/test success is not a website audit.

### R04e dependency-aware import step — 2026-09-20

Review4056385615 RCA: payload hash omits the header, so unchanged cumulative
R2 equals R1. Scope canonical duplicate queries to the same filename round suffix
in BOTH the neutral preflight and process_file; waiting bypass additionally
requires a valid R2 source. Preserve legacy unscoped lookup for callers omitting
filename. Actual PG zero-delta case: R1 retired => waiting/no R2 marker; restored
=> R0=3/R1=3/R2=0 and two half events. Removing SQL half filter reproduces
Skipped duplicate payload file and missing R2; restored/cmp. Same-half identity
across different matches remains legacy payload-based behavior, not a complete
source-identity guarantee. No historical data repair or application DB changes.
66 combined unit/actual-PG tests pass; two waiting-gate mutations fail as well,
restored/cmp. Changed small modules Ruff clean; manager diagnostics identical
to parent20-code/message multiset. Disposable PG stopped; fresh CI required.

Review4056323000: validate actual calendar/time before dependency waiting,
not only regex shape.23 unit/PG cases pass, including impossible timestamp
through canonical failure, leap-day and midnight boundaries. Skipping calendar
validation fails7 cases; restored/cmp. Ruff clean; disposable PG stopped.

Review4056294780/4056294781: preserve canonical renamed-payload deduplication
when R1 is gone, via a public read-only manager preflight; malformed R2 names
use canonical import/failure instead of waiting.14 unit/actual-PG cases pass:
mirror gets a success marker without new rounds/events, malformed fixture gets
a failed marker. Both guard mutations fail, restored/cmp. New modules lint
clean; manager retains exactly its previous20 code/message diagnostics. Isolated
PG stopped after proof; no application DB/service changes. Fresh CI required.

Review4056275060/4056275062 fixed: completed R2 remains imported after R1
retention, and bare paths normalize before both lookups.12 unit/actual-PG cases
pass; actual deferred scenario uses relative paths and then retires R1 before
retry. Both removed guards fail their tests, restored/cmp. PG stopped. Lookup
failure is not waiting/absence: processed-state errors propagate to caller.

Verified:69 combined cases pass,0skips,2existingwarnings. Actual-PG deferred-R1
scenario has zero rounds/markers/events before R1 arrives, then R1=3/R2=5/R0=8
and exactly2half-events with duplicate retry unchanged. Disabling dependency
guard imports an orphan and fails waiting-state assertion; restored/cmp.
Changed Python files lint clean; disposable PG stopped. Pending review/CI.

Caller-driven step reuses canonical parser R1 lookup and process_file; missing
R1 returns explicit waiting_for_r1 after a read-only processed-state check,
without marker writes. Already-processed R2 remains successful if R1 was pruned.
Bare relative paths normalize to absolute for both lookup and import. No scheduler,
connection ownership change, automatic orphan repair or activation. Caller must
provide immutable completed spool and retain R1 during parsing; dependency check
does not solve concurrent file deletion/replacement or bound filesystem scans.
Capture publication/retention and bounded-scan behavior remain separate gates
before live use.

### Local #1059 main refresh — 2026-09-25

Prepared fix/db-runtime-startup-main-refresh from921af249 plus main89a2fd38.
Preserved both documentation tracks; sole importer conflict was constructor
docstring. Production parser/importer/startup files remain byte-identical to
921af249. Fresh checkout exposed test ambient SSH_ENABLED dependence; legacy
logging fixture now explicitly disables SSH/automation and tests inherited
true/false.26 startup/parser/pool/logging tests pass; removing isolation fails
the existing SSH dev guard, restored/cmp. Eager Discord mutation also fails,
restored/cmp. Targeted lint clean; manager's20 existing Ruff diagnostics unchanged.
Remote #1059 remains open on old base with merge conflict; old SHA has9successful
check runs and0review threads. This LOCAL refresh is not published, remotely
reviewed or merge-approved. main is ancestor after this merge; diff10files.
Earlier progress/approval notes below are historical. Integrated runtime work
continues separately; SQL batch/lock gates still await owner-started test PG.

### R04d neutral importer startup — 2026-09-20

R1/R2 characterization: ordered imports and R2-first with both files retained
produce R1=3,R2=5,R0=8 kills; journal contains only rounds1/2. If R1 file arrives
after R2 was imported, R2 stays orphan_r2 with raw8 kills and successful marker;
ordinary retry returns Already processed even after R1 arrives. Confirmed with
real isolated PG and observer rows, not a proposed policy. This is an activation
gap: next capture layer must defer R2 until dependency is available or implement
an explicitly designed repair; do not silently change parser semantics here.
63 combined cases pass0skips2existingwarnings. Removing orphan flag fails status
assertion; restored/cmp. Temporary PG stopped. Test quoting collection error
was corrected before evidence runs. No production code changes in follow-up.

Actual-PG follow-up: fresh subprocess with Discord/config/logging imports blocked
ran canonical parser and process_file, with no mocked persistence methods.
Private disposable PG schema bootstrapped explicitly by test only; observer
connection confirmed one R1 round/player (3 kills), event and successful marker.
COUNT and fetched rows agree; repeated file adds no player/event, borrowed pool
remains usable. Synthetic single-player fixture, NOT R2/capture/cutover proof.
Initial assertion expected32-char GUID; canonical parser short_guid proved8,
so corrected test, not code. Disabling event emission caused actual-PG assertion
failure; restored/cmp, combined60 cases pass0skips2existingwarnings. Test PG
stopped, shutdown log/status agree; random schemas removed. No live DB changes.

Follow-up preflight lifecycle proof: three fresh subprocesses invoke real
process_file with a caller-owned protocol-test pool: duplicate, query outage,
and cancellation. They assert lease release, retained pool identity, retryable
outage and propagated cancellation, with setup/presentation imports forbidden.
36 focused cases pass. Adding disconnect to the duplicate branch fails the
success contract (borrowed pool close raises); restored/cmp. This is NOT a real
PostgreSQL commit proof and does not cover the full successful write path yet.

Branch feat/db-runtime-import-startup-r04d builds on #1057 at908d238e and
cherry-picks #1056 parser-only slice65f5cbac as aaee6c52 (not its cache stack).
Parser/test contents unchanged; progress notes from both sides preserved.
Manager import no longer mutates sys.path, loads dotenv or configures logging.
Explicit configuration uses neutral emitters; default constructor's load_config
seam delegates to lazy legacy startup, dotenv before log-path selection and
logging setup once under a lock. Configuration reloads on each default call.
Import/logging failures now propagate rather than selecting a silent no-op
logging fallback. This intentionally changes import-only side effects; callers
needing legacy setup must construct with defaults, not merely import the module.

78 selected regression cases pass, no skips, two existing websockets warnings.
Fresh subprocess proves neutral parsing/validation, no config/Discord imports,
environment/path/cwd/root-handler changes, log files or connections. Another
process verifies legacy dotenv-before-file-logging and stable repeat handlers.
Forbidden bot.config import mutation failed, restored/cmp. Initial legacy proof
failed missing BOT_ENVIRONMENT; fixed test setup with explicit dev, not the guard.
No services/DB touched. This is construction/startup, NOT full independent ingest.
Next: reviews and canonical process_file proof with owned/injected pool, followed
by capture cadence, source retention, single-writer cutover and failure matrix.

### Side quest: preserve and consolidate open PRs — 2026-09-20

Execution update: owner explicitly approved #1076/#1057/#962. First two merged
via cycle.sh as1a78b713 and249f7b8e; #962 now integrates both and waits fresh gates.
Older proposals preserved/refreshed: #965c8fa8e41, #969884b1baf, #966a05bbf39,
#97994cf8e3d (three provenance gaps fixed), #9631a743945 (historical corrections),
#964be53dbf4 (ledger reconciliation), #1027f0d263c2 (normal branch update).
Each still needs exact-head checks/review/current-main readiness and its own
merge permission. No NEVER MERGE changes, no release/deploy activation.

Owner requested consolidation, including older fixes, without losing the original
plan. Pause new runtime slices while preparing existing PRs. No per-PR merge
permission was granted by this request. NEVER MERGE #924–#943 and #967 remain
untouched; release #956 stays a separate decision. At audit: 56 open PRs, confirmed
by REST and GraphQL: 21 review snapshots, 26 runtime slices, 9 older proposals.

Older work preservation/order:
- #962 disk measurement then #965 notification acknowledgement: both mechanisms
  are still absent from main; keep both, refresh/test separately and together.
- #969 Node pin then #1027 lockfile update then #979 artifact preflight: preserve
  each purpose; current main still has old Node pin/mocker/build command. Refresh
  and verify narrow diffs. #979 has three outstanding substantive review findings.
- #966 immutable review tooling: refresh/test without touching review snapshot refs.
- #964 execution ledger and #963 historical handoff: reconcile together, retain
  unique lessons, correct stale operational instructions, distinguish historical
  measurements from current facts. Do not discard merely because they conflict.
- #956 release: hold, never equate merge permission with deploy permission.

Runtime dependency order remains #1076; #1057→#1059→#1060;
#1061→#1062→#1064→#1065→#1066 (also needs #1060);
#1063→#1067→#1068→#1069→#1070→#1071→#1072 (also needs #1062/#1064);
#1073→#1074→#1075, and #1077 after #1076/#1072. Backport #1077 worker fixes
before merging #1068. Cache lane #1051→#1052→#1053→#1054→#1055→#1056 needs
main conflict resolution and investigation of #1056 Docker failure. Each PR gets
current-main integration, exact-head checks, substantive review-thread handling,
functional/runtime/mutation proofs and explicit owner permission before cycle.sh.
No child PR merges into another feature branch; retarget to main after prerequisites.

Started #962: normal merge of current main retained the original two-file fix.
Found zero-capacity fixture returned false healthy zero usage; now None/unknown,
while positive used space with no available space remains measured 100%/fail.
31 targeted tests pass; guard mutation raises TypeError, restored/cmp. Actual
read-only collect_disk and df byte ratio agree twice at96.9%, df displays97%.
This is current host measurement, not deployed watchdog proof. Disk pressure
blocks heavy build/install work pending safe capacity planning; no deletion.
Next finish refreshed #962 CI/review, then #965 integration and older lanes above.

Resume point: runtime #1077 c015270b completed worker review fixes; trusted
completion delivery and immutable snapshot sealing remain next development.
Then full new-site design/functionality/security audit, then owner-approved
reversible DEV cutover. Production v1.39.0 remains frozen. No service activation.

2026-09-20 checkpoint: owner-approved #1058 merged as b5e20c9d after prescribed
cycle (0 red/threads/behind, unchanged SHA). Squash tree equals da1a5136.
Fresh14 logging/retry cases passed before merge. R04b synced main normally;
both progress sections retained in documentation conflicts, no constructor
changes. Older approval/CI notes below are historical. #1057 not approved.
Next startup contract: /tmp/slomix-r04d-startup-contract-2026-09-20.md (local).

### R04a parser presentation boundary — 2026-09-19

Branch feat/db-runtime-parser-boundary-r04a, parent #1055 at5b0d305f.
Move Discord import into create_stylish_round_embed only; parsing and R2 logic
unchanged. Separate subprocesses compare full parser/differential output with
Discord preloaded versus forbidden (also forbid bot.config/dotenv/website).
Clock frozen in proof to avoid comparing two generation timestamps. Existing
committed sample files produce zero parsed players; explicitly recorded, not
treated as player coverage. Valid synthetic player lines separately prove one
player and differential kills8-3=5; real Discord Embed rendering remains covered.

151 parser/helper/R2/import-journal/retry/replay cases passed, zero skips, two
existing warnings. Ruff clean. Restoring eager import as a mutation caused
ModuleNotFoundError: Presentation/config dependency forbidden: discord; restored
apply_patch/cmp, then full151 passed. No network, database or service activation.

Discovery correction: manager load_config constructs BotConfig but does NOT
call its token validator. Importing bot.config still loads dotenv, and the
manager initializes logging at module import. Neutral config extraction must
preserve explicit legacy logging/config behavior; deferred to its own slice.
This prerequisite does not make the canonical importer or ingestion independent.
Original R04 capture/cadence/metadata/single-writer acceptance gates remain open.

### R03d independent cache-consumer process — 2026-09-19


### R04b explicit importer constructor configuration — 2026-09-19

Independent branch feat/db-runtime-import-config-r04b based on main2518735f;
does not depend on R03 cache consumers or R04a parser import changes. Add a
keyword-only config argument to the canonical PostgreSQLDatabaseManager. Only
None invokes the existing loader; explicit configuration retains object identity,
including falsey objects, and the PostgreSQL-only check remains. Existing callers
and load/config/logging order are unchanged. No pool/connect/migrate on creation.

Seven boundary cases and expanded154 parser/journal/retry/replay cases passed,
zero skips, two existing warnings. Actual subprocess supplies configuration while
ambient loader and pool creation are forbidden, then exercises canonical player
validation. Mutation config-or-loader rejected a falsey supplied config and
failed; restored apply_patch/cmp, expanded154 rerun passed. New tests lint clean;
manager's20 pre-existing Ruff diagnostics match baseline by code/message.
Unit harness probes the stopped disposable PG socket (FileNotFoundError); no
live-DB fallback, no PG restarted for this slice and no DB-ingestion claim.

Limits: bot.config module still loads dotenv; manager still initializes logging
at import, parser still imports Discord on this independent main-based branch
(separately addressed by #1056). This isolates construction, not all module side
effects. Next separate explicit startup/logging ownership while preserving legacy
behavior; then R04 source/cadence/metadata/single-writer acceptance proofs. No
activation, service operation, production changes or new merge permission.

### R04u exclusive source-generation reservation — 2026-09-20

Independent main-based primitive, not a reset of the runtime plan. Existing
capture/producer/manifest chain remains in #1059–#1075; latest #1075 checks green
at966f829d. Its branch touches24paths vs main, so this independently testable
reservation slice avoids exceeding25path hook without bypass or premature merge.
reserve_source_generation creates a caller-chosen32lowerhex directory with atomic
mkdir beneath an existing private0700owner root; child then parent fsync before
success. Any existing entry refuses reuse, including empty directories/symlinks.
Post-mkdir failure preserves reservation; no cleanup or automatic new token.
Caller retains stable root, hands reservation to one producer and prevents later
rewrites. This is namespace reservation, not a lease, snapshot completion or
producer wiring. Returned Path is not a capability; no source/DB/service action.
16 focused actual-filesystem tests pass0skips: sync order/mode, two concurrent
attempts have one winner, all existing types preserved, failed sync blocks reuse.
Swallowing FileExistsError fails two existing-directory proofs DID NOT RAISE;
restored/cmp, Ruff clean. No broader capture tests claimed on this independent
branch. Next explicit producer handoff and trusted completion delivery, keeping
reservation/data/receipt identities aligned. Runtime first, then new-site full
audit, then owner-approved reversible dev transition; production unchanged.

### R04c neutral database logging helpers — 2026-09-19

239775fc received all22successful checks, Codex no-major-issues review and
CodeRabbit no actionable findings. Addressed its remaining docstring-coverage
warning by documenting all four test functions; no production code changes.
Fresh checks required after this documentation-only follow-up. Await #1058
individual merge permission; do not infer permission from continuation requests.

Review follow-up: #1058 initial CI failed I001 in the modified legacy module;
the initial local lint scope covered only new files and missed it. Explicit
module-attribute aliases now preserve exports without the CodeQL unused-import
finding4053798928. All three changed Python files lint clean; 25 regressions
pass again. Wrong-export mutation failed identity guard, restored/cmp verified.
Fresh exact-head CI and external review are still required; no merge approval.

Independent main-based slice extracts unchanged database/import/performance
record emitters into shared.database_logging; legacy bot imports re-export
the same functions. No logging setup, directory creation or bot dependencies
in the new module. Legacy setup and dotenv ordering remain unchanged.
25 focused regression cases pass (two existing websockets warnings). An actual
subprocess emits three records with bot/Discord/dotenv/website imports blocked;
no root-handler/environment changes or log directory creation. Adding an eager
bot import at module end fails with `Forbidden dependency: bot`; restored/cmp.
The first mutation at module start failed collection on circular import instead,
so it was replaced by the executable guard mutation above. New files lint clean.
This is a foundation, NOT independent ingestion: manager startup, transport,
single-writer handoff and failure-matrix proofs still need separate slices.
#1050 is merged; #1051–#1057 remain unmerged and need individual permission.
Next: review/CI, then compose neutral manager startup without changing legacy
dotenv/log-directory ordering. No deployment, service or live DB changes.

### R02d5 durable bounded Lua repair attempts — 2026-09-18

2026-09-19 checkpoint: owner-approved #1049 merged90eae0f8 through prescribed
cycle, all22checks successful and final0red/0threads/0behind/unchangedSHA.
Squash tree matches964630e8. Fresh112 actual-PG/repair/inbox/override/coverage/
bootstrap cases passed before merge. #1050 retargeted main; normal ancestry sync
preserved the full tree. Fresh checks required; no approval for #1050 inferred.
No service/deployment changes. Older progress notes below are historical.

Historical R02d5 checkpoint (current position is in R03a above):
#1044 and #1045 merged through prescribed cycles with
review dispositions and verified squash trees. #1046 is ready/main at a58277f9;
fresh CI pending. #1050 external Codex found no major issues at 51505e84 and
all nine branch checks passed there. Subsequent ancestry sync changed no code.
CodeRabbit's two findings were fixed in 46e9be8e (readable counts and evaluated
release-array guard), replied to with mutation evidence and resolved. Fresh CI
is required for the new head. No local merge monitor remains running; test PG
is stopped and helpers completed. Next: inspect checks/reviews, then #1046 cycle.

Separate branch feat/db-runtime-lua-retry-state-r02d5, parent #1049 e8011a81.
Migration090 keeps scheduling state separate from retained payload/receipts.
Explicit gated seeding (100 unseen inputs, no MAX-ID cursor) and one due attempt
per call. Attempt-row SKIP LOCKED precedes identity/input/round locks; nested
savepoint rolls correction back before persisting classified retry outcomes.
Five semantic attempts maximum, durable exponential delay, terminal quarantine;
lock contention defers without consuming budget. Unexpected errors are durably
deferred then re-raised, not silently swallowed or allowed to starve later input.
Global/correction/repair flags required, default OFF. No loop, lease, deployment,
or source transport guarantee. Caller must not hold an outer transaction; lock
timeout bounds repair lock waits only, not total call execution.
47 focused actual-PG/bootstrap/coverage cases passed, zero skips, two existing
warnings. Outer-transaction mutation failed600!=1800, restored by patch/cmp.
Read-only review found starvation gap, now fixed and regression-tested; second
review found no remaining concrete blocker. Combined regression 256 passed,
zero skips, two existing warnings. Ruff/whitespace clean; disposable PG stopped,
confirmed by pg_ctl and shutdown log. Next: draft PR/external review/exact-head CI.
Published draft #1050 with independent review findings fixed and external review
requested. #1044 merged21eb638a, verified identical approved tree; normal sync
through #1045/#1046/#1048/#1049/#1050 changed only documentation. #1045 now
ready/main with fresh CI pending. No service or live-data changes.
Follow-up: 21 retry-specific cases now pass, including explicit ambiguous/revision
quarantine and 107-input discovery in 100+7 batches. Code unchanged; temporary PG
stopped after the expanded proof. CI/external review still pending.
External review follow-up: fixed result-spacing typos and replaced migration
substring detection with inspection of the evaluated Bash MIGRATIONS array.
Commenting out migration 090 while retaining its filename made the guard fail;
restored with patch/cmp and reran successfully. No runtime implementation change.

### R02d4 atomic retained-input repair — local implementation 2026-09-18

Current checkpoint: #1048 merged with explicit owner approval as 422f056a;
its tree exactly matches approved 9bcac196. #1049 retargeted to main and
normal ancestry merge preserved the entire implementation tree. Fresh exact-head
CI/review required; #1049 still needs its own merge approval. No activation.
The following development checkpoints are historical, not current permissions.

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
#1042 merged as9ffbcd5e after all22 checks and the required pause. Fix pushed
at93096648 after normal stack synchronization. Seven contract cases pass and
runtime-loaded detection/fanout/inventory exclude receipts. Independent review
found no blocker; wording now includes accepted no-op corrections. New CI pending.
Size correction: existing-branch pre-push checks the update from the old remote
tip (three files here), intersected with paths changed vs main; the total stack
is26files. The hook ran unchanged and was not bypassed. #1043 merge cycle active.

### R02d3 intake wiring — started 2026-09-18

2026-09-18 latest checkpoint: #1046 merged as 64488de1 through required cycle,
all 22 checks successful, no open threads/behind commits and unchanged head.
Squash tree equals a58277f9. #1048 retargeted main; normal ancestry sync preserved
the complete content tree. Prior Codex review found no major issues; recheck
fresh main-target CI and threads before the next conditionally authorized merge.
No live deployment or activation.

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

2026-09-18 latest checkpoint: #1045 merged3099633d via required cycle,
no unresolved threads/behind commits, unchanged head; squash tree equalsc4a8303d.
Required checks passed; three Codacy advisory SQL alerts were independently
reviewed as false positives with bound-input runtime proof, not suppressed.
#1046 now ready/main; ancestry synchronization preserved the complete tree.
All five prior findings are addressed/resolved. Fresh main-target CI required
before the next conditional-authorized merge. No live activation or deployment.

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

2026-09-18 current checkpoint: #1044 merged21eb638a through prescribed cycle,
all22checks successful and final gates clear; squash tree identical196d19f7.
#1045 retargeted main; ancestry merge preserved its entire content tree. Prior
Codex review found no major issues; Codacy SQL annotations were examined with
bound-parameter/allowlist runtime proofs, not suppressed. Refresh exact-head CI
and inspect current findings before a conditional-authorized merge. No deploy.

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

2026-09-18 latest checkpoint: #1042 and #1043 merged through prescribed
cycles with all checks green, zero unresolved threads, unchanged heads and no
behind-main commits. #1043 squash d946772b exactly matches2c14ab59. #1044
now targets main; normal ancestry merge preserved the complete content tree.
Prior external review found no major issues and no open threads remain; new
main-target exact-head CI is required before its conditionally authorized merge.
No deployment/activation. A combined downstream regression passed238cases,
zero skips, two existing warnings; temporary PG stopped. Manual repair scripts
still bypass journaling and need explicit constraints before runtime activation.

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

## Astra — SPA artifact provenance before dev mutation (2026-09-07)

Follow-up 2026-09-08: root completed the interrupted helper's parent-symlink
fix. All source/output path components and run website/static parents are
checked before any proof unlink or activation. Nineteen behavioral tests pass
in the isolated agent Python environment. Removing the early output-parent
check caused the static-parent test to fail with FileNotFoundError (the existing
proof was wrongly deleted); restored with apply_patch and cmp. Node version is
recorded as metadata, not enforced against .nvmrc by this slice; use the pinned
toolchain from #969. No real build, deploy or service action performed.

- Implemented locally on `fix/website-artifact-preflight`; no real build,
  deployment, restart or production changes. Parent review and feature PR next.
- `npm run build:app` keeps `prebuild:app` API generation, then wraps the
  existing Vite command with `scripts/spa_artifact.py`. A deployable build
  requires the exact target commit checked out and all tracked changes committed.
  Record includes source SHA, frontend/config/lock/OpenAPI/generated-type input
  hashes, output hashes and Node version. Failed builds invalidate old provenance;
  changed source during a build cannot receive successful provenance.
- **Policy changes:** `SKIP_STATIC=1` is rejected, not an escape from missing
  or stale artifacts. Untracked frontend inputs and ignored source/public inputs
  other than generated API types are refused. Frontend production `.env` files,
  `VITE_*` overrides and non-production `NODE_ENV` are unsupported and fail with
  an actionable error. Commit-before-build applies even to unrelated tracked edits.
- `dev_deploy.sh` pins the requested ref in the source clone (fetch source refs
  explicitly before choosing/building the target), verifies and copies artifacts
  into a unique sibling staging directory, and revalidates staged bytes before
  any run-clone checkout. Initial artifact failure occurs before even fetching
  into the run clone. `DEV_PREFLIGHT_ONLY=1` performs staging/checks only and
  cleans its own temporary directory; it does not change services or run checkout.
- Only proven SPA output is installed. **Legacy `static/modern` is preserved
  with a warning**, not copied on a timestamp claim; legacy provenance remains
  a separate slice. Previous SPA output is retained in a uniquely named sibling
  recovery directory; automatic backup deletion is not part of this change.
- Evidence: 15 behavioral tests passed with disposable Git clones, mock Vite
  and mutation-recording executables. Missing, corrupt, dirty, wrong-target,
  stale, changed generated inputs, untracked input, unsupported env, symlink and
  SKIP_STATIC cases leave the active fixture checkout/assets untouched and call
  no fetch/checkout/service command. Additional cases cover copy corruption,
  failed/during-build source changes and successful disposable activation with
  restarts disabled, previous assets retained and legacy unchanged.
- Mutation: disabling output-hash equality was seen accepting corrupt output
  and failing `assert result.returncode != 0`; restored, `cmp` passed, all 15
  tests passed again. Ruff, shell syntax and whitespace checks passed.
- Limits: this is trusted-local provenance/integrity bookkeeping, not signing,
  hermetic dependency verification or an atomic code-plus-assets release manager.
  Failures after successful preflight/checkout may still require owner recovery;
  no live activation or browser rendering has been proven by these tests.

## Proga: Astra shared Node 22 pin

Zadnja posodobitev: 2026-09-07 (Astra). Implemented; local contract verified.
Pin local development and both CI Node setup jobs to `.nvmrc`, version 22.23.2.
Verified against the official release index and archive (latest 22, Jod LTS),
and the security release announcement:
https://nodejs.org/en/blog/release/v22.23.2
Contract tests parse package engines and workflow YAML, rejecting a pin below
the frontend floor or an inline CI override. No local installation, dependencies,
build, browser, global environment or service changes in this slice.
Proof: three tests and targeted Ruff pass. Mutations to old Node 22.13.1 and
inline CI `22.x` both failed the respective contract; restored files match
pre-mutation snapshots by `cmp`. Independent Node JSON comparison confirms the
pin meets the floor; parsed YAML resolves both jobs to 22.23.2. That is config
proof, not execution under the selected Node: host Node remains v20.20.0.
Next: root review/PR, then isolated portable runtime validation and actual CI.
