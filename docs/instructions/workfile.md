# Paste-ready prompt for Codex / Claude Code (Slomix)

> Return-after-break handover first: `docs/reports/SHOP_CLOSE_HANDOVER_AVAILABILITY_2026-02-19.md`
> Context compact/source-of-truth: `docs/reports/AVAILABILITY_V2_CONTEXT_COMPACT_2026-02-19.md`

You are an autonomous senior full‑stack engineer working in the **iamez/slomix** repo. Your mission is to implement and ship an **Availability + Promote + Planning Room** system that works across **Website + Discord + Telegram + Signal**.

## Operating principles
- **Assume everything is broken first.** Your first job is to get the project running locally on Linux with **zero errors**.
- **Small, safe steps.** Each step must end with tests + a quick manual validation checklist.
- **Source of truth:** Website DB/API is authoritative for availability state.
- **Opt‑in only:** Do not message users unless they explicitly opted in / linked that channel.
- **Idempotent + rate‑limited:** Every scheduled/notification action must be safe to retry and never double‑send.
- **Security by default:** No secrets in code; follow OAuth2 best practices; hash/expire link tokens.

## Context you must internalize
- Availability is date-based: **one status per user per date**.
- Existing docs/code mention:
  - `availability_entries` with UNIQUE `(user_id, entry_date)`.
  - `availability_subscriptions` with UNIQUE `(user_id, channel_type)`.
  - `availability_channel_links` for one-time verification tokens.
  - `notifications_ledger` for idempotent notifications.
  - Bot already has `!avail`, `!avail_link`, `!avail_unsubscribe` commands.
  - Bot has a scheduled loop that posts daily polls + reminders.
  - There is a `voice_channel_tracker` service that can fetch voice status from DB.

## Deliverables
1) **Green boot**: project runs on Linux (web on port **7000**) + bot starts + no startup errors.
2) **Availability UI/UX revamp**: Today/Tomorrow summary + “Current Queue” + compact upcoming days + optional full calendar toggle.
3) **Multi-channel linking UX**: a Profile/Settings section to link/unlink Discord/Telegram/Signal; token-based flow for Telegram/Signal.
4) **Promote campaign**: a "Promote" button (admin/permitted) that schedules two reminders (T‑15 and T0), then runs a voice-ready check.
5) **Planning Room (MVP)**: unlocked when enough players commit; basic team drafting + team name voting; optional Discord thread creation.
6) **Docs + tests**: update docs and add tests for critical flows.

---

# Stage 0 — Make it run (assume broken)

## Tasks
- Inspect repo structure: locate website frontend + backend, bot, config, docker, migrations.
- Identify required environment variables and defaults.
- Bring up the stack on **Linux**:
  - Web server on **port 7000**.
  - DB connectivity working.
  - Bot can connect (use a safe “dev/test” mode so it doesn’t spam real users).

## Output
- Create `docs/RUNBOOK_LOCAL_LINUX.md` with:
  - exact commands to install deps
  - env vars
  - run commands (web + bot)
  - common failures + fixes

## Done criteria
- `curl http://localhost:7000/health` (or equivalent) returns OK.
- bot starts without exceptions.

---

# Stage 1 — Availability Page UX revamp

## UX requirements
- Keep Today/Tomorrow summary as the hero.
- Add **Current Queue**: list users with status **LOOKING today** (or show “Queue is empty”).
- Add **Upcoming (next 3 days)** digest with counts (LOOKING/AVAILABLE/MAYBE/NOT_PLAYING).
- Add **Open Calendar** toggle that reveals the full calendar UI; default is collapsed.
- If not logged in or not linked: user can view aggregate data but **cannot set status**.

## Engineering requirements
- Use existing `GET /api/availability?from=...&to=...` to fetch range.
- Avoid new endpoints unless necessary.
- Keep UI responsive and mobile-friendly.

## Output
- Commit with clear message: `feat(availability-ui): today/tomorrow + queue + upcoming + calendar toggle`
- Add a short `docs/AVAILABILITY_UI.md` with screenshots/notes.

---

# Stage 2 — Linking accounts (Discord login + Telegram/Signal token linking)

