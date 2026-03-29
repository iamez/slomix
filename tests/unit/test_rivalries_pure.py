"""Tests for pure functions in rivalries_service.py."""


from website.backend.services.rivalries_service import MIN_ENCOUNTERS, _classify
from website.backend.utils.et_constants import strip_et_colors, weapon_name

# --- _classify ---

class TestClassify:
    """Tests for _classify(win_rate, total)."""

    def test_prey_high_win_rate(self):
        assert _classify(0.85, 10) == "PREY"

    def test_prey_boundary_70(self):
        assert _classify(0.70, 10) == "PREY"

    def test_nemesis_high_loss_rate(self):
        assert _classify(0.15, 10) == "NEMESIS"

    def test_nemesis_boundary_30(self):
        assert _classify(0.30, 10) == "NEMESIS"

    def test_rival_balanced(self):
        assert _classify(0.50, 10) == "RIVAL"

    def test_rival_boundary_40(self):
        assert _classify(0.40, 10) == "RIVAL"

    def test_rival_boundary_60(self):
        assert _classify(0.60, 10) == "RIVAL"

    def test_contender_between_nemesis_and_rival(self):
        # 0.31-0.39 is neither NEMESIS nor RIVAL
        assert _classify(0.35, 10) == "CONTENDER"

    def test_contender_between_rival_and_prey(self):
        # 0.61-0.69 is neither RIVAL nor PREY
        assert _classify(0.65, 10) == "CONTENDER"

    def test_insufficient_data_below_min(self):
        assert _classify(0.90, MIN_ENCOUNTERS - 1) == "INSUFFICIENT_DATA"

    def test_insufficient_data_zero_encounters(self):
        assert _classify(0.0, 0) == "INSUFFICIENT_DATA"

    def test_exact_min_encounters_classifies(self):
        assert _classify(0.80, MIN_ENCOUNTERS) == "PREY"

    def test_min_encounters_is_five(self):
        assert MIN_ENCOUNTERS == 5


# --- et_constants integration ---

class TestEtConstantsIntegration:
    """Verify that et_constants helpers work as used by rivalries_service."""

    def test_strip_et_colors_basic(self):
        assert strip_et_colors("^1Red^7Name") == "RedName"

    def test_strip_et_colors_empty(self):
        assert strip_et_colors("") == ""

    def test_strip_et_colors_no_codes(self):
        assert strip_et_colors("PlainName") == "PlainName"

    def test_weapon_name_known(self):
        assert weapon_name(3) == "Knife"
        assert weapon_name(15) == "Panzerfaust"

    def test_weapon_name_unknown(self):
        assert weapon_name(999) == "MOD_999"

    def test_weapon_name_none(self):
        assert weapon_name(None) == "Unknown"
