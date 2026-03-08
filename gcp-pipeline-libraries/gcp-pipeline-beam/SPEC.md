# Specification: gcp-pipeline-beam

**Version:** 1.0
**Layer:** Ingestion — Apache Beam transforms, I/O, file management
**Dependency rule:** MAY import `gcp-pipeline-core` and `apache_beam`. MUST NOT import `apache_airflow`.

---

## Purpose

Apache Beam-based data ingestion for mainframe-to-GCP migrations. Provides:
- Fluent pipeline builder API (`BeamPipelineBuilder`)
- HDR/TRL file validation (mainframe header/trailer parsing)
- Schema-driven CSV parsing with full error routing
- GCS and BigQuery I/O DoFns
- Resource auto-configuration based on file size

---

## Boundary Rules

| Rule | Rationale |
|------|-----------|
| MUST NOT import `apache_airflow` | Separation of concerns |
| MUST NOT contain entity-specific field names or business rules | Generic; deployments add specifics |
| All DoFns MUST route errors to a tagged output, not raise | Beam error handling pattern |
| MUST NOT use `print()` | All output through `logging` |

---

## Module Contracts

### `BeamPipelineBuilder`

**Purpose:** Fluent, chainable API for constructing standard migration pipelines. Hides Beam boilerplate.

**Pattern:**
```python
result = (
    BeamPipelineBuilder("pipeline_name", run_id)
    .read_csv(["gs://bucket/file.csv"])
    .validate(validate_fn)
    .transform(transform_fn)
    .write_to_bigquery("dataset", "table")
    .run()
)
```

**Contract:**

| Method | Precondition | Postcondition |
|--------|-------------|---------------|
| `read_csv(gcs_paths, field_names=None)` | `gcs_paths` non-empty | Sets `current_pcoll`; `field_names=None` → `skip_header=True`; `field_names` provided → `skip_header=False` |
| `read_from_bigquery(query=None, dataset=None, table=None, sources=None)` | At least one source arg | Sets `current_pcoll` |
| `validate(validation_fn)` | `current_pcoll` set | Valid records → `current_pcoll`; invalid records silently routed to `invalid` output |
| `transform(transform_fn)` | `current_pcoll` set | Applies `transform_fn` to each record; returns builder |
| `write_to_bigquery(dataset, table)` | `current_pcoll` set | Success records → `current_pcoll`; failures → `error_pcoll` |
| `write_segmented_to_gcs(bucket, prefix, segment_size)` | `current_pcoll` set | Writes segments; failures → `error_pcoll` |
| `enrich_metadata(**extra)` | `current_pcoll` set | Adds `_run_id`, `_pipeline_name`, plus any extra fields to each record |
| `run()` | Pipeline constructed | Calls `pipeline.run()` and returns result |

**Test scenarios:**
- `read_csv` with `field_names=None` creates DoFn with `skip_header=True`
- `read_csv` with `field_names=['a','b']` creates DoFn with `skip_header=False`
- Chained `validate → transform → write_to_bigquery` builds valid pipeline graph
- `write_to_bigquery` populates `error_pcoll` for failed writes
- `_get_project()` failure returns `"unknown"` without raising

---

### `transforms.csv_parser` — CSVParserDoFn / CSVParserConfig

**Purpose:** Production-grade CSV parsing for mainframe files. Handles encoding issues, field count mismatches, delimiter detection, corruption.

**Contract:**

| Behaviour | Detail |
|-----------|--------|
| Valid record | Yielded to main output as `Dict[str, str]` |
| Field count mismatch | Routed to `'errors'` tagged output; never dropped silently |
| Null bytes / control characters | Cleaned or routed to errors |
| Delimiter auto-detection | Tried when `delimiter` is ambiguous |
| Metrics | `valid_count`, `error_count`, `corruption_count` incremented per worker |

**CSVParserConfig contract:**
- `field_names` must be non-empty
- `delimiter` and `alternative_delimiters` must not overlap
- `max_field_length` must be > 0

**Test scenarios:**
- Well-formed CSV row → dict with all fields
- Row with extra columns → routed to `'errors'` output
- Row with missing columns → routed to `'errors'` output
- Row with null bytes → cleaned and routed or error based on config
- Encoding detection falls back to `latin-1` when UTF-8 fails
- Error output record contains `raw_line`, `error_type`, `field_name`

