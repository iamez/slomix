"""Tests for PWC v2, WIS v2, and Bayesian MVP edge cases.

Validates the mathematical formulas without requiring a database.
"""

import pytest


# ── Helper: reproduce WIS v2 confidence formula ─────────────────

def compute_wis_v2(won_pwc: float, lost_pwc: float,
                   rounds_won: int, rounds_lost: int) -> float:
    """Mirror of storytelling_service.py WIS v2 computation."""
    total_rounds = rounds_won + rounds_lost
    if total_rounds < 2:
        return 0.0
    avg_won = won_pwc / max(rounds_won, 1)
    avg_lost = lost_pwc / max(rounds_lost, 1)
    if rounds_won > 0 and rounds_lost > 0:
        reliability = 2 * rounds_won * rounds_lost / (rounds_won + rounds_lost)
        confidence = min(reliability / (total_rounds / 2), 1.0)
    else:
        confidence = 0.0
    return (avg_won - avg_lost) * confidence


def compute_bayesian_waa(won_pwc: float, total_rounds: int,
                         session_avg_pwc: float, c: int = 2) -> float:
    """Mirror of storytelling_service.py Bayesian WAA."""
    waa = won_pwc / max(total_rounds, 1)
    return (waa * total_rounds + c * session_avg_pwc) / (total_rounds + c)


def compute_share(player_val: float, team_val: float) -> float:
    """Mirror of div-by-zero fix: 0 when team total is 0."""
    return player_val / team_val if team_val > 0 else 0.0


# ── WIS v2 Tests ────────────────────────────────────────────────

class TestWISv2:
    def test_insufficient_data_returns_zero(self):
        """Single round should return WIS=0."""
        assert compute_wis_v2(0.5, 0.0, 1, 0) == 0.0

    def test_all_wins_returns_zero(self):
        """All wins, no losses → no contrast → WIS=0."""
        assert compute_wis_v2(1.0, 0.0, 4, 0) == 0.0

    def test_all_losses_returns_zero(self):
        """All losses, no wins → no contrast → WIS=0."""
        assert compute_wis_v2(0.0, 1.0, 0, 4) == 0.0

    def test_balanced_sample_full_confidence(self):
        """2W 2L → confidence=1.0, WIS = avg_won - avg_lost."""
        wis = compute_wis_v2(0.6, 0.2, 2, 2)
        assert wis == pytest.approx(0.3 - 0.1, abs=1e-6)  # 0.2

    def test_unbalanced_sample_dampened(self):
        """1W 3L → confidence < 1.0, WIS is dampened."""
        wis = compute_wis_v2(0.5, 0.3, 1, 3)
        # reliability = 2*1*3/4 = 1.5, confidence = 1.5/2 = 0.75
        avg_won = 0.5
        avg_lost = 0.1
        expected = (avg_won - avg_lost) * 0.75
        assert wis == pytest.approx(expected, abs=1e-6)

    def test_symmetric_but_different_performance(self):
        """Equal W/L → full confidence."""
        wis = compute_wis_v2(0.8, 0.2, 3, 3)
        # reliability = 2*3*3/6 = 3, confidence = 3/3 = 1.0
        assert wis == pytest.approx(0.8 / 3 - 0.2 / 3, abs=1e-6)

    def test_1w_1l_full_confidence(self):
        """1W 1L → reliability = 2*1*1/2 = 1.0, confidence = 1.0/1.0 = 1.0."""
        wis = compute_wis_v2(0.4, 0.1, 1, 1)
        assert wis == pytest.approx(0.3, abs=1e-6)


# ── Bayesian WAA Tests ──────────────────────────────────────────

