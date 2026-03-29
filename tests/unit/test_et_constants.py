"""Tests for website/backend/utils/et_constants.py."""

import pytest

from website.backend.utils.et_constants import (
    KILL_MOD_NAMES,
    strip_et_colors,
    weapon_name,
)


# --- strip_et_colors ---


class TestStripEtColors:
    def test_plain_name(self):
        assert strip_et_colors("Player") == "Player"

    def test_single_color_code(self):
        assert strip_et_colors("^1Red") == "Red"

    def test_multiple_color_codes(self):
        assert strip_et_colors("^1R^7e^3d") == "Red"

    def test_consecutive_color_codes(self):
        assert strip_et_colors("^1^2^3Name") == "Name"

    def test_empty_string(self):
        assert strip_et_colors("") == ""

    def test_none_like_input(self):
        assert strip_et_colors(None) == ""

    def test_color_code_at_end(self):
        assert strip_et_colors("Name^7") == "Name"

    def test_only_color_codes(self):
        assert strip_et_colors("^1^2^3") == ""

    def test_letter_color_codes(self):
        assert strip_et_colors("^aGreen^ZBlue") == "GreenBlue"


# --- weapon_name ---


class TestWeaponName:
    def test_known_kill_mod_knife(self):
        assert weapon_name(3) == "Knife"

    def test_known_kill_mod_mp40(self):
        assert weapon_name(8) == "MP40"

    def test_known_kill_mod_panzerfaust(self):
        assert weapon_name(15) == "Panzerfaust"

    def test_unknown_kill_mod(self):
        assert weapon_name(999) == "MOD_999"

    def test_none_returns_unknown(self):
        assert weapon_name(None) == "Unknown"

    def test_string_input_converted(self):
        assert weapon_name("8") == "MP40"

    def test_string_unknown_mod(self):
        assert weapon_name("999") == "MOD_999"


# --- KILL_MOD_NAMES dict ---


class TestKillModNames:
    def test_is_dict(self):
        assert isinstance(KILL_MOD_NAMES, dict)

    def test_has_expected_keys(self):
        for key in (3, 8, 15, 44, 66):
            assert key in KILL_MOD_NAMES

    def test_no_none_values(self):
        for key, value in KILL_MOD_NAMES.items():
            assert value is not None, f"KILL_MOD_NAMES[{key}] is None"

    def test_all_keys_are_int(self):
        for key in KILL_MOD_NAMES:
            assert isinstance(key, int)

    def test_all_values_are_str(self):
        for value in KILL_MOD_NAMES.values():
            assert isinstance(value, str)

    def test_known_mappings(self):
        assert KILL_MOD_NAMES[3] == "Knife"
        assert KILL_MOD_NAMES[44] == "Mobile MG42"
        assert KILL_MOD_NAMES[66] == "Backstab"
