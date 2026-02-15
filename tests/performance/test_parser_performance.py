"""
Performance test: Stats parser throughput.

Verifies that the production parser can handle file parsing
within acceptable time bounds. Uses real fixture files to
measure parsing speed.
"""

import pytest
import time
from pathlib import Path

from bot.community_stats_parser import C0RNP0RN3StatsParser


FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "sample_stats_files"
LOCAL_STATS_DIR = Path(__file__).parent.parent.parent / "bot" / "local_stats"


class TestParserPerformance:
    """Benchmark the stats parser against real files."""

    @pytest.fixture
    def parser(self):
        return C0RNP0RN3StatsParser()

    def test_single_file_parse_under_one_second(self, parser):
        """A single stats file should parse in under 1 second."""
        filepath = FIXTURE_DIR / "2025-12-17-120000-goldrush-round-1.txt"
        if not filepath.exists():
            pytest.skip("Fixture file not found")

        start = time.monotonic()
        result = parser.parse_stats_file(str(filepath))
        elapsed = time.monotonic() - start

        assert result is not None
        assert elapsed < 1.0, f"Single file parse took {elapsed:.3f}s (limit: 1.0s)"

    @pytest.mark.slow
    def test_batch_parse_throughput(self, parser):
        """Parser should handle 50+ files in under 10 seconds."""
        if not LOCAL_STATS_DIR.exists():
            pytest.skip("local_stats directory not found")

        files = sorted(LOCAL_STATS_DIR.glob("*-round-1.txt"))[:50]
        if len(files) < 5:
            pytest.skip(f"Not enough stats files for throughput test ({len(files)} found)")

        start = time.monotonic()
        parsed_count = 0
        for filepath in files:
            result = parser.parse_stats_file(str(filepath))
            if result is not None:
                parsed_count += 1
        elapsed = time.monotonic() - start

        assert parsed_count > 0, "No files parsed successfully"
        assert elapsed < 10.0, \
            f"Batch parse of {len(files)} files took {elapsed:.3f}s (limit: 10.0s)"

    def test_parser_instantiation_is_fast(self):
        """Parser instantiation should be near-instant (< 50ms)."""
        start = time.monotonic()
        for _ in range(100):
            _ = C0RNP0RN3StatsParser()
        elapsed = time.monotonic() - start

        assert elapsed < 0.5, \
            f"100 parser instantiations took {elapsed:.3f}s (limit: 0.5s)"
