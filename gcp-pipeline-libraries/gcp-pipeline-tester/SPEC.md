# Specification: gcp-pipeline-tester

**Version:** 1.0
**Layer:** Testing utilities — used in tests only, never in production pipeline code
**Dependency rule:** MAY import any library. MUST NOT be imported by production code.

---

## Purpose

Provide a standardised, GCP-free testing toolkit for pipeline developers:
- Mocks for GCS, BigQuery, Pub/Sub — no live GCP connections in unit tests
- Pytest fixtures for Beam, BigQuery, GCS test setups
- Fluent builders for test data (records, configs, pipelines)
- BDD-style scenario base classes
- Dual-run comparison for validating new pipeline vs legacy

---

## Design Principles

1. **GCP-free by default** — all tests must run without a GCP project or credentials
2. **Fast** — unit tests complete in seconds; no I/O to external systems
3. **Expressive** — test data builders read like plain English
4. **Composable** — fixtures are modular; combine freely

---

## Module Contracts

### `mocks.GCSClientMock`

**Purpose:** In-memory GCS simulation for unit tests.

**Contract:**

| Method | Postcondition |
|--------|--------------|
| `write_file(path, content)` | Content stored in-memory; path appears in `get_written_files()` |
| `get_written_files()` | Returns dict of all written files (path → content) |
| `open(path, mode)` | Returns file-like object for reading/writing |

**Test scenarios:**
- Write then retrieve via `get_written_files()` returns same content
- `get_written_files()` returns only files that were written
- `open()` provides file-like access to stored content

---

### `mocks.BigQueryClientMock`

**Purpose:** In-memory BigQuery simulation.

**Contract:**

| Method | Postcondition |
|--------|--------------|
| `insert_rows_json(table, rows)` | Rows retrievable via `get_inserted_rows()` |
| `get_inserted_rows()` | Returns all rows inserted across all tables |
| `query(sql)` | Returns rows from pre-configured result set |
| `get_table(table_ref)` | Returns table metadata |
| `create_table(table)` | Registers table in mock |
| `reset()` | Clears all tables and rows |

**Test scenarios:**
- Insert 5 rows → `len(get_inserted_rows())` returns 5
- `get_inserted_rows()` after no inserts returns empty list
- `reset()` clears all state

---

### `mocks.PubSubClientMock`

**Purpose:** In-memory Pub/Sub simulation.

**Contract:**

| Method | Postcondition |
|--------|--------------|
| `publish(topic, data, **attrs)` | Message retrievable via `get_published_messages()` |
| `get_published_messages()` | Returns list of all published messages in order |
| `pull(subscription, max_messages)` | Returns messages added via `add_message_to_subscription()` |
| `acknowledge(subscription, ack_ids)` | Messages removed from pending |
| `add_message_to_subscription(subscription, message)` | Message available for `pull()` |
| `subscribe(subscription, callback)` | Registers streaming pull callback |
| `topic_path(project, topic)` | Returns formatted topic path string |
| `subscription_path(project, subscription)` | Returns formatted subscription path string |
| `reset()` | Clears all messages and subscriptions |

---

### `fixtures`

**Purpose:** Pytest fixtures for common test setups. Import and use directly in test files.

**Available fixtures:**

| Fixture | Scope | Provides |
|---------|-------|---------|
| `gcs_client_mock` | function | `GCSClientMock` instance, reset per test |
| `bq_client_mock` | function | `BigQueryClientMock` instance, reset per test |
| `test_pipeline` | function | `TestPipeline` for running Beam transforms in tests |
| `sample_records` | function | List of sample data records |
| `sample_config_dict` | function | Sample configuration dictionary |

**Usage:**
```python
def test_my_pipeline(gcs_client_mock, bq_client_mock):
    gcs_client_mock.write_file("gs://my-bucket/input/data.csv", "col1,col2\nval1,val2")
    # ... run pipeline ...
    assert len(bq_client_mock.get_inserted_rows()) == 1
```

---

### `builders.RecordBuilder`

**Purpose:** Build test CSV and dict records with readable, fluent syntax.

**Contract:**

| Method | Postcondition |
|--------|--------------|
| `with_field(name, value)` | Field added to record |
| `with_fields(dict)` | All key-value pairs added |
| `build()` | Returns immutable dict; does not mutate builder |
| `build_csv_line(delimiter=',')` | Returns CSV-formatted string of all fields |
| `build_many(count)` | Returns list of `count` records with sequential IDs |

**Test scenarios:**
- `build()` returns correct dict
- `with_field` called twice with same name → second value wins
- `build_many(3)` returns 3 distinct records

---

### `builders.ConfigBuilder`

**Purpose:** Build `EntitySchema` and `PipelineConfig` objects for tests.

**Contract:**
- `with_field(name, type, required=False, is_pii=False)` → adds field
- `build_schema()` → returns `EntitySchema` with `entity_name="test_entity"`
- `with_pii_field(name, pii_type)` → adds field with `is_pii=True`

---

### `assertions`

**Purpose:** Higher-level assertions for pipeline outputs.

**Contract:**

| Function | Asserts |
|----------|---------|
| `assert_pcollection_equal(actual, expected)` | PCollection matches expected elements |
| `assert_record_structure(record, expected_fields)` | Record contains all expected fields |
| `assert_no_errors(error_handler)` | No errors were recorded |
| `assert_pipeline_success(audit_record)` | Pipeline audit record shows success |
| `assert_field_exists(record, field)` | Field is present in record |
| `assert_field_value(record, field, expected)` | Field has expected value |

---

### `base.BaseBeamTest`

**Purpose:** Base class for Beam unit tests. Manages `TestPipeline` lifecycle.

**Contract:**
- `setUp()` creates a fresh `TestPipeline`
- `tearDown()` calls `pipeline.run().wait_until_finish()`
- `assert_pcollection_equal(pcoll, expected)` wraps `assert_that`

**Test scenarios for the test base itself:**
- Beam pipeline runs without external dependencies
- Failed assertion in `assert_pcollection_equal` raises `AssertionError`

---

### `comparison.DualRunComparison`

**Purpose:** Run two pipeline implementations against the same input and compare outputs. Used to validate new implementations against legacy.

**Contract:**
- Both pipelines receive identical input
- `compare()` returns `ComparisonResult` with `match: bool`, `differences: List`
- Differences include record-level detail (which field, expected vs actual value)
- `match=True` only when all outputs are identical

**Test scenarios:**
- Identical outputs → `match=True`, empty differences
- One extra record in new pipeline → `match=False`, difference captured
- Field value differs → `match=False`, field name and values in difference

---

### `bdd` — BDD Scenario Tests

**Purpose:** Readable Given/When/Then test structure for end-to-end pipeline scenarios.

**Pattern:**
```python
class TestIngestionScenario(PipelineScenarioTest):
    def test_customer_file_processed(self):
        (self
         .given_a_file("gs://bucket/customers.csv", content=SAMPLE_CSV)
         .when_pipeline_runs()
         .then_bigquery_contains(table="customers", count=100)
         .then_no_errors())
```

**Contract:**
- `given_*` methods set up state; return `self` for chaining
- `when_pipeline_runs()` executes the pipeline under test
- `then_*` methods assert on outcomes; raise `AssertionError` on failure
- All GCP calls use mocks; no real GCP access
