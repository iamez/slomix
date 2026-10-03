#!/usr/bin/env python3
"""Immutable review vehicles. No checkout, fetch, ref overwrite or hook bypass.

The caller supplies area pathspecs. Every invocation pins both commits once,
preflights the entire selection, and uses a private index to construct trees.
Historical review refs are never touched. Existing content conflicts fail closed.
Remote publication creates complete absent pairs atomically; partial pairs are
rejected. Already complete pairs are observed only, not locked against other writers.
Remote command diagnostics are withheld because Git/hooks can echo credentials.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

MAX_FILES = 25
REVIEWER_FILES = 500
MAX_LINES = 8000


def git(*args, data=None, env=None):
    return subprocess.check_output(["git", *args], input=data, env=env)


def remote_git(command, *args):
    """Remote output (even on success) can contain credentials from its URL/hooks."""
    result = subprocess.run(["git", command, *args], capture_output=True)
    if result.returncode:
        raise ValueError(f"git {command} failed (exit {result.returncode}); "
                         "remote diagnostics withheld because they may contain credentials")
    return result.stdout


def oid(ref):
    return git("rev-parse", "--verify", f"{ref}^{{commit}}").decode().strip()


def partition(base, source, areas, exclusions):
    """Split at file boundaries; unsupported/oversize files block all writes."""
    if any(not exclusion_pathspec(spec) for spec in exclusions):
        raise ValueError("exclude requires an exclusion pathspec with a pattern")
    result = []
    names = set()
    for area in areas:
        name, specs = area.split("|", 1)
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9-]*", name):
            raise ValueError("invalid area name")
        if name in names:
            raise ValueError("duplicate area name")
        names.add(name)
        specs = specs.split()
        if not any(positive_pathspec(spec) for spec in specs):
            raise ValueError("area requires a positive pathspec")
        records = git("diff", "-O/dev/null", "--diff-algorithm=myers", "--no-ext-diff", "--no-textconv", "--no-renames",
                      "--numstat", "-z", base, source, "--", *specs,
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
        if not chunks:
            raise ValueError(f"area selects no changes: {name}")
        for number, (paths, lines) in enumerate(chunks, 1):
            result.append((f"{name}-p{number:03}", paths, lines))
    return result


def exclusion_pathspec(spec):
    """An exclusion option must never become an additional positive selection."""
    if spec.startswith(":("):
        magic, separator, pattern = spec[2:].partition(")")
        return bool(separator and pattern) and "exclude" in magic.split(",")
    if spec.startswith(":"):
        magic = re.match(r"[:/!^]*", spec).group()
        return len(spec) > len(magic) and ("!" in magic or "^" in magic)
    return False


def positive_pathspec(spec):
    """Recognize Git's long/short exclusion magic, not its pattern text."""
    if spec == ":":  # Git's special no-pathspec spelling selects everything.
        return False
    if spec.startswith(":("):
        magic, separator, pattern = spec[2:].partition(")")
        return bool(separator and pattern) and "exclude" not in magic.split(",")
    if spec.startswith(":"):
        magic = re.match(r"[:/!^]*", spec).group()
        return "!" not in magic and "^" not in magic and len(spec) > len(magic)
    return bool(spec)


def validate_snapshot(tree, source, paths):
    """Index D/F replacement can change unselected paths: verify actual trees."""
    records = git("diff", "-O/dev/null", "--diff-algorithm=myers", "--no-ext-diff", "--no-textconv", "--no-renames",
                  "--numstat", "-z", tree, source).split(b"\0")
    actual, lines = set(), 0
    for record in filter(None, records):
        added, removed, path = record.split(b"\t", 2)
        if added == b"-" or removed == b"-":
            raise ValueError("actual snapshot contains a binary change")
        actual.add(path)
        lines += int(added) + int(removed)
    if (actual != set(paths) or len(actual) > min(MAX_FILES, REVIEWER_FILES)
            or lines > MAX_LINES):
        raise ValueError("actual snapshot exceeds selected paths or review bounds; "
                         "regroup directory/file transitions into one bounded area")


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
                mode, kind, blob = mode_type_oid.split()
                if kind == b"tree":
                    continue  # D/F transition: restore its selected leaves instead.
                update = mode + b" " + blob + b"\t" + recorded + b"\0"
                git("update-index", "-z", "--index-info", data=update, env=env)
        tree = git("write-tree", env=env).decode().strip()
    validate_snapshot(tree, source, paths)
    date = git("show", "-O/dev/null", "-s", "--format=%cI", source).decode().strip()
    env = dict(os.environ, GIT_AUTHOR_NAME="Review snapshot",
               GIT_AUTHOR_EMAIL="review@invalid", GIT_COMMITTER_NAME="Review snapshot",
               GIT_COMMITTER_EMAIL="review@invalid", GIT_AUTHOR_DATE=date,
               GIT_COMMITTER_DATE=date)
    def commit(tree, parent, kind):
        return git("-c", "i18n.commitEncoding=UTF-8", "commit-tree", tree, "-p", parent, "-m",
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
            (line.split() for line in git("for-each-ref", "--format=%(objectname) %(refname)",
                                         "refs/heads").decode().splitlines())}


