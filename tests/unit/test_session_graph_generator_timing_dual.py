from __future__ import annotations

import io

import pytest

from bot.services.session_graph_generator import SessionGraphGenerator


class _FakeDbAdapter:
    async def fetch_all(self, query, params=None):
        if "FROM player_comprehensive_stats p" in query and "GROUP BY p.player_guid" in query:
            # player_name, kills, deaths, dmg_given, dmg_received, dpm, time_played_seconds,
            # time_dead_minutes, revives_given, times_revived, gibs, headshots,
            # denied_playtime_seconds, useful_kills, self_kills, full_selfkills, guid, rounds_played
            return [
                (
                    "Alpha",
                    10,
                    5,
                    3000,
                    2000,
                    300.0,
                    600,
                    2.0,
                    2,
                    1,
                    3,
                    4,
                    120,
                    6,
                    1,
                    0,
                    "GUID_ALPHA",
                    2,
                )
            ]
        return []


@pytest.mark.asyncio
async def test_graphs_dual_mode_shows_old_vs_new_timing(monkeypatch):
    generator = SessionGraphGenerator(_FakeDbAdapter(), show_timing_dual=True)

    async def _fake_columns():
        return {"full_selfkills"}

    async def _fake_dual_payload(_session_ids):
        return {
            "players": {
                "GUID_ALPHA": {
                    "new_time_dead_seconds": 60,
                    "new_denied_seconds": 30,
                }
            },
            "meta": {
                "rounds_total": 2,
                "rounds_with_telemetry": 2,
            },
        }

    async def _fake_timeline(*_args, **_kwargs):
        return io.BytesIO(b"timeline")

    titles = []
    grouped = {}

    def _fake_style_axis(ax, title):
        titles.append(title)
        ax.set_title(title)

    def _fake_grouped_labels(ax, _bars1, _bars2, v1, v2, fmt="{:.0f}"):
        grouped[ax.get_title()] = (list(v1), list(v2), fmt)

    def _noop_bar_labels(*_args, **_kwargs):
        return None

    monkeypatch.setattr(generator, "_get_player_stats_columns", _fake_columns)
    monkeypatch.setattr(generator, "_get_session_timing_dual_by_guid", _fake_dual_payload)
    monkeypatch.setattr(generator, "_generate_timeline_graph", _fake_timeline)
    monkeypatch.setattr(generator, "_style_axis", _fake_style_axis)
    monkeypatch.setattr(generator, "_add_grouped_bar_labels", _fake_grouped_labels)
    monkeypatch.setattr(generator, "_add_bar_labels", _noop_bar_labels)

    buf1, buf2, buf3, buf4, buf5 = await generator.generate_performance_graphs(
        latest_date="2026-02-18",
        session_ids=[1001, 1002],
        session_ids_str="?,?",
    )

    assert all(buf is not None for buf in (buf1, buf2, buf3, buf4, buf5))
    assert "TIME DEAD OLD vs NEW (minutes)" in titles
    assert "TIME DENIED % (OLD vs NEW)" in titles
    assert "SURVIVAL RATE % (OLD vs NEW)" in titles

    dead_old, dead_new, _ = grouped["TIME DEAD OLD vs NEW (minutes)"]
    denied_old, denied_new, _ = grouped["TIME DENIED % (OLD vs NEW)"]
    surv_old, surv_new, _ = grouped["SURVIVAL RATE % (OLD vs NEW)"]

    # Old values come from c0rnp0rn/stats rows, new values from Lua-shadow payload.
    assert dead_old[0] == pytest.approx(2.0)
    assert dead_new[0] == pytest.approx(1.0)
    assert denied_old[0] == pytest.approx(20.0)
    assert denied_new[0] == pytest.approx(5.0)
    assert surv_old[0] == pytest.approx(80.0)
    assert surv_new[0] == pytest.approx(90.0)
