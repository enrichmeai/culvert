# Audit Trail Integration Guide

> **Culvert deployment guide.** The reference deployments live under `deployments/`:
> Java Dataflow pipelines (`original-data-to-bigqueryload-java`,
> `postgres-cdc-streaming-java`, `mainframe-segment-transform-java`,
> `reference-e2e-gcp`), dbt transforms (`bigquery-to-mapped-product`,
> `fdp-to-consumable-product`, `spanner-to-bigquery-load`), and the config-driven
> orchestrator (`data-pipeline-orchestrator`, built on the `data-pipeline-orchestration`
> library — no more `generate_dags.py` codegen). The GCP steps here are Culvert's
> **first-implementation** operations; the deploy→test→validate→publish gate is in
> [`docs/framework-evolution/13-python-parity-release.md`](framework-evolution/13-python-parity-release.md) §2.
> Predecessor `gcp-pipeline-framework` names in older passages are superseded — the
> framework is **Culvert** ([`README.md`](../README.md)). Nothing is on PyPI/Maven Central yet.

## Overview

Every pipeline in this repo writes audit records that connect raw source files
to final outputs. The audit system is provided by the `gcp-pipeline-core`
library (installed from PyPI) and consists of three complementary layers:

| Layer | What it tracks |
|-------|----------------|
| **Job control** (`job_control.pipeline_jobs`) | Run lifecycle: RUNNING → SUCCESS / FAILED |
| **Audit trail** (Pub/Sub → `job_control.audit_trail`) | Processing start/end events with source file reference |
| **Manifest** (GCS JSON file) | Record counts, shard layout, run_id — written by Dataflow |

---

## Library Components (installed from PyPI)

```
pip install gcp-pipeline-core          # audit, job control, error handling
pip install gcp-pipeline-framework     # meta-package: installs all 6 libraries
```

| Class | Module | Purpose |
|-------|--------|---------|
| `AuditTrail` | `gcp_pipeline_core.audit.trail` | Publish start/end audit events |
| `AuditPublisher` | `gcp_pipeline_core.audit.publisher` | Send events to Pub/Sub topic |
| `JobControlRepository` | `gcp_pipeline_core.job_control` | CRUD on `pipeline_jobs` table |
| `PipelineJob` | `gcp_pipeline_core.job_control` | Job record dataclass |
| `ErrorHandler` | `gcp_pipeline_core.error_handling.handler` | Classify and log exceptions |
| `MetricsCollector` | `gcp_pipeline_core.monitoring.metrics` | Increment pipeline counters |

---

## Audit Columns on Every BigQuery Record

Every record loaded through the pipeline carries these lineage columns:

| Column | Type | Set by | Description |
|--------|------|--------|-------------|
| `_run_id` | STRING | Ingestion (Dataflow) | Unique pipeline execution ID |
| `_source_file` | STRING | Ingestion (Dataflow) | Original GCS file name |
| `_extract_date` | DATE | HDR record / options | Extract date (partition key) |
| `_processed_at` | TIMESTAMP | Ingestion (Dataflow) | When loaded to ODP |
| `_transformed_at` | TIMESTAMP | dbt (FDP/CDP layer) | When transformed |
| `_cdp_transformed_at` | TIMESTAMP | dbt (CDP layer only) | When CDP model ran |

---

## Segment Transform Audit Flow

The `mainframe-segment-transform` pipeline propagates a single `run_id`
through every audit layer so any mainframe file can be traced back to its
source data.

```
Cloud Scheduler (3rd of month)
        │
        ▼
Cloud Build (cloudbuild-monthly.yaml)
  │  BUILD_ID becomes part of run_id
  │
  ├─ Step 1: FDP readiness check
  ├─ Step 2: dbt CDP refresh  ──────────────────────────────┐
  ├─ Step 3: dbt tests                                       │ writes cdp_generic.customer_risk_profile
  └─ Step 4: Dataflow launch ─────────────────────────────┐ │ with _cdp_transformed_at = now()
                                                           │ │
runner.py (Dataflow worker)                                │ │
  │                                                        │ │
  ├─ resolve run_id  ◄──────────── --run_id parameter ─────┘ │
  │   format: "seg-monthly-{YYYYMM}-{build_id[:8]}"          │
  │                                                          │
  ├─ job_control.pipeline_jobs                               │
  │   INSERT: run_id, status=RUNNING, entity_type=customer   │
  │           source_files=["project:cdp_generic.customer_risk_profile"]
  │                                                          │
  ├─ BigQuery read ◄──────── cdp_generic.customer_risk_profile (partitioned)
  │                                                          │
  ├─ FormatFixedWidthDoFn  (200-char records)               │
  │                                                          │
  ├─ GCS segment files                                       │
  │   gs://{bucket}/segments/{period}/{run_id}/customer/     │
  │       CUST-00000-of-00001.dat                            │
  │                                                          │
  ├─ GCS manifest  (run_id embedded)                         │
  │   gs://{bucket}/segments/{period}/{run_id}/customer/CUST.manifest
  │                                                          │
  ├─ job_control.pipeline_jobs                               │
  │   UPDATE: status=SUCCESS                                 │
  │                                                          │
  └─ Pub/Sub → job_control.audit_trail                       │
      record_processing_start(source_file=source_ref)        │
      record_processing_end(success=True)                    │
```

### Manifest JSON (written to GCS by Dataflow)

The manifest ties the output files back to the run. Mainframe operations teams
use this for record count verification before loading.

