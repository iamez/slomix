"""The datapoint ledger — field-level coverage of the new SPA, held as a ratchet.

The endpoint ratchet (tests/data/endpoint_gap.txt) cannot see a page that
calls an endpoint and prints one field of it; the 2026-09-07 audits found
hundreds of response keys fetched and never read (the profile's lifetime
counters, aim statistics, storytelling sub-metrics, the live "tonight"
header). scripts/datapoint_ledger.py measures that from the recorded
fixtures; this test holds the result.

The ratchet is a SET, not a sum (Codex on #978: a change that reads one
key and adds another unread one leaves a count unchanged). Every unread
row is a line of docs/parity/datapoints_unread_baseline.txt; the script
only ever removes lines from it (`--rebase-baseline`), so:
- a new unread row fails here even after the ledger is regenerated;
- a row that became read fails here until the baseline drops it — the
  ratchet step, taken in the same commit.

Each property was seen failing before it was pinned.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "datapoint_ledger.py"
LEDGER = REPO / "docs" / "parity" / "datapoints.json"
DECISIONS = REPO / "docs" / "parity" / "datapoint_decisions.json"
BASELINE = REPO / "docs" / "parity" / "datapoints_unread_baseline.txt"


def _load_script():
    spec = importlib.util.spec_from_file_location("datapoint_ledger", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _baseline() -> set[str]:
    return {line for line in BASELINE.read_text(encoding="utf-8").splitlines() if line.strip()}


def test_the_committed_ledger_is_what_the_script_produces():
    mod = _load_script()
    fresh = mod.render(mod.build(mod.app_sources(), mod.load_decisions()))
    committed = LEDGER.read_text(encoding="utf-8")
    assert committed == fresh, (
        "docs/parity/datapoints.json is stale — a fixture, a page or a decision changed; "
        "run: python scripts/datapoint_ledger.py"
    )


def test_no_unread_row_outside_the_baseline_and_none_left_in_it_once_read():
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    mod = _load_script()
    unread = mod.unread_lines(ledger)
    baseline = _baseline()
    new = sorted(unread - baseline)
    assert not new, (
        "new unread datapoints — a fixture gained keys no page reads; read them on a page "
        "or record a decision with a reason, never add them to the baseline:\n" + "\n".join(new)
    )
    gone = sorted(baseline - unread)
    assert not gone, (
        "these baseline rows are read (or dropped) now — take the ratchet step: "
        "python scripts/datapoint_ledger.py --rebase-baseline\n" + "\n".join(gone)
    )


def test_every_decision_has_a_reason_and_a_real_key():
    decisions = json.loads(DECISIONS.read_text(encoding="utf-8"))
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    present = {f"{r['endpoint']} {r['key']}" for r in ledger["rows"]}
    for key, reason in decisions.items():
        if key.startswith("_"):
            continue
        assert isinstance(reason, str) and reason.strip(), f"decision without a reason: {key}"
        if key.endswith(".*"):
            assert any(p.startswith(key[:-1]) for p in present), f"decision names a sub-object no fixture carries: {key}"
        else:
            assert key in present, f"decision names a key no fixture carries: {key}"
    assert all(r["status"] in ("read", "unread", "dropped") for r in ledger["rows"])


def test_an_empty_recording_is_unmeasured_not_covered():
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert isinstance(ledger["unmeasured"], list)
    for path in ledger["unmeasured"]:
        assert path not in ledger["per_endpoint"], f"{path}: an empty recording must not count as a covered endpoint"


def test_a_key_nobody_reads_is_counted_and_is_outside_the_baseline(tmp_path, monkeypatch):
    """The mutation, kept as a test: a fixture key with no reader in src/app
    becomes an unread row, and that row is not in the baseline — which is
    exactly the failure the row test above would raise."""
    mod = _load_script()
    sources = mod.app_sources()
    fx_dir = tmp_path / "__fixtures__"
    fx_dir.mkdir()
    for f in mod.FIXTURES.glob("*.json"):
        (fx_dir / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    target = fx_dir / "api_stats_overview.json"
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["zz_field_no_page_reads_2026_09_08"] = 1
    target.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(mod, "FIXTURES", fx_dir)
    mutated = mod.unread_lines(mod.build(sources, mod.load_decisions()))
    row = "/api/stats/overview zz_field_no_page_reads_2026_09_08"
    assert row in mutated
    assert row not in _baseline()


def test_a_heterogeneous_list_yields_the_union_of_its_keys_and_an_id_table_is_one_map():
    mod = _load_script()
    keys = dict(mod.leaf_keys({"events": [{"t": 1, "kind": "a"}, {"t": 2, "kind": "b", "victim": "x"}]}))
    assert "events.victim" in keys, "a key only later elements carry must still be a row"
    keys = dict(mod.leaf_keys({"player_stats": {"vid": {"kills": 1, "deaths": 2}, "olz": {"kills": 3, "deaths": 4}, "qmr": {"kills": 0, "deaths": 1}}}))
    assert "player_stats.<map>" in keys and "player_stats.vid" not in keys, "nick-keyed tables are data, not fields"
    assert mod.leaf_keys([]) is None and mod.leaf_keys({}) is None


def test_a_reference_counts_only_inside_the_endpoint_scope():
    """Codex on #988/#990: one token set over src/app let a new panel that
    names `advanced` for ITS endpoint flip the profile's `advanced` row to
    read. A reference is evidence only in code that can hold the answer —
    the files calling the endpoint's hook and what they import."""
    mod = _load_script()
    real = mod.app_sources()
    key = "zz_scoped_probe_2026_09_08"
    fixture_key = ("/api/stats/overview", key)
    # 1. a file NOBODY imports names the key: still unread for /api/stats/overview
    sources = {**real, "pages/Stray.tsx": f"export function Stray(d) {{ return d.{key}; }}"}
    overview_scope = mod.scope_files("/api/stats/overview", sources)
    assert overview_scope is not None and "pages/Stray.tsx" not in overview_scope
    assert key in mod.referenced_names(sources["pages/Stray.tsx"])
    names_in_scope = mod.referenced_names("\n".join(sources[f] for f in sorted(overview_scope)))
    assert key not in names_in_scope
    # 2. the same line in a file the overview's caller imports: read
    caller = next(f for f in overview_scope if f.startswith("pages/") and "useOverview" in sources.get(f, "") or "'/api/stats/overview'" in sources.get(f, ""))
    sources2 = {**real, caller: real[caller] + f"\nexport const zz = (d) => d.{key};"}
    names2 = mod.referenced_names("\n".join(sources2[f] for f in sorted(mod.scope_files("/api/stats/overview", sources2))))
    assert key in names2


def test_every_measured_endpoint_has_a_scope_note_and_almost_none_fall_back_to_global():
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    for ep in ledger["per_endpoint"]:
        assert ep in ledger["scope"], f"{ep}: no scope note"
    global_ = [ep for ep, note in ledger["scope"].items() if note.startswith("global")]
    assert len(global_) <= 1, f"endpoints matched over the whole app (no caller found): {global_}"
