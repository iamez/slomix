# Wave 1 — Varnost (4 najdb)

> Vse najdbe adversarialno preverjene (prove-or-drop). Severity je po-verifikaciji prilagojena.

### W1-06 · 🟡 MEDIUM · Parimutuel market has no betting cutoff — hindsight bets game the points leaderboard and the permanent 'Oracle' season award

- **Področje:** S3–S4 Večer/Tekma (parimutuel stave, izzivi, planning, season awards)
- **Datoteka:** `website/backend/routers/bets_router.py:110-147, 245-284`
- **Dimenzija:** security · **Effort:** small
- **Zunanja ref:** Distinct from the atomicity/payout class noted already fixed in docs/research/WHOLE_CODEBASE_AUDIT_2026-06-15.md:35 — this is betting-window/outcome integrity, not payout math.

**Dokaz:** A market only ever transitions open -> settled. `place_bet` accepts/changes a bet whenever `market.status == 'open'` (bets_router.py:146-147). Nothing in the codebase ever sets `status='closed'` or checks `parimutuel_markets.closes_at` (grep for 'closed'/'closes_at' across website/backend returns no enforcement; the columns from migration 010 lines 41,46 are dead). Meanwhile `settle_market` auto-resolves the outcome by reading the already-recorded result: `SELECT winning_team FROM session_results ... ` (bets_router.py:274-281). Session results are surfaced publicly on the site, so a logged-in user who sees the real winner can place/change a bet onto the known-winning side at any time before an admin clicks settle, guaranteeing they land in the winning pool. `season_awards_service._compute_oracle` (season_awards_service.py:136-166) then engraves a permanent season 'Oracle' award to the bettor with the best net winnings — so this sniping directly fabricates a persistent award, violating the 'no fabricated numbers' philosophy, plus pads the public points leaderboard (bets_router.py:196-213).

**Zakaj (RCA):** Undermines the integrity of a permanent engraved season award and the points leaderboard with a concrete, no-mitigation exploit path; data-integrity is ranked as high as security in this project.

**Predlog popravka:** Add a real betting cutoff: (1) enforce `closes_at` in `place_bet` (reject when `closes_at IS NOT NULL AND now() >= closes_at`), and/or require an admin `close` step that sets status='closed' before settle; (2) in `settle_market`, refuse to settle a market still in 'open' (require it be 'closed' first) so the result-known window is eliminated; (3) consider auto-closing the market the moment a `session_results` row exists for its `gaming_session_id`. This removes the hindsight-betting path without adding scale/complexity.

**Verifikacija (skeptik, conf=high):** Could not refute. The claimed gap is genuine: place_bet (bets_router.py:139-147) gates only on status=='open'; grep across website/backend, bot, and scripts shows the schema column closes_at (tools/schema_postgresql.sql:8726) is never read or written, no code ever sets status='closed', and settle_market is invoked only by a manual admin POST (no scheduled/auto settle). settle_market auto-derives the outcome from the already-recorded session_results.winning_team (bets_router.py:272-283), and since session results are published on the site there is a real open window between result-publication and admin settle during which a user can free-rebet onto the known winner via the upsert (bets_router.py:177-186). _compute_oracle (season_awards_service.py:135-166) then engraves a permanent season award from net winnings. The only inaccuracy in the finding is the schema citation: the closes_at/opens_at columns live in tools/schema_postgresql.sql:8725-8726, not 'migration 010' (which is an unrelated proximity migration). That is a wrong reference, not a refutation — the column genuinely exists and is dead.

_Ground-truth preverjeno:_ Read bets_router.py in full (place_bet 110-193, settle_market 245-344, leaderboard 196-213). Grepped website/backend, bot, scripts for closes_at / 'closed' / settle automation — only matches are the manual /settle route itself; no enforcement or auto-close exists. Confirmed parimutuel_markets schema (tools/schema_postgresql.sql:8714-8729) has closes_at defined but unused, and status defaults to 'open' with no 'closed' transition. Verified migration 010 is 010_add_proximity_support_summary.sql (unrelated to betting) — finding's migration line citation is incorrect. Read season_awards_service.py:135-166 (_compute_oracle) confirming permanent 'oracle' award written to season_awards from net bet winnings.

---

### W1-16 · 🟢 LOW · Custom display name accepts arbitrary content (no sanitization) and is surfaced into Discord embeds + site name resolution

- **Področje:** S1–S2 Jutro/Račun (digest, on-this-day, baseline, auth)
- **Datoteka:** `/home/samba/share/slomix_discord/website/backend/routers/auth.py:914-979`
- **Dimenzija:** security · **Effort:** small

