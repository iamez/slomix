"""Shared output types for the demos pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = "1.0.0"


@dataclass
class DemoEvent:
    t_ms: int
    type: str
    attacker: str | None = None
    victim: str | None = None
    weapon: str | None = None
    hit_region: str | None = None
    team: str | None = None
    message: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "t_ms": int(self.t_ms),
            "type": self.type,
        }
        if self.attacker:
            payload["attacker"] = self.attacker
        if self.victim:
            payload["victim"] = self.victim
        if self.weapon:
            payload["weapon"] = self.weapon
        if self.hit_region:
            payload["hit_region"] = self.hit_region
        if self.team:
            payload["team"] = self.team
        if self.message:
            payload["message"] = self.message
        if self.meta:
            payload["meta"] = self.meta
        return payload


@dataclass
class Highlight:
    highlight_type: str
    player: str
    start_ms: int
    end_ms: int
    score: float
    explanation: str
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "type": self.highlight_type,
            "player": self.player,
            "start_ms": int(self.start_ms),
            "end_ms": int(self.end_ms),
            "score": float(self.score),
            "explanation": self.explanation,
        }
        if self.meta:
            payload["meta"] = self.meta
        return payload


@dataclass
class AnalysisResult:
    metadata: dict[str, Any]
    players: list[dict[str, Any]]
    timeline: list[DemoEvent]
    stats: dict[str, Any]
    highlights: list[Highlight] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    parser: dict[str, Any] = field(default_factory=dict)
    player_stats: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = {
            "schema_version": SCHEMA_VERSION,
            "metadata": self.metadata,
            "players": self.players,
            "stats": self.stats,
            "timeline": [event.to_dict() for event in self.timeline],
            "highlights": [highlight.to_dict() for highlight in self.highlights],
            "warnings": list(self.warnings),
            "parser": self.parser,
        }
        if self.player_stats:
            result["player_stats"] = self.player_stats
        return result