## Requirements
- Website Profile/Settings: “Linked Accounts” panel:
  - Discord: show linked state (from login)
  - Telegram: Link/Unlink
  - Signal: Link/Unlink
- Link flow for Telegram/Signal:
  1) Website generates one-time token (TTL default 30 min)
  2) User sends token to bot (`/link <token>` or deep link)
  3) Bot calls website `link-confirm`
  4) DB marks subscription `verified_at`

## Security
- Tokens are **hashed** in DB and expire.
- Prevent replay: token single-use.
- Rate limit link generation.

## Output
- Update/extend docs: `docs/AVAILABILITY_SYSTEM.md` and/or new `docs/LINKING_ACCOUNTS.md`.

---

# Stage 3 — Promote Campaigns (notifications + voice-ready check)

## Product requirements
- Availability page has **Promote** button visible only to:
  - authenticated + linked users
  - and `is_admin` / permitted role
- Clicking Promote opens a modal:
  - shows how many recipients will be pinged
  - allow choosing which statuses are eligible (default: LOOKING + AVAILABLE)
  - confirm schedules: **T‑15** and **T0** (configurable)

## Backend requirements
- Create `promotion_campaigns` table (or equivalent):
  - `id, date, created_by, status_filters, reminder_at, start_at, reminder_sent_at, start_sent_at, created_at`
- Implement API `POST /api/promote`:
  - validates permissions
  - ensures only one active campaign per date (idempotent)
  - returns campaign id and schedule

## Worker/scheduler requirements
- Implement campaign execution in the most reliable place:
  - either extend the bot’s existing scheduled loop
  - or add a dedicated worker
- Use `notifications_ledger` with a unique event key (e.g. `PROMOTE:YYYY-MM-DD:T-15`) per user+channel to avoid double sends.
- Respect channel opt-ins (`availability_subscriptions.enabled` + `verified_at`).
- Rate limit outbound messages.

## Voice-ready check
- At start time, check who is in Discord voice (via `voice_channel_tracker` or live API).
- Compare expected players (eligible statuses) vs present players.
- Send a **targeted** follow-up only to opted-in missing players.

## Output
- Add `docs/PROMOTE_CAMPAIGNS.md` describing flow + DB schema + idempotency keys.

---

# Stage 4 — Planning Room (MVP)

## Unlock condition
- When today’s committed count reaches threshold (configurable; reuse existing “session_ready” if present).

## Features (MVP)
- Web Planning Room page/section:
  - list committed players
  - team name suggestions + voting
  - simple team drafting UI (two columns, assign players)
- Optional Discord:
  - create a private thread/channel when session unlocks
  - store thread id in DB

## Data model
- `planning_sessions (id, date, created_by, discord_thread_id, created_at)`
- `planning_team_names (id, session_id, suggested_by, name, created_at)`
- `planning_votes (id, session_id, user_id, suggestion_id, created_at)`
- `planning_teams (id, session_id, side, captain_user_id, created_at)`
- `planning_team_members (team_id, user_id)`

## Output
- `docs/PLANNING_ROOM.md`

---

# Stage 5 — Tests, docs, security checklist

## Tests (minimum)
- API auth/permissions: cannot submit availability unless authenticated+linked.
- Link token: TTL + single-use + confirm endpoint behavior.
- Promote: creating campaign is idempotent and restricted.
- Notification ledger: duplicate run does not double-send.

## Security checklist (must implement)
- OAuth: Authorization Code + PKCE + CSRF `state`.
- Secrets only in env.
- No tokens in logs.
- Input validation for dates/status enums.
- Rate limiting on bot commands and promote endpoint.

---

# Execution rules for you (the agent)

For each stage:
1) **Plan the change** (files you’ll touch, migrations, risks).
2) Implement with minimal diffs.
3) Add tests.
4) Run lint/type checks.
5) Provide a short manual QA checklist.
6) Commit with a clean message.

If you hit ambiguity, choose the safest default:
- do not spam users
- keep feature behind flags
- prefer additive changes over refactors

Start now with Stage 0 and do not skip ahead.