**Dokaz:** set_my_display_name() only validates length (`if not name or len(name) > _DISPLAY_NAME_MAX:` where _DISPLAY_NAME_MAX=32) and the action enum. It does NOT sanitize content, then writes the raw string to player_links.display_name (UPDATE player_links SET display_name = ? ...). That column is read back by the bot's PlayerDisplayNameService.get_display_name (bot/services/player_display_name_service.py:50 'SELECT display_name ... FROM player_links') and by the website's resolve_display_name (website/backend/routers/api_helpers.py:315 'SELECT COALESCE(display_name, player_name) ...') — the latter only strips ET color codes (^1..^9), not markdown/HTML/control chars. A linked user can therefore set their own name to e.g. a Discord masked link `[x](https://evil)` (<=32 chars) which renders as a clickable link in any bot embed listing that player (morning digest, leaderboards, session reports). resolve_display_name output is also fanned out to ~10 callers across the website; legacy JS escapes it (escapeHtml in auth.js:148/331/572) and React auto-escapes, so web XSS is not proven, but the stored value is untrusted-by-construction.

**Zakaj (RCA):** Untrusted user input is stored without sanitization and rendered into Discord embed markdown (proven masked-link injection) and across name-resolution surfaces; only length is validated.

**Predlog popravka:** In set_my_display_name, after the length check, reject or strip control/markdown characters from `name` for action=='custom' (e.g. allow a conservative printable set, strip `[]()` `*_~|>` backtick and C0 controls, collapse whitespace). The 'alias' path is already safe because it must match a recorded player_aliases row. Defense-in-depth even though the community is trusted.

**Verifikacija (skeptik, conf=medium):** Could not refute the core claim. set_my_display_name (auth.py:946) validates only length (max 32) + action enum, then stores name verbatim for action=='custom' (line 960). Verified the value is read back unsanitized by PlayerDisplayNameService.get_display_name (auth read returns link_result[0] raw) and get_display_names_batch, and those names flow into Discord embeds (last_session_cog.py:424 -> build_session_overview_embed; ssh_monitor.py:718/986; session_cog.py:329). Discord renders markdown/masked links in embed field values/descriptions, so a <=32-char [text](url) is injectable. resolve_display_name (api_helpers.py:319) strips only ET color codes. Mitigations that reduce but do not eliminate it: web XSS is NOT exploitable (escapeHtml in legacy JS + React auto-escape, finding concedes this); requires an authenticated Discord-linked user; self-targeting only; trusted ~30-50 player community. The alias path is correctly guarded against arbitrary input.

_Ground-truth preverjeno:_ Read auth.py:914-979 (only length+enum validation, raw UPDATE), confirmed _DISPLAY_NAME_MAX=32 at line 872. Read player_display_name_service.py (get_display_name returns raw link_result[0]; batch returns raw row[1]). Read api_helpers.py:300-339 (resolve_display_name strips only ET colors). Confirmed embed consumers via grep: last_session_cog.py:424, ssh_monitor.py:718/986, session_cog.py:329, and read last_session_cog.py:420-456 showing display names substituted into build_session_overview_embed. Grepped prior audit doc WHOLE_CODEBASE_AUDIT_2026-06-15.md for display_name/sanitize/masked link: no hits, so this is not a duplicate.

---

### W1-17 · 🟢 LOW · Authenticated session cookie lacks Secure flag by default (SESSION_HTTPS_ONLY defaults to false)

- **Področje:** S1–S2 Jutro/Račun (digest, on-this-day, baseline, auth)
- **Datoteka:** `/home/samba/share/slomix_discord/website/backend/routers/auth.py:8`
- **Dimenzija:** security · **Effort:** trivial

**Dokaz:** auth.py:8 `_SESSION_HTTPS_ONLY = os.getenv("SESSION_HTTPS_ONLY", "false").lower() == "true"` and the matching SessionMiddleware in website/backend/main.py:225 `https_only=SESSION_HTTPS_ONLY` (default "false", main.py:101) plus the logout/discord-unlink cookie deletions (auth.py:483, auth.py:863 `secure=_SESSION_HTTPS_ONLY`). The session cookie carries the authenticated Discord identity (request.session['user'] set in callback, auth.py:460). If SESSION_HTTPS_ONLY is not explicitly set in the production .env, the cookie is issued without the Secure attribute and can be transmitted over plain HTTP, enabling network-level session theft. The code respects the env var, so this is an insecure default, not a hard bug; real-world risk is reduced by Cloudflare always-HTTPS in front of slomix.fyi.

