"""Narrative baseline cutoff must be the narrated session (Codex DATA-01).

The trailing "your usual" baseline has to exclude the session being
narrated and nothing else. Deriving the cutoff as MIN(gaming_session_id)
over the calendar date widened that exclusion whenever a date held two
sessions: narrating the later one also discarded the earlier one from the
baseline, even though it is legitimate history by then.
"""
from __future__ import annotations

import inspect

from website.backend.services.storytelling import narrative


def test_cutoff_comes_from_the_resolved_scope_not_a_date_lookup():
    src = inspect.getsource(narrative)
    assert "before_gsid = scope.gaming_session_id" in src
    # the re-derivation must be gone, not merely bypassed
    assert "SELECT MIN(gaming_session_id) FROM rounds" not in src


def test_no_stale_date_helper_left_behind():
    """The date-string helper existed only for the removed lookup; leaving
    the import would keep implying a date-based cutoff."""
    src = inspect.getsource(narrative)
    assert "_to_date_str" not in src


def test_baseline_helper_still_takes_an_exclusive_session_bound():
    """`before_session_id` is the contract the cutoff feeds; if it changed
    meaning, the cutoff fix would be silently wrong."""
    from website.backend.services.storytelling.baseline import trailing_averages

    params = inspect.signature(trailing_averages).parameters
    assert "before_session_id" in params