```json
{
  "segment":              "customer",
  "period":               "202603",
  "run_id":               "seg-monthly-202603-a1b2c3d4",
  "extract_date":         "20260331",
  "total_records":        48321,
  "record_length":        200,
  "num_shards":           1,
  "max_records_per_shard": 1000000,
  "file_pattern":         "CUST-*-of-*.dat"
}
```

### Job Control Table (BigQuery)

```sql
SELECT
  run_id,
  status,
  entity_type,
  extract_date,
  source_files,
  started_at,
  completed_at
FROM job_control.pipeline_jobs
WHERE entity_type = 'customer'
ORDER BY started_at DESC
LIMIT 10;
```

---

## Lineage Queries

### 1. Check the status of a monthly segment run

```sql
SELECT
  run_id,
  status,
  extract_date,
  started_at,
  completed_at,
  TIMESTAMP_DIFF(completed_at, started_at, MINUTE) AS duration_minutes
FROM `{project}.job_control.pipeline_jobs`
WHERE entity_type = 'customer'
  AND extract_date = '2026-03-31'
ORDER BY started_at DESC;
```

### 2. Trace a mainframe file back to its CDP source record

Given a `run_id` from the manifest (or from a support ticket), find the
CDP snapshot that was the source:

```sql
-- Step 1: what CDP records were in scope for this run?
SELECT
  customer_id,
  customer_status,
  risk_score,
  current_balance,
  _extract_date,
  _cdp_transformed_at,
  _run_id          AS ingestion_run_id   -- traces back to original CSV load
FROM `{project}.cdp_generic.customer_risk_profile`
WHERE _extract_date = '2026-03-31';
```

### 3. Full lineage: mainframe file → CDP → FDP → ODP → source file

```sql
-- Follow one customer_id through all four layers
WITH cdp AS (
  SELECT
    customer_id,
    _extract_date,
    _cdp_transformed_at,
    _run_id AS cdp_run_id
  FROM `{project}.cdp_generic.customer_risk_profile`
  WHERE customer_id = 'CUST001'
    AND _extract_date = '2026-03-31'
),
fdp AS (
  SELECT
    customer_id,
    _extract_date,
    _transformed_at AS fdp_transformed_at,
    _run_id         AS fdp_run_id
  FROM `{project}.fdp_generic.event_transaction_excess`
  WHERE customer_id = 'CUST001'
    AND _extract_date = '2026-03-31'
),
odp AS (
  SELECT
    customer_id,
    _extract_date,
    _processed_at,
    _source_file,
    _run_id AS odp_run_id
  FROM `{project}.odp_generic.customers`
  WHERE customer_id = 'CUST001'
    AND _extract_date = '2026-03-31'
)
SELECT
  odp._source_file                        AS source_csv,
  odp._processed_at                       AS loaded_to_odp,
  fdp.fdp_transformed_at                  AS transformed_to_fdp,
  cdp._cdp_transformed_at                 AS snapshot_in_cdp,
  'seg-monthly-202603-*'                  AS segment_run_pattern,
  'gs://{bucket}/segments/202603/{run_id}/customer/CUST.manifest' AS manifest
FROM cdp
JOIN fdp USING (customer_id, _extract_date)
JOIN odp USING (customer_id, _extract_date);
```

### 4. Reconcile mainframe record count against CDP source

```sql
-- Compare manifest total_records against what was in CDP for that period
-- Run this after the Dataflow job completes to confirm no records were dropped
SELECT
  j.run_id,
  j.extract_date,
  j.status                                      AS job_status,
  cdp.cdp_count                                 AS cdp_source_count,
  -- total_records comes from the manifest JSON — paste it here
  48321                                         AS manifest_total_records,
  cdp.cdp_count - 48321                         AS discrepancy
FROM `{project}.job_control.pipeline_jobs` j
CROSS JOIN (
  SELECT COUNT(*) AS cdp_count
  FROM `{project}.cdp_generic.customer_risk_profile`
  WHERE customer_status IN ('ACTIVE', 'DORMANT')
    AND _extract_date = '2026-03-31'
) cdp
WHERE j.run_id = 'seg-monthly-202603-a1b2c3d4';
```

---

## Ingestion Pipeline Audit (original-data-to-bigqueryload)

```python
from gcp_pipeline_core.audit import AuditTrail
from gcp_pipeline_core.audit.publisher import AuditPublisher

audit_publisher = AuditPublisher(
    project_id=gcp_project,
    topic_name='generic-pipeline-events',
)
audit = AuditTrail(
    run_id=run_id,
    pipeline_name='mainframe-segment-transform',
    entity_type='customer',
    publisher=audit_publisher,
)

audit.record_processing_start(source_file='project:cdp_generic.customer_risk_profile')
# ... pipeline runs ...
audit.record_processing_end(success=True)
```

The events land in `job_control.audit_trail` via the Pub/Sub subscription
`generic-pipeline-events-sub`. Infrastructure for the topic and subscription
is provisioned by Terraform (`infrastructure/terraform/systems/generic/main.tf`).

---

## References

- [E2E Functional Flow](./E2E_FUNCTIONAL_FLOW.md)
- [Data Quality Guide](./DATA_QUALITY_GUIDE.md)
- [Deployment Operations Guide](./DEPLOYMENT_OPERATIONS_GUIDE.md)
- [runner.py](../deployments/mainframe-segment-transform/src/segment_transform/pipeline/runner.py) — where run_id, job_control, and audit_trail are wired together
- [segment_pipeline.py](../deployments/mainframe-segment-transform/src/segment_transform/pipeline/segment_pipeline.py) — where run_id is embedded in manifest and GCS paths
