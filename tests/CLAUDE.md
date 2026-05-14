# Tests Package - CLAUDE.md

## Overview

Test suite for the ET:Legacy Statistics Bot.
Includes unit, security, parser, and Greatshot regression coverage.

## Directory Structure

```text
tests/
├── conftest.py                         # Shared pytest fixtures
├── security/                           # Security validation tests
│   └── test_security_validation.py
├── unit/                               # Core unit and regression tests (~170+ files)
│   ├── test_database_adapter.py
│   ├── test_data_integrity.py
│   ├── test_round_contract.py
│   ├── test_greatshot_crossref.py
│   └── ... (run `ls tests/unit/` for the full set)
├── integration/                        # Cross-module integration tests
├── e2e/                                # End-to-end pipeline tests
├── performance/                        # Performance/benchmark tests
├── smoke/                              # Smoke / quick-sanity tests
├── test_community_stats_parser.py      # Parser regression coverage
├── test_greatshot_*.py                 # Greatshot integration / scanner / upload regression
├── test_alias_fallback.py, test_simple_bulk_import.py
└── fixtures/                           # Test data and fixtures
```

## Running Tests

```bash
# All tests
pytest

# Specific directory
pytest tests/security/

# With coverage
pytest --cov=bot --cov-report=html

# Verbose output
pytest -v
```yaml

## Existing Coverage

### Security Tests (`tests/security/`)

| Test | Purpose |
|------|---------|
| `test_webhook_id_validation` | Validates webhook ID format |
| `test_filename_format` | Validates stats filename format |
| `test_sql_injection_prevention` | Tests SQL parameter escaping |

### High-Value Unit/Regression Tests (`tests/unit/`)

| Test | Purpose |
|------|---------|
| `test_data_integrity.py` | Caps/constraints and aggregation safety checks |
| `test_round_contract.py` | Round-contract storage invariants |
| `test_lua_round_teams_param_packing.py` | Lua webhook DB param-packing regression |
| `test_greatshot_crossref.py` | Greatshot cross-reference logic |
| `test_greatshot_router_crossref.py` | Greatshot API route behavior |

## Remaining Gaps

- Add true end-to-end suite covering bot startup + DB + command smoke tests.
- Add load/performance tests for high-frequency webhook and importer paths.
- Add CI matrix for both PostgreSQL-only and SQLite-fallback runtime modes.

## Writing New Tests

### Unit Test Template

```python
import pytest
from bot.core.database_adapter import DatabaseAdapter

class TestDatabaseAdapter:
    @pytest.fixture
    def adapter(self):
        # Create test adapter
        return DatabaseAdapter(test_config)

    async def test_fetch_all_returns_list(self, adapter):
        """fetch_all should return a list"""
        result = await adapter.fetch_all("SELECT 1")
        assert isinstance(result, list)

    async def test_parameterized_query(self, adapter):
        """Queries should use parameters safely"""
        result = await adapter.fetch_one(
            "SELECT ? as val",
            ("test'; DROP TABLE--",)
        )
        # Should not execute SQL injection
        assert result['val'] == "test'; DROP TABLE--"
```text

### Fixtures

```python
# tests/conftest.py
import pytest

@pytest.fixture
def sample_round_1_data():
    return {
        "kills": 15,
        "deaths": 5,
        "damage_given": 6000,
        "time_played_seconds": 600
    }

@pytest.fixture
def sample_stats_file():
    path = "tests/fixtures/sample_stats_files/round-1.txt"
    with open(path) as f:
        return f.read()
```text

## Test Data

Sample stats files should be placed in:

```text

tests/fixtures/sample_stats_files/
├── 2025-01-01-120000-oasis-round-1.txt
├── 2025-01-01-121500-oasis-round-2.txt
└── midnight_crossover/
    ├── 2025-01-01-235500-map-round-1.txt
    └── 2025-01-02-001000-map-round-2.txt

```bash

## CI/CD Integration

Tests run via [`.github/workflows/tests.yml`](../.github/workflows/tests.yml) on every push and PR against `main` / `develop`. The workflow:

- Spins up PostgreSQL 14 + Redis 7 service containers
- Installs `requirements.txt` (Python 3.11)
- Runs `ruff check`, the Python test suite, JS lint, file-hygiene checks, Docker build, CodeQL, and Codacy

The workflow file is the single source of truth — do not duplicate its content here, since the snippet would drift the moment CI changes. To see the current set of jobs and checks, open the file directly or check the "Actions" tab on a recent PR.
