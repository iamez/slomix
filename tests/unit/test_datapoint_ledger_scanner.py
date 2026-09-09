"""The ledger's caller scanner: a path literal inside a type union is not a
hook call (Codex on #1008 — the StoryPath union was credited to useSsr once
the hook above it was deleted)."""
from __future__ import annotations

import importlib.util
import pathlib

_SPEC = importlib.util.spec_from_file_location(
    "datapoint_ledger", pathlib.Path(__file__).resolve().parents[2] / "scripts" / "datapoint_ledger.py"
)
_LEDGER = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_LEDGER)


SOURCE = """
export function useSsr(guid: string) {
  return useQuery({ queryFn: () => apiGet('/api/skill/ssr', { guid }) });
}

type StoryPath =
  | '/api/storytelling/narrative'
  | '/api/storytelling/box-score';

export function useStoryBoxScore(gsid: number) {
  return useQuery({ queryFn: () => apiGet('/api/storytelling/box-score', { gsid }) });
}
"""


def test_a_literal_in_a_type_union_is_not_credited_to_the_hook_above_it():
    hooks, direct = _LEDGER._hooks_defining("/api/storytelling/box-score", {"lib/queries.ts": SOURCE})
    assert hooks == {"useStoryBoxScore"}
    assert direct == set()


def test_a_literal_only_in_the_union_has_no_caller():
    hooks, direct = _LEDGER._hooks_defining("/api/storytelling/narrative", {"lib/queries.ts": SOURCE})
    assert hooks == set()
    assert direct == set()


def test_a_real_call_after_a_closed_union_still_counts():
    hooks, _ = _LEDGER._hooks_defining("/api/skill/ssr", {"lib/queries.ts": SOURCE})
    assert hooks == {"useSsr"}
