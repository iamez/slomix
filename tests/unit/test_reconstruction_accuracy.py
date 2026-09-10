"""The error bars the page draws, and the honesty rules around them."""

from __future__ import annotations

import pytest

from website.backend.services.reconstruction_accuracy import (
    CLEAN_BANDS,
    CONFLICT_BANDS,
    MEASUREMENT,
    position_error,
    to_dict,
)


class TestBandLookup:
    @pytest.mark.parametrize("stale", [0, 1, 199])
    def test_fresh_samples_get_the_measured_fresh_band(self, stale):
        error = position_error(stale)
        assert error.p50 == 12.0
        assert error.well_sampled is True

    def test_the_last_band_is_open_ended(self):
        """A stale sample has no ceiling: a player who disconnects mid-round can
        leave one arbitrarily old (207,375 ms observed)."""
        assert position_error(10**9) is not None

    def test_bands_are_ordered_and_end_open(self):
        for bands in (CLEAN_BANDS, CONFLICT_BANDS):
            edges = [b[0] for b in bands]
            assert edges[-1] is None, "the last band must be open-ended"
            finite = [e for e in edges if e is not None]
            assert finite == sorted(finite)


class TestHonesty:
    def test_no_position_means_no_error_bar(self):
        """Attaching one would imply a position exists to be wrong about."""
        assert position_error(None) is None
        assert to_dict(None) is None

    def test_negative_staleness_is_refused(self):
        """A sample from after `t` is a floor-invariant violation, not a fresh
        reading — Layer 1 must never produce one, and this will not paper over
        it if it does."""
        assert position_error(-1) is None

    def test_a_contested_position_is_an_order_of_magnitude_worse(self):
        """Measured: ~875 units against ~12. Drawing both with one confidence is
        what this whole module exists to stop."""
        clean = position_error(100, overlap_conflict=False)
        contested = position_error(100, overlap_conflict=True)
        assert contested.p50 > clean.p50 * 20

    def test_a_contested_position_says_why(self):
        error = position_error(100, overlap_conflict=True)
        assert "overlapping lives" in error.basis

    def test_thin_bands_are_marked_not_well_sampled(self):
        """The 200-5000 ms bands rest on 9-645 samples and their percentiles
        swing accordingly. Marked rather than dropped: a reader still needs to
        know the drawing is uncertain there."""
        assert position_error(300).well_sampled is False
        assert position_error(3000).well_sampled is False
        assert position_error(50).well_sampled is True


class TestProvenance:
    def test_measurement_names_its_source_and_date(self):
        """A number without provenance is read three months later as a fact
        about code that has since changed."""
        for key in ("measured_at", "script", "rounds", "samples", "sources"):
            assert MEASUREMENT.get(key), f"missing provenance: {key}"

    def test_the_victim_coordinate_exclusion_is_recorded(self):
        """§12 A1: it shares a writer with the track's death sample, so
        comparing them would measure the writer, not the reconstruction."""
        assert "victim" in MEASUREMENT["excluded"]

    def test_to_dict_carries_the_basis(self):
        payload = to_dict(position_error(100))
        assert set(payload) == {"p50", "p90", "well_sampled", "basis"}