**Zakaj (RCA):** Insecure-by-default for the cookie that authenticates the user; correctness depends on remembering to set an env var in every deployment.

**Predlog popravka:** Default SESSION_HTTPS_ONLY to true (opt-out for local dev via SESSION_HTTPS_ONLY=false) so production is secure-by-default, or assert it is true when a production indicator (e.g. FRONTEND_ORIGIN starts with https) is detected at startup. Ensure prod .env sets SESSION_HTTPS_ONLY=true regardless.

**Verifikacija (skeptik, conf=high):** Could not refute. The cited code is exactly as described: auth.py:8 and main.py:101 both default SESSION_HTTPS_ONLY to "false"; main.py:225 passes https_only=SESSION_HTTPS_ONLY into SessionMiddleware; auth.py:483/863 use secure=_SESSION_HTTPS_ONLY on cookie deletion. The session stores authenticated Discord identity (auth.py:460 request.session["user"] = _build_session_user(...)). Mitigating factors exist but do not neutralize the insecure default: cookie is httponly=True and samesite="lax", and Cloudflare fronts slomix.fyi with always-HTTPS — but without the Secure attribute the browser will still attach the cookie to any plaintext http:// request made before a redirect, allowing leakage. Notably .env.example:31 ships SESSION_HTTPS_ONLY=false, so a deployment copying the example inherits the insecure value, reinforcing the "must remember to set an env var" risk the finding describes.

_Ground-truth preverjeno:_ Read auth.py:1-15 and the cited cookie-deletion lines (483, 863) plus session-set line (460). Read main.py:95-110 and 220-230 (SessionMiddleware config). Grepped SESSION_HTTPS_ONLY across .env* and website/: only .env.example sets it (=false); no production override visible in repo. Confirmed the prior scanner audit (docs/research/WHOLE_CODEBASE_AUDIT_2026-06-15.md) does NOT cover this (no SESSION_HTTPS/Secure flag/https_only hits) — this is a new finding, not a re-report.

---

### W1-21 · 🟢 LOW · `/today/balanced-teams` POST is the only planning write-shaped endpoint missing the CSRF header check

- **Področje:** S3–S4 Večer/Tekma (parimutuel stave, izzivi, planning, season awards)
- **Datoteka:** `website/backend/routers/planning.py:1001-1010`
- **Dimenzija:** security · **Effort:** trivial

**Dokaz:** Every other POST in planning.py calls `_require_ajax_csrf_header(request)` (create:560, join:636, suggestions:693, vote:769, teams:836, ping:1051), and all bets/challenges/season POSTs do too. `suggest_balanced_teams` (planning.py:1001) only calls `_require_linked_identity` and omits the CSRF header guard. Impact is limited because the handler performs no DB writes (read-only roster + ET-rating enumeration) and CORS blocks cross-origin reading of the credentialed response, but it is an inconsistent contract that exposes the linked roster + ratings to a forced same-cookie cross-site request.

**Zakaj (RCA):** Defense-in-depth consistency; the deviation is the kind of drift that becomes a real gap if the endpoint later gains a write.

**Predlog popravka:** Add `_require_ajax_csrf_header(request)` at the top of `suggest_balanced_teams` to match the rest of the router's contract (one line).

**Verifikacija (skeptik, conf=high):** Could not refute the factual claim: planning.py:1001-1010 (suggest_balanced_teams) is indeed the only POST in the router that omits _require_ajax_csrf_header — all six sibling POSTs (create:560, join:636, suggestions:693, vote:769, teams:836, ping:1051) call it. The one mitigating angle is that the CSRF guard exists to protect state-changing routes, and this endpoint is read-only (only a SELECT at 1018-1045, no writes) with CORS blocking cross-origin reads, so the real-world exploit value is effectively zero. That makes it a genuine consistency/defense-in-depth nit rather than a live vulnerability — but the deviation itself is real and the reviewer scoped it honestly.

_Ground-truth preverjeno:_ Read planning.py:990-1059 (confirmed suggest_balanced_teams calls only _require_linked_identity, no CSRF guard; handler is read-only SELECT). Grepped all @router.post + _require_ajax_csrf_header occurrences in planning.py — confirmed every other POST guards, only balanced-teams omits. Read auth_helpers.py:47-50 — require_ajax_csrf_header enforces X-Requested-With: XMLHttpRequest header (standard non-simple-header CSRF defense for state-changing routes).

---
