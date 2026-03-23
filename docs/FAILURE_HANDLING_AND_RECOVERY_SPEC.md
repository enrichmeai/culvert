# Failure Handling & Recovery Specification

> For testers, developers, and operators: how the pipeline handles mid-execution
> failures today, what guardrails exist, where the gaps are, and what changes
> are needed to make ODP and FDP layers fully resumable.
>
> **Status**: ALL GUARDRAILS IMPLEMENTED (G1–G10, 2026-03-16).

---

## Table of Contents

1. [Pipeline Overview](#1-pipeline-overview)
2. [Job Control System — How It Works Today](#2-job-control-system--how-it-works-today)
3. [ODP Layer — Failure Scenarios & Recovery](#3-odp-layer--failure-scenarios--recovery)
4. [FDP Layer — Failure Scenarios & Recovery](#4-fdp-layer--failure-scenarios--recovery)
5. [Current Guardrails Inventory](#5-current-guardrails-inventory)
6. [Gap Analysis](#6-gap-analysis)
7. [Implemented Changes — Library](#7-implemented-changes--library)
8. [Implemented Changes — Infrastructure (Terraform)](#8-implemented-changes--infrastructure-terraform)
9. [Implemented Changes — Orchestration (DAGs)](#9-implemented-changes--orchestration-dags)
10. [Implemented Changes — dbt Models](#10-implemented-changes--dbt-models)
11. [Implemented Changes — system.yaml Config](#11-implemented-changes--systemyaml-config)
12. [Test Scenarios for Testers](#12-test-scenarios-for-testers)

---

## 1. Pipeline Overview

```
Mainframe CSV files → GCS landing bucket
                         ↓  (.ok trigger → Pub/Sub)
              DAG 1: pubsub_trigger_dag
                         ↓  (validates file HDR/TRL)
              DAG 2: ingestion_dag
                         ↓  (Dataflow loads to BigQuery ODP)
              BigQuery ODP tables (odp_generic.*)
                         ↓  (dependency check: are all required entities loaded?)
              DAG 3: transformation_dag
                         ↓  (dbt staging views → FDP incremental models)
              BigQuery FDP tables (fdp_generic.*)
```

**Five DAGs per system** (generated at build time by `generate_dags.py`):

| DAG | Schedule | Purpose | Job Control? |
|-----|----------|---------|-------------|
| `{system}_pubsub_trigger_dag` | Every minute | Listens for `.ok` files, validates, triggers ingestion | No record (trigger only) |
| `{system}_ingestion_dag` | Triggered | Creates ODP_INGESTION job, runs Dataflow, reconciles, checks FDP deps | Yes — full lifecycle with reconciliation |
| `{system}_transformation_dag` | Triggered | Creates FDP_TRANSFORMATION job, runs dbt staging → FDP → tests → reconcile | Yes — full lifecycle with parent lineage |
| `{system}_pipeline_status_dag` | Daily 23:00 | End-of-day health check with ObservabilityManager — alerts on gaps/failures | Read-only (queries job_control) |
| `{system}_error_handling_dag` | Every 30 min | Scans failed jobs, auto-retries eligible (with partial cleanup), alerts critical | Yes — marks RETRYING, triggers re-runs |

---

## 2. Job Control System — How It Works Today

### 2.1 Job Statuses

Defined in `gcp-pipeline-core/job_control/types.py`:

| Status | Meaning | Used? |
|--------|---------|-------|
| `PENDING` | Job record created, not yet started | Yes — ODP + FDP |
| `RUNNING` | Processing in progress | Yes — ODP + FDP |
| `SUCCESS` | Completed successfully | Yes — ODP + FDP |
| `FAILED` | Processing failed | Yes — ODP + FDP (with error details, failure_stage) |
| `RETRYING` | Previous failed job being retried | Yes — set by `mark_retrying()` during ODP cleanup-before-retry |
| `QUARANTINED` | Moved to quarantine for review | Reserved — not yet used |

### 2.2 Failure Stages

Defined in `gcp-pipeline-core/job_control/types.py`:

| Stage | Meaning | Used? |
|-------|---------|-------|
| `FILE_DISCOVERY` | Could not find source files | Yes — ODP `create_job_record` task failures |
| `FILE_VALIDATION` | HDR/TRL parsing failed | Available — set by trigger DAG validation |
| `DATA_QUALITY` | Schema/field validation failed | Available — set by Beam pipeline |
| `ODP_LOAD` | BigQuery write failed | Yes — Dataflow task failures |
| `RECONCILIATION` | Source/dest count mismatch | Yes — ODP and FDP reconciliation task failures |
| `FDP_DEPENDENCY` | Upstream ODP entities not loaded | Yes — transformation DAG dependency check failures |
| `FDP_STAGING` | dbt staging view creation failed | Yes — `run_dbt_staging` task failures |
| `FDP_MODEL` | dbt FDP model MERGE failed | Yes — `run_dbt_fdp` task failures |
| `FDP_TEST` | dbt test assertion failed | Yes — `run_dbt_tests` task failures |
| `TRANSFORMATION` | Generic transformation failure | Fallback — used when task_id doesn't match a specific stage |

All failure stages are now set by the DAG `on_failure_callback` functions using task-to-stage mapping.

### 2.3 Pipeline Jobs Table Schema

Table: `job_control.pipeline_jobs` (managed by Terraform)

| Column | Type | Description |
|--------|------|-------------|
| `run_id` | STRING | Unique job identifier |
| `system_id` | STRING | Source system (e.g., "GENERIC") |
| `entity_type` | STRING | Entity being processed |
| `extract_date` | DATE | Source data extract date |
| `status` | STRING | Current status |
| `source_files` | ARRAY<STRING> | GCS file paths |
| `total_records` | INT64 | Record count on SUCCESS |
| `started_at` | TIMESTAMP | When RUNNING was set |
| `completed_at` | TIMESTAMP | When SUCCESS was set |
| `failed_at` | TIMESTAMP | When FAILED was set |
| `error_code` | STRING | Error classification |
| `error_message` | STRING | Error details |
| `failure_stage` | STRING | Which stage failed |
| `error_file_path` | STRING | GCS path to error log |
| `created_at` | TIMESTAMP | Record creation time |
| `updated_at` | TIMESTAMP | Last modification time |
| `job_type` | STRING | `ODP_INGESTION`, `FDP_TRANSFORMATION`, or `CDP_TRANSFORMATION` |
| `retry_count` | INT64 | Number of retry attempts |
| `max_retries` | INT64 | Configured maximum retries |
| `parent_run_ids` | ARRAY<STRING> | Source ODP job run_ids (FDP lineage) |
| `dbt_model_name` | STRING | dbt model name (FDP/CDP jobs only) |

### 2.4 Audit Trail Table

Table: `job_control.audit_trail` (managed by Terraform)

| Column | Type | Description |
|--------|------|-------------|
| `run_id` | STRING | Links to pipeline_jobs |
| `pipeline_name` | STRING | DAG or deployment name |
| `entity_type` | STRING | Entity processed |
| `source_file` | STRING | Input file path |
| `record_count` | INTEGER | Records processed |
| `processed_timestamp` | TIMESTAMP | Completion time |
| `processing_duration_seconds` | FLOAT | Runtime |
| `success` | BOOLEAN | Pass/fail |
| `error_count` | INTEGER | Invalid record count |
| `audit_hash` | STRING | SHA256 verification |

### 2.5 What the Job Control Repository Provides

Source: `gcp-pipeline-core/job_control/repository.py`

| Method | What It Does |
|--------|-------------|
| `create_job(job)` | INSERT new record with PENDING status |
| `update_status(run_id, status, total_records)` | Transitions status; sets `started_at` (RUNNING), `completed_at` (SUCCESS) |
| `mark_failed(run_id, error_code, error_message, failure_stage, error_file_path)` | Sets FAILED with full error details |
| `get_job(run_id)` | Retrieve single job |
| `get_entity_status(system_id, extract_date)` | Get all entity statuses for a date (used by dependency checker) |
| `get_pending_jobs(system_id)` | Find jobs stuck in PENDING |

---

## 3. ODP Layer — Failure Scenarios & Recovery

### 3.1 How ODP Ingestion Works (DAG 2: ingestion_dag)

```
create_job_record → run_dataflow_pipeline → update_job_success → reconcile_odp_load → check_ready_fdp_models → trigger_ready_transforms
```

1. **create_job_record**: Creates `ODP_INGESTION` pipeline_jobs record → PENDING → RUNNING. Cleans up partial data from prior FAILED runs.
2. **run_dataflow_pipeline**: Launches Dataflow Flex Template (Apache Beam)
3. **update_job_success**: Marks job SUCCESS, records audit trail
4. **reconcile_odp_load**: Compares HDR/TRL expected count vs BigQuery actual count. Raises exception on mismatch.
5. **check_ready_fdp_models**: Queries which FDP models have all ODP dependencies loaded
6. **trigger_ready_transforms**: Triggers `transformation_dag` for each ready FDP model

**On failure**: `on_failure_callback` → `mark_failed()` with `failure_stage`, `error_code`, `error_message` → `ErrorHandler` classifies and stores to GCS → `AuditTrail` records failure

### 3.2 Failure at Each Stage

| Stage | What Fails | Data State | Source Files | Job Control | Recovery |
|-------|-----------|-----------|-------------|-------------|---------|
| **File Discovery** | `.ok` file arrives but no `.csv` | Nothing loaded | In landing bucket | No record yet (trigger DAG) | Fix file, re-land `.ok` |
| **File Validation** | HDR/TRL mismatch, wrong system_id | Nothing loaded | Moved to error bucket | No record yet | Fix file, re-land to landing bucket |
| **Dataflow Startup** | Template not found, quota | Nothing loaded | In landing bucket | FAILED | Fix config, re-trigger ingestion DAG |
| **Dataflow Processing** | Worker OOM, schema mismatch | **Partial load possible** | In landing bucket | FAILED | See 3.3 below |
| **BigQuery Write** | Timeout, quota exceeded | Partial load | In landing bucket | FAILED | See 3.3 below |
| **Post-Load Success** | check_ready task fails | **ODP fully loaded** | In landing bucket | Still RUNNING (not yet SUCCESS) | Manual: update to SUCCESS, re-trigger check |

### 3.3 Is ODP Safe to Retry?

**Yes, with caveats:**

- **Dataflow provides exactly-once semantics** within a single pipeline run — if a worker fails, Beam checkpoints prevent duplicate writes
- **On full retry** (re-running the Dataflow job): the pipeline reads the entire CSV and writes to BigQuery. If a previous partial run left rows in the ODP table, a retry will insert **duplicate rows** unless:
  - The table has a unique constraint (BigQuery tables do NOT enforce uniqueness)
  - The pipeline uses `WRITE_TRUNCATE` (it doesn't — uses `WRITE_APPEND`)

**Current gap**: Re-running a failed ODP load on the same file can produce duplicates. The `_run_id` column exists on every row, so a manual `DELETE FROM table WHERE _run_id = '<failed_run>'` before retry would clean this up, but this is **not automated**.

### 3.4 Error Records

- Valid rows → `odp_generic.{entity}` (e.g., `odp_generic.customers`)
- Invalid rows → `odp_generic.{entity}_errors` (e.g., `odp_generic.customers_errors`)
- This separation is handled by the Beam pipeline's branching (valid/errors side outputs)

---

## 4. FDP Layer — Failure Scenarios & Recovery

### 4.1 How FDP Transformation Works (DAG 3: transformation_dag)

```
verify_model_dependencies ──┬──→ create_fdp_job_record → run_dbt_staging → run_dbt_fdp → run_dbt_tests → reconcile_fdp_model → mark_fdp_success → end
                            └──→ handle_dependency_failure → end
```

1. **verify_model_dependencies**: Queries `pipeline_jobs` for loaded entities. If all deps met → proceed. If not → records FAILED job with `FDP_DEPENDENCY` stage.
2. **create_fdp_job_record**: Creates `FDP_TRANSFORMATION` pipeline_jobs record with `parent_run_ids` linking to source ODP jobs → PENDING → RUNNING.
3. **run_dbt_staging**: `dbt run --select staging` (creates/refreshes staging views)
4. **run_dbt_fdp**: `dbt run --select {fdp_model}` (incremental MERGE into FDP table)
5. **run_dbt_tests**: `dbt test --select {fdp_model}` (data quality assertions)
6. **reconcile_fdp_model**: Verifies FDP table has rows (JOIN models: non-empty check; MAP models: 1:1 count against source)
7. **mark_fdp_success**: Updates job control to SUCCESS, records audit trail

**On failure**: `on_failure_callback` → `mark_failed()` with stage-specific `FDP_STAGING`/`FDP_MODEL`/`FDP_TEST`/`RECONCILIATION` → `ErrorHandler` classifies and stores to GCS → `AuditTrail` records failure

### 4.2 dbt Materialization Strategy

All FDP models use:
```sql
config(
    materialized='incremental',
    unique_key='event_key',          -- surrogate key
    incremental_strategy='merge',     -- MERGE statement in BigQuery
    partition_by={"field": "_extract_date", "data_type": "date"},
    on_schema_change='fail'
)
```

**Incremental filter** (only processes new data):
```sql
{% if is_incremental() %}
WHERE c._processed_at > (SELECT MAX(_transformed_at) FROM {{ this }})
   OR a._processed_at > (SELECT MAX(_transformed_at) FROM {{ this }})
{% endif %}
```

### 4.3 Failure at Each Stage

| Stage | What Fails | Data State | Job Control | Recovery |
|-------|-----------|-----------|-------------|---------|
| **Dependency Check** | Upstream ODP not loaded | FDP unchanged | No record created | **Silent skip** — DAG ends without error or notification |
| **dbt Staging** | SQL error, permission | FDP unchanged (views not tables) | No record created | Fix SQL, re-trigger DAG |
| **dbt FDP Model** | JOIN error, NULL keys, quota | **Partial MERGE possible** | No record created (gap!) | See 4.4 below |
| **dbt Tests** | Assertion failure (NOT NULL, unique) | **FDP table updated but data may be invalid** | No record created | Investigate data, potentially need to rollback |
| **mark_success** | BigQuery update fails | FDP is correct, but job_control not updated | Status not updated | Manual: update job_control |

### 4.4 Is FDP Safe to Retry?

**Mostly yes, because of MERGE with unique_key:**

The dbt `incremental_strategy='merge'` with `unique_key='event_key'` means:
- BigQuery generates a MERGE statement: `MERGE INTO fdp_table USING (...) ON event_key = event_key`
- If rows already exist from a partial run, they get **updated** (not duplicated)
- New rows get **inserted**

**However, there are edge cases:**

1. **Timestamp-based incremental filter**: The `WHERE _processed_at > MAX(_transformed_at)` check relies on `_transformed_at` being set by the dbt model (`current_timestamp()`). If a partial run set `_transformed_at` for some rows, a retry may skip those rows' source records because `_processed_at` is no longer > the new `MAX(_transformed_at)`.

2. **Cross-entity JOINs**: `event_transaction_excess` joins customers + accounts. If the join produces different results on retry (e.g., account data was updated between runs), the MERGE will update rows — this is actually correct behavior but may confuse reconciliation.

3. **No FDP job control record**: Even if retry succeeds, there's no job history showing it was retried.

### 4.5 Dependency Check — No Longer Silent

The transformation DAG now records dependency failures explicitly:
```python
if checker.all_entities_loaded(date_obj):
    return "create_fdp_job_record"   # → proceed with dbt
else:
    missing = checker.get_missing_entities(date_obj)
    return "handle_dependency_failure"  # → creates FAILED job record
```

`handle_dependency_failure` creates a `pipeline_jobs` record with:
- `status = FAILED`
- `failure_stage = FDP_DEPENDENCY`
- `error_code = DEPENDENCY_NOT_MET`
- `error_message = "Missing ODP entities: [accounts]. DAG triggered prematurely."`

This makes dependency failures **visible** in job control queries and Airflow email alerts.

---

## 5. Current Guardrails Inventory

### 5.1 What Exists and Works

| Guardrail | Layer | Implementation |
|-----------|-------|---------------|
| Job status tracking (PENDING→RUNNING→SUCCESS/FAILED) | ODP | `JobControlRepository` + ingestion DAG |
| Error record separation (valid vs. errors tables) | ODP | Beam pipeline side outputs |
| File validation (HDR/TRL) | Trigger | `HDRTRLParser` in pubsub_trigger_dag |
| Invalid file quarantine | Trigger | Move to error bucket |
| Airflow task retries | ODP + FDP | `default_args.retries` (3 for ODP, 2 for FDP) |
| Dataflow exactly-once (within single run) | ODP | Apache Beam checkpointing |
| dbt MERGE idempotency | FDP | `unique_key` + `incremental_strategy='merge'` |
| Reconciliation engine | Library | `ReconciliationEngine` (compare source count vs. BQ count) |
| Error classification | Library | `ErrorClassifier` (severity, category, retry strategy) |
| Retry policy with backoff | Library | `RetryPolicy` (exponential/linear backoff, jitter) |
| Audit trail logging | Library | `AuditTrail` (SHA256 hash, Pub/Sub publish) |
| Recovery checkpoints | Library | `RecoveryManager` (in-memory only) |
| Duplicate detection | Library | `DuplicateDetector` (in-memory set) |
| Pub/Sub dead letter queue | Infra | Terraform: `dead_letter_policy` with max 5 attempts |

### 5.2 Previously Disconnected — Now Connected

All previously disconnected guardrails have been wired into the pipeline:

| Guardrail | Status | How It's Connected |
|-----------|--------|-------------------|
| `RETRYING` status | Connected | `mark_retrying()` called during ODP cleanup-before-retry |
| `QUARANTINED` status | Reserved | Not yet needed — available for future manual quarantine workflows |
| `FailureStage` enum | Connected | Both DAG `on_failure_callback`s use task-to-stage mapping with `mark_failed()` |
| `RecoveryManager` | Connected | `GCSRecoveryManager` persists checkpoints to GCS (available for Dataflow/DAG use) |
| `ErrorHandler` + `ErrorClassifier` | Connected | Called in both ODP and FDP `on_failure_callback`s — classifies severity/category |
| `ReconciliationEngine` | Connected | `reconcile_odp_load` (ODP) and `reconcile_fdp_model` (FDP) tasks in DAGs |
| `AuditTrail` | Connected | `record_processing_start()` + `record_processing_end()` called in success and failure paths |
| `GCSErrorStorage` | Connected | Configured in both failure callbacks — errors stored at `gs://{error_bucket}/error_logs/{run_id}/` |

---

## 6. Gap Analysis

### 6.1 Critical Gaps

| # | Gap | Impact | Severity | Status |
|---|-----|--------|----------|--------|
| G1 | **FDP builds have no job control record** | Failed dbt runs are invisible to job tracking. Cannot query "which FDP models failed?" | CRITICAL | RESOLVED — `create_fdp_job_record` creates FDP_TRANSFORMATION record with parent_run_ids lineage |
| G2 | **Dependency check silently skips** | If upstream ODP fails, FDP DAG succeeds with no work done, no alert, no retry | CRITICAL | RESOLVED — `handle_dependency_failure` creates FAILED record with FDP_DEPENDENCY stage |
| G3 | **ODP retry can produce duplicates** | No cleanup of partial data before retry. `WRITE_APPEND` + no unique constraint = duplicates | HIGH | RESOLVED — `cleanup_partial_load()` + `mark_retrying()` in `create_job_record` |
| G4 | **`on_failure_callback` doesn't use `mark_failed()`** | Failure stage, error code, error message never recorded. Only status changes to FAILED | HIGH | RESOLVED — `mark_job_failed` now calls `repo.mark_failed()` with stage/code/message |
| G5 | **Reconciliation not wired into pipeline** | Source file record count vs. BigQuery row count never compared automatically | HIGH | RESOLVED — `reconcile_odp_load` task added after `update_job_success` |

### 6.2 Medium Gaps

| # | Gap | Impact | Severity | Status |
|---|-----|--------|----------|--------|
| G6 | **RETRYING status never used** | Cannot distinguish "failed permanently" from "being retried" | MEDIUM | RESOLVED — `mark_retrying()` method added, called during ODP cleanup-before-retry |
| G7 | **RecoveryManager is in-memory** | Checkpoints lost on worker restart. Useless for long-running Dataflow | MEDIUM | RESOLVED — `GCSRecoveryManager` persists checkpoints to GCS as JSON, restores on restart |
| G8 | **Audit trail incomplete** | Only `record_processing_start()` called, never `_end()`. No FDP audit entries | MEDIUM | RESOLVED — Both ODP and FDP success/failure paths now call `record_processing_start()` + `record_processing_end()` |
| G9 | **Error handler not integrated** | Classification, storage, alerting all available but not called from DAGs | MEDIUM | RESOLVED — `ErrorHandler` + `GCSErrorStorage` wired into both ODP and FDP `on_failure_callback`s |
| G10 | **No FDP reconciliation** | ODP has record counts from HDR/TRL. FDP has no expected vs. actual comparison | MEDIUM | RESOLVED — `reconcile_fdp_model()` added to ReconciliationEngine; `reconcile_fdp_model` task in transformation DAG |

---

## 7. Implemented Changes — Library

### 7.1 `gcp-pipeline-core/job_control/types.py`

**Add new failure stage for FDP dependency failures:**

```python
class FailureStage(Enum):
    FILE_DISCOVERY = "FILE_DISCOVERY"
    FILE_VALIDATION = "FILE_VALIDATION"
    DATA_QUALITY = "DATA_QUALITY"
    ODP_LOAD = "ODP_LOAD"
    TRANSFORMATION = "TRANSFORMATION"
    # NEW:
    FDP_DEPENDENCY = "FDP_DEPENDENCY"        # Upstream ODP not loaded
    FDP_STAGING = "FDP_STAGING"              # dbt staging view creation failed
    FDP_MODEL = "FDP_MODEL"                  # dbt FDP model MERGE failed
    FDP_TEST = "FDP_TEST"                    # dbt test assertion failed
    RECONCILIATION = "RECONCILIATION"        # Source/dest count mismatch
```

**Add job type to distinguish ODP from FDP records:**

```python
class JobType(Enum):
    ODP_INGESTION = "ODP_INGESTION"
    FDP_TRANSFORMATION = "FDP_TRANSFORMATION"
    CDP_TRANSFORMATION = "CDP_TRANSFORMATION"  # Future
```

### 7.2 `gcp-pipeline-core/job_control/models.py`

**Add `job_type` and `parent_run_ids` to PipelineJob:**

```python
@dataclass
class PipelineJob:
    # ... existing fields ...
    job_type: Optional[str] = None           # NEW: "ODP_INGESTION" or "FDP_TRANSFORMATION"
    parent_run_ids: List[str] = field(default_factory=list)  # NEW: links FDP job to source ODP jobs
    retry_count: int = 0                     # NEW: how many times this job has been retried
    max_retries: int = 3                     # NEW: configured max retries
    dbt_model_name: Optional[str] = None     # NEW: for FDP jobs, which model was run
```

### 7.3 `gcp-pipeline-core/job_control/repository.py`

**Add new methods:**

```python
class JobControlRepository:
    # ... existing methods ...

    def mark_retrying(self, run_id: str, retry_count: int) -> None:
        """Transition job to RETRYING status with retry count."""
        # UPDATE SET status='RETRYING', retry_count=@retry_count, updated_at=NOW()

    def cleanup_partial_load(self, run_id: str, table: str) -> int:
        """Delete rows from a failed partial load. Returns rows deleted."""
        # DELETE FROM `{table}` WHERE _run_id = @run_id

    def get_failed_jobs(self, system_id: str, extract_date: date) -> List[PipelineJob]:
        """Get all FAILED jobs for a system/date. Used for retry decisions."""
        # SELECT * WHERE status='FAILED' AND system_id=@system_id AND extract_date=@date

    def get_fdp_job_status(self, system_id: str, extract_date: date, model_name: str) -> Optional[PipelineJob]:
        """Get FDP job status for a specific model/date. Used for skip-if-done checks."""
        # SELECT * WHERE job_type='FDP_TRANSFORMATION' AND dbt_model_name=@model_name AND extract_date=@date

    def create_fdp_job(self, run_id: str, system_id: str, model_name: str,
                       extract_date: date, parent_run_ids: List[str]) -> None:
        """Create a job control record specifically for FDP transformation."""
        # INSERT with job_type='FDP_TRANSFORMATION', parent_run_ids, dbt_model_name
```

**Update `mark_failed` to accept exception details:**

```python
    def mark_failed_with_context(
        self, run_id: str, exception: Exception,
        failure_stage: FailureStage, error_file_path: Optional[str] = None
    ) -> None:
        """Mark failed using ErrorClassifier for consistent error classification."""
        from ..error_handling.handler import ErrorClassifier
        severity, category, _ = ErrorClassifier.classify(exception)
        error_code = f"{category.value}_{severity.value}"
        self.mark_failed(run_id, error_code, str(exception), failure_stage, error_file_path)
```

### 7.4 `gcp-pipeline-core/audit/reconciliation.py`

**Add FDP reconciliation method:**

```python
class ReconciliationEngine:
    # ... existing methods ...

    def reconcile_fdp_model(
        self, model_name: str, source_tables: List[str],
        destination_table: str, join_type: str = "inner",
        bq_client: Any = None
    ) -> ReconciliationResult:
        """
        Reconcile FDP model output against ODP source tables.

        For JOIN models: expected_count = count of matching rows from joined sources
        For MAP models: expected_count = count from single source table
        """
        # Query each source table count, compute expected based on join_type
        # Compare with actual FDP table count for this run_id
```

### 7.5 `gcp-pipeline-core/data_deletion/recovery.py`

**Add GCS persistence to RecoveryManager:**

```python
class GCSRecoveryManager(RecoveryManager):
    """RecoveryManager that persists checkpoints to GCS."""

    def __init__(self, bucket_name: str, prefix: str = "recovery_points"):
        super().__init__()
        self.bucket_name = bucket_name
        self.prefix = prefix

    def create_recovery_point(self, checkpoint_name, state, malformed_records=None):
        """Create recovery point and persist to GCS."""
        rp = super().create_recovery_point(checkpoint_name, state, malformed_records)
        self._save_to_gcs(rp)
        return rp

    def restore_from_recovery_point(self, checkpoint_name):
        """Restore from GCS if not in memory."""
        if checkpoint_name not in self.recovery_points:
            self._load_from_gcs(checkpoint_name)
        return super().restore_from_recovery_point(checkpoint_name)
```

---

## 8. Implemented Changes — Infrastructure (Terraform)

### 8.1 Update `pipeline_jobs` Table Schema

File: `infrastructure/terraform/main.tf` (add BigQuery table resource)

New columns to add to `pipeline_jobs`:

```sql
job_type          STRING        -- "ODP_INGESTION" or "FDP_TRANSFORMATION"
parent_run_ids    ARRAY<STRING> -- links FDP job to ODP source jobs
retry_count       INT64         -- number of retry attempts
max_retries       INT64         -- configured maximum retries
dbt_model_name    STRING        -- for FDP jobs: which dbt model
```

### 8.2 Add `transformation_jobs` View (Optional)

Create a view for easy querying of FDP job status:

```sql
CREATE VIEW job_control.transformation_jobs AS
SELECT * FROM job_control.pipeline_jobs
WHERE job_type = 'FDP_TRANSFORMATION'
```

### 8.3 IAM — dbt Service Account Needs job_control Access

Currently, the dbt service account has:
- `bigquery.dataViewer` on `odp_generic` (read source)
- `bigquery.dataEditor` on `fdp_generic` (write FDP)

**Missing**: dbt (via Airflow) needs to write to `job_control.pipeline_jobs` for FDP tracking.

```hcl
resource "google_bigquery_dataset_iam_member" "dbt_job_control_editor" {
  dataset_id = google_bigquery_dataset.job_control.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.dbt.email}"
}
```

---

## 9. Implemented Changes — Orchestration (DAGs)

### 9.1 Ingestion DAG — Use `mark_failed()` Instead of `update_status()`

**Current** (`dag_factory.py:348-356`):
```python
def mark_job_failed(context):
    run_id = context["ti"].xcom_pull(key="run_id")
    if run_id:
        repo = JobControlRepository(project_id=project_id)
        repo.update_status(run_id, JobStatus.FAILED)  # ← loses error details
```

**Proposed**:
```python
def mark_job_failed(context):
    run_id = context["ti"].xcom_pull(key="run_id")
    task_id = context["task_instance"].task_id
    exception = context.get("exception")

    if run_id:
        repo = JobControlRepository(project_id=project_id)
        # Map task_id to failure stage
        stage_map = {
            "create_job_record": FailureStage.FILE_DISCOVERY,
            "run_dataflow_pipeline": FailureStage.ODP_LOAD,
            "update_job_success": FailureStage.ODP_LOAD,
        }
        stage = stage_map.get(task_id, FailureStage.ODP_LOAD)
        repo.mark_failed(
            run_id=run_id,
            error_code=type(exception).__name__ if exception else "UNKNOWN",
            error_message=str(exception) if exception else f"Task {task_id} failed",
            failure_stage=stage,
        )
```

### 9.2 Ingestion DAG — Add Reconciliation After ODP Load

Add a new task between `update_job_success` and `check_ready_fdp_models`:

```python
def reconcile_odp_load(**context):
    """Compare HDR/TRL expected count with actual BigQuery count."""
    run_id = context["ti"].xcom_pull(key="run_id")
    entity = context["ti"].xcom_pull(key="entity")
    # Get expected count from hdr_metadata passed by trigger DAG
    conf = context.get("dag_run").conf or {}
    hdr_metadata = conf.get("hdr_metadata", {})
    expected_count = hdr_metadata.get("record_count", 0)

    engine = ReconciliationEngine(entity_type=entity, run_id=run_id, project_id=project_id)
    result = engine.reconcile_with_bigquery(
        expected_count=expected_count,
        destination_table=f"{project_id}.odp_{config['file_prefix']}.{entity}",
        error_table=f"{project_id}.odp_{config['file_prefix']}.{entity}_errors",
    )

    if not result.is_reconciled:
        raise Exception(f"Reconciliation MISMATCH: {result.message}")
```

### 9.3 Ingestion DAG — Add Cleanup Before Retry

Add pre-flight check at start of ingestion to handle retries:

```python
def create_job_record(**context):
    # ... existing logic ...

    # Check if a FAILED job already exists for this entity/date
    existing = repo.get_entity_status(system_id, extract_date_obj)
    for entry in existing:
        if entry["entity_type"] == entity and entry["status"] == "FAILED":
            old_run_id = entry["run_id"]
            logger.info(f"Found failed job {old_run_id}. Cleaning up partial data.")
            repo.cleanup_partial_load(old_run_id, f"{project_id}.odp_{file_prefix}.{entity}")
            repo.update_status(old_run_id, JobStatus.RETRYING)
```

### 9.4 Transformation DAG — Add FDP Job Control Record

**This is the biggest gap.** The transformation DAG needs to create its own job record:

```python
def create_fdp_job_record(**context):
    """Create job control record for FDP transformation."""
    conf = context.get("dag_run").conf or {}
    fdp_model = conf.get("fdp_model")
    extract_date = conf.get("extract_date")
    run_id = context.get("run_id")

    # Find parent ODP run_ids
    required_entities = fdp_deps.get(fdp_model, [])
    date_obj = datetime.strptime(extract_date, "%Y%m%d").date()
    parent_statuses = repo.get_entity_status(system_id, date_obj)
    parent_run_ids = [
        s["run_id"] for s in parent_statuses
        if s["entity_type"] in required_entities and s["status"] == "SUCCESS"
    ]

    repo.create_fdp_job(
        run_id=run_id,
        system_id=system_id,
        model_name=fdp_model,
        extract_date=date_obj,
        parent_run_ids=parent_run_ids,
    )
    repo.update_status(run_id, JobStatus.RUNNING)
```

### 9.5 Transformation DAG — Add On-Failure Callback

Currently, transformation_dag has no `on_failure_callback`:

```python
default_args = {
    # ... existing ...
    "on_failure_callback": mark_fdp_job_failed,  # NEW
}

def mark_fdp_job_failed(context):
    """Mark FDP job as failed with stage-specific details."""
    run_id = context.get("run_id")
    task_id = context["task_instance"].task_id
    exception = context.get("exception")

    stage_map = {
        "verify_model_dependencies": FailureStage.FDP_DEPENDENCY,
        "run_dbt_staging": FailureStage.FDP_STAGING,
        "run_dbt_fdp": FailureStage.FDP_MODEL,
        "run_dbt_tests": FailureStage.FDP_TEST,
    }
    stage = stage_map.get(task_id, FailureStage.TRANSFORMATION)

    repo = JobControlRepository(project_id=project_id)
    repo.mark_failed(
        run_id=run_id,
        error_code=type(exception).__name__ if exception else "UNKNOWN",
        error_message=str(exception) if exception else f"Task {task_id} failed",
        failure_stage=stage,
    )
```

### 9.6 Transformation DAG — Fix Silent Skip

Change dependency check from skip to **fail with clear message**:

```python
def verify_model_dependencies(**context) -> str:
    # ... existing check ...
    if not checker.all_entities_loaded(date_obj):
        missing = checker.get_missing_entities(date_obj)
        # Instead of silently skipping:
        raise Exception(
            f"FDP model {fdp_model} cannot run. "
            f"Missing ODP entities: {missing}. "
            f"This DAG was triggered prematurely."
        )
    return "create_fdp_job_record"  # NEW: create job record before dbt
```

**Or** keep the skip but mark it clearly:

```python
    else:
        # Create a job record with FAILED status so it's visible
        repo = JobControlRepository(project_id=project_id)
        repo.create_fdp_job(run_id=..., ...)
        repo.mark_failed(
            run_id=...,
            error_code="DEPENDENCY_NOT_MET",
            error_message=f"Missing entities: {missing}",
            failure_stage=FailureStage.FDP_DEPENDENCY,
        )
        return "skip_transformation"
```

---

## 10. Implemented Changes — dbt Models

### 10.1 No Code Changes Needed for Idempotency

The existing dbt configuration is already sound:
- `incremental_strategy='merge'` with `unique_key` prevents duplicates on retry
- `partition_by` allows partition-level operations
- `on_schema_change='fail'` prevents silent schema drift

### 10.2 Consider Adding dbt Artifacts Storage

After each dbt run, store `target/run_results.json` to GCS for audit:

```bash
# In transformation_dag BashOperator:
dbt run --select "{model}" --target prod && \
gsutil cp target/run_results.json gs://{temp_bucket}/dbt_artifacts/{run_id}/run_results.json
```

This enables post-mortem analysis of failed runs.

---

## 11. Implemented Changes — system.yaml Config

Add retry and error handling configuration:

```yaml
# NEW SECTION
retry_config:
  odp:
    max_retries: 3
    retry_delay_minutes: 5
    cleanup_on_retry: true        # DELETE partial data before retry
  fdp:
    max_retries: 2
    retry_delay_minutes: 10
    cleanup_on_retry: false       # MERGE handles idempotency
  dependency_check:
    mode: "fail"                  # "fail" | "skip" | "wait"
    wait_timeout_minutes: 60      # only if mode="wait"

reconciliation:
  enabled: true
  on_mismatch: "fail"            # "fail" | "warn"
  tolerance_percentage: 0        # allow 0% mismatch (strict)

error_handling:
  storage: "gcs"                 # "gcs" | "bigquery" | "memory"
  alert_on_critical: true
  error_bucket: "{project_id}-{system}-{env}-error"
```

---

## 12. Test Scenarios for Testers

### 12.1 ODP Failure Scenarios

| # | Scenario | How to Simulate | Expected Behavior (Current) | Expected Behavior (After Changes) |
|---|----------|----------------|---------------------------|----------------------------------|
| T1 | File validation fails | Upload CSV with wrong HDR system_id | File moved to error bucket, no job record | Same + error logged to error_handling storage |
| T2 | Dataflow fails mid-load | Kill Dataflow worker during processing | Job marked FAILED, partial rows in ODP | Job marked FAILED **with failure_stage=ODP_LOAD**. On retry: partial rows cleaned up first |
| T3 | Dataflow succeeds but BQ quota hit | Set low BQ quota | Job marked FAILED | Job marked FAILED with error_code=RESOURCE_HIGH |
| T4 | Same file re-landed after failure | Re-upload .ok file | New Dataflow run, **duplicate rows** | New run **deletes old partial rows first**, then loads fresh |
| T5 | Reconciliation mismatch | Modify CSV after validation but before load | No check performed | **Reconciliation task fails**, job marked FAILED with stage=RECONCILIATION |

### 12.2 FDP Failure Scenarios

| # | Scenario | How to Simulate | Expected Behavior (Current) | Expected Behavior (After Changes) |
|---|----------|----------------|---------------------------|----------------------------------|
| T6 | Upstream ODP not loaded | Trigger transform_dag manually without loading ODP first | **Silent skip** — DAG succeeds | **Job record created with FAILED status**, failure_stage=FDP_DEPENDENCY |
| T7 | dbt staging model fails | Introduce SQL error in staging view | Airflow retries 2x, then DAG fails. **No job record** | Job record created, marked FAILED with stage=FDP_STAGING |
| T8 | dbt FDP model MERGE fails | Add NULL to a NOT NULL column in source data | Airflow retries 2x, then DAG fails. **No job record** | Job record created, marked FAILED with stage=FDP_MODEL. dbt artifacts saved to GCS |
| T9 | dbt tests fail | Add duplicate `event_key` in source data | DAG fails after dbt test. **No job record**. FDP table has bad data | Job record marked FAILED with stage=FDP_TEST. Alert triggered |
| T10 | FDP model retried after failure | Re-trigger transform_dag for same model/date | New dbt run with MERGE (no duplicates). **No job history** | Previous job marked RETRYING, new job record created with parent link |
| T11 | Partial FDP then retry | Kill dbt mid-MERGE, then re-trigger | MERGE handles idempotency (updates existing + inserts new). **No record** | Job record tracks both attempts. Reconciliation verifies row count |

### 12.3 End-to-End Recovery Scenarios

| # | Scenario | Steps | Expected (After Changes) |
|---|----------|-------|------------------------|
| T12 | Full pipeline: ODP fails, retry succeeds, FDP runs | 1. Land file 2. Dataflow fails (quota) 3. Quota clears 4. Re-land .ok 5. FDP triggers | ODP: FAILED→RETRYING→SUCCESS. FDP: auto-triggered, creates job, runs dbt, SUCCESS |
| T13 | ODP succeeds, FDP dependency not met, then met | 1. Load customers only 2. FDP triggered for event_transaction_excess (needs customers+accounts) 3. Load accounts 4. FDP re-triggered | First FDP: FAILED (FDP_DEPENDENCY). Second FDP: SUCCESS with parent_run_ids linking both ODP jobs |
| T14 | Full pipeline success then re-run same date | 1. Run full pipeline 2. Re-land same files | ODP: detects existing SUCCESS run, skips or warns. FDP: dbt incremental filter finds no new rows, no-op |

### 12.4 Queries Testers Can Use to Verify

**Check all jobs for a date:**
```sql
SELECT run_id, job_type, entity_type, dbt_model_name, status, failure_stage,
       error_code, error_message, retry_count, started_at, completed_at, failed_at
FROM `job_control.pipeline_jobs`
WHERE extract_date = '2026-03-16'
ORDER BY created_at
```

**Find failed FDP jobs:**
```sql
SELECT run_id, dbt_model_name, failure_stage, error_message, retry_count
FROM `job_control.pipeline_jobs`
WHERE job_type = 'FDP_TRANSFORMATION' AND status = 'FAILED'
ORDER BY failed_at DESC
```

**Trace FDP lineage back to ODP:**
```sql
SELECT fdp.run_id AS fdp_run, fdp.dbt_model_name,
       odp.run_id AS odp_run, odp.entity_type, odp.total_records
FROM `job_control.pipeline_jobs` fdp
CROSS JOIN UNNEST(fdp.parent_run_ids) AS parent_id
JOIN `job_control.pipeline_jobs` odp ON odp.run_id = parent_id
WHERE fdp.job_type = 'FDP_TRANSFORMATION'
  AND fdp.extract_date = '2026-03-16'
```

**Check reconciliation status (after changes):**
```sql
SELECT run_id, entity_type, status, total_records,
       CASE WHEN failure_stage = 'RECONCILIATION' THEN 'MISMATCH' ELSE 'OK' END AS reconciliation
FROM `job_control.pipeline_jobs`
WHERE extract_date = '2026-03-16' AND job_type = 'ODP_INGESTION'
```

---

## Summary of All Implemented Changes

| Area | File/Resource | Change | Fixes Gap |
|------|-------------|--------|-----------|
| **Library** | `job_control/types.py` | Added `JobType` enum, `FDP_DEPENDENCY`/`FDP_STAGING`/`FDP_MODEL`/`FDP_TEST`/`RECONCILIATION` failure stages | G1, G4 |
| **Library** | `job_control/models.py` | Added `job_type`, `retry_count`, `max_retries`, `parent_run_ids`, `dbt_model_name` to `PipelineJob` | G1, G6 |
| **Library** | `job_control/repository.py` | Added `mark_retrying()`, `cleanup_partial_load()`, `get_failed_jobs()`, `get_fdp_job_status()`; updated `create_job` with all new fields | G1, G3, G6 |
| **Library** | `audit/reconciliation.py` | Added `reconcile_fdp_model()` — MAP (1:1 count check) and JOIN (non-empty verification) | G5, G10 |
| **Library** | `data_deletion/recovery.py` | Added `GCSRecoveryManager` — persists checkpoints to GCS as JSON, restores on restart | G7 |
| **Terraform** | `orchestration/main.tf` | Added `job_type`, `retry_count`, `max_retries`, `parent_run_ids`, `dbt_model_name` columns; upgraded dbt IAM to `dataEditor` on `job_control` | G1 |
| **DAG** | `dag_factory.py` ingestion | Rewrote `on_failure_callback` with `mark_failed()` + error details + `ErrorHandler` + `AuditTrail`; added cleanup-before-retry; added `reconcile_odp_load` task; passes `hdr_metadata` from trigger DAG | G3, G4, G5, G8, G9 |
| **DAG** | `dag_factory.py` transformation | Added `create_fdp_job_record` (with parent lineage), `handle_dependency_failure` (no silent skip), `reconcile_fdp_model` task, `on_failure_callback` with stage-specific error details + `ErrorHandler` + `AuditTrail` | G1, G2, G4, G8, G9, G10 |
| **Config** | `system.yaml` | Added `retry_config` (ODP + FDP) and `reconciliation` sections | G3, G5 |
| **dbt** | No model changes needed | dbt `incremental_strategy='merge'` with `unique_key` already provides idempotency | N/A |
