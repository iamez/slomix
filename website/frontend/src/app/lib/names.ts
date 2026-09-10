/**
 * ET:Legacy colour-code stripping — `^1name^7` renders red in-game and as
 * literal control tokens everywhere else. THE one copy for the SPA: pages
 * and the geo module import it from here, because the repo already carries
 * two DIFFERENT semantics and the wrong one nearly became the shared one.
 *
 * The canonical character class is `\^[0-9a-zA-Z]` — backend
 * `strip_et_colors` (et_constants.py:25), six legacy JS files (e.g.
 * js/story.js:10) and the old React tree all agree on it.
 * `geo/mapTransforms.ts` used to hand-roll `\^.` under a comment claiming it
 * was "the same strip as legacy" — it was not, and measured on the corpus
 * (94 player names) the difference is one-sided: NO real name contains
 * `^`+alphanumeric beyond actual colour codes, while all six names that
 * contain a caret at all pair it with a NON-alphanumeric
 * (`^<ABD-AL-KL3M3N`, `'^/fnx`, `//^?/M.Gekku`, `//^?/M.rAzzdOG`,
 * `//^?/M.Demonslayer`, `one^>4ass.squAze`) — the canonical class leaves
 * every one intact, `\^.` mangles all six.
 *
 * The two-sided fact, for the next person who reads ET's source: by the
 * engine's own `Q_IsColorString`, `^<` IS a colour code, so `\^.` is closer
 * to what the GAME renders. But changing how 6 of 94 names display is a
 * product decision that has to land everywhere at once, not on one panel —
 * until then, agreement with backend `strip_et_colors` (which every
 * server-cleaned name already went through) is the contract.
 *
 * Most storytelling endpoints strip server-side; the momentum-session
 * service returns player_comprehensive_stats names raw (momentum.py
 * `_build_player_groups` / `_team_labels` import no stripper — Codex on
 * #842), which is why the SPA needs this at all.
 */
export function stripEtColors(text: string): string {
  // The mapTransforms copy this replaced was defensive (`String(value ?? '')`)
  // and callers on this codebase routinely discover a field is `string | null`
  // after the fact — so the defence stays at runtime while the type keeps the
  // compile-time contract honest (verifier on #842).
  return String(text ?? '').replace(/\^[0-9A-Za-z]/g, '');
}
