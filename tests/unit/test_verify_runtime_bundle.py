"""Prepared unit files must match their contract before any installation."""
import json

import pytest

from scripts import dev_runtime_contract as contract
from scripts import verify_runtime_bundle as verifier
from tests.unit import test_dev_runtime_contract as contract_tests

inputs = contract_tests.inputs


@pytest.fixture
def bundle(inputs, tmp_path):
    output = tmp_path / "prepared"
    contract.prepare(output, **inputs)
    return output


def test_actual_prepared_bundle_passes_without_readiness_claim(bundle):
    result = verifier.verify_bundle(bundle)
    assert result["status"] == "prepared_bundle_verified_not_installed"
    assert result["ready_for_activation"] is False
    assert len(result["bundle_sha256"]) == 3
    assert "database_schema" in result["not_checked"]


@pytest.mark.parametrize("role", ["bot", "web"])
def test_unit_bytes_cannot_drift_while_json_is_valid(bundle, role):
    path = bundle / f"etlegacy-{role}.service"
    path.write_text(path.read_text().replace("ProtectSystem=strict", "ProtectSystem=false"))
    # Reproduce the gap: old contract-only validation cannot see this change.
    assert contract.load_contract(bundle / "contract.json")["revision"] == "a" * 40
    with pytest.raises(ValueError, match="service bytes differ"):
        verifier.verify_bundle(bundle)


@pytest.mark.parametrize("damage", ["extra", "missing", "symlink", "directory", "oversized", "contract"])
def test_invalid_bundle_refused(bundle, tmp_path, damage):
    path = bundle / "etlegacy-web.service"
    if damage == "extra":
        (bundle / "unreviewed.service").write_text("[Service]\n")
    elif damage == "oversized":
        path.write_bytes(b"x" * 65537)
    elif damage == "contract":
        (bundle / "contract.json").write_text("invalid-json-secret-sentinel")
    else:
        archived = tmp_path / "saved-unit"
        path.rename(archived)
        if damage == "symlink":
            path.symlink_to(archived)
        elif damage == "directory":
            path.mkdir()
    with pytest.raises(ValueError):
        verifier.verify_bundle(bundle)


def test_change_during_observation_is_refused(bundle, monkeypatch):
    original = verifier.file_hash
    seen = 0
    def changing_hash(path):
        nonlocal seen
        seen += 1
        return original(path) if seen <= 3 else "0" * 64
    monkeypatch.setattr(verifier, "file_hash", changing_hash)
    with pytest.raises(ValueError, match="changed during"):
        verifier.verify_bundle(bundle)


def test_cli_refusal_does_not_echo_untrusted_config(bundle, capsys):
    (bundle / "contract.json").write_text("secret-sentinel")
    assert verifier.main(["--directory", str(bundle)]) == 1
    output = capsys.readouterr().out
    assert "secret-sentinel" not in output
    assert json.loads(output)["ready_for_activation"] is False
