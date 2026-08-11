"""Tonight roster: bot identities must never reach the public surface.

Live evidence (2026-08-11): a bot test ran hours before a real session.
Unlinked lua_round_teams rows pass the is_valid join through the
`r.id IS NULL` escape (legitimate — a live round is unlinked for minutes),
so the roster builder needs an identity-level filter too. This pins the
helper's contract; the row-skip semantics live in get_tonight.
"""

from __future__ import annotations

from website.backend.routers.players_router import _is_bot_player


def test_omnibot_guid_both_shapes():
    # Stats path and Lua path generate DIFFERENT OMNIBOT guids for the same
    # bot; both share the OMNIBOT prefix (measured 2026-08-11).
    assert _is_bot_player({"guid": "OMNIBOT08d08fd9f5a92589102b2ee59", "name": "lagger"})
    assert _is_bot_player({"guid": "omnibot0500000000000000000000000", "name": "x"})


def test_bot_name_prefix():
    assert _is_bot_player({"guid": "ABCD1234", "name": "[BOT]vid"})


def test_real_player_passes():
    assert not _is_bot_player({"guid": "D8423F90ABCD1234", "name": "vid"})
    assert not _is_bot_player({"guid": "", "name": ""})


def test_name_containing_bot_elsewhere_is_not_a_bot():
    assert not _is_bot_player({"guid": "ABCD1234", "name": "robotnik"})