---

### `transforms.validators` — SchemaValidateRecordDoFn

**Purpose:** Validate records against an `EntitySchema`. Route invalid records to error output.

**Contract:**
- Valid records yielded to main output unchanged
- Invalid records yielded to `'invalid'` tagged output with `validation_errors` list
- MUST NOT drop records silently
- `required` field missing → validation error
- `allowed_values` violation → validation error
- `max_length` exceeded → validation error

**Test scenarios:**
- Record missing required field → routed to `'invalid'`
- Record with value not in `allowed_values` → routed to `'invalid'`
- Fully valid record → routed to main output
- Multiple violations → all captured in `validation_errors` list

---

### `io.gcs` — ReadCSVFromGCSDoFn / ReadFromGCSDoFn

**Contract:**

| DoFn | Input | Output |
|------|-------|--------|
| `ReadFromGCSDoFn` | GCS path string | One `str` per line |
| `ReadCSVFromGCSDoFn(skip_header=True)` | GCS path string | One `Dict[str,str]` per data row |
| `WriteToGCSDoFn` | `(path, content)` | Writes file; yields path on success |

- `skip_header=True` → first row of file is skipped
- `skip_header=False` → all rows yielded (caller supplied field names)
- GCS errors are caught, logged, and re-raised (not silently swallowed)

---

### `io.bigquery` — BatchWriteToBigQueryDoFn

**Contract:**
- Accumulates records in buffer up to `batch_size`
- Flushes on `finish_bundle()`
- BigQuery insert failures routed to `'errors'` output, not raised
- Adds `_run_id` to every inserted row

**Test scenarios:**
- Batch of 1000 records → single BQ insert call
- BQ insert error → records routed to `'errors'`, main pipeline continues
- `finish_bundle()` flushes partial batch

---

### `io.bigquery_retry` — ResilientWriteToBigQueryDoFn

**Purpose:** Extends `WriteToBigQueryDoFn` with explicit retry logic for transient BQ errors.

**Contract:**
- Retries on `RATE_LIMIT`, `QUOTA_EXCEEDED`, `SERVER_ERROR` error types
- Does NOT retry on `SCHEMA_MISMATCH`, `AUTH_ERROR` (non-retryable)
- Uses exponential backoff between retries
- Exhausted retries → routed to `'errors'` output

---

### `file_management.hdr_trl` — HDRTRLParser

**Purpose:** Parse mainframe-style header and trailer records to extract record counts and metadata.

**Contract:**
- `parse_header(line)` → `HeaderRecord` or raises `ParseError`
- `parse_trailer(line)` → `TrailerRecord` with `record_count: int`
- Supports configurable regex patterns via `HDRTRLConfig`
- Regex patterns MUST be validated on `HDRTRLConfig` construction

**Test scenarios:**
- Standard header line → `HeaderRecord` with correct fields
- Standard trailer line → `TrailerRecord` with correct `record_count`
- Malformed line → raises `ParseError`
- Custom regex pattern → correctly parsed

---

### `resource_config` — ResourceConfigurator

**Purpose:** Recommend Dataflow worker config and Docker resources based on file size.

**Contract:**

| File size | Category | Machine type |
|-----------|----------|-------------|
| < 100 MB | SMALL | n1-standard-2 |
| 100 MB – 1 GB | MEDIUM | n1-standard-4 |
| 1 GB – 10 GB | LARGE | n1-highmem-8 |
| 10 GB – 100 GB | XLARGE | n1-highmem-16 |
| > 100 GB | SPLIT_REQUIRED | n1-highmem-32 |

- `get_recommendation_summary()` always returns a dict with `dataflow`, `docker`, `estimates`, `recommendations` keys
- Cost estimates are clearly marked as approximate
- `SPLIT_REQUIRED` category logs a `WARNING`

**Test scenarios:**
- 50 MB → SMALL category
- 500 MB → MEDIUM category
- 5000 MB → LARGE category
- 50000 MB → XLARGE category
- 200000 MB → SPLIT_REQUIRED category
- `categorize_file_size()` boundary values (exactly 100 MB → SMALL, 100.1 MB → MEDIUM)
