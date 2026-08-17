# ruff: noqa: SLF001  (testi namenoma sežejo v privatne dele zanke)
"""The reader for the game server's console log.

The 2026-08-17 RCA found that a Lua error printed into etconsole.log on every
supply map load for three months with zero readers: the one grep with the
right pattern pointed at the local dev clone, the deploy runbook's "no
etconsole errors" was an adjective without a step, and every alert path to
Discord begins as a Python exception inside the bot's own process. This loop
is the missing sensor; these tests pin its judgement — what counts as an
error, what gets deduped, and that a broken fetch never kills the loop.
"""
from __future__ import annotations

from bot.services.monitor_tasks_mixin import _MonitorTasksMixin

_CRASH = ("Lua 5.4 API: et_InitGame error running lua script: "
          "'[string \"luascripts/proximity_tracker.lua\"]:2511: bad argument #4 "
          "to 'format' (number has no integer representation)'")


class _Cfg:
    ssh_enabled = True
    ssh_host = "puran.example"
    ssh_port = 48101
    ssh_user = "et"
    ssh_key_path = "/tmp/key"
    game_console_log_path = "/home/et/.etlegacy/legacy/etconsole.log"


class Bot(_MonitorTasksMixin):
    def __init__(self, spans):
        """`spans` = list of (new_offset, text) the fake fetch returns in order."""
        self.config = _Cfg()
        self._spans = list(spans)
        self.fetch_offsets: list = []
        self.alerts: list[tuple[str, str]] = []

    def _fetch_console_span(self, offset):
        self.fetch_offsets.append(offset)
        return self._spans.pop(0)

    async def alert_admins(self, title, message):
        self.alerts.append((title, message))


async def _tick(bot):
    await _MonitorTasksMixin.lua_console_sentinel.coro(bot)


# ---------------------------------------------------------------------------
# pattern judgement
# ---------------------------------------------------------------------------

def test_the_production_crash_line_matches():
    bot = Bot([])
    assert bot._scan_console_chunk(_CRASH, now=0.0) == [_CRASH]


def test_the_prox_pcall_failures_match():
    """#751 made failures loud on purpose; the sentinel must hear them."""
    bot = Bot([])
    lines = ("[PROX] scanVehicleEntities FAILED: boom\n"
             "[PROX] round-end handling FAILED: boom")
    assert len(bot._scan_console_chunk(lines, now=0.0)) == 2


def test_ordinary_console_noise_does_not_alert():
    bot = Bot([])
    noise = ("WeaponStats: 1 1 12599548 5 10 0\n"
             ">>> Proximity Tracker v6.10 initialized\n"
             "Lua 5.4 API: file 'luascripts/live_events.lua' loaded into Lua VM\n"
             "ClientConnect: 5\n"
             "broadcast: print \"match is paused!\"")
    assert bot._scan_console_chunk(noise, now=0.0) == []


def test_the_same_error_is_reported_once_per_cooldown():
    """The crash prints on EVERY map load; an alert channel that repeats
    itself gets muted, which recreates the blindness this loop ends."""
    bot = Bot([])
    assert bot._scan_console_chunk(_CRASH, now=0.0) == [_CRASH]
    assert bot._scan_console_chunk(_CRASH, now=100.0) == []
    assert bot._scan_console_chunk(
        _CRASH, now=bot._CONSOLE_ALERT_COOLDOWN_S + 1.0) == [_CRASH]


# ---------------------------------------------------------------------------
# the loop
# ---------------------------------------------------------------------------

async def test_an_error_line_becomes_an_admin_alert():
    bot = Bot([(1000, _CRASH)])

    await _tick(bot)

    assert len(bot.alerts) == 1
    assert "Lua napaka" in bot.alerts[0][0]
    assert "2511" in bot.alerts[0][1]


async def test_offset_carries_between_passes():
    bot = Bot([(1000, _CRASH), (1000, "")])

    await _tick(bot)
    await _tick(bot)

    assert bot.fetch_offsets == [None, 1000]


async def test_quiet_log_means_no_alert():
    bot = Bot([(500, "ClientBegin: 3\n")])

    await _tick(bot)

    assert bot.alerts == []


async def test_a_failing_fetch_does_not_kill_the_loop_or_move_the_offset():
    class B(Bot):
        def _fetch_console_span(self, offset):
            raise OSError("ssh down")

    bot = B([])
    await _tick(bot)          # must not raise

    assert getattr(bot, "_console_log_offset", None) is None
    assert bot.alerts == []


async def test_disabled_ssh_disables_the_sentinel():
    bot = Bot([(1000, _CRASH)])
    bot.config.ssh_enabled = False

    await _tick(bot)

    assert bot.fetch_offsets == []
    assert bot.alerts == []


async def test_a_failing_alert_is_contained():
    class B(Bot):
        async def alert_admins(self, *a):
            raise RuntimeError("discord down")

    bot = B([(1000, _CRASH)])
    await _tick(bot)          # must not raise


async def test_a_failed_alert_does_not_consume_the_cooldown():
    """The dedupe map is marked before the send; without the rollback a Discord
    outage silenced the very lines the sentinel exists to surface — for an
    hour, with the offset already advanced past them."""
    class B(Bot):
        def __init__(self, spans):
            super().__init__(spans)
            self.fail_alerts = 1

        async def alert_admins(self, title, message):
            if self.fail_alerts:
                self.fail_alerts -= 1
                raise RuntimeError("discord down")
            self.alerts.append((title, message))

    bot = B([(1000, _CRASH), (1000, _CRASH)])
    await _tick(bot)                      # send fails → cooldown rolled back
    assert bot.alerts == []
    await _tick(bot)                      # same line must alert now
    assert len(bot.alerts) == 1


def test_fetch_never_advances_past_a_split_line(monkeypatch):
    """A read can end mid-line; the offset must stop at the last complete
    newline so an error straddling the boundary is scanned whole next pass."""
    import io

    class _FakeFile(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _FakeSftp:
        def __init__(self, blob):
            self._blob = blob

        def stat(self, path):
            class S:
                st_size = len(self._blob)
            return S()

        def open(self, path, mode):
            return _FakeFile(self._blob)

        def get_channel(self):
            class C:
                def settimeout(self, t):
                    pass
            return C()

    class _FakeSSH:
        def __init__(self, blob):
            self._blob = blob

        def set_missing_host_key_policy(self, policy):
            pass

        def load_system_host_keys(self):
            pass

        def load_host_keys(self, path):
            pass

        def connect(self, **kw):
            pass

        def open_sftp(self):
            return _FakeSftp(self._blob)

        def close(self):
            pass

    blob = b"line one\n" + _CRASH.encode()      # crash line NOT yet newline-terminated
    bot = Bot([])
    import paramiko
    monkeypatch.setattr(paramiko, "SSHClient", lambda: _FakeSSH(blob))

    # the REAL fetch (the test Bot overrides it with a fake for loop tests)
    new_off, text = _MonitorTasksMixin._fetch_console_span(bot, 0)

    assert text == "line one\n"
    assert new_off == len(b"line one\n")

    # once the writer finishes the line, the next pass picks it up whole
    blob2 = blob + b"\n"
    monkeypatch.setattr(paramiko, "SSHClient", lambda: _FakeSSH(blob2))
    new_off2, text2 = _MonitorTasksMixin._fetch_console_span(bot, new_off)
    assert "2511" in text2 and new_off2 == len(blob2)
