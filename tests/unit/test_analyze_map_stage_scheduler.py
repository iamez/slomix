"""S5 deterministic measurement and checkpoint contracts."""

import subprocess
from pathlib import Path

import pytest

from website.backend.map_geometry.stage_measurement import (
    FILTERED_CORPUS_SCOPE,
    FULL_CORPUS_SCOPE,
    MEASUREMENT_PROTOCOL,
    MeasurementCheckpoint,
    _semantic_value,
    checkpoint_metadata,
    content_hash,
    git_provenance,
    prepare_scout_reuse,
    reusable_seed_results,
    summarize_occurrences,
    validate_generated_artifact_paths,
    validate_measured_denominator,
)


def _metadata(**changes):
    values = {
        "git_head": "a" * 40,
        "clean_tree": True,
        "worktree_state_sha256": None,
        "asset_manifest": "b" * 64,
        "map_names": ("alpha", "beta"),
        "measurement_scope": FULL_CORPUS_SCOPE,
        "et_source_commit": "c" * 40,
        "work_limit": 64,
        "max_paths": 16,
    }
    values.update(changes)
    return checkpoint_metadata(**values)


def test_checkpoint_metadata_is_explicit_and_rejects_invalid_budgets():
    metadata = _metadata()

    assert metadata == {
        "protocol": MEASUREMENT_PROTOCOL,
        "git_head": "a" * 40,
        "clean_tree": True,
        "worktree_state_sha256": None,
        "asset_manifest_sha256": "b" * 64,
        "map_names": ["alpha", "beta"],
        "measurement_scope": FULL_CORPUS_SCOPE,
        "et_source_commit": "c" * 40,
        "work_limit": 64,
        "max_paths": 16,
    }
    with pytest.raises(ValueError, match="must be positive"):
        _metadata(work_limit=0)


