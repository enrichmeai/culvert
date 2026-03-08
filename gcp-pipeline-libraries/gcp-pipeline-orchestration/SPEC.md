# Specification: gcp-pipeline-orchestration

**Version:** 1.0
**Layer:** Control — Airflow DAG creation, sensors, operators
**Dependency rule:** MAY import `gcp-pipeline-core` and `apache_airflow`. MUST NOT import `apache_beam`.

---

## Purpose

Reusable Airflow components for orchestrating data migration pipelines:
- `DAGFactory` — config-driven DAG creation
- `BasePubSubPullSensor` — event-driven file arrival detection
- `BaseDataflowOperator` — Dataflow job submission (Classic and Flex templates)
- Callback handlers — on-failure DLQ publishing, quarantine routing
- Entity dependency management — wait for all entities before transformation

---

## Boundary Rules

| Rule | Rationale |
|------|-----------|
| MUST NOT import `apache_beam` | Separation of concerns |
| MUST NOT contain record-level transform logic | That belongs in `gcp-pipeline-beam` |
| All Airflow imports MUST be guarded with `try/except ImportError` | Enables local testing without Airflow installed |
| MUST NOT use `print()` | All output through `logging` |
| MUST NOT hardcode project IDs, bucket names, or table names | Configuration via Airflow Variables |

---

## Module Contracts

### `factories.DAGFactory`

**Purpose:** Create standardised Airflow DAGs from config objects or dicts. Prevents duplicate DAG IDs and enforces common defaults.

**Contract:**

| Method | Precondition | Postcondition |
|--------|-------------|---------------|
| `create_dag(dag_id, ...)` | `dag_id` unique (not seen before in this factory) | Returns Airflow `DAG` instance with `owner`, `retries`, `retry_delay` defaults set |
| `create_dag_from_config(config)` | Valid `DAGConfig` | Returns configured `DAG`; validates config before creation |
| `create_dag_from_dict(config_dict)` | Dict with at least `dag_id` key | Parses and validates; returns `DAG` or raises `ValidationError` |
| `reset_created_dag_ids()` | — | Clears duplicate ID tracking; use in tests only |

**Default args (always applied unless overridden):**

| Arg | Default |
|-----|---------|
| `owner` | `'gdw'` |
| `depends_on_past` | `False` |
| `email_on_failure` | `True` |
| `retries` | `3` |
| `retry_delay` | `timedelta(minutes=5)` |

**Test scenarios:**
- `create_dag("my_dag")` returns an Airflow `DAG` with correct `dag_id`
- Calling `create_dag("my_dag")` twice raises `ValidationError` (duplicate ID)
- After `reset_created_dag_ids()`, same ID can be used again
- `create_dag_from_dict` with missing `dag_id` raises `ValidationError`
- Default `retry_delay` is a `timedelta`, not a string or `__import__` call
- `retry_delay` type is `datetime.timedelta` (not `int`)

---

### `sensors.BasePubSubPullSensor`

**Purpose:** Pull messages from a Pub/Sub subscription and filter by file extension. Pushes extracted file metadata to XCom.

**Contract:**

| Behaviour | Detail |
|-----------|--------|
| No messages | Returns `None`; does not raise |
| Messages but none match `filter_extension` | Returns `None`; logs at INFO |
| Matching messages found | Returns filtered list; pushes metadata to XCom under `metadata_xcom_key` |
| Metadata extraction error | Logs ERROR; does not raise; returns messages |

**XCom metadata schema (pushed by `_extract_metadata`):**

```python
{
    "gcs_path": str | None,
    "bucket": str | None,
    "object_id": str | None,
    "system_id": str | None,
    "entity_type": str | None,
    "event_type": str | None,
    "publish_time": str | None,
    "message_id": str | None,
}
```

**Test scenarios:**
- Messages with `.ok` extension, `filter_extension='.ok'` → returned
- Messages with `.csv` extension, `filter_extension='.ok'` → filtered out → returns `None`
- Empty message list → returns `None`
- Malformed message attributes → logs warning; message skipped; no exception
- `extract_metadata=False` → XCom push skipped
- `_extract_metadata` correctly constructs `gcs_path` from `bucketId` + `objectId` when `gcs_path` attribute absent

---

### `operators.BaseDataflowOperator`

**Purpose:** Submit Dataflow jobs (Classic template, Flex template, or Python). Abstracts source type and processing mode.

**Contract:**

| Method | Postcondition |
|--------|--------------|
| `_validate_configuration()` | Raises `ValueError` if GCS source and no `input_path`, or Pub/Sub source and no `input_subscription`, or no `output_table` |
| `_build_parameters(context)` | Returns dict with `outputTable`, `tempLocation`, `maxNumWorkers`, `workerMachineType` always; source-specific params added; routing metadata from XCom merged if available |
| `_get_job_name(context)` | Returns lowercase, hyphenated string matching `[a-z]([-a-z0-9]*[a-z0-9])?` |
| `execute(context)` | Calls `_validate_configuration()` before launching; delegates to Classic/Flex/Python based on mode |

**Processing mode routing:**

| `processing_mode` | `use_template` | Operator used |
|------------------|---------------|--------------|
| `batch` | `True` | `DataflowTemplatedJobStartOperator` |
| `streaming` | `True` | `DataflowStartFlexTemplateOperator` |
| any | `False` | `DataflowCreatePythonJobOperator` |

**Convenience subclasses:**
- `BatchDataflowOperator` — pre-configured `source_type='gcs'`, `processing_mode='batch'`
- `StreamingDataflowOperator` — pre-configured `source_type='pubsub'`, `processing_mode='streaming'`

**Test scenarios:**
- GCS source without `input_path` → `_validate_configuration()` raises `ValueError`
- Pub/Sub source without `input_subscription` → raises `ValueError`
- Missing `output_table` → raises `ValueError`
- `_get_job_name()` output matches `[a-z]([-a-z0-9]*[a-z0-9])?`
- Underscores in pipeline name → converted to hyphens in job name
- `_build_parameters()` with XCom metadata → `entityType` and `systemId` in params
- `_build_parameters()` with no XCom metadata → no error raised; params still valid

---

### `callbacks` — Error Callbacks

**Purpose:** Standardised on-failure Airflow callbacks that publish to DLQ or quarantine storage.

**Contract:**
- Failure callback MUST publish to Pub/Sub DLQ topic
- Callback MUST include `dag_id`, `task_id`, `run_id`, `execution_date`, `error_message`
- Callback failure MUST be logged; MUST NOT re-raise (prevents swallowing original failure)

**Test scenarios:**
- Failure callback publishes correct message to DLQ
- Pub/Sub publish failure logged; callback returns normally

---

### `dependency` — EntityDependencyChecker

**Purpose:** Check that all required entities for a system/date are in SUCCESS state before triggering transformation.

**Contract:**
- Returns `True` only when ALL required entities have `JobStatus.SUCCESS`
- Returns `False` if any entity is PENDING, RUNNING, or FAILED
- Uses `JobControlRepository` — must be testable with mock repo

**Test scenarios:**
- All entities SUCCESS → returns `True`
- One entity FAILED → returns `False`
- One entity still RUNNING → returns `False`
- Empty required entities list → returns `True`
