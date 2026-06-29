# Wave 1 — UI/UX & Dizajn (7 najdb)

> Vse najdbe adversarialno preverjene (prove-or-drop). Severity je po-verifikaciji prilagojena.

### W1-18 · 🟢 LOW · Player-search result rows are clickable <div>s — not keyboard/screen-reader accessible

- **Področje:** S1–S2 Jutro/Račun (digest, on-this-day, baseline, auth)
- **Datoteka:** `website/js/auth.js:570-588 (also 328-336)`
- **Dimenzija:** ux · **Effort:** small

**Dokaz:** searchHeroPlayer() (live on the homepage hero) builds each result as `const div = document.createElement('div')` with `cursor-pointer` class and `div.onclick=...` (auth.js:570-588). The legacy searchPlayer() does the same (auth.js:328-336). Neither sets role="button", tabindex, an Enter/Space keydown handler, or aria. A keyboard or screen-reader user can type a query but cannot select any returned player. Inconsistent with the S2 link picker renderLinkCandidates() (auth.js:144-155) which correctly uses real <button> elements for the same purpose. Not covered in WHOLE_CODEBASE_AUDIT_2026-06-15.md.

**Predlog popravka:** Render each result as a `<button type="button">` (as renderLinkCandidates already does), or at minimum add role="button", tabindex="0" and an Enter/Space keydown handler mirroring onclick. Keep existing Tailwind classes so visuals are unchanged.

**Verifikacija (skeptik, conf=high):** Could not refute. Verified all three cited locations: searchHeroPlayer (auth.js:570-588) and searchPlayer (auth.js:328-336) both build result rows as createElement('div') with cursor-pointer + div.onclick, with no role/tabindex/keydown/aria. renderLinkCandidates (auth.js:144-155) for the same player-pick task correctly uses createElement('button') with type='button' and addEventListener('click'). So both the a11y gap and the internal-inconsistency claims hold. No guard elsewhere neutralizes this — the div onclick is the only selection path.

_Ground-truth preverjeno:_ Read auth.js:120-180, 310-355, 555-596 directly. Confirmed line-exact: div.onclick on hero results (583-587) and legacy claim results (332-335); button element in renderLinkCandidates (144-154). escapeHtml is used in all three so this is purely accessibility, not an XSS angle. Not present in WHOLE_CODEBASE_AUDIT_2026-06-15.md (a11y was out of scope there).

---

### W1-19 · 🟢 LOW · Display-name management block silently disappears on any transient API error

- **Področje:** S1–S2 Jutro/Račun (digest, on-this-day, baseline, auth)
- **Datoteka:** `website/js/auth.js:684-702`
- **Dimenzija:** ux · **Effort:** small

**Dokaz:** refreshDisplayNameBlock() catch body is just `block.classList.add('hidden'); return;` (auth.js:699-701). For a linked user, a transient /account/aliases failure makes the entire 'set name / aliases' UI vanish with zero feedback. The same hide path also handles the legitimate not-linked case (auth.js:690-692), so the user cannot distinguish 'feature unavailable' from 'feature broken right now' — an error state presented as feature absence. Other functions in the same file (refreshProfileLinkCard auth.js:121-126, loadPromotionPreferences auth.js:198-202) show an explicit error message in this situation, so this is the outlier. Not in WHOLE_CODEBASE_AUDIT_2026-06-15.md.

