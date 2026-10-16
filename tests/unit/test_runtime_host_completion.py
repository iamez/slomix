"""Credentialed writer-close transport, durable evidence and native full-writer proof."""

import hashlib
import json
import os
import shutil
import subprocess
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest

from shared import runtime_host_completion as completion
from shared.runtime_host_bootstrap import bootstrap_round
from shared.runtime_host_capture import capture_closed_stats
from shared.runtime_manifest_reader import inspect_completion_manifest
from shared.runtime_process_authority import reserve_process_epoch
from shared.runtime_process_pin import pin_process
from shared.runtime_round_identity import stats_header_identity
from tests.unit import test_runtime_host_bootstrap as bootstrap_fixtures
from tests.unit.test_runtime_host_bootstrap import issued
from tests.unit.test_runtime_process_channel import approval
from tests.unit.test_runtime_stats_dispatch import prepare, setup_pair

ROOT = Path(__file__).resolve().parents[2]
NAME = "2026-09-25-120000-supply-round-1.txt"
approved, child, pin = bootstrap_fixtures.approved, bootstrap_fixtures.child, bootstrap_fixtures.pin
channels, prepared, listener = bootstrap_fixtures.channels, bootstrap_fixtures.prepared, bootstrap_fixtures.listener


@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
@pytest.mark.parametrize('fault', ['source', 'path', 'bootstrap-timeout', 'completion-timeout',
                                  'unknown', 'missing', 'clock', 'late', 'dependency'])
