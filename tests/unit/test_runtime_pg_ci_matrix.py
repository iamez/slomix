"""Keep two required Python checks while proving paired PostgreSQL coverage."""

from pathlib import Path

import pytest
import yaml

from tests.integration.test_runtime_website_privileges_pg import assert_expected_pg_major


def test_ci_pairs_two_pinned_postgres_versions_without_expanding_jobs():
    workflow = yaml.safe_load((Path(__file__).resolve().parents[2] / ".github/workflows/tests.yml").read_text())
    assert set(workflow.get("on", workflow.get(True))) == {"push", "pull_request", "merge_group"}
    assert set(workflow["jobs"]) == {
        "python", "javascript", "react-frontend", "shellcheck", "lua", "security", "docker-build",
    }
    job = workflow["jobs"]["python"]
    assert job["name"] == "Python Lint + Tests (${{ matrix.python-version }})"
    matrix = job["strategy"]["matrix"]
    assert set(matrix) == {"include"}, "Extra matrix axes multiply CI jobs"
    assert matrix["include"] == [
        {
            "python-version": "3.11", "postgres-major": "14",
            "postgres-image": "postgres:14.15-alpine@sha256:9a437826bdf12bda56c491f27d06c024d05acef98715baa1bf93df263afe850b",
        },
        {
            "python-version": "3.13", "postgres-major": "17",
            "postgres-image": "postgres:17-alpine@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24",
        },
    ]
    assert job["services"]["postgres"]["image"] == "${{ matrix.postgres-image }}"
    step = next(step for step in job["steps"] if step.get("name") == "Run tests")
    assert step["env"]["RUNTIME_ACL_EXPECTED_PG_MAJOR"] == "${{ matrix.postgres-major }}"
    assert step["env"]["RUNTIME_EVENTS_TEST_CI"] == "true"


@pytest.mark.parametrize("expected,actual", [("14", 170000), ("17", 140024)])
def test_wrong_server_major_cannot_turn_coverage_into_skips(monkeypatch, expected, actual):
    monkeypatch.setenv("RUNTIME_EVENTS_TEST_CI", "true")
    monkeypatch.setenv("RUNTIME_ACL_EXPECTED_PG_MAJOR", expected)
    with pytest.raises(AssertionError, match="Expected PostgreSQL"):
        assert_expected_pg_major(actual)


def test_ci_major_required_but_local_major_optional(monkeypatch):
    monkeypatch.delenv("RUNTIME_ACL_EXPECTED_PG_MAJOR", raising=False)
    monkeypatch.setenv("RUNTIME_EVENTS_TEST_CI", "true")
    with pytest.raises(AssertionError, match="must declare"):
        assert_expected_pg_major(140024)
    monkeypatch.delenv("RUNTIME_EVENTS_TEST_CI")
    assert_expected_pg_major(140024)
    for major, version in (("14", 140024), ("17", 170000)):
        monkeypatch.setenv("RUNTIME_ACL_EXPECTED_PG_MAJOR", major)
        assert_expected_pg_major(version)
