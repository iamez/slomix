# Tests Package - CLAUDE.md

## Overview

Test suite for the ET:Legacy Statistics Bot.
Currently focused on security testing, with room for expansion.

## Directory Structure

```python
tests/
├── __init__.py
├── conftest.py              # Pytest fixtures (if exists)
├── unit/                    # Unit tests
│   └── test_database_adapter.py
├── integration/             # Integration tests
│   └── (empty)
├── security/                # Security tests
│   └── test_security_validation.py
├── e2e/                     # End-to-end tests
│   └── (empty)
├── performance/             # Performance tests
│   └── (empty)
└── fixtures/                # Test data
    └── sample_stats_files/
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

## Existing Tests

### Security Tests (`tests/security/`)

| Test | Purpose |
|------|---------|
| `test_webhook_id_validation` | Validates webhook ID format |
| `test_filename_format` | Validates stats filename format |
| `test_sql_injection_prevention` | Tests SQL parameter escaping |

## Test Gaps (To Be Created)

### Data Integrity Tests (HIGH PRIORITY)

```python
# tests/unit/test_data_integrity.py
def test_headshot_kills_not_exceed_kills():
    """headshot_kills should never exceed kills"""

def test_time_dead_not_exceed_played():
    """time_dead should never exceed time_played"""

def test_dpm_calculation_accuracy():
    """DPM = damage_given / (time_played_seconds / 60)"""
```text

### Parser Tests

```python
# tests/unit/test_parser.py
def test_r2_differential_calculation():
    """R2_only = R2_cumulative - R1"""

def test_midnight_crossover():
    """R1 at 23:55, R2 at 00:10 next day"""

def test_same_map_twice():
    """Same map played twice in session"""
```text

### Session Tests

```python
# tests/unit/test_sessions.py
def test_60_minute_session_gap():
    """Rounds 60+ min apart = new session"""

def test_session_id_consistency():
    """Same session_id for continuous play"""
```text

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
