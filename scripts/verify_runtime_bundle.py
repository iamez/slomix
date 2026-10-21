"""Read-only prepared DEV bundle check; never installs or starts anything.

The JSON contract alone does not cover edited .service siblings. Compare their
actual bytes with the verified contract before handing them to an operator.
This is a point-in-time integrity check, not a signature or activation gate.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.dev_runtime_contract import canonical, load_contract, render_unit  # noqa: E402
from shared.release_manifest import file_hash  # noqa: E402


def verify_bundle(directory: Path) -> dict:
    directory = canonical(directory)
    expected = {"contract.json", "etlegacy-bot.service", "etlegacy-web.service"}
    if not directory.is_dir() or {path.name for path in directory.iterdir()} != expected:
        raise ValueError("Expected only the prepared DEV contract and two service files")
    for name in expected:
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
            raise ValueError("Invalid prepared bundle file")
    before = {name: file_hash(directory / name) for name in sorted(expected)}
    contract = load_contract(directory / "contract.json")
    for name, specification in contract["services"].items():
        if (directory / f"{name}.service").read_bytes() != render_unit(name, specification).encode("utf-8"):
            raise ValueError("Prepared service bytes differ from verified contract")
    after = {name: file_hash(directory / name) for name in sorted(expected)}
    if before != after or load_contract(directory / "contract.json") != contract:
        raise ValueError("Prepared bundle changed during inspection")
    return {"status": "prepared_bundle_verified_not_installed", "revision": contract["revision"],
            "bundle_sha256": after, "ready_for_activation": False,
            "not_checked": ["installed_units_and_dropins", "privileged_install_access",
                            "database_schema", "quiesced_backup_and_state_delta",
                            "network_policy", "external_login", "running_services"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(verify_bundle(args.directory), sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({"status": "refused", "ready_for_activation": False,
                          "error": "Invalid or changed prepared DEV bundle"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
