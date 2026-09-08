"""The datapoint ledger — field-level coverage of the new SPA, held as a ratchet.

The endpoint ratchet (tests/data/endpoint_gap.txt) cannot see a page that
calls an endpoint and prints one field of it; the 2026-09-07 audits found
hundreds of response keys fetched and never read (the profile's lifetime
counters, aim statistics, storytelling sub-metrics, the live "tonight"
header). scripts/datapoint_ledger.py measures that from the recorded
fixtures; this test holds the number and refuses allowances without a
reason.

Three properties, each seen failing before it was pinned:
- the committed ledger is what the script produces now (edit a fixture
  without regenerating and this fails with the script to run);
- the unread count is EXACTLY the budget — it may fall, and the budget is
  lowered in the same commit; a `<=` would let it grow back (the #823 lesson);
- every decision carries a reason and names a key a fixture really has.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "datapoint_ledger.py"
LEDGER = REPO / "docs" / "parity" / "datapoints.json"
DECISIONS = REPO / "docs" / "parity" / "datapoint_decisions.json"

# 358 unread of 2,577 keys over 133 endpoints on 2026-09-08 (main 4bc00b1f +
# the ratchet correction), after 45 decisions. Lower it in the commit that
# reads a key; never raise it — a new fixture key that no page reads is a
# datapoint captured and dropped, which is the thing this exists to show.
UNREAD_BUDGET = 358


def _load_script():
    spec = importlib.util.spec_from_file_location("datapoint_ledger", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_the_committed_ledger_is_what_the_script_produces():
    mod = _load_script()
    fresh = mod.render(mod.build(mod.app_sources(), mod.load_decisions()))
    committed = LEDGER.read_text(encoding="utf-8")
    assert committed == fresh, (
        "docs/parity/datapoints.json is stale — a fixture, a page or a decision changed; "
        "run: python scripts/datapoint_ledger.py"
    )


def test_unread_keys_sit_exactly_at_the_budget():
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    unread = ledger["summary"]["unread"]
    worst = sorted(ledger["per_endpoint"].items(), key=lambda kv: -kv[1]["unread"])[:5]
    assert unread == UNREAD_BUDGET, (
        f"unread datapoints rose to {unread}; read the new key on a page or record a decision with a reason "
        f"(worst: {worst})"
        if unread > UNREAD_BUDGET
        else f"unread datapoints are down to {unread} — lower UNREAD_BUDGET to {unread} in this commit"
    )


def test_every_decision_has_a_reason_and_a_real_key():
    mod = _load_script()
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
    # A decision only ever turns a row into `dropped`; it must never hide a row.
    assert all(r["status"] in ("read", "unread", "dropped") for r in ledger["rows"])
    assert mod.load_decisions()  # the file is read the way the script reads it


def test_a_key_nobody_reads_is_counted(tmp_path, monkeypatch):
    """The mutation, kept as a test: a fixture key with no reader in src/app
    raises the unread count by one."""
    mod = _load_script()
    sources = mod.app_sources()
    base = mod.build(sources, mod.load_decisions())["summary"]["unread"]
    fx_dir = tmp_path / "__fixtures__"
    fx_dir.mkdir()
    for f in mod.FIXTURES.glob("*.json"):
        (fx_dir / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    target = fx_dir / "api_stats_overview.json"
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["zz_field_no_page_reads_2026_09_08"] = 1
    target.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(mod, "FIXTURES", fx_dir)
    mutated = mod.build(sources, mod.load_decisions())["summary"]["unread"]
    assert mutated == base + 1
