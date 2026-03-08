# Testing Standards

**Version:** 1.0
**Applies to:** All `gcp-pipeline-*` libraries and deployments
**Runtime:** Python 3.11 · pytest ≥ 7

---

## Core Principles

1. **Tests exist to prevent regressions, not to hit a coverage number.**
   Write tests that would catch a real bug. Delete tests that test nothing meaningful.

2. **Each test asserts one logical thing.**
   A test that asserts ten things is ten tests failing to tell you where the problem is.

3. **Tests must be order-independent.**
   Any test, in any order, must produce the same result. Global state mutations break this.

4. **Use real objects. Mock only at the boundary.**
   Mock external services (BigQuery, GCS, Pub/Sub). Do not mock classes you own.

---

## What to Mock — and What Not to

| Always mock | Never mock |
|-------------|-----------|
| `google.cloud.bigquery.Client` | Business logic you own |
| `google.cloud.storage.Client` | `apache_beam.DoFn` base class |
| `google.cloud.pubsub_v1.PublisherClient` | `EntitySchema`, `SchemaField` |
| Network calls, file I/O in unit tests | Python stdlib (`json`, `csv`, `datetime`) |

### Right: `unittest.mock.patch` scoped to a test or method

```python
from unittest.mock import patch, MagicMock

def test_writes_to_bq(self):
    with patch("gcp_pipeline_beam.pipelines.beam.io.bigquery.bigquery.Client") as mock_client:
        mock_client.return_value.insert_rows_json.return_value = []
        dofn = BatchWriteToBigQueryDoFn(project="p", dataset="d", table="t")
        list(dofn.process({"id": "1"}))
    mock_client.return_value.insert_rows_json.assert_called_once()
```

### Wrong: `sys.modules` patching at module level

```python
# NEVER do this — it leaks into every test that runs after this module is loaded
sys.modules["apache_beam"] = MagicMock()
```

This causes failure of unrelated tests depending on test collection order. It also hides
real import errors you should be fixing.

---

## Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Test file | `test_<module>.py` | `test_csv_parser.py` |
| Test class | `Test<Subject>` | `TestCSVParserConfig` |
| Test method | `test_<action>_<scenario>[_<expected>]` | `test_parse_missing_columns_strict_mode` |
| Fixture | Noun describing the thing it creates | `pii_schema`, `strict_config` |

---

## Fixture Design

- **One fixture, one responsibility.** A fixture that creates a schema should not also create a DoFn.
- **Name fixtures after what they represent**, not after the test that uses them.
- **Use `pytest.fixture` scope carefully:**
  - `scope="function"` (default): safest, always isolated
  - `scope="module"`: only for truly immutable, expensive objects (e.g., parsed schemas)
  - `scope="session"`: almost never needed in unit tests

```python
# Good — single responsibility, clearly named
@pytest.fixture
def pii_schema() -> EntitySchema:
    return EntitySchema(
        entity_name="test",
        system_id="sys",
        fields=[SchemaField(name="ssn", field_type="STRING", is_pii=True, pii_type="SSN")],
        primary_key=["id"],
    )

# Bad — fixture doing too much
@pytest.fixture
def everything():
    schema = EntitySchema(...)
    dofn = MaskPIIDoFn(schema)
    dofn.setup()
    record = {"ssn": "123456789"}
    return dofn, record, schema   # What does the test actually need?
```

---

## Testing Beam DoFns

DoFns can be tested directly by calling `.process()` — no full pipeline needed for unit tests.
Use `TestPipeline` only for integration tests that verify the full DAG wiring.

```python
# Unit test — fast, no pipeline overhead
def test_masking(pii_schema):
    dofn = MaskPIIDoFn(pii_schema)
    dofn.setup()  # Call setup() as Beam would
    (result,) = dofn.process({"ssn": "123456789"})
    assert result["ssn"] == "XXX-XX-6789"

# Integration test — verifies pipeline graph and tagged outputs
def test_parser_in_pipeline():
    config = CSVParserConfig(field_names=["id", "name"])
    with TestPipeline() as p:
        results = (
            p
            | beam.Create(["1,Alice", "2,Bob"])
            | beam.ParDo(RobustCsvParseDoFn(config))
        )
        assert_that(results, has_length(2))
```

### Tagged output testing pattern

```python
def test_invalid_record_routes_to_errors():
    config = CSVParserConfig(field_names=["id", "name"], strict_field_count=True)
    dofn = RobustCsvParseDoFn(config)

    results = list(dofn.process("only_one_field"))

    # Filter by tag
    errors = [r for r in results if hasattr(r, "tag") and r.tag == "errors"]
    assert len(errors) == 1
    assert errors[0].value["error_type"] == CSVErrorType.MISSING_COLUMNS.value
```

---

## What Makes a Good Test

```python
def test_ssn_exposes_last_four_digits(pii_schema):
    """
    Given a 9-digit SSN,
    When MaskPIIDoFn processes the record,
    Then the output format should be XXX-XX-<last4>.
    """
    dofn = _make_dofn(pii_schema)
    record = {"id": "1", "ssn": "123456789"}

    (result,) = dofn.process(record)

    assert result["ssn"] == "XXX-XX-6789"
```

What makes this good:
- **Docstring explains the scenario**, not what the code does
- **Arrange / Act / Assert** separated by blank lines
- **Single assertion** (the SSN format) — if it fails, you know exactly why
- **Uses a fixture** for the schema — test is focused on the assertion, not setup

---

## Anti-Patterns to Avoid

| Anti-pattern | Why it's wrong | Fix |
|-------------|----------------|-----|
| `sys.modules["apache_beam"] = MagicMock()` at module level | Pollutes all subsequent tests in the session | Import real beam; use `patch` scoped to the test |
| `assert len(results) > 0` | Vacuous — passes even if there are 100 unexpected records | Assert the exact count and check field values |
| Test with 10+ assertions | When it fails you don't know which one mattered | One logical assertion per test |
| `class TestEverything: pass` with 30 methods | Hides structure, hard to navigate | Group by scenario (`TestHappyPath`, `TestEdgeCases`, `TestErrorRouting`) |
| Mocking the class under test | Tests nothing real | Test real code; mock only dependencies |
| `time.sleep()` in tests | Flaky, slow | Use `freeze_time` or `patch` on `datetime` |

---

## Running Tests

```bash
# All libraries under Python 3.11
python3.11 -m pytest gcp-pipeline-libraries/gcp-pipeline-core/tests/ -v
python3.11 -m pytest gcp-pipeline-libraries/gcp-pipeline-beam/tests/ -v
python3.11 -m pytest gcp-pipeline-libraries/gcp-pipeline-tester/tests/ -v

# Single library, show coverage
cd gcp-pipeline-libraries/gcp-pipeline-core
python3.11 -m pytest tests/ --cov=src --cov-report=term-missing

# Run only tests matching a keyword
python3.11 -m pytest tests/ -k "pii or ssn"
```
