# Tests Package - CLAUDE.md

## Overview

Test suite for the ET:Legacy Statistics Bot.
Includes unit, security, parser, and Greatshot regression coverage.

## Directory Structure

```python
tests/
├── conftest.py                         # Shared pytest fixtures
├── security/test_security_validation.py
├── unit/                               # Core unit and regression tests
│   ├── test_database_adapter.py
│   ├── test_data_integrity.py
│   ├── test_round_contract.py
│   ├── test_greatshot_crossref.py
│   └── ...
├── test_community_stats_parser.py      # Parser regression coverage
├── test_greatshot_api_integration.py   # API integration smoke tests
└── fixtures/                           # Test data and fixtures
```text

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

Add to GitHub Actions:

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pip install pytest pytest-cov pytest-asyncio
      - run: pytest --cov=bot --cov-report=xml
```