def test_configured_adapter_failure_keeps_whole_writer_fenced(tmp_path, lua, fault):
    authority, spool, pair = setup_pair(tmp_path / 'rounds')
    dispatch = prepare(authority, spool, pair)
    directory = spool / dispatch.generation
    socket_path = '/tmp/slomix-adapter-fixture-not-listening'
    result = subprocess.run([
        lua, str(ROOT / 'tests/lua/runtime_identity_writer_harness.lua'), str(ROOT),
        str(directory), pair.first.source_id, pair.first.match_id, pair.first.round_id,
        pair.second.round_id, '1', dispatch.generation, 'bound-hooks-frame',
        '@hooks:' + socket_path, 'required-entrypoint', '1234', socket_path,
        'ok', 'configured-host', fault,
    ], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'configuration refused, writer fenced, no files' in result.stdout
    assert not list(directory.glob('*.txt'))


@pytest.fixture
def ready(prepared, pin, channels, monkeypatch):
    host, epoch, dispatch = prepared
    accepted = bootstrap_round(None, host, pin, epoch, dispatch=dispatch)
    state = {"wire": completion.StatsCompletion(dispatch.generation, NAME, 42).encode(), "closed": 0}

    @contextmanager
    def channel(*args, **kwargs):
        class Fake:
            def receive_line(self):
                return state["wire"]

        try:
            yield Fake()
        finally:
            state["closed"] += 1

    monkeypatch.setattr(completion, "process_channel", channel)
    return host, epoch, accepted, state


def receive(ready, pin):
    host, epoch, accepted, _ = ready
    return completion.receive_stats_completion(None, host, pin, epoch, accepted=accepted)


def test_durable_authenticated_receipt_does_not_claim_payload_or_allow_duplicate(ready, pin):
    host, _, accepted, state = ready
    value = receive(ready, pin)
    assert value == completion.StatsCompletion(accepted.delivery.dispatch.generation, NAME, 42)
    path = issued(host).with_name("stats-writer-closed.txt")
    before = path.read_bytes(), path.stat().st_ino
    assert before[0] == (state["wire"] + "\n").encode()
    assert not list(host.rglob("*.complete.json"))
    with pytest.raises(FileExistsError):
        receive(ready, pin)
    assert (path.read_bytes(), path.stat().st_ino) == before
    assert state["closed"] == 2


@pytest.mark.parametrize(
    "change",
    [
        "generation",
        "map",
        "half",
        "map-prefix",
        "protocol",
        "path",
        "size-zero",
        "size-big",
        "size-padding",
        "size-float",
        "tail",
        "newline",
    ],
)
def test_wrong_receipt_never_persists(ready, pin, change):
    host, _, _, state = ready
    fields = state["wire"].split("|")
    if change == "generation":
        fields[1] = "f" * 32
    elif change == "map":
        fields[2] = fields[2].replace("supply", "radar")
    elif change == "map-prefix":
        fields[2] = fields[2].replace("supply", "evil-supply")
    elif change == "half":
        fields[2] = fields[2].replace("round-1", "round-2")
    elif change == "protocol":
        fields[0] = "slomix_round_ended_v1"
    elif change == "path":
        fields[2] = "../" + fields[2]
    elif change == "size-zero":
        fields[3] = "0"
    elif change == "size-big":
        fields[3] = "8388609"
    elif change == "size-padding":
        fields[3] = "042"
    elif change == "size-float":
        fields[3] = "42.0"
    elif change == "tail":
        fields.append("extra")
    else:
        fields[2] += "\n"
    state["wire"] = "|".join(fields)
    with pytest.raises(ValueError):
        receive(ready, pin)
    assert not issued(host).with_name("stats-writer-closed.txt").exists()
    assert state["closed"] == 1


@pytest.mark.parametrize("name", ["bootstrap-issued.json", "bootstrap-accepted.txt"])
@pytest.mark.parametrize("when", ["before", "after-receive", "after-write"])
def test_bootstrap_record_drift_refuses_success(ready, pin, monkeypatch, name, when):
    host, _, _, state = ready
    path = issued(host).with_name(name)
    original_verify = completion.verify_process_epoch
    count = 0

    def verify(*args):
        nonlocal count
        count += 1
        if count == {"before": 1, "after-receive": 2, "after-write": 3}[when]:
            path.write_bytes(b"changed\n")
        return original_verify(*args)

    monkeypatch.setattr(completion, "verify_process_epoch", verify)
    with pytest.raises(ValueError, match="durable bootstrap acceptance"):
        receive(ready, pin)
    assert issued(host).with_name("stats-writer-closed.txt").exists() == (when == "after-write")
    assert state["closed"] == 1


@pytest.mark.parametrize("fail_at", [1, 2])
def test_fsync_failure_retains_receipt_and_forbids_retry(ready, pin, monkeypatch, fail_at):
    host, _, _, state = ready
    original, count = os.fsync, 0

    def sync(fd):
        nonlocal count
        count += 1
        if count == fail_at:
            raise OSError("fixture completion fsync failure")
        original(fd)

    monkeypatch.setattr(os, "fsync", sync)
    with pytest.raises(OSError, match="completion fsync"):
        receive(ready, pin)
    assert issued(host).with_name("stats-writer-closed.txt").read_text() == state["wire"] + "\n"
    monkeypatch.setattr(os, "fsync", original)
    with pytest.raises(FileExistsError):
        receive(ready, pin)


@pytest.mark.parametrize("field", ["process_epoch", "lifecycle_epoch", "init_time"])
def test_caller_cannot_substitute_bootstrap_expectation(ready, pin, field):
    host, epoch, accepted, _ = ready
    changed = replace(accepted.delivery, **{field: 5678 if field == "init_time" else "e" * 32})
    with pytest.raises((ValueError, FileNotFoundError)):
        completion.receive_stats_completion(None, host, pin, epoch, accepted=replace(accepted, delivery=changed))
    assert not issued(host).with_name("stats-writer-closed.txt").exists()


@pytest.mark.parametrize("lua", ["lua5.1", "lua5.4"])
@pytest.mark.parametrize(
    "fault",
    [
        "ok",
        "state",
        "extra",
        "version",
        "size-zero",
        "size-big",
        "size-float",
        "size-nan",
        "size-string",
        "path",
        "protocol",
        "generation",
        "open-error",
        "send-error",
    ],
)
def test_source_completion_is_bounded_one_shot_and_never_waits_for_ack(lua, fault):
    result = subprocess.run(
        [lua, str(ROOT / "tests/lua/runtime_host_completion_harness.lua"), str(ROOT), fault, "a" * 32],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    if fault == "ok":
        assert completion.decode_stats_completion(result.stdout.strip()) == completion.StatsCompletion(
            "a" * 32, NAME, 42
        )


@pytest.mark.parametrize("lua", ["lua5.1", "lua5.4"])
@pytest.mark.parametrize("fault", ["hooks-frame", "hooks-shutdown"])
@pytest.mark.parametrize("delivery_state", ["ok", "no-receiver", "lost-bootstrap-acceptance"])
@pytest.mark.parametrize("configured_host", [False, True])
def test_native_writer_close_to_durable_host_receipt_and_manifest(
    tmp_path, listener, lua, fault, delivery_state, configured_host,
):
    server, path = listener
    executable = Path(shutil.which(lua)).resolve()
    authority, spool, pair = setup_pair(tmp_path / "rounds")
    dispatch = prepare(authority, spool, pair)
    directory = spool / dispatch.generation
    host = tmp_path / "host"
    host.mkdir(mode=0o700)
    args = [
        str(executable),
        str(ROOT / "tests/lua/runtime_identity_writer_harness.lua"),
        str(ROOT),
        str(directory),
        pair.first.source_id,
        pair.first.match_id,
        pair.first.round_id,
        pair.second.round_id,
        "1",
        dispatch.generation,
        "bound-" + fault,
        "@hooks:" + str(path),
        "required-entrypoint",
        "1234",
        str(path),
        delivery_state,
        "configured-host" if configured_host else "manual-fixture",
    ]
    with subprocess.Popen(
        args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, umask=0o077
    ) as proc:
        prefix = []
        try:
            connection, _ = server.accept()
            with connection, pin_process(proc.pid, **approval(executable)) as pinned:
                epoch = reserve_process_epoch(host, pinned, source_id=pair.first.source_id)
                accepted = bootstrap_round(connection, host, pinned, epoch, dispatch=dispatch)
                if delivery_state == "no-receiver":
                    server.close()
                elif delivery_state == "lost-bootstrap-acceptance":
                    receipt = issued(host).with_name("bootstrap-accepted.txt")
                    receipt.rename(receipt.with_suffix(".held"))
                proc.stdin.write("finish\n")
                proc.stdin.flush()
                if delivery_state != "no-receiver":
                    done, _ = server.accept()
                    with done:
                        if delivery_state == "lost-bootstrap-acceptance":
                            # Test barrier: exercise sent-but-rejected, not the
                            # different early-close/ambiguous-send race.
                            while True:
                                line = proc.stdout.readline()
                                assert line, "source exited before sending completion"
                                prefix.append(line)
                                if line.startswith("WRITER CLOSE sent_unconfirmed"):
                                    break
                            with pytest.raises(ValueError, match="durable bootstrap acceptance"):
                                completion.receive_stats_completion(done, host, pinned, epoch, accepted=accepted)
                        else:
                            received = completion.receive_stats_completion(done, host, pinned, epoch, accepted=accepted)
                            capture_root = tmp_path / "captured"
                            capture_root.mkdir(mode=0o700)
                            captured = capture_closed_stats(
                                host, pinned, epoch, accepted=accepted, completed=received,
                                source_directory=directory, capture_root=capture_root,
                            )
            stdout, stderr = proc.communicate("" if delivery_state == "no-receiver" else "receipt\n", timeout=10)
            stdout = "".join(prefix) + stdout
        finally:
            if not proc.stdin.closed:
                proc.stdin.close()
            proc.wait(timeout=10)
    assert proc.returncode == 0, stdout + stderr
    if delivery_state != "ok":
        assert not issued(host).with_name("stats-writer-closed.txt").exists()
        files = list(directory.glob("*.txt"))
        assert len(files) == 1 and files[0].stat().st_size == len(files[0].read_bytes()) > 0
        assert not list(directory.glob("*.complete.json"))
        assert (
            "WRITER CLOSE failed; closed stats retained"
            if delivery_state == "no-receiver"
            else "WRITER CLOSE sent_unconfirmed"
        ) in stdout
        print(f"COMPLETION {lua} {fault} {delivery_state}: source bytes retained, no host receipt/manifest")
        return
    assert "WRITER CLOSE sent_unconfirmed" in stdout
    records = [json.loads(line[8:]) for line in stdout.splitlines() if line.startswith("receipt ")]
    if configured_host:
        assert records == []  # Product sink, not the harness's ticket callback.
    else:
        assert len(records) == 1 and received.receipt() == records[0]["completion"]
    source = directory / received.filename
    raw = source.read_bytes()
    assert source.stat().st_size == received.size == len(raw)
    assert stats_header_identity(raw.splitlines(keepends=True)[0].decode()) == pair.first
    digest = hashlib.sha256(raw).hexdigest()
    assert subprocess.check_output(["sha256sum", str(source)], text=True).split()[0] == digest
    assert issued(host).with_name("stats-writer-closed.txt").read_text() == received.encode() + "\n"
    # Product code captured while the authenticated source was still pinned/live.
    assert captured.reference.sha256 == digest
    assert (captured.directory / received.filename).read_bytes() == raw
    assert subprocess.check_output(["sha256sum", str(captured.directory / received.filename)], text=True).split()[0] == digest
    assert inspect_completion_manifest(captured.directory, received.filename).status == "match"
    assert not list(directory.glob("*.complete.json"))
    print(
        f"COMPLETION {lua} {fault}: whole writer close -> native credentialed socket -> fsynced host receipt "
        "-> runtime host capture/sealed bytes -> completion manifest; ET APIs synthetic"
    )
