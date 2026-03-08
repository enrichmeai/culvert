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

### `mocks.GCSMock`

**Purpose:** In-memory GCS simulation for unit tests.

**Contract:**

| Method | Postcondition |
|--------|--------------|
| `upload_blob(bucket, path, content)` | Content retrievable via `download_blob(bucket, path)` |
| `download_blob(bucket, path)` | Returns content previously uploaded; raises `NotFound` if absent |
| `list_blobs(bucket, prefix)` | Returns paths matching prefix |
| `delete_blob(bucket, path)` | Removes blob; subsequent `download_blob` raises `NotFound` |
| `blob_exists(bucket, path)` | Returns `True` iff blob was uploaded and not deleted |

**Test scenarios:**
- Upload then download returns same content
- Download of non-existent blob raises `NotFound`
- `list_blobs` returns only blobs under given prefix
- Delete removes blob; subsequent existence check returns `False`

---

### `mocks.BigQueryMock`

**Purpose:** In-memory BigQuery simulation.

**Contract:**

| Method | Postcondition |
|--------|--------------|
| `insert_rows(table, rows)` | Rows retrievable via `get_rows(table)` |
| `get_rows(table)` | Returns all rows inserted for table |
| `query(sql)` | Returns rows from pre-configured result set |
| `get_insert_count(table)` | Returns number of rows inserted |
| `reset()` | Clears all tables and rows |

**Test scenarios:**
- Insert 5 rows → `get_insert_count` returns 5
- `get_rows` with unknown table returns empty list
- `reset()` clears all state

---

### `mocks.PubSubMock`

**Purpose:** In-memory Pub/Sub simulation.

**Contract:**

| Method | Postcondition |
|--------|--------------|
| `publish(topic, message)` | Message retrievable via `get_messages(topic)` |
| `get_messages(topic)` | Returns list of published messages in order |
| `acknowledge(subscription, ack_ids)` | Messages removed from pending |
| `get_publish_count(topic)` | Returns number of messages published |

---

### `fixtures`

**Purpose:** Pytest fixtures for common test setups. Import and use directly in test files.

**Available fixtures:**

| Fixture | Scope | Provides |
|---------|-------|---------|
| `gcs_mock` | function | `GCSMock` instance, reset per test |
| `bq_mock` | function | `BigQueryMock` instance, reset per test |
| `pubsub_mock` | function | `PubSubMock` instance, reset per test |
| `beam_pipeline` | function | `TestPipeline` for running Beam transforms in tests |
| `run_id` | function | Unique `run_id` string per test |
| `test_project_id` | session | `"test-project"` constant |

**Usage:**
```python
def test_my_pipeline(gcs_mock, bq_mock, run_id):
    gcs_mock.upload_blob("my-bucket", "input/data.csv", b"col1,col2\nval1,val2")
    # ... run pipeline ...
    assert bq_mock.get_insert_count("my_table") == 1
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
| `assert_records_equal(actual, expected)` | Same records regardless of order |
| `assert_record_count(pcoll, expected_count)` | PCollection contains exactly N elements |
| `assert_no_errors(error_pcoll)` | Error PCollection is empty |
| `assert_bq_contains(bq_mock, table, expected_rows)` | BQ mock contains exactly these rows |

---

### `base.BeamTestCase`

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
