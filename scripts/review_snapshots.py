#!/usr/bin/env python3
"""Immutable review vehicles. No checkout, fetch, force push or hook bypass.

The caller supplies area pathspecs. Every invocation pins both commits once,
preflights the entire selection, and uses a private index to construct trees.
Historical review refs are never touched. Existing content conflicts fail closed.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import tempfile
from pathlib import Path

MAX_FILES = 25
REVIEWER_FILES = 500
MAX_LINES = 8000


def git(*args, data=None, env=None):
    return subprocess.check_output(["git", *args], input=data, env=env)


def oid(ref):
    return git("rev-parse", "--verify", f"{ref}^{{commit}}").decode().strip()


def partition(base, source, areas, exclusions):
    """Split at file boundaries; unsupported/oversize files block all writes."""
    result = []
    for area in areas:
        name, specs = area.split("|", 1)
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9-]*", name):
            raise ValueError("invalid area name")
        records = git("diff", "--no-ext-diff", "--no-textconv", "--no-renames",
                      "--numstat", "-z", base, source, "--", *specs.split(),
                      *exclusions).split(b"\0")
        chunks, current, total = [], [], 0
        for record in filter(None, records):
            added, removed, path = record.split(b"\t", 2)
            if added == b"-" or removed == b"-":
                raise ValueError(f"binary file needs separate review: {os.fsdecode(path)!r}")
            lines = int(added) + int(removed)
            if lines > MAX_LINES:
                raise ValueError(f"single file exceeds {MAX_LINES} lines: {os.fsdecode(path)!r}")
            if current and (len(current) >= min(MAX_FILES, REVIEWER_FILES)
                            or total + lines > MAX_LINES):
                chunks.append((current, total))
                current, total = [], 0
            current.append(path)
            total += lines
        if current:
            chunks.append((current, total))
        for number, (paths, lines) in enumerate(chunks, 1):
            result.append((f"{name}-p{number:03}", paths, lines))
    return result


def snapshot(base, source, paths, name):
    # No working tree is created or changed. Missing private index is intentional.
    with tempfile.TemporaryDirectory(prefix="slomix-review-index-") as directory:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(directory) / "index"))
        git("read-tree", source, env=env)
        for path in paths:
            git("update-index", "-z", "--index-info",
                data=b"0 " + b"0" * len(source) + b"\t" + path + b"\0", env=env)
        for path in paths:
            literal = ":(literal)" + os.fsdecode(path)
            entry = git("ls-tree", "-z", base, "--", literal)
            if entry:
                mode_type_oid, recorded = entry.rstrip(b"\0").split(b"\t", 1)
                mode, _, blob = mode_type_oid.split()
                update = mode + b" " + blob + b"\t" + recorded + b"\0"
                git("update-index", "-z", "--index-info", data=update, env=env)
        tree = git("write-tree", env=env).decode().strip()
    date = git("show", "-s", "--format=%cI", source).decode().strip()
    env = dict(os.environ, GIT_AUTHOR_NAME="Review snapshot",
               GIT_AUTHOR_EMAIL="review@invalid", GIT_COMMITTER_NAME="Review snapshot",
               GIT_COMMITTER_EMAIL="review@invalid", GIT_AUTHOR_DATE=date,
               GIT_COMMITTER_DATE=date)
    def commit(tree, parent, kind):
        return git("commit-tree", tree, "-p", parent, "-m",
                   f"review: {name} {kind} (NEVER MERGE)\n\nSource: {source}\nBaseline: {base}",
                   env=env).decode().strip()
    review_base = commit(tree, source, "base")
    source_tree = git("rev-parse", f"{source}^{{tree}}").decode().strip()
    review_head = commit(source_tree, review_base, "head")
    version = f"v2-{source}-{base}"
    return {f"refs/heads/review-base/{version}/{name}": review_base,
            f"refs/heads/review/{version}/{name}": review_head}


def existing_refs():
    return {ref: sha for sha, ref in
            (line.split() for line in git("show-ref", "--heads").decode().splitlines())}


def assert_compatible(expected, existing):
    for ref, sha in expected.items():
        if ref in existing and existing[ref] != sha:
            raise ValueError(f"immutable snapshot conflict: {ref}; no refs updated")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="v1.39.0")
    parser.add_argument("--source", default="origin/main")
    parser.add_argument("--area", action="append", required=True)
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("command", choices=["measure", "cut", "prs"], nargs="?", default="measure")
    parser.add_argument("--push", action="store_true")
    args = parser.parse_args()
    if args.push and args.command != "cut":
        parser.error("--push requires cut")
    if args.command == "prs":
        parser.error("automatic PR creation retired; use printed immutable base/head refs for new draft NEVER MERGE PRs")
    base, source = oid(args.base), oid(args.source)
    chunks = partition(base, source, args.area, args.exclude)
    print(f"source={source} baseline={base}; excluded pathspecs={args.exclude!r}")
    for name, paths, lines in chunks:
        print(f"{name}: files={len(paths)} lines={lines}")
    if args.command == "measure":
        return
    refs = {}
    for name, paths, _ in chunks:
        refs.update(snapshot(base, source, paths, name))
    existing = existing_refs()
    assert_compatible(refs, existing)
    remote = {}
    if args.push and refs:
        remote = {ref: sha for sha, ref in
                  (line.split() for line in git("ls-remote", "--heads", "origin").decode().splitlines())}
        assert_compatible(refs, remote)
    creates = [f"create {ref} {sha}" for ref, sha in refs.items() if ref not in existing]
    if creates:
        git("update-ref", "--stdin", data=("start\n" + "\n".join(creates)
            + "\nprepare\ncommit\n").encode())
    for ref, sha in refs.items():
        print(f"{ref} {sha}")
    # One atomic push per pair: real hooks see at most 25 changed files per ref.
    # Hook rejection (including historical scanner hits) is a blocker, not a bypass.
    if args.push:
        ordered = list(refs)
        for offset in range(0, len(ordered), 2):
            missing = [ref for ref in ordered[offset:offset + 2] if ref not in remote]
            if missing:
                git("push", "--atomic", "origin", *[f"{refs[ref]}:{ref}" for ref in missing])


if __name__ == "__main__":
    try:
        main()
    except (ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"review snapshots blocked: {error}") from error
