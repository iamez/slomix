"""arc.py — session story-arc classification (TOK H Steber B, Val H3).

Gives a session a SHAPE, not just a scoreline: was it a statement, a comeback,
a nail-biter, a lead-trading slugfest? The Smart Stats recap opens with that
shape so the numbers read as a story with a beginning, middle and end.

Pure and dependency-free: it classifies from the BOX-score map progression
(one team vocabulary — alpha/beta — so there is no cross-source mapping to get
wrong; the Data Trust pillar this session built stays intact). The caller
(narrative.py) turns the returned shape slug into prose, keeping all phrasing in
one place alongside the other narrative leads.
"""

from __future__ import annotations

# Shape slugs the classifier returns. Empty string = not enough to shape.
COMEBACK = "comeback"
TRADE_FEST = "trade_fest"
NAIL_BITER = "nail_biter"
STATEMENT = "statement"
DECISIVE = "decisive"


def classify_session_arc(
    maps: list[dict],
    winner_side: str,
    winner_score: int,
    loser_score: int,
) -> str:
    """Shape a completed session from its map-by-map score progression.

    ``maps`` is the BOX-score maps list in play order, each ``{"alpha_points",
    "beta_points", ...}``. ``winner_side`` is "alpha" or "beta". Returns one of
    the shape slugs above, or "" when there is nothing to shape (fewer than two
    maps, a tie, or an unknown winner) — the caller then simply omits the arc.

    The running margin is always taken from the WINNER's perspective, so:
      * the lead crossed sides twice or more           → trade_fest
      * the winner was behind at some point            → comeback
      * it finished within two points / decided late    → nail_biter
      * the winner never trailed and won comfortably    → statement
      * anything else clearly decided                   → decisive
    trade_fest is checked BEFORE comeback: crossing the lead twice necessarily
    means the winner was once behind, so both would fire, and "lead traded all
    night" is the truer description of a chaotic session than a plain comeback.
    A single behind→ahead swing (one lead change) falls through to comeback.
    """
    if not maps or len(maps) < 2 or winner_side not in ("alpha", "beta"):
        return ""
    if winner_score == loser_score:
        return ""

    winner_is_alpha = winner_side == "alpha"
    running: list[int] = []  # winner_cumulative - loser_cumulative, after each map
    w_cum = l_cum = 0
    for m in maps:
        ap = int(m.get("alpha_points", 0) or 0)
        bp = int(m.get("beta_points", 0) or 0)
        w_cum += ap if winner_is_alpha else bp
        l_cum += bp if winner_is_alpha else ap
        running.append(w_cum - l_cum)

    final_margin = winner_score - loser_score
    total_points = winner_score + loser_score
    min_margin = min(running)

    # Lead changes: count sign flips across the running margin, treating ties
    # (0) as neutral so a brief level score isn't itself a "change".
    lead_changes = 0
    prev_sign = 0
    for v in running:
        sign = (v > 0) - (v < 0)
        if sign != 0:
            if prev_sign != 0 and sign != prev_sign:
                lead_changes += 1
            prev_sign = sign

    if lead_changes >= 2:
        return TRADE_FEST
    if min_margin < 0:
        return COMEBACK
    # Close overall, or the second-to-last map left it level/one apart and the
    # final map decided it.
    if final_margin <= 2 or (len(running) >= 2 and abs(running[-2]) <= 1):
        return NAIL_BITER
    if min_margin >= 0 and final_margin >= max(4, round(total_points * 0.4)):
        return STATEMENT
    return DECISIVE
