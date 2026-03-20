# Tracked Files Audit

Date: 2026-03-17

Purpose: identify tracked files and paths that are legitimate project assets, borderline policy decisions, or likely repo noise.

This is not a deletion plan. It is a classification pass.

## First Untrack-Only Batch Applied

Completed without deleting local files:
- `freshinstall.sh`
- `update_bot.sh`

These were removed from git tracking only and are now ignored locally via [`.gitignore`](/home/samba/share/slomix_discord/.gitignore).

## Second Untrack-Only Batch Applied

Completed without deleting local files:
- `docs/reports/**`
- `docs/instructions/**`
- `docs/research/inbox/**`

Important tradeoff:
- many remaining tracked docs still reference these paths
- after commit, those references will keep working locally but will no longer resolve on GitHub for a fresh clone
- this batch follows the repo-boundary policy of treating reports, prompt corpora, and raw research inbox material as local working context rather than repository contract

## Summary

- Total tracked paths: `861`
- Tracked modern frontend build artifacts: `48`
- Tracked report files under `docs/reports/`: `23`

Main finding:
- the repo is not primarily polluted by secrets anymore
- the bigger problem is boundary ambiguity
- some tracked files are real runtime/deploy dependencies
- some tracked files are historical or operational and need an explicit keep/archive/remove decision

## Keep In Git

These are tracked and should stay tracked because current tooling or runtime depends on them.

### Security and development tooling

- `.secrets.baseline`
  Used by [`.pre-commit-config.yaml`](/home/samba/share/slomix_discord/.pre-commit-config.yaml).
- `requirements-dev.txt`
  Used by CI, Docker build inputs, and local developer setup.
- `package.json`
- `package-lock.json`
  Used by GitHub Actions JavaScript lint workflow and root frontend tooling metadata.

### Deployment and bootstrap

- `slomix_vm_setup.sh`
  Large, but it is a real VM bootstrap and migration script for `/opt/slomix`.

### Current website deploy contract

- `website/static/modern/`
  These are built assets, but they are currently part of the live app contract:
  - [website/backend/main.py](/home/samba/share/slomix_discord/website/backend/main.py) serves and cache-controls them
  - [website/frontend/README.md](/home/samba/share/slomix_discord/website/frontend/README.md) explicitly says `npm run build` writes to this directory
  - [website/js/modern-route-host.js](/home/samba/share/slomix_discord/website/js/modern-route-host.js) loads them at runtime

Conclusion:
- `website/static/modern/` is not random output today
- it is a tracked build artifact with a current production role
- if we want it out of git later, we need to change deploy architecture first

## Borderline: Needs Explicit Policy

These are not obviously wrong, but should not remain in git by accident.

### `docs/reports/`

Tracked count: `23`

This directory mixes:
- useful decision records
- incident history
- research dumps
- one-off execution handoffs
- at least one script: `docs/reports/stage4_live_verification.sh`

Recommendation:
- keep decision records and incident docs
- move disposable research snapshots and prompt outputs into a clear archive policy
- do not let `docs/reports/` become a second trash can

### `install.sh`

This is a unified installer, but it targets older assumptions:
- deploy dir `/slomix`
- branch `vps-network-migration`

It may still be useful historically or for recovery, but it does not match the current `/opt/slomix` VM world.

Recommendation:
- classify as either `legacy installer` or `current bootstrap`
- do not leave it ambiguous

## Strong Candidates To Remove From Git Or Archive

These look real, but they do not fit the current Slomix source-of-truth model cleanly.

### `update_bot.sh`

Reasons:
- targets `/slomix`
- checks out branch `vps-network-migration`
- restarts service `etlegacy-bot`
- does not match current VM service names or path conventions

Classification:
- legacy operational script

Recommendation:
- remove from active repo surface or archive under a clear `legacy/` or `docs/archive/ops/` policy

### `freshinstall.sh`

Reasons:
- bootstraps an ET:Legacy game server host
- includes server-user creation, SSH hardening, ET install, map downloads
- much broader than Slomix application runtime
- feels like adjacent infrastructure, not core app source

Classification:
- related operations script, but not core Slomix app code

Recommendation:
- either move to a separate infrastructure repo, or keep only if you deliberately want game-server provisioning versioned here

## Important Correction To Our Mental Model

Not everything that looks like “generated junk” should be removed.

Examples:
- `analytics/` looked suspicious at first, but it is a real bot runtime dependency
- `website/static/modern/` looks like build output, but it is currently part of the deploy/runtime contract

So the right rule is not:
- generated = always remove

The right rule is:
- generated + reproducible + not required by current deploy/runtime = candidate to remove

## Immediate Next Audit Pass

The next useful step is not broad cleanup. It is a targeted tracked-file review of these buckets:

1. root-level legacy ops scripts
2. `docs/reports/` and other report-like docs
3. current deploy contract for `website/static/modern/`
4. any tracked files that still encode old branch names, old paths, or old service names

## Practical Rule For Commits

Before tracking or untracking a file, ask:

1. Does current runtime or deploy logic directly use it?
2. Is it source, schema, or a real operational contract?
3. Is it just a snapshot, dump, generated output, or historical helper?
4. If we removed it from git, would current production break?

If question 4 is `yes`, keep it for now.
If question 3 is `yes` and question 4 is `no`, it is a cleanup candidate.