def _git(repo: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments], cwd=repo, check=True, capture_output=True, text=True
    )


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Tests")
    (repo / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-m", "initial")
    return repo


def test_generated_artifacts_must_be_outside_repo_or_fully_ignored(tmp_path):
    repo = _git_repo(tmp_path)
    validate_generated_artifact_paths(repo, (tmp_path / "outside.sqlite3",))
    ignored = repo / "tmp" / "checkpoint.sqlite3"
    (repo / ".gitignore").write_text("/tmp/\n", encoding="utf-8")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-m", "ignore measurement artifacts")
    validate_generated_artifact_paths(
        repo,
        tuple(Path(f"{ignored}{suffix}") for suffix in ("", "-wal", "-shm", "-journal")),
    )
    with pytest.raises(ValueError, match="untracked and Git-ignored"):
        validate_generated_artifact_paths(repo, (repo / "unignored.json",))
    with pytest.raises(ValueError, match="untracked and Git-ignored"):
        validate_generated_artifact_paths(repo, (repo / "tracked.txt",))


def test_partial_checkpoint_ignore_does_not_hide_unignored_sidecars(tmp_path):
    repo = _git_repo(tmp_path)
    checkpoint = repo / "checkpoint.sqlite3"
    (repo / ".gitignore").write_text("/checkpoint.sqlite3\n", encoding="utf-8")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-m", "ignore only checkpoint base")
    with pytest.raises(ValueError, match="untracked and Git-ignored"):
        validate_generated_artifact_paths(repo, (checkpoint, Path(f"{checkpoint}-wal")))


def test_ignored_open_checkpoint_does_not_change_git_provenance(tmp_path):
    repo = _git_repo(tmp_path)
    (repo / ".gitignore").write_text("/tmp/\n", encoding="utf-8")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-m", "ignore measurement artifacts")
    checkpoint_path = repo / "tmp" / "checkpoint.sqlite3"
    before = git_provenance(repo)
    with MeasurementCheckpoint(checkpoint_path, _metadata()) as checkpoint:
        checkpoint.put_seed_result("seed", {"outcome": "resolved"})
        assert git_provenance(repo) == before
    with MeasurementCheckpoint(checkpoint_path, _metadata()) as checkpoint:
        assert checkpoint.seed_result("seed") == {"outcome": "resolved"}


def test_full_denominator_is_frozen_but_filtered_scope_accepts_subset():
    validate_measured_denominator(7, measurement_scope=FILTERED_CORPUS_SCOPE)
    validate_measured_denominator(452, measurement_scope=FULL_CORPUS_SCOPE)
    with pytest.raises(RuntimeError, match="drifted from 452"):
        validate_measured_denominator(451, measurement_scope=FULL_CORPUS_SCOPE)


def test_checkpoint_round_trips_results_and_refuses_metadata_drift(tmp_path):
    path = tmp_path / "checkpoint.sqlite3"
    with MeasurementCheckpoint(path, _metadata()) as checkpoint:
        checkpoint.put_seed_result("seed", {"outcome": "resolved", "reasons": {}})
        checkpoint.put_occurrence("occurrence", {"outcome": "resolved"})

    with MeasurementCheckpoint(path, _metadata()) as checkpoint:
        assert checkpoint.seed_result("seed") == {"outcome": "resolved", "reasons": {}}
        assert checkpoint.occurrence("occurrence") == {"outcome": "resolved"}

    with pytest.raises(ValueError, match="metadata does not match"):
        MeasurementCheckpoint(path, _metadata(work_limit=128))

    reuse_path = tmp_path / "reuse-checkpoint.sqlite3"
    reuse_identity = {**_metadata(), "scout_reuse": {"prior_work_limit": 32}}
    with MeasurementCheckpoint(reuse_path, reuse_identity):
        pass
    with pytest.raises(ValueError, match="metadata does not match"):
        MeasurementCheckpoint(reuse_path, _metadata())


def test_semantic_hash_is_mapping_order_invariant_and_rejects_absolute_paths():
    assert content_hash({"left": 1, "right": [2, 3]}) == content_hash(
        {"right": [2, 3], "left": 1}
    )
    with pytest.raises(ValueError, match="absolute paths"):
        _semantic_value(Path("/private/asset.pk3"))


def test_summary_retains_every_outcome_and_denominator():
    records = [
        {
            "occurrence_id": "a",
            "seed_id": "seed-a",
            "map_name": "alpha",
            "root_id": "root-a",
            "domains": ["dynamic_route"],
            "outcome": "resolved",
            "adaptation_reason": None,
            "scheduler_result": {"reasons": {}, "outcome": "resolved"},
        },
        {
            "occurrence_id": "b",
            "seed_id": "seed-b",
            "map_name": "alpha",
            "root_id": "root-b",
            "domains": [],
            "outcome": "skipped_empty_complete",
            "adaptation_reason": None,
            "scheduler_result": None,
        },
        {
            "occurrence_id": "c",
            "seed_id": "seed-c",
            "map_name": "beta",
            "root_id": "root-c",
            "domains": ["objective", "spawn"],
            "outcome": "adaptation_blocked",
            "adaptation_reason": "frontier_schedule_outer_dispatch_context_unresolved",
            "scheduler_result": None,
        },
    ]

    summary = summarize_occurrences(records)

    assert summary["measured_cross_frontiers"] == 3
    assert summary["outcomes"] == {
        "adaptation_blocked": 1,
        "resolved": 1,
        "skipped_empty_complete": 1,
    }
    assert summary["maps"] == {"alpha": 2, "beta": 1}
    assert summary["domain_sets"] == {
        "dynamic_route": 1,
        "none": 1,
        "objective+spawn": 1,
    }
    assert summary["adaptation_reasons"] == {
        "frontier_schedule_outer_dispatch_context_unresolved": 1,
    }


def test_scout_reuse_keeps_only_non_exhausted_seed_results():
    prior_metadata = _metadata(work_limit=64)
    publication = {
        "semantic": {
            **prior_metadata,
            "occurrences": [
                {
                    "seed_id": "complete",
                    "scheduler_result": {"outcome": "still_blocked", "reasons": {"known": 1}},
                },
                {
                    "seed_id": "exhausted",
                    "scheduler_result": {"outcome": "budget_exhausted", "reasons": {}},
                },
                {"seed_id": "skipped", "scheduler_result": None},
            ],
        }
    }
    publication["semantic_sha256"] = content_hash(publication["semantic"])

    reusable = reusable_seed_results(publication, _metadata(work_limit=128))

    assert reusable == {
        "complete": {"outcome": "still_blocked", "reasons": {"known": 1}},
    }
    with pytest.raises(ValueError, match="strictly higher"):
        reusable_seed_results(publication, _metadata(work_limit=64))
    with pytest.raises(ValueError, match="exact corpus"):
        reusable_seed_results(
            publication,
            _metadata(work_limit=128, asset_manifest="d" * 64),
        )

    reusable, evidence = prepare_scout_reuse(publication, _metadata(work_limit=128))
    assert reusable == {
        "complete": {"outcome": "still_blocked", "reasons": {"known": 1}},
    }
    assert evidence == {
        "prior_work_limit": 64,
        "prior_semantic_sha256": publication["semantic_sha256"],
        "reused_seed_count": 1,
    }

    publication["semantic_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="hash does not match"):
        prepare_scout_reuse(publication, _metadata(work_limit=128))