**Predlog popravka:** In the catch, when the user is known linked, keep the block visible and surface a short inline error (mirroring setProfileLinkStatusMessage's error styling) instead of hiding the whole block. Only hide when data.linked is explicitly false.

**Verifikacija (skeptik, conf=high):** Could not refute. The cited code is verbatim: refreshDisplayNameBlock() at auth.js:684-702 has a catch at 699-701 that does only `block.classList.add('hidden')` with no user feedback, and the not-linked branch at 690-692 uses the identical hide path — so a transient /account/aliases failure is indistinguishable from the feature being unavailable. The claimed contrast with siblings also holds: refreshProfileLinkCard (121-126) calls setProfileLinkStatusMessage(... , true) on error, loadPromotionPreferences (198-202) writes a 'Promotion settings unavailable' message, and fetchPlayerSuggestions (165-167) renders an explicit error row. So this function is genuinely the outlier in error handling.

_Ground-truth preverjeno:_ Read auth.js:670-719 (the target function + its callers _postDisplayName/setCustomDisplayName/resetDisplayName) and auth.js:110-203 (the cited sibling functions). Confirmed the catch swallows the error and hides the block, that the not-linked case shares that hide path, and that three other functions in the same file surface explicit error UI. No guard or alternate error-display path exists for this function. This is a frontend-only UX consistency issue — no data-correctness or security impact; the block degrades gracefully (hides) rather than showing stale/fabricated data.

---

### W1-20 · 🟢 LOW · S2 account flow uses native prompt()/confirm()/alert() instead of the site's own modal system

- **Področje:** S1–S2 Jutro/Račun (digest, on-this-day, baseline, auth)
- **Datoteka:** `website/js/auth.js:351, 705`
- **Dimenzija:** ux · **Effort:** medium

**Dokaz:** setCustomDisplayName() uses `prompt('Custom display name (max 32 chars):')` (auth.js:705); linkPlayer/unlink use `confirm(...)` and surface errors via `alert(...)` (auth.js:351, 372, 377, 390, 409). The site already ships a themed modal system (openModal/closeModal in this same file auth.js:301-311, used by modal-match-details/modal-player-compare in index.html:4771,4796). Native dialogs are unstyled OS popups that break the dark visual identity, can't preview ET color codes or live-validate the 32-char limit before submit, and render as blocking system popups on mobile. This is the one place a player customizes their public identity. Not in WHOLE_CODEBASE_AUDIT_2026-06-15.md.

**Predlog popravka:** Reuse the existing modal/inline pattern: a small input bound to profile-display-name-block with a Save button + live char counter, reporting success/error via setProfileLinkStatusMessage instead of alert(). No new framework needed.

**Verifikacija (skeptik, conf=high):** Could not refute. Every cited line is accurate: auth.js:705 uses prompt() in setCustomDisplayName; auth.js:351/377 use confirm() and 372/390/409 use alert() in linkPlayer/unlinkPlayerProfile/unlinkDiscordAccount. The site does ship a themed modal system (openModal/closeModal at auth.js:301-311) which is genuinely used by modal-match-details (index.html:4763) and modal-player-compare (index.html:4789). So the inconsistency the reviewer describes is real and not neutralized by any guard. The only basis to challenge it is that it is purely cosmetic/stylistic, not a functional or data-correctness defect — the native dialogs work.

_Ground-truth preverjeno:_ Read auth.js:290-411 and 690-720 directly — confirmed prompt/confirm/alert usage at all cited lines and the openModal/closeModal helpers. Grepped index.html and confirmed the themed modal markup (modal-match-details, modal-player-compare with closeModal click-actions) at lines 4763/4789. Not present in WHOLE_CODEBASE_AUDIT_2026-06-15.md as claimed (it is a UX, not scanner-type, finding).

---

### W1-24 · 🟢 LOW · ET Rating shown on two different scales on the same profile page ("342" vs "0.342")

- **Področje:** S5–S7 Identiteta/Spomin/Live (profil v2, wrapped, record-book, Tonight)
- **Datoteka:** `/home/samba/share/slomix_discord/website/js/player-profile.js:527`
- **Dimenzija:** ux · **Effort:** trivial

**Dokaz:** The S5 identity strip renders the rating as an integer: `ET Rating ${Math.round(skill.et_rating * 1000)}` (player-profile.js:527) → e.g. "ET Rating 342". The existing Skill panel directly below renders the SAME `skill.et_rating` via `${_num(skill.et_rating, 3)}` (player-profile.js:751) → "0.342". The composite endpoint returns the value as a 0.0–1.0 float (`players_profile_router.py:531` `round(rating,3)`), and the canonical site-wide display is `toFixed(3)` (React SkillRating.tsx:117/291 `et_rating.toFixed(3)`, leaderboard same). So a visitor sees a header badge reading "342" and a panel reading "0.342" for the identical metric on one screen — a fabricated-looking discrepancy that contradicts the 'no confusing numbers' philosophy.

**Zakaj (RCA):** Self-contradicting numbers on the flagship profile page undermine trust in the stats and look like a bug to every user who scrolls down.

**Predlog popravka:** Display the rating consistently with the rest of the site. Replace `Math.round(skill.et_rating * 1000)` in the identity-strip chip with the same formatting used elsewhere, e.g. `_num(skill.et_rating, 3)` (or `skill.et_rating.toFixed(3)`), so the header chip reads "ET Rating 0.342 · <tier>" matching the Skill panel and the SkillRating page. If an integer ladder-style number is genuinely desired, change it everywhere (panel + leaderboard + React) — but the cheap, correct fix is to match the existing 3-decimal convention here.

**Verifikacija (skeptik, conf=high):** Could not refute. Verified player-profile.js:514 and :728 both source `skill` from the same `data.skill` object, and both functions are invoked for the same page in the same render call (line 653 `_renderIdentityStrip(data)` for the header chip; line 660 `renderSkillAndLifetime(data)` for the overview tab). Line 527 renders `Math.round(skill.et_rating * 1000)` while line 751 renders `_num(skill.et_rating, 3)`. Same metric, same value, two scales on one screen. No guard, conditional, or alternate code path neutralizes this — there is exactly one ET-Rating chip render and one panel render, and they disagree.

_Ground-truth preverjeno:_ Read player-profile.js lines 515-539 (identity strip chip) and 740-757 (skill panel). Grepped all `et_rating` occurrences (only :527 and :751) and confirmed both `skill` vars derive from `data.skill` (:514, :728). Confirmed call sites via grep: `_renderIdentityStrip` at :653 and `renderSkillAndLifetime` at :660 are both in the same render flow. The two formatters (`Math.round(*1000)` vs `_num(...,3)`) produce 342 vs 0.342 for an identical value. Finding's cross-references (composite endpoint returning a 0-1 float, React toFixed(3) convention) are consistent with the 3-decimal canonical display; the integer chip is the outlier.

---

### W1-25 · 🟢 LOW · Record Book tab marks itself loaded BEFORE the fetch, so a transient failure leaves the tab permanently empty

- **Področje:** S5–S7 Identiteta/Spomin/Live (profil v2, wrapped, record-book, Tonight)
- **Datoteka:** `/home/samba/share/slomix_discord/website/js/record-book.js:31`
- **Dimenzija:** ux · **Effort:** small

**Dokaz:** `_ensureLoaded` sets `_loaded[key] = true;` (line 33) before invoking the loader, and the loader's rejection is only swallowed with `.catch(e => console.warn(...))` (lines 35/37/39). If the first load of a tab (records/hof/season) fails for any transient reason (network blip, slow backend), the flag stays true and re-clicking the tab calls `_ensureLoaded`, which returns early at line 32 — the tab shows nothing with no error message and never retries until a full page reload.

**Zakaj (RCA):** Live data feeds occasionally hiccup; a permanently-blank tab with no error state is a confusing dead-end for the user.

**Predlog popravka:** Set `_loaded[key] = true` only on success: move the assignment into a `.then()` after the loader resolves, and on `.catch` keep it false and render a small inline 'Couldn't load — tap to retry' message in the tab's container so re-clicking retries.

**Verifikacija (skeptik, conf=high):** I tried to refute this by reading the actual code and looking for any retry/reset mechanism, but the finding holds. _ensureLoaded (lines 31-41) does `if (_loaded[key]) return;` (line 32) then unconditionally `_loaded[key] = true;` (line 33) BEFORE calling the loader. The loaders' rejections are only swallowed with `.catch(e => console.warn(...))` (lines 35/37/39), with no reset of the flag and no inline error/retry UI. So a transient first-load failure permanently latches the tab as 'loaded' — re-clicking calls _showTab -> _ensureLoaded which returns early at line 32, showing nothing until a full page reload. No guard elsewhere neutralizes this; the flag is module-level state mutated only here.

_Ground-truth preverjeno:_ Read website/js/record-book.js lines 1-60. Confirmed: _loaded module object at line 12 (records/hof/season all false), the early-return + premature true-set in _ensureLoaded (lines 31-33), and the three swallow-only catches (lines 35/37/39). The loaders (loadRecordsView, loadHallOfFameView, loadRecordBookSeason) are awaited only via the catch chain; nothing resets _loaded on failure. Behavior described is accurate.

---

### W1-26 · 🟢 LOW · Tonight hub rebuilds its entire DOM every 8s poll, resetting horizontal scroll of the maps strip

- **Področje:** S5–S7 Identiteta/Spomin/Live (profil v2, wrapped, record-book, Tonight)
- **Datoteka:** `/home/samba/share/slomix_discord/website/js/tonight.js:176`
- **Dimenzija:** ux · **Effort:** small

**Dokaz:** `_refresh` does `host.textContent = ''` then re-inserts the whole hub via `safeInsertHTML` on every 8s poll (tonight.js:176-218). The 'Tonight's maps' strip is `overflow-x-auto` (line 199). A user who scrolls right to view later maps — especially on mobile — has that scroll position (and any hover/focus) discarded every 8 seconds when the panel is wiped and recreated, plus the momentum/hold-prob canvases flicker on each rebuild.

**Zakaj (RCA):** A live hub people watch should not yank the view out from under them on every tick; small but noticeable polish gap on the new S7 page.

**Predlog popravka:** Either preserve the horizontal scrollLeft of `.overflow-x-auto` across refresh (read before wipe, restore after insert), or render the static shell once and update only the changing text/score/canvas nodes in place rather than replacing the whole `host`. Lightweight: capture `const sl = stripEl?.scrollLeft` before clearing and reapply after re-insert.

**Verifikacija (skeptik, conf=high):** Could not refute. The cited behavior is exactly what the code does. tonight.js:11 sets POLL_MS=8000; lines 29-32 call _refresh() on that interval whenever the view is active; _refresh() at line 176 executes host.textContent='' followed by safeInsertHTML(host,'beforeend',...) which re-renders the ENTIRE hub, including the maps strip and both canvases. There is no scroll-preservation logic anywhere (grep for scrollLeft returns nothing). The maps strip is overflow-x-auto (line 199) with fixed w-40 cards, so when enough maps accumulate to overflow (plausible on mobile / a long evening), any user-applied horizontal scroll is reset to 0 every 8s, and the momentum/hold-prob canvases (lines 207/213) are recreated and redrawn (216-217) each tick. No guard neutralizes this.

_Ground-truth preverjeno:_ Read tonight.js lines 20-47 (polling lifecycle) and 160-218 (the _refresh render path). Grepped the file for setInterval, host.textContent, scrollLeft, overflow-x-auto: confirmed 8s interval, full-DOM wipe at lines 113/125/134/176/284, no scrollLeft handling at all. The strip is genuinely overflow-x-auto with flex-shrink-0 w-40 cards (line 162), so overflow is real. This is a frontend-only UX polish issue; not in the prior scanner audit scope (that focused on security/deps). Matches project context note that tonight.js is a recently-shipped S7 live page.

---

### W1-27 · 🟢 LOW · Wrapped share-card modal: no Escape/backdrop close, no dialog semantics, inert buttons on error

- **Področje:** S5–S7 Identiteta/Spomin/Live (profil v2, wrapped, record-book, Tonight)
- **Datoteka:** `/home/samba/share/slomix_discord/website/js/wrapped.js:21`
- **Dimenzija:** ux · **Effort:** small

**Dokaz:** The Wrapped overlay (wrapped.js:21-79) is a full-screen modal but only closes via the explicit Close button (line 39); there is no Escape-key handler, no click-on-backdrop dismissal, and the container has no `role="dialog"`/`aria-modal`/focus management. Additionally, the Copy/Download buttons are rendered up-front but their click listeners are only attached after the fetch succeeds (lines 59/65); on the error paths (lines 48 / 53 set a status message and `return`) the Copy and Download buttons remain visible and clickable but do nothing.

**Zakaj (RCA):** Modal keyboard-dismiss and backdrop-close are baseline expectations; inert-looking action buttons on error read as broken to the user.

**Predlog popravka:** Add an Escape keydown handler and a backdrop-click handler (close when `e.target === overlay`) bound when opening and removed on close; set `role="dialog" aria-modal="true"` on the panel and move initial focus to Close. On the error/no-data paths, hide or disable the Copy/Download buttons (e.g. add `disabled`/`hidden`) so they don't appear actionable.

**Verifikacija (skeptik, conf=high):** I could not refute the core factual claims; they accurately describe the code. However, the finding is genuinely low-impact polish, not a correctness or security issue. The "inert buttons on error" part is the only real bug-like aspect, and even that is mild: on the two error paths (line 48 and 53) the function returns before binding the Copy/Download listeners, so those buttons are visible but no-ops. The Escape/backdrop/role=dialog points are accessibility/UX niceties, not defects.

_Ground-truth preverjeno:_ Read /home/samba/share/slomix_discord/website/js/wrapped.js in full. Confirmed: overlay built at line 11-19 with class bg-black/80 (full-screen modal), no role/aria attributes. Only close handler is the explicit #wrapped-close button (line 39-42) — no keydown(Escape) and no overlay click handler anywhere in the file. Copy/Download buttons are rendered in the initial safeInsertHTML (lines 32-33), but their addEventListener calls are at lines 59 and 65, AFTER the fetch (line 46) and the two early-return error paths at lines 48 and 53. So on fetch failure or empty data, the buttons remain clickable but unbound. All claims in the finding match the code exactly.

---