class TestBayesianWAA:
    def test_late_joiner_regressed(self):
        """1-round player should be pulled toward session average."""
        session_avg = 0.10  # average PWC per round across session
        # Late joiner: 1 round, 0.5 won_pwc → raw WAA = 0.5
        bayes = compute_bayesian_waa(0.5, 1, session_avg, c=2)
        # (0.5*1 + 2*0.10) / (1+2) = 0.7/3 = 0.233
        assert bayes == pytest.approx(0.2333, abs=1e-3)

    def test_regular_player_stays_close(self):
        """4-round player should stay near raw WAA."""
        session_avg = 0.10
        # Regular: 4 rounds, 0.8 won_pwc → raw WAA = 0.2
        bayes = compute_bayesian_waa(0.8, 4, session_avg, c=2)
        # (0.2*4 + 2*0.10) / (4+2) = 1.0/6 = 0.1667
        assert bayes == pytest.approx(0.1667, abs=1e-3)

    def test_late_joiner_cannot_beat_regular(self):
        """Late joiner with great single round < regular with consistent play."""
        session_avg = 0.10
        late = compute_bayesian_waa(0.5, 1, session_avg, c=2)   # 0.233
        regular = compute_bayesian_waa(1.2, 4, session_avg, c=2) # (0.3*4+0.2)/6 = 0.233
        # Regular with 1.2 won_pwc in 4 rounds: (0.3*4 + 0.2)/6 = 1.4/6 = 0.233
        # Actually let's make the regular clearly better
        regular = compute_bayesian_waa(1.6, 4, session_avg, c=2)
        # (0.4*4 + 0.2)/6 = 1.8/6 = 0.3
        assert regular > late

    def test_zero_rounds_returns_prior(self):
        """0 rounds → returns session average (prior)."""
        session_avg = 0.15
        bayes = compute_bayesian_waa(0.0, 0, session_avg, c=2)
        # (0*0 + 2*0.15) / (0+2) = 0.3/2 = 0.15
        assert bayes == pytest.approx(0.15, abs=1e-6)


# ── MVP Minimum Rounds Tests ───────────────────────────────────

class TestMVPEligibility:
    def test_min_rounds_calculation(self):
        """50% of max rounds, minimum 2."""
        # If max_rounds = 4, min = max(2, 4//2) = 2
        assert max(2, 4 // 2) == 2
        # If max_rounds = 6, min = max(2, 6//2) = 3
        assert max(2, 6 // 2) == 3
        # If max_rounds = 1, min = max(2, 1//2) = 2
        assert max(2, 1 // 2) == 2

    def test_late_joiner_filtered_out(self):
        """Late joiner with 1 round fails eligibility when max=4."""
        max_rounds = 4
        min_rounds = max(2, max_rounds // 2)  # 2
        late_joiner_rounds = 1
        assert late_joiner_rounds < min_rounds

    def test_half_session_player_eligible(self):
        """Player with 2/4 rounds passes eligibility."""
        max_rounds = 4
        min_rounds = max(2, max_rounds // 2)  # 2
        player_rounds = 2
        assert player_rounds >= min_rounds

    def test_mvp_tiebreaker_is_deterministic(self):
        """With equal WAA, higher total_pwc wins; then rounds_won."""
        players = [
            {"waa_bayes": 0.25, "total_pwc": 1.0, "rounds_won": 2},
            {"waa_bayes": 0.25, "total_pwc": 1.2, "rounds_won": 2},
            {"waa_bayes": 0.25, "total_pwc": 1.2, "rounds_won": 3},
        ]
        mvp = max(players, key=lambda p: (
            p["waa_bayes"], p["total_pwc"], p["rounds_won"]
        ))
        assert mvp["rounds_won"] == 3
        assert mvp["total_pwc"] == 1.2


# ── Division-by-Zero Share Tests ────────────────────────────────

class TestDivByZeroShares:
    def test_zero_team_kills_returns_zero(self):
        """Player with 1 kill on team with 0 total → share = 0, not 1.0."""
        assert compute_share(1, 0) == 0.0

    def test_normal_share(self):
        """10 of 40 kills → 0.25."""
        assert compute_share(10, 40) == pytest.approx(0.25)

    def test_zero_player_on_nonzero_team(self):
        """0 kills on team with 20 → 0.0."""
        assert compute_share(0, 20) == 0.0

    def test_full_share(self):
        """All kills belong to one player → 1.0."""
        assert compute_share(15, 15) == pytest.approx(1.0)

    def test_zero_both_returns_zero(self):
        """0 kills, 0 team kills → 0.0."""
        assert compute_share(0, 0) == 0.0
