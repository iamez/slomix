"""Compare an intact built package with two exact local Git commits, read-only.

This preserves the original build SHA after a squash merge. It does not query
GitHub, authorize promotion, reproduce dependencies or certify runtime readiness.
Run this trusted checkout's verifier, never code supplied by the inspected package.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.prepare_runtime_release import EXPLICIT, included  # noqa: E402
from scripts.spa_artifact import MANIFEST as BUILD_MANIFEST  # noqa: E402
from scripts.spa_artifact import TARGETS, output_hashes  # noqa: E402
from shared.release_manifest import MANIFEST, file_hash, verify_release  # noqa: E402


def git(repository: Path, *args: str) -> bytes:
    return subprocess.check_output(
        ['/usr/bin/git', '-C', str(repository), *args],
        env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C', 'GIT_NO_REPLACE_OBJECTS': '1',
             'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
             'GIT_OPTIONAL_LOCKS': '0'}, stderr=subprocess.DEVNULL, timeout=30,
    )


def commit_tree(repository: Path, revision: str) -> str:
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Full immutable commit SHA required')
    actual = git(repository, 'rev-parse', '--verify', revision + '^{commit}').decode().strip()
    if actual != revision:
        raise ValueError('Expected an exact commit object')
    return git(repository, 'rev-parse', '--verify', revision + '^{tree}').decode().strip()


def verify_source(repository: Path, release: Path, expected_source: str,
                  accepted_commit: str, expected_manifest_sha256: str) -> dict:
    if not re.fullmatch(r'[0-9a-f]{64}', expected_manifest_sha256):
        raise ValueError('Pinned manifest SHA256 required')
    marker = release / MANIFEST
    if file_hash(marker) != expected_manifest_sha256:
        raise ValueError('Release manifest differs from reviewed fingerprint')
    record = verify_release(release)
    if record['version'] != 2:
        raise ValueError('Mode-verified release manifest version 2 required')
    if record['source_commit'] != expected_source:
        raise ValueError('Original package source SHA differs')
    tree = commit_tree(repository, expected_source)
    if commit_tree(repository, accepted_commit) != tree:
        raise ValueError('Accepted and original source trees differ')
    entries = {}
    for entry in git(repository, 'ls-tree', '-r', '-z', expected_source).split(b'\0'):
        if entry:
            metadata, name = entry.split(b'\t', 1)
            entries[name.decode('utf-8')] = metadata.split()
    selected = {name for name in entries if included(name)}
    if not selected >= EXPLICIT:
        raise ValueError('Source lacks required runtime payload')
    for name in selected:
        mode, kind, object_id = entries[name]
        if kind != b'blob' or mode not in (b'100644', b'100755'):
            raise ValueError('Runtime source must be regular Git blobs')
        payload = (release / name).read_bytes()
        # SHA1 here is Git object identity, not the security/integrity fingerprint.
        blob = hashlib.sha1(b'blob ' + str(len(payload)).encode() + b'\0' + payload,
                            usedforsecurity=False).hexdigest().encode()
        if blob != object_id or (release / name).stat().st_mode & 0o777 != int(mode, 8) & 0o777:
            raise ValueError('Packaged source differs from committed blob or mode')
    expected_files = set(selected)
    builds = {}
    for kind, (directory, _) in TARGETS.items():
        build = json.loads((release / directory / BUILD_MANIFEST).read_text())
        if (build.get('version') != 1 or build.get('kind', 'app') != kind
                or build.get('source_commit') != expected_source
                or build.get('outputs') != output_hashes(release / directory, kind)):
            raise ValueError('Frontend output provenance differs from original build')
        expected_files.add(str(directory / BUILD_MANIFEST))
        expected_files.update(str(directory / name) for name in build['outputs'])
        builds[kind] = len(build['outputs'])
    if set(record['files']) != expected_files:
        raise ValueError('Package inventory differs from source and frontend outputs')
    if file_hash(marker) != expected_manifest_sha256 or verify_release(release) != record:
        raise ValueError('Package changed during verification')
    return {'status': 'package_source_verified_not_activated',
            'source_commit': expected_source, 'accepted_commit': accepted_commit,
            'tree': tree, 'manifest_sha256': expected_manifest_sha256,
            'source_files': len(selected), 'frontend_outputs': builds,
            'ready_for_activation': False,
            'not_checked': ['github_merge_authority', 'frontend_build_reproduction',
                            'frontend_input_provenance',
                            'dependency_reproduction', 'database_and_writer_handover',
                            'installed_units', 'runtime_acceptance']}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--release', type=Path, required=True)
    parser.add_argument('--expected-source', required=True)
    parser.add_argument('--accepted-commit', required=True)
    parser.add_argument('--expected-manifest-sha256', required=True)
    args = parser.parse_args(argv)
    try:
        report = verify_source(args.repository, args.release, args.expected_source,
                               args.accepted_commit, args.expected_manifest_sha256)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print(json.dumps({'status': 'refused', 'ready_for_activation': False,
                          'error': 'Package source verification failed'}))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