def push_destination():
    """Pin one actual destination; cross-remote atomicity is not supported."""
    urls = git("remote", "get-url", "--push", "--all", "origin").decode().splitlines()
    if len(urls) != 1 or not urls[0]:
        raise ValueError("snapshot publication requires exactly one push URL")
    return urls[0]


def assert_compatible(expected, existing):
    for ref, sha in expected.items():
        if ref in existing and existing[ref] != sha:
            raise ValueError(f"immutable snapshot conflict: {ref}; no refs updated")


def preflight_publication(refs, remote):
    """Run the bundled guard even in fresh clones with no installed Git hook.

    Feed the same create-only ref tuples the eventual push supplies. Check all
    pairs before publishing the first; normal Git hooks still run on each push.
    Diagnostics may quote prohibited content and must never reach the terminal.
    """
    updates = [f"{ref} {sha} {ref} {'0' * len(sha)}\n"
               for ref, sha in refs.items() if ref not in remote]
    if not updates:
        return
    # The shell guard's pipelines suppress scanner stderr; missing tools could
    # otherwise turn an unperformed inspection into a successful empty result.
    if any(shutil.which(tool) is None for tool in ("bash", "git", "grep", "head", "tr", "sort", "comm")):
        raise ValueError("repository publication guard requires all inspection tools")
    guard = Path(__file__).resolve().parent / "git-hooks" / "pre-push"
    # Guard diff failures are intentionally quiet. An inaccessible ambient
    # order file must not silently turn its changed-file set into an empty set.
    env = dict(os.environ)
    count = int(env.get("GIT_CONFIG_COUNT", "0"))
    env.update({"GIT_CONFIG_COUNT": str(count + 1),
                f"GIT_CONFIG_KEY_{count}": "diff.orderFile",
                f"GIT_CONFIG_VALUE_{count}": "/dev/null"})
    result = subprocess.run(["bash", str(guard)], input="".join(updates).encode(),
                            capture_output=True, env=env)
    if result.returncode:
        raise ValueError("repository publication guard failed; diagnostics withheld")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="v1.39.0")
    parser.add_argument("--source", default="origin/main")
    parser.add_argument("--area", action="append", required=True)
    parser.add_argument("--exclude", action="append", default=[],
                        help="explicit Git exclusion pathspec, e.g. ':!private/*'; plain paths are rejected")
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
        destination = push_destination()
        remote = {ref: sha for sha, ref in
                  (line.split() for line in remote_git("ls-remote", "--heads", "--", destination).decode().splitlines())}
        assert_compatible(refs, remote)
        ordered = list(refs)
        for offset in range(0, len(ordered), 2):
            pair = ordered[offset:offset + 2]
            if sum(ref in remote for ref in pair) == 1:
                # Git can elide a same-OID push, including its lease check.
                # Never complete a partial pair against an unchecked member.
                raise ValueError("partial remote snapshot pair; publication blocked")
        preflight_publication(refs, remote)
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
                # Empty expected values are create-only compare-and-swap, never
                # permission to overwrite. Preflight alone cannot exclude races.
                remote_git("push", "--atomic", *[f"--force-with-lease={ref}:" for ref in missing],
                    "--", destination, *[f"{refs[ref]}:{ref}" for ref in missing])


if __name__ == "__main__":
    try:
        main()
    except (ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"review snapshots blocked: {error}") from error
